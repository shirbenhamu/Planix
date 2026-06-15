# src/MVP/views/components/info_modal.py
"""
Help modal explaining the ranking features (PLAN-400): the five section-3
metrics, how sorting works, and Refresh vs. Sync. Fully bilingual (he/en) and
theme-driven, so it follows the app's day/night appearance automatically.
"""
import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import TRANSLATIONS, format_text
from src.MVP.views.components.ranking_bar import METRIC_DISPLAY_ORDER


def show_metrics_info_popup(parent, current_lang: str):
    # Tear down any previous instance so re-opening (or a language switch) is clean.
    if hasattr(parent, "info_box") and parent.info_box.winfo_exists():
        parent.info_box.destroy()
    parent._info_open = True  # let the view rebuild on a language switch if it wants

    rtl = current_lang == "he"
    justify = "right" if rtl else "left"
    anchor = "e" if rtl else "w"

    def t(key):
        text = TRANSLATIONS.get(key, {}).get(current_lang, key)
        return f"\u200F{text}\u200F" if rtl else text

    f_title = ctk.CTkFont(family=theme.FONT_FAMILY, size=18, weight="bold")
    f_section = ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold")
    f_body = ctk.CTkFont(family=theme.FONT_FAMILY, size=12)

    parent.info_box = ctk.CTkFrame(
        parent, fg_color=theme.BG_CARD, border_width=2,
        border_color=theme.BORDER_ACTIVE, corner_radius=15, width=520,
    )
    parent.info_box.place(relx=0.5, rely=0.5, anchor="center")
    parent.info_box.lift()

    WRAP = 460

    ctk.CTkLabel(
        parent.info_box, text=t("info_title"), font=f_title,
        text_color=theme.TEXT_ACCENT, wraplength=WRAP, justify="center",
    ).pack(pady=(18, 10), padx=20)

    body = ctk.CTkScrollableFrame(
        parent.info_box, fg_color=theme.TRANSPARENT, width=480, height=380)
    body.pack(padx=16, pady=(0, 8), fill="both", expand=True)

    def section(title_key):
        ctk.CTkLabel(
            body, text=t(title_key), font=f_section, text_color=theme.TEXT_ACCENT,
            wraplength=WRAP, justify=justify, anchor=anchor,
        ).pack(pady=(12, 2), padx=6, fill="x")

    def paragraph(text):
        ctk.CTkLabel(
            body, text=text, font=f_body, text_color=theme.TEXT_MAIN,
            wraplength=WRAP, justify=justify, anchor=anchor,
        ).pack(pady=2, padx=6, fill="x")

    # Sorting
    section("info_sort_title")
    paragraph(t("info_sort_desc"))

    # The five metrics — name (bold) + description, in the display order.
    section("info_metrics_title")
    for key in METRIC_DISPLAY_ORDER:
        name = TRANSLATIONS[f"metric_{key}"][current_lang]
        desc = TRANSLATIONS[f"info_metric_{key}"][current_lang]
        line = f"{name} — {desc}"
        paragraph(f"\u200F{line}\u200F" if rtl else line)

    # Refresh vs. Sync
    section("info_refresh_title")
    paragraph(t("info_refresh_desc"))

    def _close():
        parent._info_open = False
        parent.info_box.destroy()

    ctk.CTkButton(
        parent.info_box, text=format_text("close", current_lang),
        command=_close, width=120, fg_color=theme.TEXT_ACCENT,
        hover_color=theme.BORDER_ACTIVE,
    ).pack(pady=(4, 16))
