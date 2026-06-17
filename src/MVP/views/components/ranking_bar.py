"""
RankingBar — the GUI surface for the ranking & windowing features.

PLAN-420 replaces the old primary/secondary dropdown pair with a priority-order
selector popup. The user can enable any of the five metrics and arrange them in
priority order. Saving the popup forwards an ordered list of metric keys to the
Presenter, which calls ScheduleCollectionManager.sort_collection().
"""

from __future__ import annotations

import math

import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import TRANSLATIONS
from src.MVP.views.components.ui_components import Tooltip
from src.MVP.views.components.sort_criteria_modal import (
    normalize_selected_sort_keys,
    show_sort_criteria_popup,
)
from src.metrics.metrics_calculator import METRIC_KEYS

# Display order in UI controls: avg_gap_all first so it stays the default,
# matching the manager's DEFAULT_SORT_KEYS.
METRIC_DISPLAY_ORDER = [
    "avg_gap_all",
    "min_gap_mandatory",
    "elective_conflicts",
    "mandatory_span",
    "max_exams_per_day",
]


def format_metric_value(value) -> str:
    if value is None:
        return "—"
    numeric = float(value)
    if math.isinf(numeric):
        return "∞"
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.1f}"


class RankingBar(ctk.CTkFrame):
    def __init__(self, master, lang: str = "he", **kwargs):
        super().__init__(master, fg_color=theme.BG_CARD, corner_radius=10, **kwargs)
        self.current_lang = lang

        # Public callbacks (wired by the embedding view / presenter).
        self.on_sort_changed = None   # (sort_keys: list[str], ascending: bool) -> None
        self.on_refresh = None        # () -> None
        self.on_info = None           # () -> None  (open the help modal)

        # Selection state, stored as metric keys so it survives language changes.
        self._sort_keys = ["avg_gap_all"]
        self._primary_key = self._sort_keys[0]  # kept for backward-compatible tests/helpers
        self._secondary_key = None
        self._ascending = False
        self._last_metrics = None

        self._build()
        self.set_language(lang)

    # --- i18n helpers -------------------------------------------------------
    def _t(self, key: str) -> str:
        return TRANSLATIONS.get(key, {}).get(self.current_lang, key)

    def _rtl(self, text: str) -> str:
        return f"\u200F{text}\u200F" if self.current_lang == "he" else text

    def _metric_label(self, key: str) -> str:
        return self._t(f"metric_{key}")

    def _metric_short(self, key: str) -> str:
        return self._t(f"metric_short_{key}")

    # --- construction -------------------------------------------------------
    def _build(self) -> None:
        self._font = ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold")
        self._font_metrics = ctk.CTkFont(family=theme.FONT_FAMILY, size=11)

        menu_style = dict(
            font=self._font,
            dropdown_font=self._font,
            corner_radius=8,
            height=30,
            fg_color=theme.BG_CARD_HOVER,
            button_color=theme.TEXT_ACCENT,
            button_hover_color=theme.BORDER_ACTIVE,
            text_color=theme.TEXT_MAIN,
            dropdown_fg_color=theme.BG_CARD,
            dropdown_hover_color=theme.BG_CARD_HOVER,
            dropdown_text_color=theme.TEXT_MAIN,
            anchor="center",
        )

        self.lbl_sort = ctk.CTkLabel(self, font=self._font, text_color=theme.TEXT_ACCENT)

        # PLAN-420: one selector button opens the full priority-order modal.
        self.sort_selector_btn = ctk.CTkButton(
            self,
            width=270,
            height=30,
            corner_radius=8,
            font=self._font,
            fg_color=theme.BG_CARD_HOVER,
            hover_color=theme.BORDER_ACTIVE,
            text_color=theme.TEXT_MAIN,
            command=self._open_sort_selector,
        )
        self._sort_tooltip = Tooltip(self.sort_selector_btn, "")

        self.direction_menu = ctk.CTkOptionMenu(
            self, values=[""], width=110, command=self._on_direction, **menu_style)
        self.refresh_btn = ctk.CTkButton(
            self, font=self._font, width=110, height=30, corner_radius=8,
            fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER, text_color="white",
            command=self._on_refresh)

        # Round "i" help button — opens the metrics/sorting explanation modal.
        self.info_btn = ctk.CTkButton(
            self, text="ⓘ", width=30, height=30, corner_radius=15,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=15, weight="bold"),
            fg_color=theme.BG_CARD_HOVER, hover_color=theme.BORDER_ACTIVE,
            text_color=theme.TEXT_ACCENT, command=self._on_info_click)
        self._info_tooltip = Tooltip(self.info_btn, "")

        self.metrics_label = ctk.CTkLabel(
            self, font=self._font_metrics, text_color=theme.TEXT_MUTED)

        self._control_widgets = [
            self.lbl_sort,
            self.sort_selector_btn,
            self.direction_menu,
            self.refresh_btn,
            self.info_btn,
        ]

    # --- language / labels --------------------------------------------------
    def set_language(self, lang: str) -> None:
        self.current_lang = lang

        self.lbl_sort.configure(text=self._rtl(self._t("sort_by")))
        self.refresh_btn.configure(text=f"↻ {self._t('refresh_btn')}")
        self._info_tooltip.text = self._t("info_btn_tooltip")
        self._sort_tooltip.text = self._t("sort_selector_tooltip")

        # Compatibility maps used by the old direct unit tests and any legacy code.
        primary_labels = [self._metric_label(k) for k in METRIC_DISPLAY_ORDER]
        self._primary_label_to_key = {self._metric_label(k): k for k in METRIC_DISPLAY_ORDER}
        none_label = self._t("sort_none")
        self._none_label = none_label
        self._secondary_label_to_key = {none_label: None}
        self._secondary_label_to_key.update(
            {self._metric_label(k): k for k in METRIC_DISPLAY_ORDER}
        )

        self._dir_desc = f"{self._t('sort_dir_desc')} ▼"
        self._dir_asc = f"{self._t('sort_dir_asc')} ▲"
        self.direction_menu.configure(values=[self._dir_desc, self._dir_asc])
        self.direction_menu.set(self._dir_asc if self._ascending else self._dir_desc)

        self._update_sort_selector_label()
        self._render_metrics()
        self._layout()

    def _layout(self) -> None:
        for widget in self._control_widgets + [self.metrics_label]:
            widget.pack_forget()
        rtl = self.current_lang == "he"
        controls_side = "right" if rtl else "left"
        for widget in self._control_widgets:
            widget.pack(side=controls_side, padx=4, pady=8)
        self.metrics_label.pack(side="left" if rtl else "right", padx=14, pady=8)

    # --- priority selector --------------------------------------------------
    def _sync_legacy_keys(self) -> None:
        self._primary_key = self._sort_keys[0] if self._sort_keys else "avg_gap_all"
        self._secondary_key = self._sort_keys[1] if len(self._sort_keys) > 1 else None

    def set_sort_keys(self, sort_keys, fire: bool = False) -> None:
        """Set the ordered metric priority list and optionally notify Presenter."""

        self._sort_keys = normalize_selected_sort_keys(sort_keys)
        self._sync_legacy_keys()
        self._update_sort_selector_label()
        if fire:
            self._fire()

    def get_sort_keys(self) -> list[str]:
        return list(getattr(self, "_sort_keys", []))

    def _update_sort_selector_label(self) -> None:
        if not hasattr(self, "sort_selector_btn"):
            return
        sort_keys = normalize_selected_sort_keys(getattr(self, "_sort_keys", None))
        labels = [f"{index + 1}. {self._metric_short(key)}" for index, key in enumerate(sort_keys)]
        text = "  ›  ".join(labels)
        self.sort_selector_btn.configure(text=self._rtl(text))

    def _open_sort_selector(self) -> None:
        show_sort_criteria_popup(
            parent=self,
            current_lang=self.current_lang,
            sort_keys=getattr(self, "_sort_keys", [self._primary_key]),
            on_save_callback=self._handle_sort_selection,
        )

    def _handle_sort_selection(self, sort_keys) -> None:
        self.set_sort_keys(sort_keys, fire=True)

    # --- legacy selection callbacks ----------------------------------------
    # These methods remain for backward compatibility with the earlier tests and
    # with any old call sites. The actual UI now uses the PLAN-420 popup.
    def _on_primary(self, label: str) -> None:
        self._primary_key = self._primary_label_to_key.get(label, self._primary_key)
        if hasattr(self, "_sort_keys"):
            remainder = [key for key in self._sort_keys if key != self._primary_key]
            self._sort_keys = normalize_selected_sort_keys([self._primary_key] + remainder)
            self._sync_legacy_keys()
            self._update_sort_selector_label()
        self._fire()

    def _on_secondary(self, label: str) -> None:
        self._secondary_key = self._secondary_label_to_key.get(label)
        if hasattr(self, "_sort_keys"):
            keys = [self._primary_key]
            if self._secondary_key and self._secondary_key != self._primary_key:
                keys.append(self._secondary_key)
            self._sort_keys = normalize_selected_sort_keys(keys)
            self._sync_legacy_keys()
            self._update_sort_selector_label()
        self._fire()

    def _on_direction(self, label: str) -> None:
        self._ascending = label == self._dir_asc
        self._fire()

    def _on_refresh(self) -> None:
        if self.on_refresh:
            self.on_refresh()

    def _on_info_click(self) -> None:
        if self.on_info:
            self.on_info()

    def _fire(self) -> None:
        if not self.on_sort_changed:
            return

        if hasattr(self, "_sort_keys") and self._sort_keys:
            sort_keys = list(self._sort_keys)
        else:
            sort_keys = [self._primary_key]
            if self._secondary_key and self._secondary_key != self._primary_key:
                sort_keys.append(self._secondary_key)

        self.on_sort_changed(sort_keys, self._ascending)

    # --- live metrics readout ----------------------------------------------
    def update_metrics(self, metrics) -> None:
        self._last_metrics = metrics
        self._render_metrics()

    def _render_metrics(self) -> None:
        if not self._last_metrics:
            self.metrics_label.configure(text="")
            return
        parts = [
            f"{self._metric_short(key)}: {format_metric_value(value)}"
            for key, value in zip(METRIC_KEYS, self._last_metrics)
        ]
        self.metrics_label.configure(text=self._rtl("   |   ".join(parts)))

    def show_no_more_results(self) -> None:
        self.metrics_label.configure(text=self._rtl(self._t("end_of_results")))
