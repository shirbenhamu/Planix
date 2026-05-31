import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Dict, List

TRANSLATIONS = {
    "title": {"he": "העלאת נתונים", "en": "Data Upload"},
    "load_mode": {"he": "מצב טעינה", "en": "Load Mode"},
    "mode_replace": {"he": "החלפה", "en": "Replace"},
    "mode_append": {"he": "הוספה", "en": "Append"},
    "mode_update": {"he": "עדכון", "en": "Update"},
    "files_title": {"he": "קבצי נתונים", "en": "Data Files"},
    "btn_load_courses": {"he": "טען קובץ קורסים", "en": "Load Courses"},
    "btn_load_dates": {"he": "טען קובץ תאריכים", "en": "Load Dates"},
    "btn_load_programs": {"he": "טען קובץ תוכניות", "en": "Load Programs"},
    "programs_title": {"he": "בחירת תוכניות לימוד (עד 5)", "en": "Select Study Programs (Max 5)"},
    "details_title": {"he": "פרטי תוכנית", "en": "Program Details"},
    "no_selection": {"he": "בחר תוכנית מהרשימה כדי לראות את הקורסים שלה כאן.", "en": "Select a program from the list to view its courses here."},
    "type_hova": {"he": "חובה", "en": "Mandatory"},
    "type_bhira": {"he": "בחירה", "en": "Elective"}
}

def format_text(key: str, lang: str) -> str:
    text = TRANSLATIONS[key][lang]
    return f"\u200F{text}\u200F" if lang == "he" else text

class InputConfigurationView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_lang = "he"
        
        base_family = "Rubik"
        self.f_title = ctk.CTkFont(family=base_family, size=20, weight="bold")
        self.f_header = ctk.CTkFont(family=base_family, size=16, weight="bold")
        self.f_sub = ctk.CTkFont(family=base_family, size=14, weight="bold")
        self.f_reg = ctk.CTkFont(family=base_family, size=14)
        self.f_small = ctk.CTkFont(family=base_family, size=12)

        self.on_program_selected: Callable[[str], None] = None
        self.on_load_courses: Callable[[str], None] = None
        self.on_load_dates: Callable[[str], None] = None
        self.on_load_programs: Callable[[str], None] = None 
        
        self.checkboxes = []
        self._setup_ui()
        self.update_language(self.current_lang)

    def _setup_ui(self):
        self.toolbar_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar_frame.pack(fill="x", pady=(5, 0), padx=5)
        self.hamburger_btn = ctk.CTkLabel(self.toolbar_frame, text="☰", font=("Arial", 22), cursor="hand2")
        self.hamburger_btn.pack(side="left", padx=(5, 10))

        self.title_label = ctk.CTkLabel(self, text="", font=self.f_title, text_color="#3b8ed0")
        self.title_label.pack(pady=(0, 20))

        self.main_split = ctk.CTkFrame(self, fg_color="transparent")
        self.main_split.pack(fill="both", expand=True, padx=20, pady=10)
        self.main_split.grid_columnconfigure(0, weight=2) 
        self.main_split.grid_columnconfigure(1, weight=1) 
        self.main_split.grid_rowconfigure(0, weight=1)

        self.details_panel = ctk.CTkFrame(self.main_split)
        self.details_panel.grid(row=0, column=0, sticky="nsew", padx=10)
        self.details_title = ctk.CTkLabel(self.details_panel, text="", font=self.f_header)
        self.details_title.pack(anchor="center", pady=(15, 10))
        self.details_scroll = ctk.CTkScrollableFrame(self.details_panel, fg_color=("gray90", "gray20"))
        self.details_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        self.empty_details_lbl = ctk.CTkLabel(self.details_scroll, text="", font=self.f_reg, text_color="gray50")
        self.empty_details_lbl.pack(pady=40)

        self.controls_panel = ctk.CTkFrame(self.main_split)
        self.controls_panel.grid(row=0, column=1, sticky="nsew", padx=10)
        
        self.mode_frame = ctk.CTkFrame(self.controls_panel, fg_color=("gray85", "gray25"))
        self.mode_frame.pack(fill="x", padx=15, pady=15)
        self.mode_title = ctk.CTkLabel(self.mode_frame, text="", font=self.f_sub)
        self.mode_title.pack(anchor="e", padx=10, pady=(10, 5))
        
        self.load_mode_var = ctk.StringVar(value="replace")
        self.rb_replace = ctk.CTkRadioButton(self.mode_frame, text="", variable=self.load_mode_var, value="replace", font=self.f_reg)
        self.rb_replace.pack(anchor="e", padx=20, pady=5)
        self.rb_append = ctk.CTkRadioButton(self.mode_frame, text="", variable=self.load_mode_var, value="append", font=self.f_reg)
        self.rb_append.pack(anchor="e", padx=20, pady=5)
        self.rb_update = ctk.CTkRadioButton(self.mode_frame, text="", variable=self.load_mode_var, value="update", font=self.f_reg)
        self.rb_update.pack(anchor="e", padx=20, pady=(5, 15))

        self.files_frame = ctk.CTkFrame(self.controls_panel, fg_color=("gray85", "gray25"))
        self.files_frame.pack(fill="x", padx=15, pady=10)
        self.files_title = ctk.CTkLabel(self.files_frame, text="", font=self.f_sub)
        self.files_title.pack(anchor="e", padx=10, pady=(10, 5))
        
        self.btn_courses = ctk.CTkButton(self.files_frame, text="", font=self.f_reg, command=self._handle_load_courses)
        self.btn_courses.pack(fill="x", padx=20, pady=5)
        self.btn_dates = ctk.CTkButton(self.files_frame, text="", font=self.f_reg, command=self._handle_load_dates)
        self.btn_dates.pack(fill="x", padx=20, pady=5)
        self.btn_programs = ctk.CTkButton(self.files_frame, text="", font=self.f_reg, command=self._handle_load_programs)
        self.btn_programs.pack(fill="x", padx=20, pady=(5, 15))

        self.programs_frame = ctk.CTkFrame(self.controls_panel, fg_color=("gray85", "gray25"))
        self.programs_frame.pack(fill="both", expand=True, padx=15, pady=15)
        self.programs_title = ctk.CTkLabel(self.programs_frame, text="", font=self.f_sub)
        self.programs_title.pack(anchor="e", padx=10, pady=(10, 5))
        
        self.programs_list_frame = ctk.CTkScrollableFrame(self.programs_frame, fg_color="transparent")
        self.programs_list_frame.pack(fill="both", expand=True, padx=5, pady=5)

    def _handle_load_courses(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")])
        if file_path and self.on_load_courses: self.on_load_courses(file_path)

    def _handle_load_dates(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")])
        if file_path and self.on_load_dates: self.on_load_dates(file_path)

    def _handle_load_programs(self):
        file_path = filedialog.askopenfilename(filetypes=[("Excel/CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")])
        if file_path and self.on_load_programs: self.on_load_programs(file_path)

    def display_programs_list(self, programs: Dict[str, str]):
        for cb in self.checkboxes: cb.destroy()
        self.checkboxes.clear()
        anchor = "e" if self.current_lang == "he" else "w"
        for prog_id, prog_name in programs.items():
            display_text = f"\u200F{prog_name} ({prog_id})\u200F" if self.current_lang == "he" else f"{prog_name} ({prog_id})"
            cb = ctk.CTkCheckBox(self.programs_list_frame, text=display_text, font=self.f_reg, command=lambda pid=prog_id: self._handle_program_click(pid))
            cb.pack(anchor=anchor, pady=5, padx=10)
            self.checkboxes.append(cb)

    def _handle_program_click(self, prog_id):
        if self.on_program_selected: self.on_program_selected(prog_id)

    def display_program_courses(self, courses: List[dict]):
        for widget in self.details_scroll.winfo_children(): widget.destroy()
        if not courses:
            self.empty_details_lbl = ctk.CTkLabel(self.details_scroll, text=format_text("no_selection", self.current_lang), font=self.f_reg, text_color="gray50")
            self.empty_details_lbl.pack(pady=40)
            return

        anchor = "e" if self.current_lang == "he" else "w"
        for course in courses:
            card = ctk.CTkFrame(self.details_scroll, corner_radius=5, border_width=1, border_color=("gray70", "gray40"))
            card.pack(fill="x", pady=5, padx=5)
            c_name = course.get('name', '')
            c_id = course.get('id', '')
            c_type = format_text("type_hova" if course.get('is_mandatory') else "type_bhira", self.current_lang)
            c_sem = course.get('semester', '')
            c_year = course.get('year', '')
            
            title = f"\u200F{c_name} ({c_id})\u200F" if self.current_lang == "he" else f"{c_name} ({c_id})"
            info = f"\u200Fשנה {c_year} | סמסטר {c_sem} | {c_type}\u200F" if self.current_lang == "he" else f"Year {c_year} | Sem {c_sem} | {c_type}"
            
            ctk.CTkLabel(card, text=title, font=self.f_sub).pack(anchor=anchor, padx=10, pady=(5, 0))
            ctk.CTkLabel(card, text=info, font=self.f_small, text_color="gray60").pack(anchor=anchor, padx=10, pady=(0, 5))

    def update_language(self, lang: str):
        self.current_lang = lang
        
        self.title_label.configure(text=format_text("title", lang))
        self.mode_title.configure(text=format_text("load_mode", lang))
        self.rb_replace.configure(text=format_text("mode_replace", lang))
        self.rb_append.configure(text=format_text("mode_append", lang))
        self.rb_update.configure(text=format_text("mode_update", lang))
        self.files_title.configure(text=format_text("files_title", lang))
        self.btn_courses.configure(text=format_text("btn_load_courses", lang))
        self.btn_dates.configure(text=format_text("btn_load_dates", lang))
        self.btn_programs.configure(text=format_text("btn_load_programs", lang))
        self.programs_title.configure(text=format_text("programs_title", lang))
        self.details_title.configure(text=format_text("details_title", lang))
        if hasattr(self, 'empty_details_lbl') and self.empty_details_lbl.winfo_exists():
            self.empty_details_lbl.configure(text=format_text("no_selection", lang))

        anchor = "e" if lang == "he" else "w"
        self.mode_title.pack_configure(anchor=anchor)
        self.rb_replace.pack_configure(anchor=anchor)
        self.rb_append.pack_configure(anchor=anchor)
        self.rb_update.pack_configure(anchor=anchor)
        self.files_title.pack_configure(anchor=anchor)
        self.programs_title.pack_configure(anchor=anchor)
        for cb in self.checkboxes: cb.pack_configure(anchor=anchor)