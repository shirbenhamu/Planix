"""Sort criteria selector modal for PLAN-420.

The modal lets the user choose which ranking metrics participate in sorting and
sets their priority order. The saved result is an ordered list of metric keys,
which is forwarded by RankingBar to CalendarPresenter -> ScheduleCollectionManager.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

import tkinter as tk
import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import format_text, TRANSLATIONS
from src.MVP.views.components.ui_components import create_secondary_button
from src.metrics.metrics_calculator import METRIC_KEYS

# The user-facing order matches the metrics panel and previous ranking dropdowns.
SORT_CRITERIA_ORDER = [
    "avg_gap_all",
    "min_gap_mandatory",
    "elective_conflicts",
    "mandatory_span",
    "max_exams_per_day",
]

DEFAULT_SORT_CRITERIA = ["avg_gap_all"]


def normalize_selected_sort_keys(sort_keys: Optional[Iterable[str]]) -> List[str]:
    """Return a non-empty, unique, valid ordered sort-key list.

    The Presenter/CollectionManager expects at least one metric key. Invalid
    values and duplicates are ignored. If nothing valid remains, the default
    primary metric is used.
    """

    if sort_keys is None:
        candidates = []
    elif isinstance(sort_keys, str):
        candidates = [sort_keys]
    else:
        candidates = list(sort_keys)

    valid = set(METRIC_KEYS)
    normalized: List[str] = []
    for key in candidates:
        if key in valid and key not in normalized:
            normalized.append(key)

    return normalized or list(DEFAULT_SORT_CRITERIA)


def normalize_full_metric_order(sort_keys: Optional[Iterable[str]]) -> List[str]:
    """Return all metric keys, preserving the selected order first.

    The modal displays all five metrics. Selected metrics are shown first in
    their current priority order; the remaining metrics are appended in the
    canonical display order.
    """

    ordered = normalize_selected_sort_keys(sort_keys)
    for key in SORT_CRITERIA_ORDER:
        if key not in ordered:
            ordered.append(key)
    return ordered


def move_key_in_order(order: Iterable[str], key: str, delta: int) -> List[str]:
    """Move a metric key up/down by delta positions inside an order list."""

    items = list(order)
    if key not in items:
        return items

    old_index = items.index(key)
    new_index = max(0, min(len(items) - 1, old_index + delta))
    if new_index == old_index:
        return items

    items.pop(old_index)
    items.insert(new_index, key)
    return items


def place_key_at_index(order: Iterable[str], key: str, target_index: int) -> List[str]:
    """Place a metric key at a specific index, used by drag-and-drop."""

    items = list(order)
    if key not in items:
        return items

    target_index = max(0, min(len(items) - 1, int(target_index)))
    items.remove(key)
    items.insert(target_index, key)
    return items


class SortCriteriaSelectorModal(ctk.CTkToplevel):
    """Popup for enabling/disabling sort metrics and ordering them by priority."""

    ROW_HEIGHT = 56

    def __init__(
        self,
        parent,
        current_lang: str = "he",
        sort_keys: Optional[Iterable[str]] = None,
        on_save_callback: Optional[Callable[[List[str]], None]] = None,
        on_close_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(parent)
        self.parent = parent
        self.current_lang = current_lang
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback

        self._selected_keys = normalize_selected_sort_keys(sort_keys)
        self._ordered_keys = normalize_full_metric_order(self._selected_keys)
        self._enabled_vars: dict[str, tk.BooleanVar] = {}
        self._row_frames: dict[str, ctk.CTkFrame] = {}
        self._drag_key: Optional[str] = None
        self._drag_start_x = 0
        self._drag_start_y = 0

        self.overrideredirect(True)
        self.title(format_text("sort_selector_title", current_lang))
        self.configure(fg_color=theme.BG_CARD)
        self.geometry("720x560")
        self.minsize(640, 500)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close_without_saving)
        self.bind("<Escape>", lambda _event: self._close_without_saving())

        self._build_ui()
        self._center_on_parent()
        self.lift()
        self.focus_force()

    # --- i18n helpers -----------------------------------------------------
    def _t(self, key: str) -> str:
        return TRANSLATIONS.get(key, {}).get(self.current_lang, key)

    def _rtl(self, text: str) -> str:
        return f"\u200F{text}\u200F" if self.current_lang == "he" else text

    def _metric_label(self, key: str) -> str:
        return self._t(f"metric_{key}")

    # --- UI construction --------------------------------------------------
    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        outer = ctk.CTkFrame(
            self,
            fg_color=theme.BG_CARD,
            border_width=2,
            border_color=theme.TEXT_ACCENT,
            corner_radius=theme.RADIUS_CARD,
        )
        outer.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(2, weight=1)
        self.outer_frame = outer

        title = ctk.CTkLabel(
            outer,
            text=self._rtl(self._t("sort_selector_title")),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=24, weight="bold"),
            text_color=theme.TEXT_ACCENT,
        )
        title.grid(row=0, column=0, sticky="ew", padx=30, pady=(26, 8))
        title.bind("<ButtonPress-1>", self._start_drag)
        title.bind("<B1-Motion>", self._on_drag)

        hint = ctk.CTkLabel(
            outer,
            text=self._rtl(self._t("sort_selector_hint")),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold"),
            text_color=theme.TEXT_MUTED,
            wraplength=610,
            justify="right" if self.current_lang == "he" else "left",
        )
        hint.grid(row=1, column=0, sticky="ew", padx=36, pady=(0, 12))

        self.list_frame = ctk.CTkFrame(
            outer,
            fg_color=theme.BG_CARD,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
            corner_radius=theme.RADIUS_CARD,
        )
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=36, pady=(0, 18))
        self.list_frame.grid_columnconfigure(0, weight=1)

        for key in SORT_CRITERIA_ORDER:
            self._enabled_vars[key] = tk.BooleanVar(value=key in self._selected_keys)

        self._render_rows()

        footer = ctk.CTkFrame(outer, fg_color=theme.TRANSPARENT)
        footer.grid(row=3, column=0, sticky="ew", padx=36, pady=(0, 24))

        self.error_label = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold"),
            text_color=theme.DANGER,
        )
        self.error_label.pack(side="top", fill="x", pady=(0, 8))

        buttons = ctk.CTkFrame(footer, fg_color=theme.TRANSPARENT)
        buttons.pack(side="bottom", fill="x")

        self.cancel_btn = create_secondary_button(
            buttons,
            text=format_text("cancel", self.current_lang),
            command=self._close_without_saving,
        )
        self.save_btn = ctk.CTkButton(
            buttons,
            text=format_text("save", self.current_lang),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold"),
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_HOVER,
            text_color="white",
            height=42,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._save_and_close,
        )

        if self.current_lang == "he":
            self.save_btn.pack(side="left", padx=(8, 0))
            self.cancel_btn.pack(side="left")
        else:
            self.cancel_btn.pack(side="left", padx=(0, 8))
            self.save_btn.pack(side="left")

    def _render_rows(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        self._row_frames.clear()

        for index, key in enumerate(self._ordered_keys):
            enabled = bool(self._enabled_vars[key].get())
            row = ctk.CTkFrame(
                self.list_frame,
                fg_color=theme.BG_CARD_HOVER if enabled else theme.BG_CARD,
                border_width=1,
                border_color=theme.TEXT_ACCENT if enabled else theme.BORDER_DEFAULT,
                corner_radius=theme.RADIUS_BUTTON,
                height=self.ROW_HEIGHT,
            )
            row.grid(row=index, column=0, sticky="ew", padx=12, pady=(10 if index == 0 else 4, 4))
            row.grid_columnconfigure(1, weight=1)
            row.grid_propagate(False)
            self._row_frames[key] = row

            priority = ctk.CTkLabel(
                row,
                text=str(index + 1),
                width=34,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold"),
                text_color=theme.TEXT_ACCENT if enabled else theme.TEXT_MUTED,
            )
            priority.grid(row=0, column=0, padx=(10, 4), pady=8)

            checkbox = ctk.CTkCheckBox(
                row,
                text=self._rtl(self._metric_label(key)),
                variable=self._enabled_vars[key],
                command=self._refresh_rows_after_toggle,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold"),
                text_color=theme.TEXT_MAIN if enabled else theme.TEXT_MUTED,
                fg_color=theme.TEXT_ACCENT,
                hover_color=theme.BORDER_ACTIVE,
                border_color=theme.BORDER_DEFAULT,
                checkmark_color=theme.BG_CARD,
            )
            checkbox.grid(row=0, column=1, sticky="ew", padx=8, pady=8)

            down_btn = self._small_order_button(row, "↓", lambda k=key: self._move_key(k, +1))
            up_btn = self._small_order_button(row, "↑", lambda k=key: self._move_key(k, -1))

            if self.current_lang == "he":
                down_btn.grid(row=0, column=2, padx=(2, 4), pady=8)
                up_btn.grid(row=0, column=3, padx=(2, 10), pady=8)
            else:
                up_btn.grid(row=0, column=2, padx=(2, 4), pady=8)
                down_btn.grid(row=0, column=3, padx=(2, 10), pady=8)

            for widget in (row, priority, checkbox):
                widget.bind("<ButtonPress-1>", lambda event, k=key: self._start_row_drag(event, k), add="+")
                widget.bind("<ButtonRelease-1>", self._finish_row_drag, add="+")

    def _small_order_button(self, parent, text: str, command: Callable[[], None]):
        return ctk.CTkButton(
            parent,
            text=text,
            width=32,
            height=30,
            fg_color=theme.TRANSPARENT,
            border_width=1,
            border_color=theme.BORDER_DEFAULT,
            hover_color=theme.BG_CARD_HOVER,
            text_color=theme.TEXT_ACCENT,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold"),
            corner_radius=theme.RADIUS_BUTTON,
            command=command,
        )

    # --- modal movement ---------------------------------------------------
    def _start_drag(self, event) -> None:
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _on_drag(self, event) -> None:
        self.geometry(f"+{event.x_root - self._drag_start_x}+{event.y_root - self._drag_start_y}")

    # --- order manipulation -----------------------------------------------
    def _move_key(self, key: str, delta: int) -> None:
        self._ordered_keys = move_key_in_order(self._ordered_keys, key, delta)
        self._render_rows()

    def _start_row_drag(self, event, key: str) -> None:
        self._drag_key = key

    def _finish_row_drag(self, event) -> None:
        if not self._drag_key:
            return
        try:
            local_y = event.y_root - self.list_frame.winfo_rooty()
            target_index = int(local_y // self.ROW_HEIGHT)
            self._ordered_keys = place_key_at_index(self._ordered_keys, self._drag_key, target_index)
            self._render_rows()
        finally:
            self._drag_key = None

    def _refresh_rows_after_toggle(self) -> None:
        self.error_label.configure(text="")
        self._render_rows()

    # --- save / close ------------------------------------------------------
    def _collect_sort_keys(self) -> List[str]:
        selected = [
            key for key in self._ordered_keys
            if bool(self._enabled_vars[key].get())
        ]
        return normalize_selected_sort_keys(selected) if selected else []

    def _validate_before_save(self) -> bool:
        if not self._collect_sort_keys():
            self.error_label.configure(text=self._rtl(self._t("sort_selector_empty_error")))
            return False
        self.error_label.configure(text="")
        return True

    def _save_and_close(self) -> None:
        if not self._validate_before_save():
            return
        sort_keys = self._collect_sort_keys()
        if self.on_save_callback:
            self.on_save_callback(sort_keys)
        self.destroy()

    def _close_without_saving(self) -> None:
        if self.on_close_callback:
            self.on_close_callback()
        self.destroy()

    def _center_on_parent(self) -> None:
        try:
            self.update_idletasks()
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()
            modal_w = self.winfo_width()
            modal_h = self.winfo_height()
            x = parent_x + max(0, (parent_w - modal_w) // 2)
            y = parent_y + max(0, (parent_h - modal_h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass


def show_sort_criteria_popup(
    parent,
    current_lang: str = "he",
    sort_keys: Optional[Iterable[str]] = None,
    on_save_callback: Optional[Callable[[List[str]], None]] = None,
    on_close_callback: Optional[Callable[[], None]] = None,
):
    return SortCriteriaSelectorModal(
        parent=parent,
        current_lang=current_lang,
        sort_keys=sort_keys,
        on_save_callback=on_save_callback,
        on_close_callback=on_close_callback,
    )
