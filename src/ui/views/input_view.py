import customtkinter as ctk
from typing import Callable, Dict

# מילון התרגומים שלנו (קל לתחזוקה ולהוספת שפות בעתיד)
TRANSLATIONS = {
    "title": {"he": "הגדרות קלט וטעינת נתונים", "en": "Input Configuration & Data Loading"},
    "load_courses": {"he": "טען קובץ קורסים", "en": "Load Courses File"},
    "load_dates": {"he": "טען קובץ תאריכים", "en": "Load Dates File"},
    "full_mode": {"he": "החלפת נתונים מלאה", "en": "Full Data Replacement"},
    "inc_mode": {"he": "עדכון נתונים (הוספה)", "en": "Incremental Data Update"},
    "programs_title": {"he": "בחר תוכניות לימוד (עד 5)", "en": "Select Study Programs (Max 5)"},
    "details_title": {"he": "פרטי התוכנית", "en": "Program Details"},
    "details_placeholder": {"he": "בחר תוכנית מהרשימה כדי לראות את הקורסים שלה כאן.", "en": "Select a program from the list to view its courses here."},
}

def format_text(key: str, lang: str) -> str:
    """שולף את הטקסט מהמילון, ומוסיף תו כיווניות רק אם השפה היא עברית"""
    text = TRANSLATIONS[key][lang]
    if lang == "he":
        return f"\u200F{text}\u200F"
    return text

class InputConfigurationView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        self.current_lang = "he" # שפת ברירת מחדל
        
        # --- Callbacks ---
        self.on_load_courses_clicked: Callable[[], None] = None
        self.on_load_dates_clicked: Callable[[], None] = None
        self.on_upload_mode_changed: Callable[[str], None] = None
        self.on_program_toggled: Callable[[str, bool], None] = None  
        self.on_program_info_clicked: Callable[[str], None] = None   
        
        self.checkboxes = {} 
        
        self._setup_ui()
        self.update_language(self.current_lang) # טעינת הטקסטים בפעם הראשונה

    def _setup_ui(self):
        # הרכיבים נוצרים ללא טקסט - הטקסט יוזרק מיד לאחר מכן
        self.title_label = ctk.CTkLabel(self, text="", font=("Arial", 20, "bold"))
        self.title_label.pack(pady=20)

        self.files_frame = ctk.CTkFrame(self)
        self.files_frame.pack(pady=10, padx=20, fill="x")
        
        self.courses_btn = ctk.CTkButton(self.files_frame, text="", command=self._handle_courses_click)
        self.courses_btn.pack(side="right", padx=10, pady=10)
        
        self.dates_btn = ctk.CTkButton(self.files_frame, text="", command=self._handle_dates_click)
        self.dates_btn.pack(side="right", padx=10, pady=10)

        self.mode_var = ctk.StringVar()
        self.mode_menu = ctk.CTkOptionMenu(
            self.files_frame, 
            variable=self.mode_var,
            values=[],
            command=self._handle_mode_change
        )
        self.mode_menu.pack(side="left", padx=10, pady=10)

        self.programs_main_frame = ctk.CTkFrame(self)
        self.programs_main_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.programs_main_frame.grid_columnconfigure(0, weight=2) 
        self.programs_main_frame.grid_columnconfigure(1, weight=1) 
        self.programs_main_frame.grid_rowconfigure(0, weight=1)

        self.programs_list_frame = ctk.CTkScrollableFrame(self.programs_main_frame, label_text="")
        self.programs_list_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.program_details_frame = ctk.CTkFrame(self.programs_main_frame)
        self.program_details_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.details_label = ctk.CTkLabel(self.program_details_frame, text="", font=("Arial", 16, "bold"))
        self.details_label.pack(pady=10)
        
        self.details_textbox = ctk.CTkTextbox(self.program_details_frame, wrap="word", font=("Arial", 14))
        self.details_textbox.pack(fill="both", expand=True, padx=10, pady=10)
        self.details_textbox.configure(state="disabled")

    # ==========================================
    # Language Management
    # ==========================================
    
    def update_language(self, lang: str):
        """פונקציה ציבורית לעדכון שפת הממשק באופן מיידי"""
        self.current_lang = lang
        
        # עדכון כותרות וכפתורים
        self.title_label.configure(text=format_text("title", lang))
        self.courses_btn.configure(text=format_text("load_courses", lang))
        self.dates_btn.configure(text=format_text("load_dates", lang))
        
        # עדכון תפריט גלילה
        full_mode_text = format_text("full_mode", lang)
        inc_mode_text = format_text("inc_mode", lang)
        self.mode_menu.configure(values=[full_mode_text, inc_mode_text])
        # שמירה על הבחירה הנוכחית בעת שינוי שפה
        if self.mode_var.get() in [TRANSLATIONS["full_mode"]["he"], TRANSLATIONS["full_mode"]["en"]]:
            self.mode_var.set(full_mode_text)
        else:
            self.mode_var.set(inc_mode_text)
            
        self.programs_list_frame.configure(label_text=format_text("programs_title", lang))
        self.details_label.configure(text=format_text("details_title", lang))
        
        # עדכון טקסט הפלייסחולדר (רק אם המשתמש לא לחץ על תוכנית עדיין)
        current_details = self.details_textbox.get("1.0", "end-1c").strip()
        if current_details in [f"\u200F{TRANSLATIONS['details_placeholder']['he']}\u200F", TRANSLATIONS['details_placeholder']['en'], ""]:
            self.details_textbox.configure(state="normal")
            self.details_textbox.delete("1.0", "end")
            self.details_textbox.insert("1.0", format_text("details_placeholder", lang))
            self.details_textbox.configure(state="disabled")

    # ==========================================
    # Public Methods (API) - לפריזנטר
    # ==========================================
    
    def display_programs_list(self, programs: Dict[str, str]):
        for widget in self.programs_list_frame.winfo_children():
            widget.destroy()
        self.checkboxes.clear()
        
        for prog_id, prog_name in programs.items():
            row_frame = ctk.CTkFrame(self.programs_list_frame, fg_color="transparent")
            row_frame.pack(fill="x", pady=2)
            
            var = ctk.BooleanVar()
            # מחיל את הכיווניות רק אם המערכת כרגע בעברית
            display_text = f"\u200F{prog_name} ({prog_id})\u200F" if self.current_lang == "he" else f"{prog_name} ({prog_id})"
            
            cb = ctk.CTkCheckBox(
                row_frame, 
                text=display_text, 
                variable=var,
                command=lambda pid=prog_id, v=var: self._handle_program_toggle(pid, v.get())
            )
            cb.pack(side="right", padx=5)
            self.checkboxes[prog_id] = cb

            info_btn = ctk.CTkButton(
                row_frame, text="ℹ️", width=30, fg_color="gray",
                command=lambda pid=prog_id: self._handle_program_info_click(pid)
            )
            info_btn.pack(side="left", padx=5)

    def display_program_details(self, details_text: str):
        self.details_textbox.configure(state="normal")
        self.details_textbox.delete("1.0", "end")
        
        if self.current_lang == "he":
            formatted_lines = [f"\u200F{line}\u200F" for line in details_text.split("\n")]
            formatted_text = "\n".join(formatted_lines)
        else:
            formatted_text = details_text
            
        self.details_textbox.insert("1.0", formatted_text)
        self.details_textbox.configure(state="disabled")

    # ==========================================
    # Internal Event Handlers
    # ==========================================
    def _handle_courses_click(self):
        if self.on_load_courses_clicked: self.on_load_courses_clicked()
    def _handle_dates_click(self):
        if self.on_load_dates_clicked: self.on_load_dates_clicked()
    def _handle_mode_change(self, new_mode: str):
        if self.on_upload_mode_changed: self.on_upload_mode_changed(new_mode)
    def _handle_program_toggle(self, prog_id: str, is_selected: bool):
        if self.on_program_toggled: self.on_program_toggled(prog_id, is_selected)
    def _handle_program_info_click(self, prog_id: str):
        if self.on_program_info_clicked: self.on_program_info_clicked(prog_id)