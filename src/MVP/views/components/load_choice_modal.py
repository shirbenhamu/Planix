# src/MVP/views/components/load_choice_modal.py

import customtkinter as ctk
from src.MVP.views.ui_utils import format_text


def show_load_choice_popup(parent, current_lang: str, on_choice_callback=None,
                           title_key: str = "dates_load_title"):
    """
    In-app overlay popup (NOT an OS window) for choosing how to load a file:
      - "append"  -> add to existing data ("Add File")
      - "replace" -> overwrite existing data ("Overwrite Existing")

    Mirrors the attach/place pattern of date_edit_modal so it renders centered over
    the main window without being clipped by inner frames.

    title_key selects the header text (defaults to the dates title); pass
    "courses_load_title" to reuse the same chooser for the courses file.

    on_choice_callback(mode: str) is invoked with "append" or "replace" AFTER the
    popup closes.
    """
    # Get the real main window
    root_window = parent.winfo_toplevel()

    # Destroy previous popup if it exists
    if hasattr(root_window, "load_choice_box") and root_window.load_choice_box.winfo_exists():
        root_window.load_choice_box.destroy()

    # Overlay frame - attached to the top-level window, centered
    root_window.load_choice_box = ctk.CTkFrame(
        root_window,
        fg_color=("gray90", "gray15"),
        border_width=2,
        border_color="#87CEEB",
        corner_radius=15,
        width=420,
    )
    root_window.load_choice_box.place(relx=0.5, rely=0.5, anchor="center")
    root_window.load_choice_box.lift()

    # Fonts
    f_title = ctk.CTkFont(family="Rubik", size=22, weight="bold")
    f_reg = ctk.CTkFont(family="Rubik", size=14, weight="bold")
    f_small = ctk.CTkFont(family="Rubik", size=13)

    # Main content container
    content = ctk.CTkFrame(root_window.load_choice_box, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=25, pady=20)

    # Title
    ctk.CTkLabel(
        content,
        text=format_text(title_key, current_lang),
        font=f_title,
        text_color="#87CEEB",
        wraplength=360,
        justify="center",
    ).pack(pady=(5, 20))

    def _choose(mode):
        root_window.load_choice_box.destroy()
        if on_choice_callback:
            on_choice_callback(mode)

    # Add file (append)
    add_btn = ctk.CTkButton(
        content,
        text=format_text("add_file", current_lang),
        font=f_reg,
        fg_color="#3b8ed0",
        hover_color="#2f7ab0",
        text_color="#ffffff",
        height=44,
        corner_radius=8,
        command=lambda: _choose("append"),
    )
    add_btn.pack(fill="x", pady=6, padx=10)

    # Overwrite existing (replace)
    overwrite_btn = ctk.CTkButton(
        content,
        text=format_text("overwrite_file", current_lang),
        font=f_reg,
        fg_color="transparent",
        border_width=2,
        border_color="#87CEEB",
        hover_color=("gray80", "gray25"),
        text_color=("black", "white"),
        height=44,
        corner_radius=8,
        command=lambda: _choose("replace"),
    )
    overwrite_btn.pack(fill="x", pady=6, padx=10)

    # Cancel
    btn_cancel = ctk.CTkButton(
        content,
        text=format_text("cancel", current_lang),
        fg_color="transparent",
        border_width=1,
        border_color="gray",
        text_color=("black", "white"),
        font=f_small,
        height=34,
        corner_radius=8,
        command=root_window.load_choice_box.destroy,
        width=120,
    )
    btn_cancel.pack(pady=(14, 5))