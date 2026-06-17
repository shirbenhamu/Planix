# src/MVP/views/input_view.py

import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Dict
from src.MVP.views.ui_utils import format_text
from src.MVP.views.components.date_edit_modal import show_date_edit_popup
from src.MVP.views.components.load_choice_modal import show_load_choice_popup
from src.MVP.views.components.robot_mascot import RobotMascot
from src.MVP.views.components.constraints_modal import (
    show_constraints_popup, default_constraints_data, normalize_constraints_data
)

from src.MVP.views import theme
from src.MVP.views.components.ui_components import (
    create_card, create_icon_button, create_primary_action_button, 
    create_secondary_button, add_card_hover, Tooltip, ICON_UPLOAD, ICON_TRASH, ICON_SETTINGS
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
        self._detail_labels = [] 
        
        self.f_mega = ctk.CTkFont(family=theme.FONT_FAMILY, size=32, weight="bold")
        self.f_title = ctk.CTkFont(family=theme.FONT_FAMILY, size=24, weight="bold")
        self.f_header = ctk.CTkFont(family=theme.FONT_FAMILY, size=20, weight="bold")
        self.f_sub = ctk.CTkFont(family=theme.FONT_FAMILY, size=16, weight="bold")
        self.f_reg = ctk.CTkFont(family=theme.FONT_FAMILY, size=14)
        self.f_small = ctk.CTkFont(family=theme.FONT_FAMILY, size=12)

        self.on_program_selected: Callable[[str], None] = None
        self.on_program_details: Callable[[str], None] = None
        self.on_load_courses: Callable[[str], bool] = None
        self.on_load_dates: Callable[[str], bool] = None
        self.on_clear_courses: Callable[[], None] = None
        self.on_run_clicked: Callable[[], None] = None
        self.on_range_update_clicked: Callable[[list], None] = None
        self.on_save_constraints: Callable[[dict], None] = None
        self.get_exam_periods_callback: Callable[[], list] = None
        
        self.checkboxes = []
        self._program_ids = []
        self.load_mode_var = ctk.StringVar(value="append")
        self._constraints_state = default_constraints_data()
        self._constraints_save_enabled = True
        
        self.has_courses = False
        self.has_dates = False
        
        self._setup_ui()
        self.update_language(self.current_lang)

    def _setup_ui(self):
        self.toolbar_frame = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self.toolbar_frame.pack(fill="x", pady=(theme.SPACING_SMALL, 0), padx=theme.SPACING_SMALL)
        
        self.hamburger_btn = ctk.CTkLabel(self.toolbar_frame, text="☰", font=("Arial", 22), cursor="hand2", text_color=theme.TEXT_MAIN)
        self.hamburger_btn.pack(side="left", padx=(theme.SPACING_SMALL, theme.SPACING_REGULAR))

        self.btn_constraints = ctk.CTkButton(
            self.toolbar_frame,
            text=f"{ICON_SETTINGS} {format_text('constraints_button', self.current_lang)}",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold"),
            fg_color=theme.TRANSPARENT,
            border_width=2,
            border_color=theme.BORDER_ACTIVE,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_ACCENT,
            height=36,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._open_constraints_modal,
        )
        self.btn_constraints.pack(side="right", padx=(theme.SPACING_SMALL, theme.SPACING_REGULAR))
        self.tip_constraints = Tooltip(self.btn_constraints, format_text("constraints_tooltip", self.current_lang))

        self.main_split = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self.main_split.pack(fill="both", expand=True, padx=theme.SPACING_LARGE, pady=theme.SPACING_REGULAR)
        self.main_split.grid_columnconfigure(0, weight=6) 
        self.main_split.grid_columnconfigure(1, weight=4) 
        self.main_split.grid_rowconfigure(0, weight=1)
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
        self.files_row.grid_columnconfigure(1, weight=0)
        self.files_row.grid_columnconfigure(2, weight=1)
        
        self.courses_cell = ctk.CTkFrame(self.files_row, fg_color=theme.TRANSPARENT)
        self.lbl_courses = ctk.CTkLabel(self.courses_cell, text="", font=self.f_title, text_color=theme.TEXT_MAIN)
        self.lbl_courses.pack(pady=(0, theme.SPACING_SMALL))
        
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
        self.mascot = RobotMascot(self.files_row, reserve_bubble=True)
        self.mascot.grid(row=0, column=1, padx=8)
        self.dates_cell.grid(row=0, column=2, sticky="nsew")

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
        periods_data = self.get_exam_periods_callback() if callable(self.get_exam_periods_callback) else []
        
        def on_save(date_pairs):
            if self.on_range_update_clicked:
                self.on_range_update_clicked(date_pairs)
        
        show_date_edit_popup(
            parent=self, 
            current_lang=self.current_lang, 
            exam_periods_data=periods_data or [],
            on_save_callback=on_save
        )

    def _open_constraints_modal(self):
        show_constraints_popup(
            parent=self,
            current_lang=self.current_lang,
            constraints_data=self._constraints_state,
            on_save_callback=self._handle_constraints_save,
            on_close_callback=self._persist_constraints_state,
            save_enabled=self._constraints_save_enabled,
        )

    def _handle_constraints_save(self, constraints_data: dict):
        self._persist_constraints_state(constraints_data)
        if self.on_save_constraints:
            self.on_save_constraints(self.get_constraints_data())
        self.mascot.show_speech(format_text("constraints_saved", self.current_lang), duration=2500)

    def _persist_constraints_state(self, constraints_data: dict):
        self._constraints_state = normalize_constraints_data(constraints_data)

    def get_constraints_data(self) -> dict:
        return dict(self._constraints_state)

    def set_constraints_data(self, constraints_data: dict) -> None:
        self._constraints_state = normalize_constraints_data(constraints_data)

    def set_save_button_state(self, enabled: bool) -> None:
        self._constraints_save_enabled = bool(enabled)

    def enable_save_constraints(self) -> None:
        self.set_save_button_state(True)

    def disable_save_constraints(self) -> None:
        self.set_save_button_state(False)

    def show_warning_dialog(self, message: str):
        self.mascot.show_speech(format_text("max_programs_err", self.current_lang), duration=3500)

    def _handle_load_courses(self):
        file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")])
        if file_path and self.on_load_courses: 
            success = self.on_load_courses(file_path)
            if success:
                self.has_courses = True
                self.mascot.show_speech(format_text("toast_courses_loaded", self.current_lang))
            else:
                self.mascot.show_speech(format_text("err_courses_format", self.current_lang), duration=3500)

    def _open_dates_load_chooser(self):
        show_load_choice_popup(self, self.current_lang, on_choice_callback=self._perform_dates_load)

    def _perform_dates_load(self, mode: str):
        self.load_mode_var.set(mode)
        file_path = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")]
        )
        if file_path and self.on_load_dates:
            success = self.on_load_dates(file_path)
            if success:
                self.has_dates = True
                self.mascot.show_speech(format_text("toast_dates_loaded", self.current_lang))
            else:
                self.mascot.show_speech(format_text("err_dates_format", self.current_lang), duration=3500)
        
    def _handle_clear_courses(self):
        if self.on_clear_courses:
            self.on_clear_courses()
            # The trash button clears only the courses file — the dates state is preserved (has_dates unchanged)
            self.has_courses = False
            self.mascot.show_speech(format_text("toast_courses_cleared", self.current_lang))

    def _handle_run_click(self):
        # Pre-run checks to prevent switching screens when data is missing
        if not self.has_courses and not self.has_dates:
            self.mascot.show_speech(format_text("err_both_missing", self.current_lang), duration=3500)
            return
        if not self.has_courses:
            self.mascot.show_speech(format_text("err_courses_missing", self.current_lang), duration=3500)
            return
        if not self.has_dates:
            self.mascot.show_speech(format_text("err_dates_missing", self.current_lang), duration=3500)
            return
            
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
        w = self.main_split.winfo_width()
        if w <= 1:
            w = 1000
        return int(w * 0.6)

    def _resize_columns(self, event=None):
        w = self.main_split.winfo_width()
        if w <= 1:
            return
        col0 = int(w * 0.6)
        col1 = w - col0
        self.main_split.grid_columnconfigure(0, weight=0, minsize=col0)
        self.main_split.grid_columnconfigure(1, weight=0, minsize=col1)
        self.details_title.configure(wraplength=max(120, col0 - 60))
        card_wrap = max(120, col0 - 90)
        for lbl in self._detail_labels:
            try:
                lbl.configure(wraplength=card_wrap)
            except Exception:
                pass

    def display_program_courses(self, hierarchy: Dict):
        self._last_hierarchy = hierarchy
        self._detail_labels = [] 
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
        self.btn_constraints.configure(text=f"{ICON_SETTINGS} {format_text('constraints_button', lang)}")
        self.tip_constraints.text = format_text("constraints_tooltip", lang)
        
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