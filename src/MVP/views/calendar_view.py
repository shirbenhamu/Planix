import customtkinter as ctk
import calendar
from datetime import datetime
from tkinter import filedialog
from typing import Callable, Dict, List
from src.MVP.views.ui_utils import format_text, TRANSLATIONS
from src.MVP.views.components.exam_modal import show_exam_popup
from src.MVP.views.components.top_toolbar import TopToolbar
from src.MVP.views.components.date_edit_modal import show_date_edit_popup
from src.MVP.views.components.robot_mascot import RobotMascot
from src.MVP.views import theme

class CalendarGridView(ctk.CTkFrame):
    CELL_HEIGHT = 110 

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BG_MAIN, **kwargs)
        self.current_lang = "he"
        self._current_page, self._total_pages = 1, 1
        
        # Define fonts for different text elements
        self.f_header = ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold")
        self.f_card = ctk.CTkFont(family=theme.FONT_FAMILY, size=10, weight="bold")
        self.f_empty = ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold")

        self.on_hamburger_clicked = None 
        self.on_next_clicked, self.on_prev_clicked = None, None
        self.on_page_jump, self.on_range_update_clicked = None, None 
        self.on_export_clicked, self.on_exclude_clicked = None, None 
        self.on_date_selected, self.on_filter_clicked = None, None 
        self.get_exam_periods_callback = None
        self.on_load_more_clicked = None
        self.day_headers, self.month_labels, self.grid_cells = [], [], {}  
        self.selected_cell_key = None 
        self.active_month_indices = []
        self._last_grid_data = {}  # cache for redrawing only changed cells (prevents flickering on live refresh)
        self._cell_day_number = {}  # day number (1..31) for each valid cell, for calendar-like display
        
        # OBJECT POOLING: Store widget references for each cell to avoid destroy/recreate
        self._cell_widget_pools: Dict[str, dict] = {}  # cell_key -> {day_label, exams_container, exam_cards}
        
        # --- Toolbar ---
        self.toolbar = TopToolbar(self, is_monthly=False)
        self.toolbar.pack(fill="x", pady=(15, 15), padx=20)
        self.toolbar.on_load_more = lambda: self.on_load_more_clicked() if self.on_load_more_clicked else None
        
        self.toolbar.on_hamburger = lambda: self.on_hamburger_clicked() if self.on_hamburger_clicked else None
        self.toolbar.on_next = lambda: self.on_next_clicked() if self.on_next_clicked else None
        self.toolbar.on_prev = lambda: self.on_prev_clicked() if self.on_prev_clicked else None
        self.toolbar.on_page_jump = lambda p: self.on_page_jump(p) if self.on_page_jump else None
        self.toolbar.on_export = self._handle_export
        self.toolbar.on_edit_dates = self._open_dates_modal
        self.toolbar.on_exclude = lambda: self.on_exclude_clicked(self.selected_cell_key) if self.selected_cell_key and self.on_exclude_clicked else None
        self.toolbar.on_filter = lambda: self.on_filter_clicked() if self.on_filter_clicked else None
        self.on_sync_clicked = None
        self.toolbar.on_sync_clicked = lambda: self._fire_sync()

        self.scrollable_container = ctk.CTkScrollableFrame(self, fg_color=theme.TRANSPARENT)
        self.grid_frame = ctk.CTkFrame(self.scrollable_container, fg_color=theme.TRANSPARENT)
        self.grid_frame.pack(fill="both", expand=False)
        
        self._setup_empty_state()
        self.update_language(self.current_lang)
    
    def _handle_load_more(self):
        print("Annual View: Load more requested")

    def _open_dates_modal(self):
        periods_data = []

        if callable(self.get_exam_periods_callback):
            try:
                callback_result = self.get_exam_periods_callback()
                periods_data = callback_result or []
                print(
                    f"[CalendarGridView] _open_dates_modal callback type={type(callback_result).__name__}, count={len(periods_data)}"
                )
            except Exception as ex:
                print(f"[CalendarGridView] Failed to fetch exam periods from callback: {ex}")
                periods_data = []
        else:
            print("[CalendarGridView] get_exam_periods_callback is not callable.")

        # Callback to handle saving updated date pairs from the modal
        def on_save(date_pairs):

            if self.on_range_update_clicked:
                print(f"[CalendarGridView] Saving date pairs: {date_pairs}")
                self.on_range_update_clicked(date_pairs)
            else:
                print("[CalendarGridView] on_range_update_clicked is not set")
        
        show_date_edit_popup(
            parent=self,
            current_lang=self.current_lang,
            exam_periods_data=periods_data,
            on_save_callback=on_save
        )
    
    def set_monthly_view(self, monthly_view):
        self.monthly_view = monthly_view

    def _setup_empty_state(self):
        self.empty_state_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.empty_robot = RobotMascot(self.empty_state_frame, speech=format_text("empty_state", self.current_lang))
        self.empty_robot.pack(expand=True)
        self.show_empty_state()

    def show_empty_state(self):
        self.scrollable_container.pack_forget()
        self.empty_state_frame.pack(fill="both", expand=True)

    def hide_empty_state(self):
        self.empty_state_frame.pack_forget()
        self.scrollable_container.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _get_semester_color(self, month_idx: int):
        # Simple heuristic: assume months 9-2 are in the "winter" semester (green), 3-6 in "summer" (accent), and 7-8 are "off-season" (orange)
        if month_idx in [9, 10, 11, 0, 1]: return theme.SUCCESS  
        elif month_idx in [2, 3, 4, 5]: return theme.TEXT_ACCENT 
        else: return ("#e67e22", "#f39c12") 

    def init_grid(self, month_indices: List[int]):
        if not month_indices:
            return self.show_empty_state()
        self.hide_empty_state()
        self.active_month_indices = month_indices
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        self.day_headers.clear()
        self.month_labels.clear()
        self.grid_cells.clear()
        self._last_grid_data = {}  
        self._cell_day_number = {}
        self._cell_widget_pools.clear()  # Clear widget pool when reinitializing grid

        for i in range(31): self.grid_frame.grid_columnconfigure(i, weight=1, uniform="day_column")
        self.grid_frame.grid_columnconfigure(31, weight=0, minsize=50)
        self.grid_frame.grid_rowconfigure(0, minsize=30)
        
        days = TRANSLATIONS["days"][self.current_lang]
        for i in range(31):
            # header labels for days of the week (repeating every 7 columns)
            lbl = ctk.CTkLabel(self.grid_frame, text=days[i % 7], font=self.f_header, fg_color="transparent", text_color=theme.TEXT_MUTED)
            lbl.grid(row=0, column=i, sticky="nsew", padx=1, pady=1)
            self.day_headers.append(lbl)

        year = datetime.now().year
        for row_idx, month_idx in enumerate(month_indices, start=1):
            self.grid_frame.grid_rowconfigure(row_idx, weight=0, minsize=self.CELL_HEIGHT) 
            num_days = calendar.monthrange(year, month_idx + 1)[1]
            for col in range(31):
                cell_key = f"{row_idx}-{col}"
                # create block for each cell and store reference in grid_cells for later updates
                cell = ctk.CTkFrame(self.grid_frame, border_width=1, border_color=theme.BORDER_DEFAULT, fg_color=theme.BG_CARD, corner_radius=0, height=self.CELL_HEIGHT)
                cell.grid(row=row_idx, column=col, sticky="nsew", padx=0, pady=0)
                cell.pack_propagate(False)  
                self.grid_cells[cell_key] = cell
                cell.bind("<Button-1>", lambda e, k=cell_key: self._handle_cell_click(k))
                
                if col < num_days:  # only assign day numbers to valid cells within the month
                    self._cell_day_number[cell_key] = col + 1
                else:
                    # illigible cells at month end - keep them transparent and non-interactive
                    cell.configure(fg_color=theme.BG_MAIN, border_width=0)
                
            m_text = TRANSLATIONS["months"][self.current_lang][month_idx]
            m_lbl = ctk.CTkLabel(self.grid_frame, text=f"\u200F{m_text}\u200F" if self.current_lang == "he" else m_text, font=self.f_header, text_color=self._get_semester_color(month_idx))
            m_lbl.grid(row=row_idx, column=31, sticky="nsew", padx=8)
            self.month_labels.append(m_lbl)
            
        self.grid_frame.grid_rowconfigure(len(month_indices) + 1, weight=1)


    def update_single_cell(self, cell_key: str, cell_data: dict):
        """
        Update a single cell efficiently using object pooling with pack_forget().
        Reuses existing widgets instead of destroying and recreating them.
        All widgets are kept in memory and shown/hidden using pack_forget().
        """
        cell_frame = self.grid_cells.get(cell_key)
        if not cell_frame:
            return

        day_num = self._cell_day_number.get(cell_key)
        
        # if the cell has no valid day number (e.g. 31st in February), keep it transparent and skip all updates
        if day_num is None:
            cell_frame.configure(fg_color=theme.BG_MAIN, border_width=0)
            return

        # Initialize widget pool for this cell if it doesn't exist
        if cell_key not in self._cell_widget_pools:
            self._cell_widget_pools[cell_key] = {
                "day_label": None,
                "exams_container": None,
                "exam_cards": []
            }

        pool = self._cell_widget_pools[cell_key]

        # Update cell frame properties
        cell_frame.configure(border_width=1, border_color=theme.BORDER_DEFAULT)
        if cell_data.get("is_excluded"):
            cell_frame.configure(fg_color=("#ffe6e6", "#4a1c1c"))
        else:
            cell_frame.configure(fg_color=theme.BG_CARD)

        # Handle day label (create if missing, update if exists)
        if pool["day_label"] is None:
            anchor = "ne" if self.current_lang == "he" else "nw"
            day_lbl = ctk.CTkLabel(cell_frame, text=str(day_num), font=self.f_card, text_color=theme.TEXT_MAIN)
            day_lbl.pack(anchor=anchor, padx=4, pady=2)
            day_lbl.bind("<Button-1>", lambda e, k=cell_key: self._handle_cell_click(k))
            pool["day_label"] = day_lbl
        else:
            # Just update text if it changed
            if pool["day_label"].cget("text") != str(day_num):
                pool["day_label"].configure(text=str(day_num))

        # Handle exams container - use pack_forget/pack instead of destroy
        exams = cell_data.get("exams", [])
        
        if exams:
            # Create exams container if it doesn't exist
            if pool["exams_container"] is None:
                exams_container = ctk.CTkScrollableFrame(cell_frame, fg_color="transparent")
                exams_container.pack(fill="both", expand=True, padx=2, pady=(0, 2))
                
                if hasattr(exams_container, "_parent_canvas"):
                    exams_container._parent_canvas.bind("<Button-1>", lambda e, k=cell_key: self._handle_cell_click(k))
                
                pool["exams_container"] = exams_container
            else:
                # Container exists, show it if it was hidden
                exams_container = pool["exams_container"]
                try:
                    exams_container.pack(fill="both", expand=True, padx=2, pady=(0, 2))
                except:
                    pass
        else:
            # No exams, hide the container using pack_forget (keep it in memory)
            if pool["exams_container"] is not None:
                pool["exams_container"].pack_forget()
            exams_container = None

        # Update exam cards in the pool (only if we have an exams container)
        if exams_container:
            elegant_colors = [
                ("#0d6efd", "#0077b6"), # blue
                ("#20c997", "#128260"), # green-magenta
                ("#f39c12", "#d68910"), # orange
                ("#e83e8c", "#b8306f"), # pink
                ("#8e44ad", "#6c3483")  # purple
            ]

            # Update or create exam cards
            for i, exam in enumerate(exams):
                pill_color = elegant_colors[i % len(elegant_colors)]
                
                if i < len(pool["exam_cards"]):
                    # Card exists, update it and show it
                    card = pool["exam_cards"][i]
                    card.configure(fg_color=pill_color)
                    # Update label text
                    label = None
                    for child in card.winfo_children():
                        if isinstance(child, ctk.CTkLabel):
                            label = child
                            break
                    if label and label.cget("text") != exam.get('course_id', ''):
                        label.configure(text=exam.get('course_id', ''))
                    # Ensure card is visible
                    card.pack(fill="x", expand=False, padx=1, pady=2)
                else:
                    # Create new card
                    card = ctk.CTkFrame(exams_container, fg_color=pill_color, corner_radius=10)
                    card.pack(fill="x", expand=False, padx=1, pady=2)
                    card.bind("<Button-1>", lambda e, ex=exam: show_exam_popup(self, ex, self.current_lang))

                    lbl = ctk.CTkLabel(card, text=f"{exam.get('course_id', '')}", font=self.f_card, text_color="white", justify="center")
                    lbl.pack(padx=2, pady=2)
                    lbl.bind("<Button-1>", lambda e, ex=exam: show_exam_popup(self, ex, self.current_lang))

                    pool["exam_cards"].append(card)
            
            # Hide excess cards using pack_forget (keep them in memory for reuse)
            for i in range(len(exams), len(pool["exam_cards"])):
                pool["exam_cards"][i].pack_forget()

        # Update selection border - always apply regardless of data change
        if self.selected_cell_key == cell_key:
            cell_frame.configure(border_color=theme.BORDER_ACTIVE, border_width=2)
        else:
            cell_frame.configure(border_color=theme.BORDER_DEFAULT, border_width=1)

    def render_calendar_data(self, grid_data: Dict[str, dict]):
        if not grid_data:
            self.show_empty_state()
            self._last_grid_data = {}
            if hasattr(self, 'monthly_view') and self.monthly_view: self.monthly_view.show_empty_state()
            return
        self.hide_empty_state()

        # only update cells that have actually changed to prevent flickering and improve performance
        changed = False
        for cell_key in self.grid_cells.keys():
            new_data = grid_data.get(cell_key, {})
            # STRICT DIRTY CHECKING: Only update if data actually changed
            old_data = self._last_grid_data.get(cell_key, {})
            if new_data == old_data:
                continue
            self.update_single_cell(cell_key, new_data)
            self._last_grid_data[cell_key] = new_data
            changed = True

        if changed and hasattr(self, 'monthly_view') and self.monthly_view:
            try:
                self.monthly_view.receive_data(grid_data, self.active_month_indices)
            except Exception as e:
                print(f"Monthly View Sync Error: {e}")

    def toggle_cell_exclusion_visual(self, cell_key: str, is_excluded: bool):
        cell_frame = self.grid_cells.get(cell_key)
        if cell_frame and self._cell_day_number.get(cell_key) is not None:
            cell_frame.configure(fg_color=("#ffcccc", "#4a1c1c") if is_excluded else theme.BG_CARD)
            self._last_grid_data.pop(cell_key, None)  
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
        if hasattr(self, "empty_robot"):
            self.empty_robot.set_speech(format_text("empty_state", lang))
        self.update_pagination(self._current_page, self._total_pages)

        if self.day_headers:
            for i, header in enumerate(self.day_headers):
                header.configure(text=TRANSLATIONS["days"][lang][i % 7])
        if self.month_labels:
            for i, m_lbl in enumerate(self.month_labels):
                if i < len(self.active_month_indices):
                    m_text = TRANSLATIONS["months"][lang][self.active_month_indices[i]]
                    m_lbl.configure(text=f"\u200F{m_text}\u200F" if lang == "he" else m_text)
        for cell_key, cell_frame in self.grid_cells.items():
            # only update anchor for valid day cells that have a day number (skip empty cells at month ends)
            if self._cell_day_number.get(cell_key) is not None and cell_frame.winfo_children() and isinstance(cell_frame.winfo_children()[0], ctk.CTkLabel):
                cell_frame.winfo_children()[0].pack_configure(anchor="ne" if lang == "he" else "nw")

        if hasattr(self, "popup_box") and self.popup_box.winfo_exists() and hasattr(self, "_last_exam_data"):
            show_exam_popup(self, self._last_exam_data, lang)

    def _handle_export(self):
        file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")], title="Save")
        if file_path and self.on_export_clicked: self.on_export_clicked(file_path)

    def _handle_cell_click(self, cell_key):
        if self._cell_day_number.get(cell_key) is None:
            return

        if self.selected_cell_key and self.selected_cell_key in self.grid_cells:
            self.grid_cells[self.selected_cell_key].configure(border_color=theme.BORDER_DEFAULT, border_width=1)
        
        self.selected_cell_key = cell_key
        if self.selected_cell_key in self.grid_cells:
            self.grid_cells[self.selected_cell_key].configure(border_color=theme.BORDER_ACTIVE, border_width=2)
            
        if hasattr(self, 'monthly_view') and self.monthly_view:
            self.monthly_view.highlight_cell(cell_key)
        if self.on_date_selected: 
            self.on_date_selected(cell_key)

    def _fire_sync(self):
        print(f"[DEBUG] _fire_sync called. on_sync_clicked={self.on_sync_clicked}")
        if self.on_sync_clicked:
            self.on_sync_clicked()
        else:
            print("[DEBUG] on_sync_clicked is None — binding never set!")