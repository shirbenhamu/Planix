# src/MVP/views/components/confirm_modal.py

import customtkinter as ctk


def show_confirm_popup(
    parent,
    title: str,
    message: str,
    confirm_text: str,
    cancel_text: str,
    on_confirm=None,
):
    """In-app overlay confirm dialog (NOT an OS Toplevel, so no input-grab/focus
    pitfalls). Mirrors the attach/place pattern of load_choice_modal: it renders
    centered over the main window. ``on_confirm`` runs AFTER the popup closes."""
    root_window = parent.winfo_toplevel()

    if hasattr(root_window, "confirm_box") and root_window.confirm_box.winfo_exists():
        root_window.confirm_box.destroy()

    root_window.confirm_box = ctk.CTkFrame(
        root_window,
        fg_color=("gray90", "gray15"),
        border_width=2,
        border_color="#87CEEB",
        corner_radius=15,
        width=480,
    )
    root_window.confirm_box.place(relx=0.5, rely=0.5, anchor="center")
    root_window.confirm_box.lift()

    f_title = ctk.CTkFont(family="Rubik", size=22, weight="bold")
    f_msg = ctk.CTkFont(family="Rubik", size=14)
    f_btn = ctk.CTkFont(family="Rubik", size=14, weight="bold")

    content = ctk.CTkFrame(root_window.confirm_box, fg_color="transparent")
    content.pack(fill="both", expand=True, padx=25, pady=20)

    ctk.CTkLabel(
        content, text=title, font=f_title, text_color="#87CEEB",
        wraplength=420, justify="center",
    ).pack(pady=(5, 12))

    ctk.CTkLabel(
        content, text=message, font=f_msg, text_color=("black", "white"),
        wraplength=420, justify="center",
    ).pack(pady=(0, 18))

    def _confirm():
        root_window.confirm_box.destroy()
        if on_confirm:
            on_confirm()

    ctk.CTkButton(
        content, text=confirm_text, font=f_btn,
        fg_color="#2e8b57", hover_color="#256f46", text_color="#ffffff",
        height=44, corner_radius=8, command=_confirm,
    ).pack(fill="x", pady=6, padx=10)

    ctk.CTkButton(
        content, text=cancel_text, fg_color="transparent",
        border_width=1, border_color="gray", text_color=("black", "white"),
        font=f_btn, height=36, corner_radius=8,
        command=root_window.confirm_box.destroy, width=140,
    ).pack(pady=(10, 5))
