"""
MetricsPanel — themed live display for the five sorting metrics (PLAN-419).

The ranking bar still owns the sort controls. This component focuses only on the
readability of the current schedule metrics: five labeled values, rendered as a
small themed panel that can be embedded in the calendar views.
"""
from __future__ import annotations

import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import TRANSLATIONS
from src.MVP.views.components.ranking_bar import format_metric_value
from src.metrics.metrics_calculator import METRIC_KEYS


METRICS_PANEL_FIELDS = tuple(METRIC_KEYS)


class MetricsPanel(ctk.CTkFrame):
    """A language-aware panel that displays all five schedule metrics."""

    def __init__(self, master, lang: str = "he", **kwargs):
        super().__init__(
            master,
            fg_color=theme.BG_CARD,
            border_color=theme.BORDER_DEFAULT,
            border_width=theme.BORDER_WIDTH_DEFAULT,
            corner_radius=theme.RADIUS_CARD,
            **kwargs,
        )
        self.current_lang = lang
        self._last_metrics = None
        self._name_labels = {}
        self._value_labels = {}
        self._metric_cards = {}

        self._build()
        self.set_language(lang)

    # --- i18n helpers -------------------------------------------------------
    def _t(self, key: str) -> str:
        return TRANSLATIONS.get(key, {}).get(self.current_lang, key)

    def _rtl(self, text: str) -> str:
        return f"\u200F{text}\u200F" if self.current_lang == "he" else text

    def _metric_label(self, key: str) -> str:
        return self._t(f"metric_{key}")

    # --- construction -------------------------------------------------------
    def _build(self) -> None:
        self._title_font = ctk.CTkFont(
            family=theme.FONT_FAMILY,
            size=theme.FONT_SIZE_BODY,
            weight=theme.FONT_WEIGHT_BOLD,
        )
        self._label_font = ctk.CTkFont(
            family=theme.FONT_FAMILY,
            size=theme.FONT_SIZE_XS,
            weight=theme.FONT_WEIGHT_BOLD,
        )
        self._value_font = ctk.CTkFont(
            family=theme.FONT_FAMILY,
            size=theme.FONT_SIZE_TITLE,
            weight=theme.FONT_WEIGHT_BOLD,
        )

        self.title_label = ctk.CTkLabel(
            self,
            font=self._title_font,
            text_color=theme.TEXT_ACCENT,
        )
        self.title_label.pack(fill="x", padx=theme.SPACING_REGULAR, pady=(theme.SPACING_COMPACT, theme.SPACING_TINY))

        self.metrics_row = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self.metrics_row.pack(fill="x", padx=theme.SPACING_SMALL, pady=(theme.SPACING_NONE, theme.SPACING_COMPACT))

        for column, key in enumerate(METRICS_PANEL_FIELDS):
            self.metrics_row.grid_columnconfigure(column, weight=1, uniform="metric")

            card = ctk.CTkFrame(
                self.metrics_row,
                fg_color=theme.BG_CARD_HOVER,
                border_color=theme.BORDER_DEFAULT,
                border_width=theme.BORDER_WIDTH_DEFAULT,
                corner_radius=theme.RADIUS_BUTTON,
            )
            card.grid(
                row=0,
                column=column,
                sticky="nsew",
                padx=theme.SPACING_TINY,
                pady=theme.SPACING_XS,
            )

            name_label = ctk.CTkLabel(
                card,
                font=self._label_font,
                text_color=theme.TEXT_MUTED,
                wraplength=theme.CONTROL_WRAP_METRIC_CARD,
                justify="center",
            )
            name_label.pack(fill="x", padx=theme.SPACING_SMALL, pady=(theme.SPACING_SMALL, theme.SPACING_XS))

            value_label = ctk.CTkLabel(
                card,
                text=theme.EMPTY_VALUE_TEXT,
                font=self._value_font,
                text_color=theme.TEXT_MAIN,
            )
            value_label.pack(fill="x", padx=theme.SPACING_SMALL, pady=(theme.SPACING_NONE, theme.SPACING_SMALL))

            self._metric_cards[key] = card
            self._name_labels[key] = name_label
            self._value_labels[key] = value_label

        self.status_label = ctk.CTkLabel(
            self,
            text="",
            font=self._label_font,
            text_color=theme.TEXT_MUTED,
        )
        self.status_label.pack(fill="x", padx=theme.SPACING_REGULAR, pady=(theme.SPACING_NONE, theme.SPACING_SMALL))

    # --- public API ---------------------------------------------------------
    def set_language(self, lang: str) -> None:
        self.current_lang = lang
        self.title_label.configure(text=self._rtl(self._t("metrics_panel_title")))
        for key in METRICS_PANEL_FIELDS:
            self._name_labels[key].configure(text=self._rtl(self._metric_label(key)))
        self._render_metrics()

    def update_metrics(self, metrics) -> None:
        self._last_metrics = metrics
        self.status_label.configure(text="")
        self._render_metrics()

    def show_no_more_results(self) -> None:
        self.status_label.configure(text=self._rtl(self._t("end_of_results")))

    # --- rendering ----------------------------------------------------------
    def _metrics_by_key(self) -> dict:
        if not self._last_metrics:
            return {}
        if isinstance(self._last_metrics, dict):
            return self._last_metrics
        return {
            key: value
            for key, value in zip(METRICS_PANEL_FIELDS, self._last_metrics)
        }

    def _render_metrics(self) -> None:
        metrics_by_key = self._metrics_by_key()
        for key in METRICS_PANEL_FIELDS:
            value = metrics_by_key.get(key)
            self._value_labels[key].configure(text=format_metric_value(value))
