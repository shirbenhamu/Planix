# src/MVP/views/components/export_choice_modal.py

import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import format_text


def show_export_choice_popup(parent, current_lang: str, on_choice_callback=None):
    """Show the PLAN-556 export choice popup.

    The user chooses one of two flows:
      - "text"     -> save the active board as the legacy text file.
      - "calendar" -> save an RFC 5545 .ics file and open it with the default
                      local calendar application.
    """
    root_window = parent.winfo_toplevel()

    if hasattr(root_window, "export_choice_box") and root_window.export_choice_box.winfo_exists():
        root_window.export_choice_box.destroy()

    root_window.export_choice_box = ctk.CTkFrame(
        root_window,
        fg_color=theme.BG_CARD,
        border_width=theme.BORDER_WIDTH_ACTIVE,
        border_color=theme.BORDER_ACTIVE,
        corner_radius=theme.RADIUS_ROUND,
        width=theme.EXPORT_POPUP_WIDTH if hasattr(theme, "EXPORT_POPUP_WIDTH") else 440,
    )

    def _show_centered():
        root_window.update_idletasks()
        root_window.export_choice_box.place(relx=0.5, rely=0.5, anchor="center")
        root_window.export_choice_box.lift()

    f_title = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_TITLE,
        weight=theme.FONT_WEIGHT_BOLD,
    )
    f_body = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_SMALL,
    )
    f_button = ctk.CTkFont(
        family=theme.FONT_FAMILY,
        size=theme.FONT_SIZE_BUTTON,
        weight=theme.FONT_WEIGHT_BOLD,
    )

    content = ctk.CTkFrame(root_window.export_choice_box, fg_color=theme.TRANSPARENT)
    content.pack(fill="both", expand=True, padx=theme.SPACING_TITLE_TOP, pady=theme.SPACING_REGULAR)

    ctk.CTkLabel(
        content,
        text=format_text("export_choice_title", current_lang),
        font=f_title,
        text_color=theme.TEXT_ACCENT,
        wraplength=380,
        justify="center",
    ).pack(pady=(theme.SPACING_TINY, theme.SPACING_SMALL))

    ctk.CTkLabel(
        content,
        text=format_text("export_choice_desc", current_lang),
        font=f_body,
        text_color=theme.TEXT_MUTED,
        wraplength=380,
        justify="right" if current_lang == "he" else "left",
    ).pack(fill="x", padx=theme.SPACING_SMALL, pady=(theme.SPACING_NONE, theme.SPACING_SMALL))

    def _choose(choice: str):
        root_window.export_choice_box.destroy()
        if on_choice_callback:
            on_choice_callback(choice)

    ctk.CTkButton(
        content,
        text=format_text("export_text_file", current_lang),
        font=f_button,
        fg_color=theme.TEXT_ACCENT,
        hover_color=theme.ACCENT_HOVER,
        text_color=theme.TEXT_ON_ACCENT,
        height=theme.CONTROL_HEIGHT_LARGE if hasattr(theme, "CONTROL_HEIGHT_LARGE") else 44,
        corner_radius=theme.RADIUS_SMALL,
        command=lambda: _choose("text"),
    ).pack(fill="x", padx=theme.SPACING_SMALL, pady=theme.SPACING_XS)

    ctk.CTkButton(
        content,
        text=format_text("export_local_calendar", current_lang),
        font=f_button,
        fg_color=theme.SUCCESS,
        hover_color=theme.SUCCESS_HOVER,
        text_color=theme.TEXT_ON_ACCENT,
        height=theme.CONTROL_HEIGHT_LARGE if hasattr(theme, "CONTROL_HEIGHT_LARGE") else 44,
        corner_radius=theme.RADIUS_SMALL,
        command=lambda: _choose("calendar"),
    ).pack(fill="x", padx=theme.SPACING_SMALL, pady=theme.SPACING_XS)

    ctk.CTkButton(
        content,
        text=format_text("cancel", current_lang),
        font=f_body,
        fg_color=theme.TRANSPARENT,
        border_width=theme.BORDER_WIDTH_THIN if hasattr(theme, "BORDER_WIDTH_THIN") else 1,
        border_color=theme.BORDER_DEFAULT,
        text_color=theme.TEXT_MAIN,
        height=theme.CONTROL_HEIGHT_SMALL,
        corner_radius=theme.RADIUS_SMALL,
        width=theme.CONTROL_WIDTH_MONTH_LABEL,
        command=root_window.export_choice_box.destroy,
    ).pack(pady=(theme.SPACING_SMALL, theme.SPACING_TINY))

    _show_centered()
