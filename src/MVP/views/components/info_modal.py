# src/MVP/views/components/info_modal.py
"""
Help modals for the ranking, constraints, and calendar controls.

PLAN-582 updates the Information pop-up so Hebrew content is rendered in a
right-to-left friendly way and the help text covers the Sprint 3 controls:
sort priority, metrics, constraints, refresh feed, load more, and the calendar
view action buttons.
"""
from __future__ import annotations

import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import TRANSLATIONS, format_text
from src.MVP.views.components.ranking_bar import METRIC_DISPLAY_ORDER
from src.metrics.metrics_calculator import METRIC_KEYS

# Metrics where a HIGHER value is the better outcome (the rest: lower is better).
_PREF_HIGHER = {"avg_gap_all", "min_gap_mandatory", "mandatory_span"}

INFO_CONSTRAINT_KEYS = [
    "min_days_mandatory",
    "min_days_any",
    "max_elective_conflicts",
    "span_mandatory",
    "max_exams_per_day",
]

INFO_CALENDAR_BUTTON_KEYS = [
    "navigation",
    "sort_selector",
    "metrics",
    "refresh_feed",
    "load_more",
    "constraints",
    "edit_dates",
    "exclude",
    "undo",
    "export",
    "deep_search",
]


def _is_rtl(lang: str) -> bool:
    return lang == "he"


def _shape_text(text: str, lang: str) -> str:
    """Wrap Hebrew help text in an RTL embedding for mixed Hebrew/English lines."""

    if not _is_rtl(lang):
        return text
    return f"\u202B{text}\u202C"


def _translation(key: str, lang: str) -> str:
    return TRANSLATIONS.get(key, {}).get(lang, key)


def show_metrics_info_popup(parent, current_lang: str):
    """Open the full Information pop-up for result-screen controls."""

    # Tear down any previous instance so re-opening (or a language switch) is clean.
    if hasattr(parent, "info_box") and parent.info_box.winfo_exists():
        parent.info_box.destroy()
    parent._info_open = True

    rtl = _is_rtl(current_lang)
    justify = "right" if rtl else "left"
    anchor = "e" if rtl else "w"

    def tr(key: str) -> str:
        return _translation(key, current_lang)

    def shape(text: str) -> str:
        return _shape_text(text, current_lang)

    f_title = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_TITLE,
        weight=theme.FONT_WEIGHT_BOLD,
    )
    f_section = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_BUTTON,
        weight=theme.FONT_WEIGHT_BOLD,
    )
    f_item = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_BODY,
        weight=theme.FONT_WEIGHT_BOLD,
    )
    f_body = ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL)
    f_hint = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_XS,
        slant=theme.FONT_SLANT_ITALIC,
    )

    parent.info_box = ctk.CTkFrame(
        parent,
        fg_color=theme.BG_CARD,
        border_width=theme.BORDER_WIDTH_ACTIVE,
        border_color=theme.BORDER_ACTIVE,
        corner_radius=theme.RADIUS_ROUND,
        width=theme.INFO_POPUP_WIDTH,
    )
    parent.info_box.place(relx=0.5, rely=0.5, anchor="center")
    parent.info_box.lift()

    ctk.CTkLabel(
        parent.info_box,
        text=shape(tr("info_title")),
        font=f_title,
        text_color=theme.TEXT_ACCENT,
        wraplength=theme.INFO_POPUP_WRAP,
        justify="center",
    ).pack(pady=(theme.SPACING_TITLE_TOP, theme.SPACING_COMPACT), padx=theme.SPACING_MEDIUM)

    body = ctk.CTkScrollableFrame(
        parent.info_box,
        fg_color=theme.TRANSPARENT,
        width=theme.INFO_POPUP_BODY_WIDTH,
        height=theme.INFO_POPUP_BODY_HEIGHT,
    )
    body.pack(
        padx=theme.SPACING_REGULAR,
        pady=(theme.SPACING_NONE, theme.SPACING_SMALL),
        fill="both",
        expand=True,
    )

    def section(title_key: str):
        ctk.CTkLabel(
            body,
            text=shape(tr(title_key)),
            font=f_section,
            text_color=theme.TEXT_ACCENT,
            wraplength=theme.INFO_POPUP_WRAP,
            justify=justify,
            anchor=anchor,
        ).pack(
            pady=(theme.SPACING_REGULAR, theme.SPACING_TINY),
            padx=theme.RADIUS_SMALL,
            fill="x",
        )

    def paragraph(text: str):
        ctk.CTkLabel(
            body,
            text=shape(text),
            font=f_body,
            text_color=theme.TEXT_MAIN,
            wraplength=theme.INFO_POPUP_WRAP,
            justify=justify,
            anchor=anchor,
        ).pack(
            pady=(theme.SPACING_NONE, theme.RADIUS_SMALL),
            padx=theme.RADIUS_SMALL,
            fill="x",
        )

    def item(title: str, description: str, hint_key: str | None = None):
        ctk.CTkLabel(
            body,
            text=shape(title),
            font=f_item,
            text_color=theme.TEXT_MAIN,
            wraplength=theme.INFO_POPUP_WRAP,
            justify=justify,
            anchor=anchor,
        ).pack(
            pady=(theme.SPACING_COMPACT, theme.SPACING_NONE),
            padx=theme.RADIUS_SMALL,
            fill="x",
        )
        ctk.CTkLabel(
            body,
            text=shape(description),
            font=f_body,
            text_color=theme.TEXT_MUTED,
            wraplength=theme.INFO_POPUP_WRAP,
            justify=justify,
            anchor=anchor,
        ).pack(padx=theme.RADIUS_SMALL, fill="x")
        if hint_key:
            ctk.CTkLabel(
                body,
                text=shape(tr(hint_key)),
                font=f_hint,
                text_color=theme.TEXT_ACCENT,
                wraplength=theme.INFO_POPUP_WRAP,
                justify=justify,
                anchor=anchor,
            ).pack(
                pady=(theme.SPACING_NONE, theme.SPACING_XS),
                padx=theme.RADIUS_SMALL,
                fill="x",
            )

    # How sorting works.
    section("info_sort_title")
    paragraph(tr("info_sort_desc"))

    # The five metrics, in dropdown display order.
    section("info_metrics_title")
    for key in METRIC_DISPLAY_ORDER:
        hint_key = "info_pref_higher" if key in _PREF_HIGHER else "info_pref_lower"
        item(tr(f"metric_{key}"), tr(f"info_metric_{key}"), hint_key)

    # New constraints section.
    section("info_constraints_title")
    paragraph(tr("info_constraints_desc"))
    for key in INFO_CONSTRAINT_KEYS:
        item(tr(f"constraint_{key}"), tr(f"info_constraint_{key}"))

    # Calendar toolbar controls section.
    section("info_calendar_buttons_title")
    paragraph(tr("info_calendar_buttons_desc"))
    for key in INFO_CALENDAR_BUTTON_KEYS:
        item(tr(f"info_button_{key}_title"), tr(f"info_button_{key}_desc"))

    def _close():
        parent._info_open = False
        parent.info_box.destroy()

    ctk.CTkButton(
        parent.info_box,
        text=format_text("close", current_lang),
        command=_close,
        width=theme.CONTROL_WIDTH_MONTH_LABEL,
        fg_color=theme.TEXT_ACCENT,
        hover_color=theme.BORDER_ACTIVE,
        text_color=theme.TEXT_ON_ACCENT,
    ).pack(pady=(theme.SPACING_TINY, theme.SPACING_REGULAR))


def show_metrics_values_popup(parent, current_lang: str, metrics):
    """Small on-demand popup with the current schedule's five metric values."""

    if hasattr(parent, "metrics_values_box") and parent.metrics_values_box.winfo_exists():
        parent.metrics_values_box.destroy()

    rtl = _is_rtl(current_lang)
    justify = "right" if rtl else "left"
    anchor = "e" if rtl else "w"

    def t(key: str) -> str:
        return _shape_text(_translation(key, current_lang), current_lang)

    def value_text(value):
        if value is None:
            return theme.EMPTY_VALUE_TEXT
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return theme.EMPTY_VALUE_TEXT
        if numeric == float("inf"):
            return "∞"
        if numeric.is_integer():
            return str(int(numeric))
        return f"{numeric:.1f}"

    if isinstance(metrics, dict):
        metrics_by_key = metrics
    elif metrics:
        metrics_by_key = {
            key: value for key, value in zip(METRIC_KEYS, metrics)
        }
    else:
        metrics_by_key = {}

    f_title = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_TITLE,
        weight=theme.FONT_WEIGHT_BOLD,
    )
    f_label = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_BODY,
        weight=theme.FONT_WEIGHT_BOLD,
    )
    f_value = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_ICON,
        weight=theme.FONT_WEIGHT_BOLD,
    )

    parent.metrics_values_box = ctk.CTkFrame(
        parent,
        fg_color=theme.BG_CARD,
        border_width=theme.BORDER_WIDTH_ACTIVE,
        border_color=theme.BORDER_ACTIVE,
        corner_radius=theme.RADIUS_ROUND,
        width=theme.METRICS_VALUES_POPUP_WIDTH,
    )
    parent.metrics_values_box.place(relx=0.5, rely=0.32, anchor="center")
    parent.metrics_values_box.lift()

    ctk.CTkLabel(
        parent.metrics_values_box,
        text=t("metrics_panel_title"),
        font=f_title,
        text_color=theme.TEXT_ACCENT,
        justify="center",
    ).pack(pady=(theme.SPACING_TITLE_TOP, theme.SPACING_SMALL), padx=theme.SPACING_TITLE_TOP, fill="x")

    body = ctk.CTkFrame(parent.metrics_values_box, fg_color=theme.TRANSPARENT)
    body.pack(fill="x", padx=theme.SPACING_LARGE, pady=(theme.SPACING_NONE, theme.SPACING_COMPACT))
    body.grid_columnconfigure(0, weight=1)
    body.grid_columnconfigure(1, weight=0)

    if not metrics_by_key:
        ctk.CTkLabel(
            body,
            text=t("metrics_values_empty"),
            font=f_label,
            text_color=theme.TEXT_MUTED,
            justify="center",
        ).grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=theme.SPACING_SMALL,
            pady=theme.FONT_SIZE_BUTTON,
        )
    else:
        for row_index, key in enumerate(METRIC_DISPLAY_ORDER):
            ctk.CTkLabel(
                body,
                text=t(f"metric_{key}"),
                font=f_label,
                text_color=theme.TEXT_MAIN,
                justify=justify,
                anchor=anchor,
                wraplength=theme.METRICS_VALUES_LABEL_WRAP,
            ).grid(
                row=row_index,
                column=0,
                sticky="ew",
                padx=(theme.SPACING_SMALL, theme.SPACING_REGULAR),
                pady=theme.RADIUS_SMALL,
            )
            ctk.CTkLabel(
                body,
                text=value_text(metrics_by_key.get(key)),
                font=f_value,
                text_color=theme.TEXT_ACCENT,
                width=theme.METRICS_VALUES_VALUE_WIDTH,
            ).grid(row=row_index, column=1, sticky="e", padx=theme.SPACING_SMALL, pady=theme.RADIUS_SMALL)

    def _close():
        parent.metrics_values_box.destroy()

    ctk.CTkButton(
        parent.metrics_values_box,
        text=format_text("close", current_lang),
        command=_close,
        width=theme.CONTROL_WIDTH_MONTH_LABEL,
        fg_color=theme.TEXT_ACCENT,
        hover_color=theme.BORDER_ACTIVE,
        text_color=theme.TEXT_ON_ACCENT,
    ).pack(pady=(theme.SPACING_TINY, theme.SPACING_REGULAR))
