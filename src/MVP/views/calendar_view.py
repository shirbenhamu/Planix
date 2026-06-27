import customtkinter as ctk
import calendar
import os
import subprocess
import sys
from datetime import datetime
from tkinter import filedialog
from typing import Callable, Dict, List
from src.MVP.views.ui_utils import format_text, TRANSLATIONS
from src.MVP.views.components.exam_modal import show_exam_popup
from src.MVP.views.components.top_toolbar import TopToolbar
from src.MVP.views.components.date_edit_modal import show_date_edit_popup
from src.MVP.views.components.robot_mascot import RobotMascot
from src.MVP.views.components.ranking_bar import RankingBar
from src.MVP.views.components.info_modal import show_metrics_info_popup, show_metrics_values_popup
from src.MVP.views.components.export_choice_modal import show_export_choice_popup
from src.MVP.views.components.constraints_modal import (
    show_constraints_popup, default_constraints_data, normalize_constraints_data
)
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
        self.on_load_all_clicked = None
        self.on_refresh_feed_clicked = None
        self.on_save_constraints = None
        self._constraints_state = default_constraints_data()
        self._constraints_save_enabled = True
        self.day_headers, self.month_labels, self.grid_cells = [], [], {}  
        self.selected_cell_key = None 
        self.active_month_indices = []
        self._last_grid_data = {}  # cache for redrawing only changed cells (prevents flickering on live refresh)
        self._current_grid_data = {}  # store current grid data to support language switching with re-render
        self._cell_day_number = {}  # day number (1..31) for each valid cell, for calendar-like display
        
        # OBJECT POOLING: Store widget references for each cell to avoid destroy/recreate
        self._cell_widget_pools: Dict[str, dict] = {}  # cell_key -> {day_label, exams_container, exam_cards}
        
        # --- Toolbar ---
        self.toolbar = TopToolbar(self, is_monthly=False)
        self.toolbar.pack(fill="x", pady=(15, 15), padx=20)
        self.toolbar.on_load_more = lambda: self.on_load_more_clicked() if self.on_load_more_clicked else None
        self.toolbar.on_load_all = lambda: self._confirm_load_all()
        self.toolbar.on_refresh_feed = lambda: self.on_refresh_feed_clicked() if self.on_refresh_feed_clicked else None
        
        self.toolbar.on_hamburger = lambda: self.on_hamburger_clicked() if self.on_hamburger_clicked else None
        self.toolbar.on_next = lambda: self.on_next_clicked() if self.on_next_clicked else None
        self.toolbar.on_prev = lambda: self.on_prev_clicked() if self.on_prev_clicked else None
        self.toolbar.on_page_jump = lambda p: self.on_page_jump(p) if self.on_page_jump else None
        self.toolbar.on_export = self._handle_export
        self.toolbar.on_edit_dates = self._open_dates_modal
        self.toolbar.on_constraints_settings = self._open_constraints_modal
        self.toolbar.on_exclude = lambda: self.on_exclude_clicked(self.selected_cell_key) if self.selected_cell_key and self.on_exclude_clicked else None
        self.toolbar.on_filter = lambda: self.on_filter_clicked() if self.on_filter_clicked else None
        self.on_sync_clicked = None
        self.toolbar.on_sync_clicked = lambda: self._fire_sync()

        # Manual drag & drop (PLAN-554): callbacks set by the presenter, plus the
        # Undo button and the in-progress drag state.
        self.on_exam_dropped = None      # (course_id, src_cell_key, dst_cell_key)
        self.on_undo_clicked = None
        self.on_drag_validate = None     # (course_id, src, dst) -> bool, for live feedback
        self.toolbar.on_undo = lambda: self.on_undo_clicked() if self.on_undo_clicked else None
        self._drag = None

        # --- Ranking bar (PLAN-411..414): sort + live metrics ---
        self.on_sort_changed = None      # set by the presenter -> _handle_sort_changed
        self.ranking_bar = RankingBar(self, lang=self.current_lang)
        self.ranking_bar.pack(fill="x", padx=20, pady=(0, 10))
        self.ranking_bar.on_sort_changed = lambda keys, asc: (
            self.on_sort_changed(keys, asc) if self.on_sort_changed else None)
        self.ranking_bar.on_info = lambda: show_metrics_info_popup(self, self.current_lang)
        self.ranking_bar.on_metrics_details = lambda metrics: show_metrics_values_popup(
            self, self.current_lang, metrics
        )

        self.scrollable_container = ctk.CTkScrollableFrame(self, fg_color=theme.TRANSPARENT)
        self.grid_frame = ctk.CTkFrame(self.scrollable_container, fg_color=theme.TRANSPARENT)
        self.grid_frame.pack(fill="both", expand=False)
        
        self._setup_empty_state()
        self.update_language(self.current_lang)
    
    def update_metrics_display(self, metrics):
        """Shows the five section-3 metrics of the active schedule (PLAN-408),
        and bridges them to the monthly view so both stay in sync."""
        self.ranking_bar.update_metrics(metrics)
        if getattr(self, "monthly_view", None):
            self.monthly_view.update_metrics_display(metrics)

    def show_no_more_results(self):
        """End-of-results boundary indicator for the refresh-feed (PLAN-415)."""
        self.ranking_bar.show_no_more_results()
        if getattr(self, "monthly_view", None):
            self.monthly_view.show_no_more_results()

    # ===== Load All + remaining-to-load indicator ============================

    def _confirm_load_all(self):
        """Idle: warn, then start the deep search. Running: cancel immediately
        (no warning) — the same callback toggles start/cancel in the controller."""
        if getattr(self, "_deep_search_running", False):
            if self.on_load_all_clicked:
                self.on_load_all_clicked()
            return
        from src.MVP.views.components.confirm_modal import show_confirm_popup
        show_confirm_popup(
            self,
            title=format_text("load_all_title", self.current_lang),
            message=format_text("load_all_warning", self.current_lang),
            confirm_text=format_text("load_all_confirm", self.current_lang),
            cancel_text=format_text("cancel", self.current_lang),
            on_confirm=lambda: self.on_load_all_clicked() if self.on_load_all_clicked else None,
        )

    def set_load_all_running(self, running: bool):
        self._deep_search_running = running
        self.toolbar.set_load_all_running(running)
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "set_load_all_running"):
            self.monthly_view.set_load_all_running(running)

    def _rtl(self, text: str) -> str:
        return f"\u200F{text}\u200F" if self.current_lang == "he" else text

    def update_remaining_indicator(self, remaining: int, total: int, loaded: int, all_loaded: bool):
        """How many schedules remain in the warehouse -> shown on the Load More
        hover tooltip. The deep-search button stays enabled (it is the entry
        point AND the cancel toggle); only Load More is retired when everything
        is loaded."""
        self.toolbar.set_load_more_remaining(0 if all_loaded else remaining)
        if all_loaded:
            self.toolbar.set_remaining_text(self._rtl(format_text("all_loaded", self.current_lang)))
            self.toolbar.set_load_more_enabled(False)
        else:
            self.toolbar.set_remaining_text("")   # side meter only used during the search
            self.toolbar.set_load_more_enabled(True)
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "update_remaining_indicator"):
            self.monthly_view.update_remaining_indicator(remaining, total, loaded, all_loaded)

    def set_load_all_progress(self, percent: float):
        """Side percentage meter while the deep search scans (time-based)."""
        text = TRANSLATIONS["load_all_progress"][self.current_lang].format(p=f"{percent:.2f}")
        self.toolbar.set_remaining_text(self._rtl(text))
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "set_load_all_progress"):
            self.monthly_view.set_load_all_progress(percent)

    def set_load_all_saving(self):
        """Shown after the scan budget is reached while the best-N are written."""
        self.toolbar.set_remaining_text(self._rtl(format_text("load_all_saving", self.current_lang)))
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "set_load_all_saving"):
            self.monthly_view.set_load_all_saving()

    def set_deep_search_done(self, scanned: int, kept: int):
        """Final summary: how many were scanned for the kept best-N."""
        text = TRANSLATIONS["deep_search_done"][self.current_lang].format(
            scanned=f"{scanned:,}", kept=f"{kept:,}")
        self.toolbar.set_remaining_text(self._rtl(text))
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "set_deep_search_done"):
            self.monthly_view.set_deep_search_done(scanned, kept)

    def set_load_more_enabled(self, enabled: bool):
        self.toolbar.set_load_more_enabled(enabled)
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "set_load_more_enabled"):
            self.monthly_view.set_load_more_enabled(enabled)

    def set_load_all_enabled(self, enabled: bool):
        self.toolbar.set_load_all_enabled(enabled)
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "set_load_all_enabled"):
            self.monthly_view.set_load_all_enabled(enabled)

    def set_load_more_calculating(self):
        self.toolbar.set_load_more_calculating()
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "set_load_more_calculating"):
            self.monthly_view.set_load_more_calculating()

    def clear_load_indicators(self):
        """Wipe the side meter and reset the Load More tooltip immediately (e.g.
        a new run replaces a prior deep-search result, so 'best 100K…' and the
        stale remaining number must go at once, not after the next count)."""
        self.toolbar.set_remaining_text("")
        self.toolbar.set_load_more_remaining(None)
        if getattr(self, "monthly_view", None) and hasattr(self.monthly_view, "clear_load_indicators"):
            self.monthly_view.clear_load_indicators()

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
        root = self.winfo_toplevel()
        if hasattr(root, "show_toast"):
            root.show_toast(format_text("constraints_saved", self.current_lang))

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
                "holiday_label": None,  
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

        # Handle holiday name label (show only if excluded + has holiday_name)
        holiday_name = cell_data.get("holiday_name")
        if cell_data.get("is_excluded") and holiday_name:
            if pool["holiday_label"] is None:
                # Create holiday label with translation + proper wrapping for annual view
                trans_key = f"holiday_{holiday_name}"
                display_name = holiday_name
                if trans_key in TRANSLATIONS:
                    display_name = TRANSLATIONS[trans_key].get(self.current_lang, holiday_name)
                
                # Split multi-word names across lines (e.g., "Rosh Hashanah" -> "Rosh\nHashanah")
                display_name = "\n".join(display_name.split())
                
                holiday_lbl = ctk.CTkLabel(
                    cell_frame,
                    text=display_name,
                    font=("Arial", 7),  # Smaller font for annual view
                    text_color="#d32f2f",
                    wraplength=100,  # Large wraplength for annual view cells
                    justify="center"  # Center alignment for multi-word holidays like "Independence Day"
                )
                holiday_lbl.pack(anchor="n", padx=4, pady=0, fill="x")
                holiday_lbl.bind("<Button-1>", lambda e, k=cell_key: self._handle_cell_click(k))
                pool["holiday_label"] = holiday_lbl
            else:
                # Update existing holiday label
                trans_key = f"holiday_{holiday_name}"
                display_name = holiday_name
                if trans_key in TRANSLATIONS:
                    display_name = TRANSLATIONS[trans_key].get(self.current_lang, holiday_name)
                
                # Split multi-word names across lines
                display_name = "\n".join(display_name.split())
                
                if pool["holiday_label"].cget("text") != display_name:
                    pool["holiday_label"].configure(text=display_name, justify="right" if self.current_lang == "he" else "center")
                # Ensure it's visible
                try:
                    pool["holiday_label"].pack(anchor="ne" if self.current_lang == "he" else "nw", padx=4, pady=0, fill="x")
                except:
                    pass
        else:
            # Hide holiday label if no holiday or not excluded
            if pool["holiday_label"] is not None:
                try:
                    pool["holiday_label"].pack_forget()
                except:
                    pass

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
            # Update or create exam cards
            for i, exam in enumerate(exams):
                # Color by course type: Mandatory (ח) = Blue, Elective (ב) = Green
                if exam.get("type") == "ח":
                    pill_color = ("#0d6efd", "#0077b6")  # Blue for Mandatory
                else:
                    pill_color = ("#20c997", "#128260")  # Green for Elective
                
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

                    lbl = ctk.CTkLabel(card, text=f"{exam.get('course_id', '')}", font=self.f_card, text_color="white", justify="center")
                    lbl.pack(padx=2, pady=2)

                    # Drag & drop bindings (PLAN-560). Bound once; handlers read the
                    # live (course_id, cell_key) stored on the card below, so pooled
                    # reuse never carries a stale exam.
                    for widget in (card, lbl):
                        self._bind_drag_handlers(widget, card)
                        # A "move" cursor on hover signals the card is draggable.
                        try:
                            widget.configure(cursor="hand2")
                        except Exception:
                            pass

                    pool["exam_cards"].append(card)

                # Stash the current drag identity on the card (create AND reuse path).
                card._drag_course_id = exam.get("course_id", "")
                card._drag_exam = exam
                card._drag_cell_key = cell_key
            
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
            self._current_grid_data = {}
            if hasattr(self, 'monthly_view') and self.monthly_view: self.monthly_view.show_empty_state()
            return
        self.hide_empty_state()
        
        # Store current grid data for language switching
        self._current_grid_data = grid_data

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

    def _relocalize_open_ranking_popups(self, lang: str):
        """Rebuild any open info / metrics-values popup in the new language so it
        switches live while the user is looking at it."""
        if getattr(self, "info_box", None) is not None and self.info_box.winfo_exists():
            show_metrics_info_popup(self, lang)
        if getattr(self, "metrics_values_box", None) is not None and self.metrics_values_box.winfo_exists():
            show_metrics_values_popup(self, lang, getattr(self.ranking_bar, "_last_metrics", None))

    def update_language(self, lang: str):
        self.current_lang = lang
        self.toolbar.update_language(lang)
        if hasattr(self, "ranking_bar"):
            self.ranking_bar.set_language(lang)
        self._relocalize_open_ranking_popups(lang)
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

        # Re-render all cells to update holiday names with new language (fixes PLAN-629)
        if self._current_grid_data:
            self._last_grid_data = {}
            self.render_calendar_data(self._current_grid_data)

        if hasattr(self, "popup_box") and self.popup_box.winfo_exists() and hasattr(self, "_last_exam_data"):
            show_exam_popup(self, self._last_exam_data, lang)

    def _handle_export(self):
        """Open the PLAN-556 two-option export flow."""
        show_export_choice_popup(
            parent=self,
            current_lang=self.current_lang,
            on_choice_callback=self._handle_export_choice,
        )

    def _handle_export_choice(self, choice: str):
        normalized_choice = (choice or "").strip().lower()

        if normalized_choice == "text":
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title=format_text("export_text_dialog_title", self.current_lang),
            )
            if file_path and self.on_export_clicked:
                # Preserve the legacy one-argument text export callback contract.
                self.on_export_clicked(file_path)
            return

        if normalized_choice == "calendar":
            file_path = filedialog.asksaveasfilename(
                defaultextension=".ics",
                filetypes=[("iCalendar files", "*.ics"), ("All files", "*.*")],
                title=format_text("export_calendar_dialog_title", self.current_lang),
            )
            if not file_path or not self.on_export_clicked:
                return
            exported_path = self.on_export_clicked(file_path, "ics", True)
            if exported_path:
                self._open_local_calendar_file(exported_path)

    def _open_local_calendar_file(self, file_path: str) -> None:
        """Open the exported .ics through the operating system's default app."""
        try:
            if sys.platform.startswith("win"):
                os.startfile(file_path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as ex:
            print(f"[CalendarGridView] Could not open local calendar file: {ex}")

    # ===== Manual drag & drop of exam cards (PLAN-560/561/563) ===============

    _DRAG_THRESHOLD_PX = 6  # movement beyond this turns a click into a drag

    def set_undo_enabled(self, enabled: bool):
        if hasattr(self, "toolbar"):
            self.toolbar.set_undo_enabled(enabled)
        monthly = getattr(self, "monthly_view", None)
        if monthly is not None and hasattr(monthly, "toolbar"):
            monthly.toolbar.set_undo_enabled(enabled)

    def _bind_drag_handlers(self, widget, card):
        widget.bind("<ButtonPress-1>", lambda e, c=card: self._on_drag_press(e, c))
        widget.bind("<B1-Motion>", self._on_drag_motion)
        widget.bind("<ButtonRelease-1>", self._on_drag_release)

    def _on_drag_press(self, event, card):
        self._drag = {
            "card": card,
            "course_id": getattr(card, "_drag_course_id", ""),
            "exam": getattr(card, "_drag_exam", {}),
            "src_cell": getattr(card, "_drag_cell_key", None),
            "x0": event.x_root,
            "y0": event.y_root,
            "moved": False,
            "highlight": None,
        }

    def _on_drag_motion(self, event):
        if not self._drag:
            return
        if not self._drag["moved"]:
            dx = abs(event.x_root - self._drag["x0"])
            dy = abs(event.y_root - self._drag["y0"])
            if dx + dy <= self._DRAG_THRESHOLD_PX:
                return
            self._drag["moved"] = True
            try:
                self.configure(cursor="fleur")
            except Exception:
                pass
        # Live feedback: green target if the drop is valid, red if not.
        target = self._cell_key_at(event.x_root, event.y_root)
        valid = bool(
            target and target != self._drag["src_cell"] and self.on_drag_validate
            and self.on_drag_validate(self._drag["course_id"], self._drag["src_cell"], target)
        )
        self._highlight_drop_target(target, valid)

    def _on_drag_release(self, event):
        drag = self._drag
        self._drag = None
        if not drag:
            return
        try:
            self.configure(cursor="")
        except Exception:
            pass
        self._highlight_drop_target(None)

        if not drag["moved"]:
            # A plain click — keep the existing behavior: show the exam details.
            if drag["exam"]:
                show_exam_popup(self, drag["exam"], self.current_lang)
            return

        target_cell = self._cell_key_at(event.x_root, event.y_root)
        src_cell = drag["src_cell"]
        if target_cell and src_cell and target_cell != src_cell and self.on_exam_dropped:
            self.on_exam_dropped(drag["course_id"], src_cell, target_cell)
        # else: dropped on nothing / same cell -> presenter not called; the card
        # stays where it is (snap back is implicit, no error shown).

    def _highlight_drop_target(self, cell_key, valid=False):
        prev = self._drag.get("highlight") if self._drag else None
        prev_valid = self._drag.get("highlight_valid") if self._drag else None
        if prev == cell_key and prev_valid == valid:
            return  # nothing changed; avoid needless reconfigure/flicker
        if prev and prev in self.grid_cells and prev != self.selected_cell_key:
            self.grid_cells[prev].configure(border_color=theme.BORDER_DEFAULT, border_width=1)
        new_highlight = None
        if cell_key and cell_key in self.grid_cells and self._cell_day_number.get(cell_key) is not None:
            color = theme.SUCCESS if valid else theme.DANGER
            self.grid_cells[cell_key].configure(border_color=color, border_width=2)
            new_highlight = cell_key
        if self._drag:
            self._drag["highlight"] = new_highlight
            self._drag["highlight_valid"] = valid

    def _cell_key_at(self, x_root, y_root):
        """Return the grid cell_key under the given screen coordinates (or None).
        Matches by widget path so it works through CTk's nested frames."""
        target = self.winfo_containing(x_root, y_root)
        if target is None:
            return None
        target_path = str(target)
        for cell_key, cell in self.grid_cells.items():
            cell_path = str(cell)
            if target_path == cell_path or target_path.startswith(cell_path + "."):
                return cell_key
        return None

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