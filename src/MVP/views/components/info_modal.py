# src/MVP/views/components/info_modal.py
"""
Help modals for the ranking features (PLAN-400):
  * show_metrics_info_popup  — explains how sorting works and what each of the
    five section-3 metrics measures (bold name + plain description + a hint on
    whether higher or lower is better).
  * show_metrics_values_popup — the current schedule's five metric values.

Both are fully bilingual (he/en) and theme-driven, so they follow the app's
day/night appearance automatically.
"""
import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import TRANSLATIONS, format_text
from src.MVP.views.components.ranking_bar import METRIC_DISPLAY_ORDER
from src.metrics.metrics_calculator import METRIC_KEYS

# Metrics where a HIGHER value is the better outcome (the rest: lower is better).
_PREF_HIGHER = {"avg_gap_all", "min_gap_mandatory", "mandatory_span"}


def show_metrics_info_popup(parent, current_lang: str):
    # Tear down any previous instance so re-opening (or a language switch) is clean.
    if hasattr(parent, "info_box") and parent.info_box.winfo_exists():
        parent.info_box.destroy()
    parent._info_open = True

    rtl = current_lang == "he"
    justify = "right" if rtl else "left"
    anchor = "e" if rtl else "w"

    def tr(key):
        return TRANSLATIONS.get(key, {}).get(current_lang, key)

    def shape(text):
        # Wrap Hebrew lines in RTL marks so mixed text/punctuation reads correctly.
        return f"\u200F{text}\u200F" if rtl else text

    f_title = ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold")
    f_section = ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold")
    f_item = ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold")
    f_body = ctk.CTkFont(family=theme.FONT_FAMILY, size=12)
    f_hint = ctk.CTkFont(family=theme.FONT_FAMILY, size=11, slant="italic")
    WRAP = 460

    parent.info_box = ctk.CTkFrame(
        parent, fg_color=theme.BG_CARD, border_width=2,
        border_color=theme.BORDER_ACTIVE, corner_radius=15, width=520,
    )
    parent.info_box.place(relx=0.5, rely=0.5, anchor="center")
    parent.info_box.lift()

    ctk.CTkLabel(
        parent.info_box, text=tr("info_title"), font=f_title,
        text_color=theme.TEXT_ACCENT, wraplength=WRAP, justify="center",
    ).pack(pady=(18, 10), padx=20)

    body = ctk.CTkScrollableFrame(
        parent.info_box, fg_color=theme.TRANSPARENT, width=480, height=380)
    body.pack(padx=16, pady=(0, 8), fill="both", expand=True)

    def section(title_key):
        ctk.CTkLabel(
            body, text=shape(tr(title_key)), font=f_section, text_color=theme.TEXT_ACCENT,
            wraplength=WRAP, justify=justify, anchor=anchor,
        ).pack(pady=(16, 4), padx=6, fill="x")

    def paragraph(text):
        ctk.CTkLabel(
            body, text=shape(text), font=f_body, text_color=theme.TEXT_MAIN,
            wraplength=WRAP, justify=justify, anchor=anchor,
        ).pack(pady=(0, 6), padx=6, fill="x")

    def metric_item(key):
        # Bold name, then a plain description, then a small better-direction hint.
        ctk.CTkLabel(
            body, text=shape(tr(f"metric_{key}")), font=f_item,
            text_color=theme.TEXT_MAIN, wraplength=WRAP, justify=justify, anchor=anchor,
        ).pack(pady=(10, 0), padx=6, fill="x")
        ctk.CTkLabel(
            body, text=shape(tr(f"info_metric_{key}")), font=f_body,
            text_color=theme.TEXT_MUTED, wraplength=WRAP, justify=justify, anchor=anchor,
        ).pack(padx=6, fill="x")
        pref_key = "info_pref_higher" if key in _PREF_HIGHER else "info_pref_lower"
        ctk.CTkLabel(
            body, text=shape(tr(pref_key)), font=f_hint,
            text_color=theme.TEXT_ACCENT, wraplength=WRAP, justify=justify, anchor=anchor,
        ).pack(pady=(0, 2), padx=6, fill="x")

    # How sorting works.
    section("info_sort_title")
    paragraph(tr("info_sort_desc"))

    # The five metrics, in dropdown display order.
    section("info_metrics_title")
    for key in METRIC_DISPLAY_ORDER:
        metric_item(key)

    def _close():
        parent._info_open = False
        parent.info_box.destroy()

    ctk.CTkButton(
        parent.info_box, text=format_text("close", current_lang),
        command=_close, width=120, fg_color=theme.TEXT_ACCENT,
        hover_color=theme.BORDER_ACTIVE,
    ).pack(pady=(4, 16))


def show_metrics_values_popup(parent, current_lang: str, metrics):
    """Small on-demand popup with the current schedule's five metric values."""

    if hasattr(parent, "metrics_values_box") and parent.metrics_values_box.winfo_exists():
        parent.metrics_values_box.destroy()

    rtl = current_lang == "he"
    justify = "right" if rtl else "left"
    anchor = "e" if rtl else "w"

    def t(key):
        text = TRANSLATIONS.get(key, {}).get(current_lang, key)
        return f"\u200F{text}\u200F" if rtl else text

    def value_text(value):
        if value is None:
            return "—"
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "—"
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

    f_title = ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold")
    f_label = ctk.CTkFont(family=theme.FONT_FAMILY, size=13, weight="bold")
    f_value = ctk.CTkFont(family=theme.FONT_FAMILY, size=15, weight="bold")

    parent.metrics_values_box = ctk.CTkFrame(
        parent,
        fg_color=theme.BG_CARD,
        border_width=2,
        border_color=theme.BORDER_ACTIVE,
        corner_radius=15,
        width=420,
    )
    parent.metrics_values_box.place(relx=0.5, rely=0.32, anchor="center")
    parent.metrics_values_box.lift()

    ctk.CTkLabel(
        parent.metrics_values_box,
        text=t("metrics_panel_title"),
        font=f_title,
        text_color=theme.TEXT_ACCENT,
        justify="center",
    ).pack(pady=(18, 12), padx=18, fill="x")

    body = ctk.CTkFrame(parent.metrics_values_box, fg_color=theme.TRANSPARENT)
    body.pack(fill="x", padx=22, pady=(0, 10))
    body.grid_columnconfigure(0, weight=1)
    body.grid_columnconfigure(1, weight=0)

    if not metrics_by_key:
        ctk.CTkLabel(
            body,
            text=t("metrics_values_empty"),
            font=f_label,
            text_color=theme.TEXT_MUTED,
            justify="center",
        ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=14)
    else:
        for row_index, key in enumerate(METRIC_DISPLAY_ORDER):
            ctk.CTkLabel(
                body,
                text=t(f"metric_{key}"),
                font=f_label,
                text_color=theme.TEXT_MAIN,
                justify=justify,
                anchor=anchor,
                wraplength=290,
            ).grid(row=row_index, column=0, sticky="ew", padx=(8, 16), pady=7)
            ctk.CTkLabel(
                body,
                text=value_text(metrics_by_key.get(key)),
                font=f_value,
                text_color=theme.TEXT_ACCENT,
                width=70,
            ).grid(row=row_index, column=1, sticky="e", padx=8, pady=7)

    def _close():
        parent.metrics_values_box.destroy()

    ctk.CTkButton(
        parent.metrics_values_box,
        text=format_text("close", current_lang),
        command=_close,
        width=120,
        fg_color=theme.TEXT_ACCENT,
        hover_color=theme.BORDER_ACTIVE,
    ).pack(pady=(4, 16))
