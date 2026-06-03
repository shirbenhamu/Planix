import customtkinter as ctk
import calendar
from datetime import datetime
from typing import Callable, Dict, List
from src.MVP.views.ui_utils import format_text, TRANSLATIONS
from src.MVP.views.components.exam_modal import show_exam_popup
from src.MVP.views.components.top_toolbar import TopToolbar

class MonthlyGridView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.current_lang = "he"
        self._current_page, self._total_pages = 1, 1
        
        self.f_header = ctk.CTkFont(family="Rubik", size=14, weight="bold")
        self.f_card = ctk.CTkFont(family="Rubik", size=10, weight="bold")
        self.f_empty = ctk.CTkFont(family="Rubik", size=18, weight="bold")

        self.on_hamburger_clicked = None 
        self.on_cell_clicked = None 
        
        self.day_headers = [] 
        self.grid_cells = {}  
        
        self.full_grid_data = {}
        self.active_months = []
        self.current_month_index = 0
        self.selected_original_key = None
        self.original_to_target_map = {}
        
        self.toolbar = TopToolbar(self, is_monthly=True)
        self.toolbar.pack(fill="x", pady=(5, 10), padx=10)
        
        self.toolbar.on_hamburger = lambda: self.on_hamburger_clicked() if self.on_hamburger_clicked else None
        self.toolbar.on_month_prev = self._prev_month
        self.toolbar.on_month_next = self._next_month
        self.toolbar.on_load_more = self._handle_load_more # חיבור הכפתור החדש

        self.grid_frame = ctk.CTkFrame(self)
        self._setup_empty_state()
        self.update_language(self.current_lang)

    def _handle_load_more(self):
        print("Monthly View: Load more requested - waiting for engine logic")

    def _setup_empty_state(self):
        self.empty_state_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(self.empty_state_frame, text="📅", font=("Arial", 60)).pack(pady=(50, 10))
        self.empty_text = ctk.CTkLabel(self.empty_state_frame, text="", font=self.f_empty, text_color="gray50")
        self.empty_text.pack()
        self.show_empty_state()

    def show_empty_state(self):
        self.grid_frame.pack_forget()
        self.empty_state_frame.pack(fill="both", expand=True)

    def hide_empty_state(self):
        self.empty_state_frame.pack_forget()
        self.grid_frame.pack(fill="both", expand=True, padx=15, pady=(5, 15))

    def init_grid(self):
        self.hide_empty_state()
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        self.day_headers.clear()
        self.grid_cells.clear()

        for i in range(7): self.grid_frame.grid_columnconfigure(i, weight=1, uniform="day")
        self.grid_frame.grid_rowconfigure(0, minsize=40)
        
        days = TRANSLATIONS["days"][self.current_lang]
        for i in range(7):
            lbl = ctk.CTkLabel(self.grid_frame, text=days[i], font=self.f_header, fg_color=("gray80", "gray30"), corner_radius=5)
            lbl.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
            self.day_headers.append(lbl)

        for row in range(1, 7):
            self.grid_frame.grid_rowconfigure(row, weight=1, uniform="week") 
            for col in range(7):
                cell_key = f"{row}-{col}"
                cell = ctk.CTkFrame(self.grid_frame, border_width=1, border_color=("gray70", "gray40"), fg_color=("gray80", "gray15"), corner_radius=5)
                cell.grid(row=row, column=col, sticky="nsew", padx=2, pady=2)
                self.grid_cells[cell_key] = cell

    def receive_data(self, grid_data: Dict[str, dict], active_months: List[int]):
        self.full_grid_data = grid_data
        self.active_months = active_months
        if self.current_month_index >= len(active_months) and active_months:
            self.current_month_index = 0
        self.render_current_month()

    def render_current_month(self):
        if not self.active_months:
            return self.show_empty_state()
            
        self.hide_empty_state()
        self.init_grid()
        
        target_month = self.active_months[self.current_month_index]
        month_name = TRANSLATIONS["months_full"][self.current_lang][target_month]
        self.toolbar.month_year_lbl.configure(text=f"{month_name}")
        
        current_year = datetime.now().year
        first_weekday, num_days = calendar.monthrange(current_year, target_month + 1)
        start_col = (first_weekday + 1) % 7
        row_idx_in_data = self.active_months.index(target_month) + 1
        
        current_row, current_col = 1, start_col
        self.original_to_target_map.clear()
        
        for day in range(1, num_days + 1):
            original_key = f"{row_idx_in_data}-{day - 1}"
            target_key = f"{current_row}-{current_col}"
            
            self.original_to_target_map[original_key] = target_key
            self.update_single_cell(target_key, self.full_grid_data.get(original_key, {}), str(day), original_key)
            
            current_col += 1
            if current_col > 6:
                current_col, current_row = 0, current_row + 1
                
        if self.selected_original_key in self.original_to_target_map:
            t_key = self.original_to_target_map[self.selected_original_key]
            self.grid_cells[t_key].configure(border_color="#3b8ed0", border_width=2)

    def _handle_cell_click(self, original_key):
        if self.on_cell_clicked: self.on_cell_clicked(original_key)

    def update_single_cell(self, target_key: str, data: dict, day_str: str, original_key: str):
        cell_frame = self.grid_cells.get(target_key)
        if not cell_frame: return
        
        for widget in cell_frame.winfo_children(): widget.destroy()
        
        cell_frame.configure(fg_color=("#ffcccc", "#4d0000") if data.get("is_excluded") else ("gray90", "gray20"))
        cell_frame.bind("<Button-1>", lambda e, k=original_key: self._handle_cell_click(k))
        
        anchor = "ne" if self.current_lang == "he" else "nw"
        day_lbl = ctk.CTkLabel(cell_frame, text=day_str, font=ctk.CTkFont(family="Rubik", size=12, weight="bold"), text_color=("gray50", "gray60"))
        day_lbl.pack(anchor=anchor, padx=5, pady=2)
        day_lbl.bind("<Button-1>", lambda e, k=original_key: self._handle_cell_click(k))
        
        exams_container = ctk.CTkScrollableFrame(cell_frame, fg_color="transparent", height=60)
        exams_container.pack(fill="both", expand=True)
        
        if hasattr(exams_container, "_parent_canvas"):
            exams_container._parent_canvas.bind("<Button-1>", lambda e, k=original_key: self._handle_cell_click(k))
        
        for exam in data.get("exams", []):
            card = ctk.CTkFrame(exams_container, fg_color="#3b8ed0" if exam.get("type") == "ח" else "#2fa572", corner_radius=4)
            card.pack(fill="x", expand=False, padx=2, pady=2)
            
            full_name = exam.get('short_name', '')
            display_name = full_name[:20] + ".." if len(full_name) > 20 else full_name
            c_type = format_text("type_hova", self.current_lang) if exam.get("type") == "ח" else format_text("type_bhira", self.current_lang)
            
            txt = f"{display_name}\n{exam.get('course_id', '')} | {c_type} | {format_text('program', self.current_lang)} {exam.get('program', '')}"
            lbl = ctk.CTkLabel(card, text=txt, font=self.f_card, text_color="white", justify="center")
            lbl.pack(padx=2, pady=2)
            
            for widget in [card, lbl]:
                widget.bind("<Button-1>", lambda e, ex=exam: show_exam_popup(self, ex, self.current_lang))
                widget.bind("<Button-3>", lambda e, k=original_key: self._handle_cell_click(k))

    def _prev_month(self):
        if self.current_month_index > 0:
            self.current_month_index -= 1
            self.render_current_month()

    def _next_month(self):
        if self.current_month_index < len(self.active_months) - 1:
            self.current_month_index += 1
            self.render_current_month()

    def update_pagination(self, current_page: int, total_pages: int):
        self._current_page, self._total_pages = current_page, total_pages
        self.toolbar.set_pagination(current_page, total_pages)

    def highlight_cell(self, original_key: str):
        self.selected_original_key = original_key
        for cell in self.grid_cells.values(): cell.configure(border_color=("gray70", "gray40"), border_width=1)
        if original_key in self.original_to_target_map:
            self.grid_cells[self.original_to_target_map[original_key]].configure(border_color="#3b8ed0", border_width=2)

    def toggle_cell_exclusion_visual(self, original_key: str, is_excluded: bool):
        if original_key in self.original_to_target_map:
            cell = self.grid_cells.get(self.original_to_target_map[original_key])
            if cell: cell.configure(fg_color=("#ffcccc", "#4d0000") if is_excluded else ("gray90", "gray20"))

    def update_language(self, lang: str):
        self.current_lang = lang
        self.toolbar.update_language(lang)
        self.empty_text.configure(text=format_text("empty_state", lang))
        self.update_pagination(self._current_page, self._total_pages)

        if self.day_headers:
            for i, header in enumerate(self.day_headers):
                header.configure(text=TRANSLATIONS["days"][lang][i])
        if self.active_months:
            self.render_current_month()