import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Dict

TRANSLATIONS = {
    "title": {"he": "תצוגת לוח מבחנים", "en": "Exam Schedule View"},
    "prev": {"he": "הקודם", "en": "Previous"},
    "next": {"he": "הבא", "en": "Next"},
    "exclude_btn": {"he": "תאריך החרג", "en": "Exclude Date"}, # יוצג כ- "החרג תאריך"
    "export_btn": {"he": "לוח הורד", "en": "Download Schedule"}, # יוצג כ- "הורד לוח"
    "start_date": {"he": "תאריך התחלה (DD/MM/YYYY)", "en": "Start Date (DD/MM/YYYY)"},
    "end_date": {"he": "תאריך סיום (DD/MM/YYYY)", "en": "End Date (DD/MM/YYYY)"},
    "update_range": {"he": "טווח עדכן", "en": "Update Range"}, 
    "filter_btn": {"he": "מערכות ומיון סינון", "en": "Filter & Sort Schedules"}, 
    "days": {
        "he": ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"],
        "en": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    }
}

def format_text(key: str, lang: str) -> str:
    text = TRANSLATIONS[key][lang]
    return f"\u200F{text}\u200F" if lang == "he" else text

class CalendarGridView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_lang = "he"
        
        # --- Callbacks ---
        self.on_next_clicked: Callable[[], None] = None
        self.on_prev_clicked: Callable[[], None] = None
        self.on_page_jump: Callable[[int], None] = None 
        self.on_export_clicked: Callable[[str], None] = None 
        self.on_exclude_clicked: Callable[[str], None] = None 
        self.on_date_selected: Callable[[str], None] = None
        self.on_range_update_clicked: Callable[[str, str], None] = None 
        self.on_filter_clicked: Callable[[], None] = None 
        
        self.day_headers = [] 
        self.grid_cells = {}  
        self.selected_cell_key = None 
        
        self._setup_ui()
        self.update_language(self.current_lang)

    def _setup_ui(self):
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.pack(fill="x", pady=(10, 0), padx=20)
        
        self.title_label = ctk.CTkLabel(self.controls_frame, text="", font=("Arial", 20, "bold"))
        self.title_label.pack(side="right", padx=10)
        
        self.export_btn = ctk.CTkButton(self.controls_frame, text="", fg_color="#28a745", hover_color="#218838", command=self._handle_export)
        self.export_btn.pack(side="right", padx=10)
        
        self.exclude_btn = ctk.CTkButton(self.controls_frame, text="", fg_color="#b22222", hover_color="#8b0000", command=self._handle_exclude)
        self.exclude_btn.pack(side="left", padx=20)

        self.nav_frame = ctk.CTkFrame(self.controls_frame, fg_color="transparent")
        self.nav_frame.pack(side="left", padx=10)
        
        self.next_btn = ctk.CTkButton(self.nav_frame, text="", width=70, command=self._handle_next)
        self.next_btn.pack(side="left", padx=5)
        
        self.page_frame = ctk.CTkFrame(self.nav_frame, fg_color="transparent")
        self.page_frame.pack(side="left", padx=10)
        
        self.current_page_entry = ctk.CTkEntry(self.page_frame, width=45, justify="center")
        self.current_page_entry.pack(side="left")
        self.current_page_entry.bind("<Return>", self._handle_page_jump) 
        
        self.total_pages_label = ctk.CTkLabel(self.page_frame, text=" / 1", font=("Arial", 16, "bold"))
        self.total_pages_label.pack(side="left", padx=(5, 0))
        
        self.prev_btn = ctk.CTkButton(self.nav_frame, text="", width=70, command=self._handle_prev)
        self.prev_btn.pack(side="left", padx=5)

        self.tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.tools_frame.pack(fill="x", pady=5, padx=20)

        self.filter_btn = ctk.CTkButton(self.tools_frame, text="", fg_color="#4B0082", hover_color="#300052", command=self._handle_filter)
        self.range_frame = ctk.CTkFrame(self.tools_frame, fg_color="transparent")
        
        self.start_entry = ctk.CTkEntry(self.range_frame, width=170)
        self.end_entry = ctk.CTkEntry(self.range_frame, width=170)
        self.update_range_btn = ctk.CTkButton(self.range_frame, text="", width=100, command=self._handle_update_range)

        self.grid_frame = ctk.CTkFrame(self)
        self.grid_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        for i in range(7):
            self.grid_frame.grid_columnconfigure(i, weight=1)
            
        for i in range(7):
            lbl = ctk.CTkLabel(self.grid_frame, text="", font=("Arial", 14, "bold"), fg_color=("gray80", "gray30"), corner_radius=5)
            self.day_headers.append(lbl)
            
        for row in range(1, 6):
            self.grid_frame.grid_rowconfigure(row, weight=1)
            for col in range(7):
                cell = ctk.CTkFrame(self.grid_frame, border_width=1, border_color=("gray70", "gray40"), fg_color=("gray90", "gray20"))
                self.grid_cells[f"{row}-{col}"] = cell
                self._bind_cell_click(cell, f"{row}-{col}")

    def _bind_cell_click(self, widget, cell_key):
        widget.bind("<Button-1>", lambda e: self._handle_cell_click(cell_key))

    def update_pagination(self, current_page: int, total_pages: int):
        self.current_page_entry.delete(0, "end")
        self.current_page_entry.insert(0, str(current_page))
        self.total_pages_label.configure(text=f" / {total_pages}")

    def render_calendar_data(self, grid_data: Dict[str, dict]):
        for row in range(1, 6):
            for col in range(7):
                cell_key = f"{row}-{col}"
                cell_frame = self.grid_cells[cell_key]
                
                for widget in cell_frame.winfo_children():
                    widget.destroy()
                
                cell_data = grid_data.get(cell_key)
                if not cell_data:
                    cell_frame.configure(fg_color=("gray90", "gray20"))
                    continue
                
                if cell_data.get("is_excluded", False):
                    cell_frame.configure(fg_color=("#ffcccc", "#4d0000")) 
                else:
                    cell_frame.configure(fg_color=("gray90", "gray20"))
                
                anchor = "ne" if self.current_lang == "he" else "nw"
                day_lbl = ctk.CTkLabel(cell_frame, text=cell_data.get("day_text", ""), font=("Arial", 12, "bold"))
                day_lbl.pack(anchor=anchor, padx=5, pady=2)
                self._bind_cell_click(day_lbl, cell_key) 
                
                for exam in cell_data.get("exams", []):
                    card_color = "#3b8ed0" if exam.get("type") == "חובה" else "#2fa572" 
                    card = ctk.CTkFrame(cell_frame, fg_color=card_color, corner_radius=4)
                    card.pack(fill="x", padx=4, pady=2)
                    self._bind_cell_click(card, cell_key)
                    
                    exam_name = exam.get('name', '')
                    exam_id = exam.get('course_id', '')
                    display_text = f"\u200F{exam_name}\u200F" if self.current_lang == "he" else exam_name
                    
                    name_lbl = ctk.CTkLabel(card, text=display_text, font=("Arial", 11, "bold"), text_color="white")
                    name_lbl.pack(padx=2, pady=1)
                    self._bind_cell_click(name_lbl, cell_key)
                    
                    id_lbl = ctk.CTkLabel(card, text=exam_id, font=("Arial", 10), text_color="white")
                    id_lbl.pack(padx=2, pady=1)
                    self._bind_cell_click(id_lbl, cell_key)
                    
        if self.selected_cell_key and self.selected_cell_key in self.grid_cells:
            self.grid_cells[self.selected_cell_key].configure(border_color="#3b8ed0", border_width=3)

    def update_language(self, lang: str):
        self.current_lang = lang
        self.title_label.configure(text=format_text("title", lang))
        self.prev_btn.configure(text=format_text("prev", lang))
        self.next_btn.configure(text=format_text("next", lang))
        self.exclude_btn.configure(text=format_text("exclude_btn", lang))
        self.export_btn.configure(text=format_text("export_btn", lang))
        
        self.filter_btn.configure(text=format_text("filter_btn", lang))
        self.update_range_btn.configure(text=format_text("update_range", lang))
        self.start_entry.configure(placeholder_text=format_text("start_date", lang))
        self.end_entry.configure(placeholder_text=format_text("end_date", lang))
        
        self.next_btn.pack_forget()
        self.page_frame.pack_forget()
        self.prev_btn.pack_forget()
        
        if lang == "he":
            self.next_btn.pack(side="right", padx=5)
            self.page_frame.pack(side="right", padx=10)
            self.prev_btn.pack(side="right", padx=5)
            
            self.filter_btn.pack_forget()
            self.range_frame.pack_forget()
            self.filter_btn.pack(side="left", padx=10)
            self.range_frame.pack(side="right", padx=10)
            self.start_entry.pack(side="right", padx=5)
            self.end_entry.pack(side="right", padx=5)
            self.update_range_btn.pack(side="right", padx=5)
        else:
            self.next_btn.pack(side="left", padx=5)
            self.page_frame.pack(side="left", padx=10)
            self.prev_btn.pack(side="left", padx=5)
            
            self.filter_btn.pack_forget()
            self.range_frame.pack_forget()
            self.filter_btn.pack(side="right", padx=10)
            self.range_frame.pack(side="left", padx=10)
            self.start_entry.pack(side="left", padx=5)
            self.end_entry.pack(side="left", padx=5)
            self.update_range_btn.pack(side="left", padx=5)

        days = TRANSLATIONS["days"][lang]
        for i, header in enumerate(self.day_headers):
            display_col = 6 - i if lang == "he" else i
            text = f"\u200F{days[i]}\u200F" if lang == "he" else days[i]
            header.configure(text=text)
            header.grid(row=0, column=display_col, sticky="nsew", padx=2, pady=2)
            
        for row in range(1, 6):
            for col in range(7):
                display_col = 6 - col if lang == "he" else col
                self.grid_cells[f"{row}-{col}"].grid(row=row, column=display_col, sticky="nsew", padx=2, pady=2)
                
                cell = self.grid_cells[f"{row}-{col}"]
                if cell.winfo_children():
                    day_lbl = cell.winfo_children()[0]
                    if isinstance(day_lbl, ctk.CTkLabel):
                        day_lbl.pack_configure(anchor="ne" if lang == "he" else "nw")

    def _handle_next(self):
        if self.on_next_clicked: self.on_next_clicked()
    def _handle_prev(self):
        if self.on_prev_clicked: self.on_prev_clicked()
    def _handle_page_jump(self, event=None):
        if self.on_page_jump:
            try:
                page = int(self.current_page_entry.get())
                self.on_page_jump(page)
            except ValueError:
                pass 
    def _handle_export(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("PDF files", "*.pdf"), ("All files", "*.*")],
            title="שמור מערכת בחינות" if self.current_lang == "he" else "Save Exam Schedule"
        )
        if file_path and self.on_export_clicked:
            self.on_export_clicked(file_path)
    def _handle_exclude(self):
        if self.selected_cell_key and self.on_exclude_clicked:
            self.on_exclude_clicked(self.selected_cell_key)
    def _handle_cell_click(self, cell_key):
        if self.selected_cell_key and self.selected_cell_key in self.grid_cells:
            self.grid_cells[self.selected_cell_key].configure(border_color=("gray70", "gray40"), border_width=1)
        self.selected_cell_key = cell_key
        if self.selected_cell_key in self.grid_cells:
            self.grid_cells[self.selected_cell_key].configure(border_color="#3b8ed0", border_width=3)
        if self.on_date_selected: 
            self.on_date_selected(cell_key)
    def _handle_update_range(self):
        if self.on_range_update_clicked:
            self.on_range_update_clicked(self.start_entry.get(), self.end_entry.get())
    def _handle_filter(self):
        if self.on_filter_clicked: self.on_filter_clicked()