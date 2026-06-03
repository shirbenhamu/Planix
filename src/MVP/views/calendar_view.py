import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Dict, List

# Dictionary containing localized strings for internationalization (I18n)
TRANSLATIONS = {
    "title": {"he": "שנת הלימודים תשפ\"ו", "en": "Academic Year 2026"},
    "exclude_btn": {"he": "תאריך החרג", "en": "Exclude Date"},
    "export_btn": {"he": "📥", "en": "📥"},
    "start_date": {"he": "התחלה", "en": "Start"},
    "end_date": {"he": "סיום", "en": "End"},
    "update_range": {"he": "עדכן", "en": "Update"},
    "filter_btn": {"he": "סינון לפי", "en": "Filter By"},
    "schedule_lbl": {"he": "מערכת", "en": "Schedule"},
    "out_of_lbl": {"he": "מתוך", "en": "out of"},
    "empty_state": {"he": "יש לטעון קבצי נתונים (קורסים ותאריכים) כדי להציג את הלוח.", "en": "Please load data files (courses and dates) to view the schedule."},
    "days": {
        "he": ["א'", "ב'", "ג'", "ד'", "ה'", "ו'", "ש'"],
        "en": ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"]
    },
    "months": {
        "he": ["ינו", "פבר", "מרץ", "אפר", "מאי", "יונ", "יול", "אוג", "ספט", "אוק", "נוב", "דצמ"],
        "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    }
}

def format_text(key: str, lang: str) -> str:
    """Helper to return direction-aware formatted strings."""
    text = TRANSLATIONS[key][lang]
    return f"\u200F{text}\u200F" if lang == "he" else text

class CalendarGridView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_lang = "he"
        
        # Apply Rubik font globally to maintain consistent typography
        base_family = "Rubik"
        self.f_title = ctk.CTkFont(family=base_family, size=16, weight="bold")
        self.f_btn = ctk.CTkFont(family=base_family, size=12, weight="bold")
        self.f_header = ctk.CTkFont(family=base_family, size=11, weight="bold")
        # Scaled down card font size to ensure all metadata fits tightly within the blocks
        self.f_card = ctk.CTkFont(family=base_family, size=8, weight="bold")
        self.f_empty = ctk.CTkFont(family=base_family, size=18, weight="bold")

        # Callbacks for component interactions
        self.on_hamburger_clicked: Callable[[], None] = None 
        self.on_next_clicked: Callable[[], None] = None
        self.on_prev_clicked: Callable[[], None] = None
        self.on_page_jump: Callable[[int], None] = None 
        self.on_export_clicked: Callable[[str], None] = None 
        self.on_exclude_clicked: Callable[[str], None] = None 
        self.on_date_selected: Callable[[str], None] = None
        self.on_range_update_clicked: Callable[[str, str], None] = None 
        self.on_filter_clicked: Callable[[], None] = None 
        
        self.day_headers = [] 
        self.month_labels = []
        self.grid_cells = {}  
        self.selected_cell_key = None 
        self.active_month_indices = []
        
        self._setup_ui()
        self._setup_empty_state()
        self.update_language(self.current_lang)
        self.show_empty_state() 

    def _setup_ui(self):
        # Initialize the top toolbar
        self.toolbar_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.toolbar_frame.pack(fill="x", pady=(5, 5), padx=5)
        
        # Hamburger menu button positioned at the start of the toolbar
        self.hamburger_btn = ctk.CTkLabel(self.toolbar_frame, text="☰", font=("Arial", 22), cursor="hand2")
        self.hamburger_btn.pack(side="left", padx=(5, 10))
        self.hamburger_btn.bind("<Enter>", lambda e: self._handle_hamburger())
        
        self.schedule_title = ctk.CTkLabel(self.toolbar_frame, text="", font=self.f_title, text_color="#3b8ed0")
        self.schedule_title.pack(side="left", padx=10)
        
        # Navigation controls for pagination formatting (Schedule X out of Y)
        self.nav_frame = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
        self.nav_frame.pack(side="left", padx=15)
        
        self.prev_btn = ctk.CTkButton(self.nav_frame, text="<", font=self.f_btn, width=30, height=26, command=self._handle_prev)
        self.prev_btn.pack(side="left", padx=2)
        
        self.schedule_lbl = ctk.CTkLabel(self.nav_frame, text="", font=self.f_btn)
        self.schedule_lbl.pack(side="left", padx=2)

        self.current_page_entry = ctk.CTkEntry(self.nav_frame, width=35, height=26, justify="center", font=self.f_btn)
        self.current_page_entry.pack(side="left", padx=2)
        self.current_page_entry.bind("<Return>", self._handle_page_jump) 
        
        self.total_pages_label = ctk.CTkLabel(self.nav_frame, text="", font=self.f_btn)
        self.total_pages_label.pack(side="left", padx=2)
        
        self.next_btn = ctk.CTkButton(self.nav_frame, text=">", font=self.f_btn, width=30, height=26, command=self._handle_next)
        self.next_btn.pack(side="left", padx=2)

        # Date range inputs
        self.range_frame = ctk.CTkFrame(self.toolbar_frame, fg_color="transparent")
        self.range_frame.pack(side="left", padx=15)
        self.start_entry = ctk.CTkEntry(self.range_frame, width=70, height=26, font=self.f_btn)
        self.start_entry.pack(side="left", padx=2)
        self.end_entry = ctk.CTkEntry(self.range_frame, width=70, height=26, font=self.f_btn)
        self.end_entry.pack(side="left", padx=2)
        self.update_range_btn = ctk.CTkButton(self.range_frame, text="", font=self.f_btn, width=50, height=26, command=self._handle_update_range)
        self.update_range_btn.pack(side="left", padx=2)

        # Action buttons aligned to the right
        self.export_btn = ctk.CTkButton(self.toolbar_frame, text="📥", fg_color="#28a745", hover_color="#218838", font=("Arial", 16), height=26, width=35, command=self._handle_export)
        self.export_btn.pack(side="right", padx=5)
        self.exclude_btn = ctk.CTkButton(self.toolbar_frame, text="", font=self.f_btn, fg_color="#b22222", hover_color="#8b0000", height=26, width=80, command=self._handle_exclude)
        self.exclude_btn.pack(side="right", padx=5)
        self.filter_btn = ctk.CTkButton(self.toolbar_frame, text="", font=self.f_btn, fg_color="#4B0082", hover_color="#300052", height=26, width=90, command=self._handle_filter)
        self.filter_btn.pack(side="right", padx=5)

        # Container for the grid
        self.grid_frame = ctk.CTkFrame(self)

    def _setup_empty_state(self):
        """Displays icon and text when no data is loaded."""
        self.empty_state_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.empty_icon = ctk.CTkLabel(self.empty_state_frame, text="📁", font=("Arial", 60))
        self.empty_icon.pack(pady=(50, 10))
        self.empty_text = ctk.CTkLabel(self.empty_state_frame, text="", font=self.f_empty, text_color="gray50")
        self.empty_text.pack()

    def show_empty_state(self):
        self.grid_frame.pack_forget()
        self.empty_state_frame.pack(fill="both", expand=True)

    def hide_empty_state(self):
        self.empty_state_frame.pack_forget()
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=(2, 10))

    def init_grid(self, month_indices: List[int]):
        """Generates the grid dynamically based on the number of months provided."""
        if not month_indices:
            self.show_empty_state()
            return
            
        self.hide_empty_state()
        self.active_month_indices = month_indices
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        self.day_headers.clear()
        self.month_labels.clear()
        self.grid_cells.clear()

        # Configure columns (31 days + 1 for month label)
        for i in range(31):
            # Enforce identical width distribution by utilizing uniform groupings
            self.grid_frame.grid_columnconfigure(i, weight=1, uniform="day_column")
        self.grid_frame.grid_columnconfigure(31, weight=0, minsize=40)
        
        # Header row for day names
        self.grid_frame.grid_rowconfigure(0, minsize=25)
        days = TRANSLATIONS["days"][self.current_lang]
        for i in range(31):
            day_text = days[i % 7]
            # Bypass format_text specifically for standalone days to avoid rendering bugs with RTL marks
            lbl = ctk.CTkLabel(self.grid_frame, text=day_text, font=self.f_header, fg_color=("gray80", "gray30"), corner_radius=0)
            lbl.grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
            self.day_headers.append(lbl)

        # Generate rows for each month
        for row_idx, month_idx in enumerate(month_indices, start=1):
            self.grid_frame.grid_rowconfigure(row_idx, weight=1) 
            for col in range(31):
                cell_key = f"{row_idx}-{col}"
                cell = ctk.CTkFrame(self.grid_frame, border_width=1, border_color=("gray70", "gray40"), fg_color=("gray90", "gray20"), corner_radius=0)
                cell.grid(row=row_idx, column=col, sticky="nsew", padx=1, pady=1)
                self.grid_cells[cell_key] = cell
                self._bind_cell_click(cell, cell_key)
                
            m_text = TRANSLATIONS["months"][self.current_lang][month_idx]
            display_m = f"\u200F{m_text}\u200F" if self.current_lang == "he" else m_text
            m_lbl = ctk.CTkLabel(self.grid_frame, text=display_m, font=self.f_header)
            m_lbl.grid(row=row_idx, column=31, sticky="nsew", padx=2)
            self.month_labels.append(m_lbl)

    def _bind_cell_click(self, widget, cell_key):
        widget.bind("<Button-1>", lambda e: self._handle_cell_click(cell_key))

    def update_single_cell(self, cell_key: str, cell_data: dict):
        """Refreshes a specific cell content without re-rendering the entire grid."""
        cell_frame = self.grid_cells.get(cell_key)
        if not cell_frame: return
        for widget in cell_frame.winfo_children(): widget.destroy()
            
        if cell_data.get("is_excluded", False):
            cell_frame.configure(fg_color=("#ffcccc", "#4d0000")) 
        else:
            cell_frame.configure(fg_color=("gray90", "gray20"))
            
        date_num = cell_data.get("day_text", "")
        if date_num:
            anchor = "ne" if self.current_lang == "he" else "nw"
            day_lbl = ctk.CTkLabel(cell_frame, text=date_num, font=self.f_card, text_color=("gray50", "gray60"))
            day_lbl.pack(anchor=anchor, padx=2, pady=0) 
        
        for exam in cell_data.get("exams", []):
            card_color = "#3b8ed0" if exam.get("type") == "ח" else "#2fa572" 
            card = ctk.CTkFrame(cell_frame, fg_color=card_color, corner_radius=2)
            
            # Constrain card stretch behavior by setting expand=False so it wraps tightly around text content
            card.pack(fill="x", expand=False, padx=1, pady=1)
            self._bind_cell_click(card, cell_key)
            
            # Compress into 2 lines. View layer formats the incoming payload from the active presenter
            short_name = exam.get('short_name', '')[:3]
            c_type = exam.get('type', '')
            c_id = exam.get('course_id', '')
            prog = exam.get('program', '')
            
            txt = f"{short_name} | {c_type}\n{c_id} | {prog}"
            lbl = ctk.CTkLabel(card, text=txt, font=self.f_card, text_color="white", justify="center")
            lbl.pack(padx=0, pady=1)
            self._bind_cell_click(lbl, cell_key)
            
        if self.selected_cell_key == cell_key:
            cell_frame.configure(border_color="#3b8ed0", border_width=2)

    def render_calendar_data(self, grid_data: Dict[str, dict]):
        if not grid_data:
            self.show_empty_state()
            return
        self.hide_empty_state()
        for cell_key in self.grid_cells.keys():
            data = grid_data.get(cell_key, {})
            self.update_single_cell(cell_key, data)

    def update_pagination(self, current_page: int, total_pages: int):
        """Updates the pagination indicators to match 'Schedule X out of Y' formatting."""
        self.current_page_entry.delete(0, "end")
        self.current_page_entry.insert(0, str(current_page))
        out_of = format_text("out_of_lbl", self.current_lang)
        self.total_pages_label.configure(text=f" {out_of} {total_pages}")

    def update_language(self, lang: str):
        """Updates all labels and UI text alignment without structural layout shifts."""
        self.current_lang = lang

        # UI updates based on translation dictionary
        self.schedule_title.configure(text=format_text("title", lang))
        self.exclude_btn.configure(text=format_text("exclude_btn", lang))
        self.export_btn.configure(text=format_text("export_btn", lang))
        self.filter_btn.configure(text=format_text("filter_btn", lang))
        self.update_range_btn.configure(text=format_text("update_range", lang))
        self.start_entry.configure(placeholder_text=format_text("start_date", lang))
        self.end_entry.configure(placeholder_text=format_text("end_date", lang))
        self.empty_text.configure(text=format_text("empty_state", lang))
        self.schedule_lbl.configure(text=format_text("schedule_lbl", lang))

        # Update headers directly without applying format_text to preserve exact punctuation flow
        days = TRANSLATIONS["days"][lang]
        for i, header in enumerate(self.day_headers):
            day_text = days[i % 7]
            header.configure(text=day_text)
            
        # Update months
        months = TRANSLATIONS["months"][lang]
        for i, m_lbl in enumerate(self.month_labels):
            if i < len(self.active_month_indices):
                m_text = months[self.active_month_indices[i]]
                m_lbl.configure(text=f"\u200F{m_text}\u200F" if lang == "he" else m_text)
            
        # Adjust text alignment within cells
        for cell_frame in self.grid_cells.values():
            if cell_frame.winfo_children():
                date_lbl = cell_frame.winfo_children()[0]
                if isinstance(date_lbl, ctk.CTkLabel):
                    date_lbl.pack_configure(anchor="ne" if lang == "he" else "nw")

    # Event handlers
    def _handle_hamburger(self):
        if self.on_hamburger_clicked: self.on_hamburger_clicked()
    def _handle_next(self):
        if self.on_next_clicked: self.on_next_clicked()
    def _handle_prev(self):
        if self.on_prev_clicked: self.on_prev_clicked()
    def _handle_page_jump(self, event=None):
        if self.on_page_jump:
            try:
                page = int(self.current_page_entry.get())
                self.on_page_jump(page)
            except ValueError: pass 
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
            self.grid_cells[self.selected_cell_key].configure(border_color="#3b8ed0", border_width=2)
        if self.on_date_selected: 
            self.on_date_selected(cell_key)
    def _handle_update_range(self):
        if self.on_range_update_clicked:
            self.on_range_update_clicked(self.start_entry.get(), self.end_entry.get())
    def _handle_filter(self):
        if self.on_filter_clicked: self.on_filter_clicked()

    #  This method attempts to extract selected academic programs from various possible checkbox containers
    # in the UI, providing flexibility for different implementations. It returns a list of selected program
    # names based on the text of the checkboxes that are currently checked.
    def get_selected_programs(self) -> List[str]:
        selected_programs: List[str] = []

        program_containers = [
            getattr(self, "program_checkboxes", None),
            getattr(self, "programs_checkboxes", None),
            getattr(self, "checkboxes", None),
        ]

        for container in program_containers:
            if not container:
                continue

            for item in container:
                get_value = getattr(item, "get", None)
                if not callable(get_value):
                    continue

                try:
                    if get_value():
                        cget = getattr(item, "cget", None)
                        if callable(cget):
                            label = cget("text")
                            if label:
                                selected_programs.append(label)
                except Exception:
                    continue

            if selected_programs:
                break

        return selected_programs