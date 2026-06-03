import customtkinter as ctk
from tkinter import filedialog
from typing import Callable, Dict, List
from src.MVP.views.ui_utils import format_text, TRANSLATIONS
from src.MVP.views.components.exam_modal import show_exam_popup
from src.MVP.views.components.top_toolbar import TopToolbar

class CalendarGridView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_lang = "he"
        self._current_page, self._total_pages = 1, 1
        
        self.f_header = ctk.CTkFont(family="Rubik", size=11, weight="bold")
        self.f_card = ctk.CTkFont(family="Rubik", size=9, weight="bold")
        self.f_empty = ctk.CTkFont(family="Rubik", size=18, weight="bold")

        self.on_hamburger_clicked = None 
        self.on_next_clicked, self.on_prev_clicked = None, None
        self.on_page_jump, self.on_range_update_clicked = None, None 
        self.on_export_clicked, self.on_exclude_clicked = None, None 
        self.on_date_selected, self.on_filter_clicked = None, None 
        
        self.day_headers, self.month_labels, self.grid_cells = [], [], {}  
        self.selected_cell_key = None 
        self.active_month_indices = []
        
        # --- Toolbar עם הכפתור החדש ---
        self.toolbar = TopToolbar(self, is_monthly=False)
        self.toolbar.pack(fill="x", pady=(5, 5), padx=5)
        
        self.toolbar.on_hamburger = lambda: self.on_hamburger_clicked() if self.on_hamburger_clicked else None
        self.toolbar.on_next = lambda: self.on_next_clicked() if self.on_next_clicked else None
        self.toolbar.on_prev = lambda: self.on_prev_clicked() if self.on_prev_clicked else None
        self.toolbar.on_page_jump = lambda p: self.on_page_jump(p) if self.on_page_jump else None
        self.toolbar.on_update_range = lambda s, e: self.on_range_update_clicked(s, e) if self.on_range_update_clicked else None
        self.toolbar.on_export = self._handle_export
        self.toolbar.on_exclude = lambda: self.on_exclude_clicked(self.selected_cell_key) if self.selected_cell_key and self.on_exclude_clicked else None
        self.toolbar.on_filter = lambda: self.on_filter_clicked() if self.on_filter_clicked else None
        self.toolbar.on_load_more = self._handle_load_more # חיבור הכפתור החדש

        self.grid_frame = ctk.CTkFrame(self)
        self._setup_empty_state()
        self.update_language(self.current_lang)

    def _handle_load_more(self):
        # כאן החברים שלך יחברו את הלוגיקה
        print("Annual View: Load more requested")

    def set_monthly_view(self, monthly_view):
        self.monthly_view = monthly_view

    def _setup_empty_state(self):
        self.empty_state_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.empty_state_frame, text="📁", font=("Arial", 60)).pack(pady=(50, 10))
        self.empty_text = ctk.CTkLabel(self.empty_state_frame, text="", font=self.f_empty, text_color="gray50")
        self.empty_text.pack()
        self.show_empty_state()

    def show_empty_state(self):
        self.grid_frame.pack_forget()
        self.empty_state_frame.pack(fill="both", expand=True)

    def hide_empty_state(self):
        self.empty_state_frame.pack_forget()
        self.grid_frame.pack(fill="both", expand=True, padx=10, pady=(2, 10))

    def _get_semester_color(self, month_idx: int) -> str:
        if month_idx in [9, 10, 11, 0, 1]: return "#4cd137" 
        elif month_idx in [2, 3, 4, 5]: return "#00a8ff" 
        else: return "#fbc531"

    def init_grid(self, month_indices: List[int]):
        if not month_indices:
            return self.show_empty_state()
        self.hide_empty_state()
        self.active_month_indices = month_indices
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        self.day_headers.clear()
        self.month_labels.clear()
        self.grid_cells.clear()

        for i in range(31): self.grid_frame.grid_columnconfigure(i, weight=1, uniform="day_column")
        self.grid_frame.grid_columnconfigure(31, weight=0, minsize=40)
        self.grid_frame.grid_rowconfigure(0, minsize=25)
        
        days = TRANSLATIONS["days"][self.current_lang]
        for i in range(31):
            lbl = ctk.CTkLabel(self.grid_frame, text=days[i % 7], font=self.f_header, fg_color=("gray80", "gray30"), corner_radius=0)
            lbl.grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
            self.day_headers.append(lbl)

        for row_idx, month_idx in enumerate(month_indices, start=1):
            self.grid_frame.grid_rowconfigure(row_idx, weight=0, minsize=110) 
            for col in range(31):
                cell_key = f"{row_idx}-{col}"
                cell = ctk.CTkFrame(self.grid_frame, border_width=1, border_color=("gray70", "gray40"), fg_color=("gray90", "gray20"), corner_radius=0)
                cell.grid(row=row_idx, column=col, sticky="nsew", padx=1, pady=1)
                self.grid_cells[cell_key] = cell
                cell.bind("<Button-1>", lambda e, k=cell_key: self._handle_cell_click(k))
                
            m_text = TRANSLATIONS["months"][self.current_lang][month_idx]
            m_lbl = ctk.CTkLabel(self.grid_frame, text=f"\u200F{m_text}\u200F" if self.current_lang == "he" else m_text, font=self.f_header, text_color=self._get_semester_color(month_idx))
            m_lbl.grid(row=row_idx, column=31, sticky="nsew", padx=2)
            self.month_labels.append(m_lbl)
            
        self.grid_frame.grid_rowconfigure(len(month_indices) + 1, weight=1)

    def update_single_cell(self, cell_key: str, cell_data: dict):
        cell_frame = self.grid_cells.get(cell_key)
        if not cell_frame: return
        for widget in cell_frame.winfo_children(): widget.destroy()
            
        cell_frame.configure(fg_color=("#ffcccc", "#4d0000") if cell_data.get("is_excluded") else ("gray90", "gray20"))
        if cell_data.get("day_text"):
            anchor = "ne" if self.current_lang == "he" else "nw"
            ctk.CTkLabel(cell_frame, text=cell_data["day_text"], font=self.f_card, text_color=("gray50", "gray60")).pack(anchor=anchor, padx=2, pady=0) 
        
        for exam in cell_data.get("exams", []):
            card = ctk.CTkFrame(cell_frame, fg_color="#3b8ed0" if exam.get("type") == "ח" else "#2fa572", corner_radius=2)
            card.pack(fill="x", expand=False, padx=1, pady=1)
            card.bind("<Button-1>", lambda e, ex=exam: show_exam_popup(self, ex, self.current_lang))
            
            lbl = ctk.CTkLabel(card, text=f"{exam.get('course_id', '')}", font=self.f_card, text_color="white", justify="center")
            lbl.pack(padx=0, pady=2)
            lbl.bind("<Button-1>", lambda e, ex=exam: show_exam_popup(self, ex, self.current_lang))
            
        if self.selected_cell_key == cell_key:
            cell_frame.configure(border_color="#3b8ed0", border_width=2)

    def render_calendar_data(self, grid_data: Dict[str, dict]):
        if not grid_data:
            self.show_empty_state()
            if hasattr(self, 'monthly_view') and self.monthly_view: self.monthly_view.show_empty_state()
            return
        self.hide_empty_state()
        for cell_key in self.grid_cells.keys():
            self.update_single_cell(cell_key, grid_data.get(cell_key, {}))
            
        if hasattr(self, 'monthly_view') and self.monthly_view:
            try:
                self.monthly_view.receive_data(grid_data, self.active_month_indices)
            except Exception as e:
                print(f"Monthly View Sync Error: {e}")

    def toggle_cell_exclusion_visual(self, cell_key: str, is_excluded: bool):
        cell_frame = self.grid_cells.get(cell_key)
        if cell_frame:
            cell_frame.configure(fg_color=("#ffcccc", "#4d0000") if is_excluded else ("gray90", "gray20"))
        if hasattr(self, 'monthly_view') and self.monthly_view:
            self.monthly_view.toggle_cell_exclusion_visual(cell_key, is_excluded)

    def update_pagination(self, current_page: int, total_pages: int):
        self._current_page, self._total_pages = current_page, total_pages
        self.toolbar.set_pagination(current_page, total_pages)
        if hasattr(self, 'monthly_view') and self.monthly_view:
            self.monthly_view.update_pagination(current_page, total_pages)

    def update_language(self, lang: str):
        self.current_lang = lang
        self.toolbar.update_language(lang)
        self.empty_text.configure(text=format_text("empty_state", lang))
        self.update_pagination(self._current_page, self._total_pages)

        for i, header in enumerate(self.day_headers):
            header.configure(text=TRANSLATIONS["days"][lang][i % 7])
        for i, m_lbl in enumerate(self.month_labels):
            if i < len(self.active_month_indices):
                m_text = TRANSLATIONS["months"][lang][self.active_month_indices[i]]
                m_lbl.configure(text=f"\u200F{m_text}\u200F" if lang == "he" else m_text)
        for cell_frame in self.grid_cells.values():
            if cell_frame.winfo_children() and isinstance(cell_frame.winfo_children()[0], ctk.CTkLabel):
                cell_frame.winfo_children()[0].pack_configure(anchor="ne" if lang == "he" else "nw")

    def _handle_export(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")], title="Save")
        if file_path and self.on_export_clicked: self.on_export_clicked(file_path)

    def _handle_cell_click(self, cell_key):
        if self.selected_cell_key and self.selected_cell_key in self.grid_cells:
            self.grid_cells[self.selected_cell_key].configure(border_color=("gray70", "gray40"), border_width=1)
        self.selected_cell_key = cell_key
        if self.selected_cell_key in self.grid_cells:
            self.grid_cells[self.selected_cell_key].configure(border_color="#3b8ed0", border_width=2)
        if hasattr(self, 'monthly_view') and self.monthly_view:
            self.monthly_view.highlight_cell(cell_key)
        if self.on_date_selected: 
            self.on_date_selected(cell_key)