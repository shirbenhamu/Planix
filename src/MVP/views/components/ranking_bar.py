"""
RankingBar — the GUI surface for the ranking & windowing features (PLAN-411..415).

A self-contained, language-aware bar with:
  * a primary + secondary sort dropdown (priority order),
  * a sort-direction toggle (descending by default),
  * a refresh button (refresh-feed), and
  * a live readout of the active schedule's five section-3 metrics.

It holds its selection as metric KEYS (not labels), so switching language simply
re-labels the controls without losing the user's choice. Both the annual and the
monthly calendar views embed one and forward its callbacks to the presenter.
"""
import math

import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import TRANSLATIONS
from src.metrics.metrics_calculator import METRIC_KEYS

# Display order in the dropdowns: avg_gap_all first so it shows as the default,
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

        # Selection state, stored as metric keys so it survives language changes.
        self._primary_key = "avg_gap_all"
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
            font=self._font, dropdown_font=self._font, corner_radius=8, height=30,
            fg_color=theme.BG_CARD_HOVER, button_color=theme.TEXT_ACCENT,
            button_hover_color=theme.BORDER_ACTIVE, text_color=theme.TEXT_MAIN,
            dropdown_fg_color=theme.BG_CARD, dropdown_hover_color=theme.BG_CARD_HOVER,
            dropdown_text_color=theme.TEXT_MAIN, anchor="center",
        )

        self.lbl_sort = ctk.CTkLabel(self, font=self._font, text_color=theme.TEXT_ACCENT)
        self.primary_menu = ctk.CTkOptionMenu(
            self, values=[""], width=210, command=self._on_primary, **menu_style)
        self.lbl_then = ctk.CTkLabel(self, font=self._font, text_color=theme.TEXT_MUTED)
        self.secondary_menu = ctk.CTkOptionMenu(
            self, values=[""], width=210, command=self._on_secondary, **menu_style)
        self.direction_menu = ctk.CTkOptionMenu(
            self, values=[""], width=110, command=self._on_direction, **menu_style)
        self.refresh_btn = ctk.CTkButton(
            self, font=self._font, width=110, height=30, corner_radius=8,
            fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER, text_color="white",
            command=self._on_refresh)
        self.metrics_label = ctk.CTkLabel(
            self, font=self._font_metrics, text_color=theme.TEXT_MUTED)

        self._control_widgets = [
            self.lbl_sort, self.primary_menu, self.lbl_then,
            self.secondary_menu, self.direction_menu, self.refresh_btn,
        ]

    # --- language / labels --------------------------------------------------
    def set_language(self, lang: str) -> None:
        self.current_lang = lang

        self.lbl_sort.configure(text=self._rtl(self._t("sort_by")))
        self.lbl_then.configure(text=self._rtl(self._t("sort_then")))
        self.refresh_btn.configure(text=f"↻ {self._t('refresh_btn')}")

        primary_labels = [self._metric_label(k) for k in METRIC_DISPLAY_ORDER]
        self._primary_label_to_key = {
            self._metric_label(k): k for k in METRIC_DISPLAY_ORDER
        }
        self.primary_menu.configure(values=primary_labels)
        self.primary_menu.set(self._metric_label(self._primary_key))

        none_label = self._t("sort_none")
        self._none_label = none_label
        self.secondary_menu.configure(values=[none_label] + primary_labels)
        self._secondary_label_to_key = {none_label: None}
        self._secondary_label_to_key.update(
            {self._metric_label(k): k for k in METRIC_DISPLAY_ORDER}
        )
        self.secondary_menu.set(
            none_label if self._secondary_key is None
            else self._metric_label(self._secondary_key)
        )

        self._dir_desc = f"{self._t('sort_dir_desc')} ▼"
        self._dir_asc = f"{self._t('sort_dir_asc')} ▲"
        self.direction_menu.configure(values=[self._dir_desc, self._dir_asc])
        self.direction_menu.set(self._dir_asc if self._ascending else self._dir_desc)

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

    # --- selection callbacks ------------------------------------------------
    def _on_primary(self, label: str) -> None:
        self._primary_key = self._primary_label_to_key.get(label, self._primary_key)
        self._fire()

    def _on_secondary(self, label: str) -> None:
        self._secondary_key = self._secondary_label_to_key.get(label)
        self._fire()

    def _on_direction(self, label: str) -> None:
        self._ascending = label == self._dir_asc
        self._fire()

    def _on_refresh(self) -> None:
        if self.on_refresh:
            self.on_refresh()

    def _fire(self) -> None:
        if not self.on_sort_changed:
            return
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
