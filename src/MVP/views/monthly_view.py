import customtkinter as ctk
import calendar
from datetime import datetime
from typing import Callable, Dict, List
from src.MVP.views.ui_utils import format_text, TRANSLATIONS
from src.MVP.views.components.exam_modal import show_exam_popup
from src.MVP.views.components.top_toolbar import TopToolbar
from src.MVP.views.components.date_edit_modal import show_date_edit_popup
from src.MVP.views.components.robot_mascot import RobotMascot
from src.MVP.views.components.ranking_bar import RankingBar
from src.MVP.views.components.info_modal import show_metrics_info_popup, show_metrics_values_popup
from src.MVP.views.components.constraints_modal import (
    show_constraints_popup, default_constraints_data, normalize_constraints_data
)
from src.MVP.views import theme

class MonthlyGridView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=theme.BG_MAIN, **kwargs)
        self.current_lang = "he"
        self._current_page, self._total_pages = 1, 1
        
        self.f_header = ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold")
        self.f_card = ctk.CTkFont(family=theme.FONT_FAMILY, size=11, weight="bold")
        self.f_empty = ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold")
        self.f_day = ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold")

        self.on_hamburger_clicked = None 
        self.on_cell_clicked = None 
        self.on_range_update_clicked = None
        self.get_exam_periods_callback = None 
        self.on_load_more_clicked = None
        self.on_save_constraints = None
        self._constraints_state = default_constraints_data()
        self._constraints_save_enabled = True
        
        self.day_headers = [] 
        self.grid_cells = {}  
        
        self.full_grid_data = {}
        self.active_months = []
        self.current_month_index = 0
        self.selected_original_key = None
        self.original_to_target_map = {}

        self._grid_built = False
        self._last_cell_content = {}
        
        self.toolbar = TopToolbar(self, is_monthly=True)
        self.toolbar.pack(fill="x", pady=(15, 15), padx=20)
        self.toolbar.on_load_more = lambda: self.on_load_more_clicked() if self.on_load_more_clicked else None
        self.toolbar.on_hamburger = lambda: self.on_hamburger_clicked() if self.on_hamburger_clicked else None
        self.toolbar.on_month_prev = self._prev_month
        self.toolbar.on_month_next = self._next_month
        self.toolbar.on_edit_dates = self._open_dates_modal
        self.toolbar.on_constraints_settings = self._open_constraints_modal

        # --- Ranking bar (PLAN-411..414): same sort + metrics as annual ---
        self.on_sort_changed = None      # wired (via app_window) to the presenter
        self.ranking_bar = RankingBar(self, lang=self.current_lang)
        self.ranking_bar.pack(fill="x", padx=20, pady=(0, 10))
        self.ranking_bar.on_sort_changed = lambda keys, asc: (
            self.on_sort_changed(keys, asc) if self.on_sort_changed else None)
        self.ranking_bar.on_info = lambda: show_metrics_info_popup(self, self.current_lang)
        self.ranking_bar.on_metrics_details = lambda metrics: show_metrics_values_popup(
            self, self.current_lang, metrics
        )

        self.grid_frame = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self._setup_empty_state()
        self.update_language(self.current_lang)

    def _handle_load_more(self):
        print("Monthly View: Load more requested - waiting for engine logic")

    def _open_dates_modal(self):
        periods_data = self.get_exam_periods_callback() if self.get_exam_periods_callback else None
        
        # Callback to handle saving updated date pairs from the modal
        def on_save(date_pairs):
            if self.on_range_update_clicked:
                print(f"[MonthlyView] Saving date pairs: {date_pairs}")
                self.on_range_update_clicked(date_pairs)
            else:
                print("[MonthlyView] on_range_update_clicked is not set")
        
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

    def _setup_empty_state(self):
        self.empty_state_frame = ctk.CTkFrame(self, fg_color="transparent")
        # The app's robot with a speech bubble showing the "Please load data" message
        self.empty_robot = RobotMascot(self.empty_state_frame, speech=format_text("empty_state", self.current_lang))
        self.empty_robot.pack(expand=True)
        self.show_empty_state()

    def show_empty_state(self):
        self.grid_frame.pack_forget()
        self.empty_state_frame.pack(fill="both", expand=True)

    def hide_empty_state(self):
        self.empty_state_frame.pack_forget()
        self.grid_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def init_grid(self):
        self.hide_empty_state()
        for widget in self.grid_frame.winfo_children(): widget.destroy()
        self.day_headers.clear()
        self.grid_cells.clear()
        self._last_cell_content = {}

        for i in range(7): self.grid_frame.grid_columnconfigure(i, weight=1, uniform="day")
        self.grid_frame.grid_rowconfigure(0, minsize=30)
        
        days = TRANSLATIONS["days"][self.current_lang]
        for i in range(7):
            # Transparent, floating day headers with a subtle text color
            lbl = ctk.CTkLabel(self.grid_frame, text=days[i], font=self.f_header, fg_color="transparent", text_color=theme.TEXT_MUTED)
            lbl.grid(row=0, column=i, sticky="nsew", padx=2, pady=2)
            self.day_headers.append(lbl)

        for row in range(1, 7):
            self.grid_frame.grid_rowconfigure(row, weight=1, uniform="week") 
            for col in range(7):
                cell_key = f"{row}-{col}"
                # Cells with sharp corners (Seamless Grid) and subtle borders
                cell = ctk.CTkFrame(self.grid_frame, border_width=1, border_color=theme.BORDER_DEFAULT, fg_color=theme.BG_CARD, corner_radius=0)
                cell.grid(row=row, column=col, sticky="nsew", padx=0, pady=0)
                self.grid_cells[cell_key] = cell

    def _ensure_grid(self):
        if not self._grid_built:
            self.init_grid()
            self._grid_built = True

    def receive_data(self, grid_data: Dict[str, dict], active_months: List[int]):
        if grid_data == self.full_grid_data and active_months == self.active_months:
            return
        self.full_grid_data = grid_data
        self.active_months = active_months
        if self.current_month_index >= len(active_months) and active_months:
            self.current_month_index = 0
        self.render_current_month()

    def render_current_month(self):
        if not self.active_months:
            return self.show_empty_state()

        self.hide_empty_state()
        self._ensure_grid()

        target_month = self.active_months[self.current_month_index]
        month_name = TRANSLATIONS["months_full"][self.current_lang][target_month]
        self.toolbar.month_year_lbl.configure(text=f"{month_name}")

        current_year = datetime.now().year
        first_weekday, num_days = calendar.monthrange(current_year, target_month + 1)
        start_col = (first_weekday + 1) % 7
        row_idx_in_data = self.active_months.index(target_month) + 1

        targets = {key: None for key in self.grid_cells}
        self.original_to_target_map.clear()
        current_row, current_col = 1, start_col
        for day in range(1, num_days + 1):
            original_key = f"{row_idx_in_data}-{day - 1}"
            target_key = f"{current_row}-{current_col}"
            self.original_to_target_map[original_key] = target_key
            data = self.full_grid_data.get(original_key, {})
            targets[target_key] = {
                "day": day,
                "original_key": original_key,
                "is_excluded": data.get("is_excluded", False),
                "exams": data.get("exams", []),
            }
            current_col += 1
            if current_col > 6:
                current_col, current_row = 0, current_row + 1

        for target_key in self.grid_cells:
            content = targets[target_key]
            if content == self._last_cell_content.get(target_key):
                continue
            self._render_cell(target_key, content)
            self._last_cell_content[target_key] = content

        for cell in self.grid_cells.values():
            cell.configure(border_color=theme.BORDER_DEFAULT, border_width=1)
        if self.selected_original_key in self.original_to_target_map:
            t_key = self.original_to_target_map[self.selected_original_key]
            self.grid_cells[t_key].configure(border_color=theme.BORDER_ACTIVE, border_width=2)

    def _handle_cell_click(self, original_key):
        if self.on_cell_clicked: self.on_cell_clicked(original_key)

    def _render_cell(self, target_key: str, content):
        cell_frame = self.grid_cells.get(target_key)
        if not cell_frame: return

        for widget in cell_frame.winfo_children(): widget.destroy()

        if content is None:
            # Empty cell - blends with the app background and looks perfectly seamless
            cell_frame.configure(fg_color=theme.BG_MAIN)
            cell_frame.unbind("<Button-1>")
            return

        original_key = content["original_key"]
        
        # Cell colors
        if content["is_excluded"]:
            cell_frame.configure(fg_color=("#ffe6e6", "#4a1c1c"))
        else:
            cell_frame.configure(fg_color=theme.BG_CARD)
            
        cell_frame.bind("<Button-1>", lambda e, k=original_key: self._handle_cell_click(k))

        anchor = "ne" if self.current_lang == "he" else "nw"
        day_lbl = ctk.CTkLabel(cell_frame, text=str(content["day"]), font=self.f_day, text_color=theme.TEXT_MAIN)
        day_lbl.pack(anchor=anchor, padx=8, pady=4)
        day_lbl.bind("<Button-1>", lambda e, k=original_key: self._handle_cell_click(k))

        exams = content["exams"]
        if exams:
            exams_container = ctk.CTkScrollableFrame(cell_frame, fg_color="transparent")
            exams_container.pack(fill="both", expand=True, padx=2, pady=(0, 2))

            if hasattr(exams_container, "_parent_canvas"):
                exams_container._parent_canvas.bind("<Button-1>", lambda e, k=original_key: self._handle_cell_click(k))

            # Elegant color palette for when there are multiple exams on the same day
            elegant_colors = [
                ("#0d6efd", "#0077b6"), # Blue
                ("#20c997", "#128260"), # Mint-green
                ("#f39c12", "#d68910"), # Orange
                ("#e83e8c", "#b8306f"), # Pink
                ("#8e44ad", "#6c3483")  # Purple
            ]

            for i, exam in enumerate(exams):
                # Pick a color dynamically based on the exam index
                pill_color = elegant_colors[i % len(elegant_colors)]
                
                # "Pill" styling with very rounded corners
                card = ctk.CTkFrame(exams_container, fg_color=pill_color, corner_radius=10)
                card.pack(fill="x", expand=False, padx=2, pady=3)

                full_name = exam.get('short_name', '')
                c_type = TRANSLATIONS["type_hova"][self.current_lang] if exam.get("type") == "ח" else TRANSLATIONS["type_bhira"][self.current_lang]
                cid_label = TRANSLATIONS["course_id"][self.current_lang]

                def _he(s):
                    return f"\u200F{s}\u200F" if self.current_lang == "he" else s

                card_lines = []
                
                # Centered or language-aligned text - kept centered in the pills to preserve a clean "event" look
                name_lbl = ctk.CTkLabel(card, text=full_name, font=self.f_card, text_color="white", justify="center")
                name_lbl.pack(padx=6, pady=(4, 0), fill="x")
                card_lines.append(name_lbl)

                id_lbl = ctk.CTkLabel(card, text=_he(f"{cid_label} {exam.get('course_id', '')}"), font=self.f_card, text_color="white", justify="center")
                id_lbl.pack(padx=6, fill="x")
                card_lines.append(id_lbl)

                type_lbl = ctk.CTkLabel(card, text=_he(c_type), font=self.f_card, text_color="white", justify="center")
                type_lbl.pack(padx=6, pady=(0, 4), fill="x")
                card_lines.append(type_lbl)

                def _wrap_all(e, lbls=card_lines):
                    w = max(40, e.width - 12)
                    for l in lbls:
                        l.configure(wraplength=w)
                card.bind("<Configure>", _wrap_all)

                for widget in [card] + card_lines:
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
        for cell in self.grid_cells.values(): cell.configure(border_color=theme.BORDER_DEFAULT, border_width=1)
        if original_key in self.original_to_target_map:
            self.grid_cells[self.original_to_target_map[original_key]].configure(border_color=theme.BORDER_ACTIVE, border_width=2)

    def toggle_cell_exclusion_visual(self, original_key: str, is_excluded: bool):
        if original_key in self.original_to_target_map:
            target_key = self.original_to_target_map[original_key]
            cell = self.grid_cells.get(target_key)
            if cell:
                cell.configure(fg_color=("#ffe6e6", "#4a1c1c") if is_excluded else theme.BG_CARD)
                self._last_cell_content.pop(target_key, None) 

    def update_metrics_display(self, metrics):
        """Live metrics readout for the active schedule (PLAN-408)."""
        if hasattr(self, "ranking_bar"):
            self.ranking_bar.update_metrics(metrics)

    def show_no_more_results(self):
        """End-of-results boundary indicator for the refresh-feed (PLAN-415)."""
        if hasattr(self, "ranking_bar"):
            self.ranking_bar.show_no_more_results()

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
                header.configure(text=TRANSLATIONS["days"][lang][i])
        if self.active_months:
            self._last_cell_content = {} 
            self.render_current_month()

        if hasattr(self, "popup_box") and self.popup_box.winfo_exists() and hasattr(self, "_last_exam_data"):
            show_exam_popup(self, self._last_exam_data, lang)