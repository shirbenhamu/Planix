# src/MVP/views/input_view.py

import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Dict
from src.MVP.views.ui_utils import format_text
from src.MVP.views.components.date_edit_modal import show_date_edit_popup
from src.MVP.views.components.load_choice_modal import show_load_choice_popup

from src.MVP.views import theme
from src.MVP.views.components.ui_components import (
    create_card, create_icon_button, create_primary_action_button, 
    create_secondary_button, add_card_hover, Tooltip, ICON_UPLOAD, ICON_TRASH
)

class _ProgramRow(ctk.CTkFrame):
    def __init__(self, master, prog_id, display_text, lang, on_box_click, on_name_click, font, **kwargs):
        super().__init__(master, fg_color=theme.TRANSPARENT, **kwargs)
        self._prog_id = prog_id
        self._text = display_text
        self._on_box_click = on_box_click
        self._on_name_click = on_name_click

        self.box = ctk.CTkCheckBox(
            self, text="", width=24,
            fg_color=theme.TEXT_ACCENT, hover_color=theme.TEXT_ACCENT,
            command=self._box_clicked,
        )
        self.name_lbl = ctk.CTkLabel(
            self, text=display_text, font=font,
            text_color=theme.TEXT_MAIN, cursor="hand2",
        )
        self.name_lbl.bind("<Button-1>", self._name_clicked)

        self.set_lang(lang)

    def set_lang(self, lang):
        self.box.pack_forget()
        self.name_lbl.pack_forget()
        if lang == "he":
            self.name_lbl.pack(side="right", padx=(0, 8))
            self.box.pack(side="right")
        else:
            self.box.pack(side="left")
            self.name_lbl.pack(side="left", padx=(8, 0))

    def _box_clicked(self):
        if self._on_box_click:
            self._on_box_click(self._prog_id)

    def _name_clicked(self, _event=None):
        if self._on_name_click:
            self._on_name_click(self._prog_id)

    def cget(self, key):
        if key == "text":
            return self._text
        return super().cget(key)

    def select(self):
        self.box.select()

    def deselect(self):
        self.box.deselect()

    def get(self):
        return self.box.get()


class InputConfigurationView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BG_MAIN, **kwargs)
        self.current_lang = "he"
        self._last_hierarchy = {}
        self._detail_labels = []  # תוויות הכרטיסים בפאנל הפרטים, לעדכון גלישה לפי רוחב העמודה
        
        self.f_mega = ctk.CTkFont(family=theme.FONT_FAMILY, size=32, weight="bold")
        self.f_title = ctk.CTkFont(family=theme.FONT_FAMILY, size=24, weight="bold")
        self.f_header = ctk.CTkFont(family=theme.FONT_FAMILY, size=20, weight="bold")
        self.f_sub = ctk.CTkFont(family=theme.FONT_FAMILY, size=16, weight="bold")
        self.f_reg = ctk.CTkFont(family=theme.FONT_FAMILY, size=14)
        self.f_small = ctk.CTkFont(family=theme.FONT_FAMILY, size=12)

        self.on_program_selected: Callable[[str], None] = None
        self.on_program_details: Callable[[str], None] = None
        self.on_load_courses: Callable[[str], None] = None
        self.on_load_dates: Callable[[str], None] = None
        self.on_clear_courses: Callable[[], None] = None
        self.on_run_clicked: Callable[[], None] = None
        self.get_exam_periods_callback: Callable[[], list] = None
        
        self.checkboxes = []
        self._program_ids = []
        self.load_mode_var = ctk.StringVar(value="append")
        
        self._setup_ui()
        self.update_language(self.current_lang)

    def _setup_ui(self):
        self.toolbar_frame = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self.toolbar_frame.pack(fill="x", pady=(theme.SPACING_SMALL, 0), padx=theme.SPACING_SMALL)
        
        self.hamburger_btn = ctk.CTkLabel(self.toolbar_frame, text="☰", font=("Arial", 22), cursor="hand2", text_color=theme.TEXT_MAIN)
        self.hamburger_btn.pack(side="left", padx=(theme.SPACING_SMALL, theme.SPACING_REGULAR))

        self.main_split = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self.main_split.pack(fill="both", expand=True, padx=theme.SPACING_LARGE, pady=theme.SPACING_REGULAR)
        self.main_split.grid_columnconfigure(0, weight=6) 
        self.main_split.grid_columnconfigure(1, weight=4) 
        self.main_split.grid_rowconfigure(0, weight=1)
        # מקבעים את רוחב העמודות כשבר קבוע מרוחב המסך (60%/40%), ללא תלות בתוכן,
        # כדי שהחלפת תוכנית לא תזיז את חלוקת העמודות (מקור הקפיצות).
        self.main_split.bind("<Configure>", self._resize_columns)

        # ---------------- LEFT PANEL (Details) ----------------
        self.details_panel = ctk.CTkFrame(self.main_split, fg_color=theme.TRANSPARENT)
        self.details_panel.grid(row=0, column=0, sticky="nsew", padx=(0, theme.SPACING_LARGE))
        
        self.details_title = ctk.CTkLabel(self.details_panel, text="", font=self.f_title, text_color=theme.TEXT_MAIN)
        self.details_title.pack(anchor="center", pady=(0, theme.SPACING_REGULAR))
        
        self.details_scroll = ctk.CTkScrollableFrame(
            self.details_panel, 
            fg_color=theme.BG_CARD, 
            corner_radius=theme.RADIUS_CARD, 
            border_width=1, 
            border_color=theme.BORDER_DEFAULT
        )
        self.details_scroll.pack(fill="both", expand=True)
        
        self.empty_details_lbl = ctk.CTkLabel(self.details_scroll, text="", font=self.f_reg, text_color=theme.TEXT_MUTED)
        self.empty_details_lbl.pack(pady=40)

        # ---------------- RIGHT PANEL (Controls) ----------------
        self.controls_panel = ctk.CTkFrame(self.main_split, fg_color=theme.TRANSPARENT)
        self.controls_panel.grid(row=0, column=1, sticky="nsew")
        
        self.files_row = ctk.CTkFrame(self.controls_panel, fg_color=theme.TRANSPARENT)
        self.files_row.pack(fill="x", pady=(0, theme.SPACING_REGULAR))
        self.files_row.grid_columnconfigure(0, weight=1)
        self.files_row.grid_columnconfigure(1, weight=1)
        
        self.courses_cell = ctk.CTkFrame(self.files_row, fg_color=theme.TRANSPARENT)
        self.lbl_courses = ctk.CTkLabel(self.courses_cell, text="", font=self.f_title, text_color=theme.TEXT_MAIN)
        self.lbl_courses.pack(pady=(0, theme.SPACING_SMALL))
        
        # הטמעת אייקון וקטורי ו-Tooltip
        self.btn_courses = create_icon_button(self.courses_cell, text=ICON_UPLOAD, command=self._handle_load_courses)
        self.btn_courses.pack()
        self.tip_courses = Tooltip(self.btn_courses, "העלאת קובץ קורסים")

        self.dates_cell = ctk.CTkFrame(self.files_row, fg_color=theme.TRANSPARENT)
        self.lbl_dates = ctk.CTkLabel(self.dates_cell, text="", font=self.f_title, text_color=theme.TEXT_MAIN)
        self.lbl_dates.pack(pady=(0, theme.SPACING_SMALL))
        
        self.btn_dates = create_icon_button(self.dates_cell, text=ICON_UPLOAD, command=self._open_dates_load_chooser)
        self.btn_dates.pack()
        self.tip_dates = Tooltip(self.btn_dates, "העלאת קובץ תאריכים")

        self.courses_cell.grid(row=0, column=0, sticky="nsew")
        self.dates_cell.grid(row=0, column=1, sticky="nsew")

        self.programs_frame = create_card(self.controls_panel)
        self.programs_frame.pack(fill="both", expand=True, pady=theme.SPACING_SMALL)
        
        self.prog_header = ctk.CTkFrame(self.programs_frame, fg_color=theme.TRANSPARENT)
        self.prog_header.pack(fill="x", padx=theme.SPACING_REGULAR, pady=theme.SPACING_REGULAR)
        
        self.programs_title = ctk.CTkLabel(self.prog_header, text="", font=self.f_sub, text_color=theme.TEXT_MAIN)

        self.btn_clear_courses = create_icon_button(self.prog_header, text=ICON_TRASH, command=self._handle_clear_courses)
        self.btn_clear_courses.configure(text_color=theme.DANGER, width=45, height=45, font=ctk.CTkFont(family="bootstrap-icons", size=18))
        self.btn_clear_courses.pack()
        self.tip_clear = Tooltip(self.btn_clear_courses, "נקה נתונים")
        
        self.programs_list_frame = ctk.CTkScrollableFrame(self.programs_frame, fg_color=theme.TRANSPARENT)
        self.programs_list_frame.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        self.error_label = ctk.CTkLabel(self.programs_frame, text="", font=self.f_small, text_color=theme.DANGER)
        self.error_label.pack(pady=(0, 5))

        self.btn_edit_dates = create_secondary_button(
            self.programs_frame, 
            text="", 
            command=self._open_dates_modal
        )
        self.btn_edit_dates.pack(pady=(0, theme.SPACING_REGULAR))

        self.btn_run = create_primary_action_button(
            self.controls_panel, 
            text="", 
            command=self._handle_run_click
        )
        self.btn_run.pack(fill="x", pady=(theme.SPACING_REGULAR, 0))

    def _open_dates_modal(self):
        periods_data = self.get_exam_periods_callback() if self.get_exam_periods_callback else None
        show_date_edit_popup(self, self.current_lang, exam_periods_data=periods_data)

    def show_warning_dialog(self, message: str):
        err_text = format_text("max_programs_err", self.current_lang)
        self.error_label.configure(text=err_text)
        if hasattr(self, "_warning_timer") and self._warning_timer:
            self.after_cancel(self._warning_timer)
        self._warning_timer = self.after(3500, lambda: self.error_label.configure(text=""))

    def _handle_load_courses(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")])
        if file_path and self.on_load_courses: 
            self.on_load_courses(file_path)
            self.winfo_toplevel().show_toast("קובץ קורסים נטען בהצלחה" if self.current_lang == "he" else "Courses file loaded successfully")

    def _open_dates_load_chooser(self):
        show_load_choice_popup(self, self.current_lang, on_choice_callback=self._perform_dates_load)

    def _perform_dates_load(self, mode: str):
        self.load_mode_var.set(mode)
        file_path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")]
        )
        if file_path and self.on_load_dates:
            self.on_load_dates(file_path)
            self.winfo_toplevel().show_toast("קובץ תאריכים עודכן בהצלחה" if self.current_lang == "he" else "Dates file updated successfully")
        
    def _handle_clear_courses(self):
        if self.on_clear_courses: 
            self.on_clear_courses()
            self.winfo_toplevel().show_toast("הנתונים נמחקו" if self.current_lang == "he" else "Data cleared")

    def _handle_run_click(self):
        if self.on_run_clicked: self.on_run_clicked()

    def display_programs_list(self, programs: Dict[str, str]):
        for cb in self.checkboxes: cb.destroy()
        self.checkboxes.clear()
        self._program_ids = list(programs.keys())

        anchor = "e" if self.current_lang == "he" else "w"
        for prog_id, prog_name in programs.items():
            display_text = f"\u200F{prog_name} ({prog_id})\u200F" if self.current_lang == "he" else f"{prog_name} ({prog_id})"

            row = _ProgramRow(
                self.programs_list_frame,
                prog_id=prog_id,
                display_text=display_text,
                lang=self.current_lang,
                on_box_click=self._handle_box_click,
                on_name_click=self._handle_name_click,
                font=self.f_reg,
            )
            row.pack(fill="x", anchor=anchor, pady=6, padx=10)
            self.checkboxes.append(row)

    def _handle_box_click(self, prog_id):
        if self.on_program_selected:
            self.on_program_selected(prog_id)

    def _handle_name_click(self, prog_id):
        if self.on_program_details:
            self.on_program_details(prog_id)

    def _current_col0(self) -> int:
        # רוחב עמודת הפרטים (השמאלית) = 60% מרוחב האזור; fallback לפני שהחלון נפרס
        w = self.main_split.winfo_width()
        if w <= 1:
            w = 1000
        return int(w * 0.6)

    def _resize_columns(self, event=None):
        # קובע את שתי העמודות לרוחב פיקסלים קבוע (יחסי למסך), בלי weight, כך שתוכן
        # לא יכול להזיז את החלוקה. עודף תוכן נגלל בתוך ה-ScrollableFrame ולא דוחף.
        w = self.main_split.winfo_width()
        if w <= 1:
            return
        col0 = int(w * 0.6)
        col1 = w - col0
        self.main_split.grid_columnconfigure(0, weight=0, minsize=col0)
        self.main_split.grid_columnconfigure(1, weight=0, minsize=col1)
        # הכותרת והכרטיסים גולשים לפי רוחב העמודה, כך שלא "ידחפו" אותה להתרחב
        self.details_title.configure(wraplength=max(120, col0 - 60))
        card_wrap = max(120, col0 - 90)
        for lbl in self._detail_labels:
            try:
                lbl.configure(wraplength=card_wrap)
            except Exception:
                pass

    def display_program_courses(self, hierarchy: Dict):
        self._last_hierarchy = hierarchy
        self._detail_labels = []  # נבנה מחדש בכל הצגה
        col0 = self._current_col0()
        card_wrap = max(120, col0 - 90)
        self.details_title.configure(wraplength=max(120, col0 - 60))
        for widget in self.details_scroll.winfo_children(): widget.destroy()

        program_name = hierarchy.get("program_name") if isinstance(hierarchy, dict) else None
        program_id = hierarchy.get("program_id") if isinstance(hierarchy, dict) else None
        if program_name:
            if self.current_lang == "he":
                self.details_title.configure(text=f"\u200F{program_name} ({program_id})\u200F")
            else:
                self.details_title.configure(text=f"{program_name} ({program_id})")
        else:
            self.details_title.configure(text=format_text("details_title", self.current_lang))

        courses_by_year_and_semester = hierarchy.get("courses_by_year_and_semester", {}) if hierarchy else {}
        if not courses_by_year_and_semester:
            self.empty_details_lbl = ctk.CTkLabel(
                self.details_scroll,
                text=format_text("no_selection", self.current_lang),
                font=self.f_reg,
                text_color=theme.TEXT_MUTED,
            )
            self.empty_details_lbl.pack(pady=40)
            return

        anchor = "e" if self.current_lang == "he" else "w"
        year_str = format_text("year", self.current_lang)
        total_groups = sum(len(sems) for sems in courses_by_year_and_semester.values())
        current_group_idx = 0

        for year in sorted(courses_by_year_and_semester.keys()):
            semesters = courses_by_year_and_semester.get(year, {})
            for semester_raw in sorted(semesters.keys()):
                current_group_idx += 1
                sem_key = f"semester_{semester_raw.strip().upper()}"
                semester_display = format_text(sem_key, self.current_lang)
                if semester_display == f"\u200F{sem_key}\u200F" or semester_display == sem_key:
                    semester_display = semester_raw

                if self.current_lang == "he":
                    header_text = f"📌 {year} {year_str} | {semester_display} סמסטר"
                else:
                    header_text = f"📌 Year {year} | Semester {semester_display}"

                group_header = ctk.CTkLabel(
                    self.details_scroll, text=header_text, font=self.f_header, text_color=theme.TEXT_ACCENT, 
                )
                group_header.pack(anchor="center", padx=10, pady=(20, 10))

                for course in semesters.get(semester_raw, []):
                    card = create_card(self.details_scroll)
                    card.pack(fill="x", pady=6, padx=15)
                    add_card_hover(card)
                    
                    c_name = course.get('course_name', '')
                    c_id = course.get('course_id', '')
                    c_type = format_text("type_hova" if course.get('requirement') == 'Obligatory' else "type_bhira", self.current_lang)
                    
                    eval_raw = course.get("evaluation_method", "EXAM").strip().upper()
                    eval_key = f"eval_{eval_raw}"
                    eval_display = format_text(eval_key, self.current_lang)
                    if eval_display == f"\u200F{eval_key}\u200F" or eval_display == eval_key:
                         eval_display = eval_raw

                    title = f"\u200F{c_name} ({c_id})\u200F" if self.current_lang == "he" else f"{c_name} ({c_id})"
                    info = f"\u200F{c_type}  •  {eval_display}\u200F" if self.current_lang == "he" else f"{c_type}  •  {eval_display}"
                    
                    title_lbl = ctk.CTkLabel(card, text=title, font=self.f_sub, text_color=theme.TEXT_MAIN, wraplength=card_wrap, justify=("right" if self.current_lang == "he" else "left"))
                    title_lbl.pack(anchor=anchor, padx=12, pady=(8, 0))
                    info_lbl = ctk.CTkLabel(card, text=info, font=self.f_small, text_color=theme.TEXT_MUTED, wraplength=card_wrap, justify=("right" if self.current_lang == "he" else "left"))
                    info_lbl.pack(anchor=anchor, padx=12, pady=(2, 8))
                    self._detail_labels.extend([title_lbl, info_lbl])

                if current_group_idx < total_groups:
                    separator = ctk.CTkFrame(self.details_scroll, height=2, fg_color=theme.BORDER_DEFAULT)
                    separator.pack(fill="x", padx=40, pady=(15, 0))

    def update_language(self, lang: str):
        self.current_lang = lang
        self.lbl_courses.configure(text=format_text("courses", lang))
        self.lbl_dates.configure(text=format_text("dates", lang))
        self.programs_title.configure(text=format_text("programs_title", lang))
        self.details_title.configure(text=format_text("details_title", lang))
        self.btn_run.configure(text=format_text("btn_run", lang))
        
        # עדכון בועות המידע בהתאם לשפה החדשה
        if lang == "he":
            self.tip_courses.text = "העלאת קובץ קורסים"
            self.tip_dates.text = "העלאת קובץ תאריכים"
            self.tip_clear.text = "נקה נתונים"
        else:
            self.tip_courses.text = "Upload Courses File"
            self.tip_dates.text = "Upload Dates File"
            self.tip_clear.text = "Clear Data"

        self.btn_courses.configure(text=ICON_UPLOAD)
        self.btn_dates.configure(text=ICON_UPLOAD)
        self.btn_clear_courses.configure(text=ICON_TRASH)
        self.btn_edit_dates.configure(text=format_text('edit_dates', lang))
        
        anchor = "e" if lang == "he" else "w"
        for row in self.checkboxes:
            row.pack_configure(anchor=anchor)
            if hasattr(row, "set_lang"):
                row.set_lang(lang)
            
        if lang == "he":
            self.programs_title.pack_configure(side="right")
            self.btn_clear_courses.pack_configure(side="left")
        else:
            self.programs_title.pack_configure(side="left")
            self.btn_clear_courses.pack_configure(side="right")

        self.display_program_courses(self._last_hierarchy)

        root = self.winfo_toplevel()
        if hasattr(root, "load_choice_box") and root.load_choice_box.winfo_exists():
            show_load_choice_popup(self, lang, on_choice_callback=self._perform_dates_load)