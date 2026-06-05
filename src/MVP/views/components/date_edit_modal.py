# src/MVP/views/components/date_edit_modal.py

import customtkinter as ctk
from src.MVP.views.ui_utils import format_text
from typing import List
from datetime import date

def show_date_edit_popup(parent, current_lang: str, exam_periods_data: List = None, on_save_callback=None):
    """
    Opens an in-app popup for editing exam period dates.

    The popup is attached to the top-level window instead of a nested component,
    so it will not be clipped by inner frames.
    """

    # Get the real main window
    root_window = parent.winfo_toplevel()

    # Destroy previous popup if it exists
    if hasattr(root_window, "date_popup_box") and root_window.date_popup_box.winfo_exists():
        root_window.date_popup_box.destroy()

    # Popup frame - ללא height קבוע כדי שיגדל בהתאם למספר השורות!
    root_window.date_popup_box = ctk.CTkFrame(
        root_window,
        fg_color=("gray90", "gray15"),
        border_width=2,
        border_color="#87CEEB",
        corner_radius=15,
        width=500
    )

    root_window.date_popup_box.place(relx=0.5, rely=0.5, anchor="center")

    # Fonts
    f_title = ctk.CTkFont(family="Rubik", size=22, weight="bold")
    f_reg = ctk.CTkFont(family="Rubik", size=14, weight="bold")
    f_small = ctk.CTkFont(family="Rubik", size=13)

    # Main content container
    content_frame = ctk.CTkFrame(
        root_window.date_popup_box,
        fg_color="transparent"
    )
    content_frame.pack(fill="both", expand=True, padx=25, pady=20)

    # Title
    title_text = format_text("edit_dates", current_lang)

    ctk.CTkLabel(
        content_frame,
        text=title_text,
        font=f_title,
        text_color="#87CEEB",
        wraplength=430,
        justify="center"
    ).pack(pady=(5, 20))

    # Case: no dates loaded
    if not exam_periods_data:
        msg = format_text("no_dates_loaded", current_lang)

        ctk.CTkLabel(
            content_frame,
            text=msg,
            font=f_reg,
            text_color="gray50",
            wraplength=420,
            justify="center",
            anchor="center"
        ).pack(pady=(25, 35), padx=20)

        btn_close = ctk.CTkButton(
            content_frame,
            text=format_text("close", current_lang),
            fg_color="transparent",
            border_width=1,
            border_color="gray",
            text_color=("black", "white"),
            font=f_reg,
            command=root_window.date_popup_box.destroy,
            width=120
        )

        btn_close.pack(pady=(5, 10))
        return

    def create_date_row(container, period_info, start_val, end_val):
        """
        Creates one editable date row inside the popup.
        """
        row_frame = ctk.CTkFrame(container, fg_color="transparent")
        row_frame.pack(fill="x", padx=10, pady=8)

        sem_raw = period_info.semester.strip().upper()
        sem_key = f"semester_{sem_raw}"
        sem_display = format_text(sem_key, current_lang)

        if sem_display == f"\u200F{sem_key}\u200F" or sem_display == sem_key:
            sem_display = sem_raw

        moed = period_info.moed
        moed_prefix = format_text("moed", current_lang)
        sem_prefix = format_text("semester", current_lang)

        if current_lang == "he":
            lbl_text = f"\u200F{sem_prefix} {sem_display} | {moed_prefix} {moed}׳\u200F"
        else:
            lbl_text = f"{sem_display} {sem_prefix} | {moed_prefix} {moed}"

        start_ph = (
            start_val.strftime("%d/%m/%Y")
            if isinstance(start_val, date)
            else format_text("date_format", current_lang)
        )

        end_ph = (
            end_val.strftime("%d/%m/%Y")
            if isinstance(end_val, date)
            else format_text("date_format", current_lang)
        )

        # 3 equal columns
        row_frame.grid_columnconfigure(0, weight=1)
        row_frame.grid_columnconfigure(1, weight=1)
        row_frame.grid_columnconfigure(2, weight=1)

        if current_lang == "he":
            ctk.CTkLabel(
                row_frame,
                text=lbl_text,
                font=f_reg,
                anchor="e"
            ).grid(row=0, column=2, sticky="e", padx=10)

            ctk.CTkEntry(
                row_frame,
                placeholder_text=end_ph,
                font=f_small,
                width=115,
                justify="center"
            ).grid(row=0, column=1, padx=5)

            ctk.CTkEntry(
                row_frame,
                placeholder_text=start_ph,
                font=f_small,
                width=115,
                justify="center"
            ).grid(row=0, column=0, padx=5)

        else:
            ctk.CTkLabel(
                row_frame,
                text=lbl_text,
                font=f_reg,
                anchor="w"
            ).grid(row=0, column=0, sticky="w", padx=10)

            ctk.CTkEntry(
                row_frame,
                placeholder_text=start_ph,
                font=f_small,
                width=115,
                justify="center"
            ).grid(row=0, column=1, padx=5)

            ctk.CTkEntry(
                row_frame,
                placeholder_text=end_ph,
                font=f_small,
                width=115,
                justify="center"
            ).grid(row=0, column=2, padx=5)

    # Date rows
    rows_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
    rows_frame.pack(fill="both", expand=True)

    for period in exam_periods_data:
        create_date_row(rows_frame, period, period.start_date, period.end_date)

    # Divider
    ctk.CTkFrame(
        content_frame,
        height=1,
        fg_color=("gray80", "gray30")
    ).pack(fill="x", padx=20, pady=(15, 15))

    # Excluded date row
    ex_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
    ex_frame.pack(fill="x", padx=10, pady=5)

    ex_lbl = ctk.CTkLabel(
        ex_frame,
        text=format_text("add_excluded_date", current_lang),
        font=f_reg,
        wraplength=250,
        justify="right" if current_lang == "he" else "left"
    )

    ex_lbl.pack(
        side="right" if current_lang == "he" else "left",
        padx=10
    )

    ex_entry = ctk.CTkEntry(
        ex_frame,
        placeholder_text=format_text("date_format", current_lang),
        font=f_small,
        width=130,
        justify="center"
    )

    ex_entry.pack(
        side="right" if current_lang == "he" else "left",
        padx=5
    )

    # Buttons
    action_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
    action_frame.pack(fill="x", pady=(25, 5))

    btn_close = ctk.CTkButton(
        action_frame,
        text=format_text("close", current_lang),
        fg_color="transparent",
        border_width=1,
        border_color="gray",
        text_color=("black", "white"),
        font=f_reg,
        command=root_window.date_popup_box.destroy,
        width=100
    )

    btn_close.pack(side="left", padx=30)

    btn_save = ctk.CTkButton(
        action_frame,
        text=format_text("save", current_lang),
        fg_color="#2ecc71",
        hover_color="#27ae60",
        font=f_reg,
        command=lambda: [
            root_window.date_popup_box.destroy(),
            on_save_callback() if on_save_callback else None
        ],
        width=100
    )

    btn_save.pack(side="right", padx=30)