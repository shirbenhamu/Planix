# src/MVP/views/components/exam_modal.py
import customtkinter as ctk
from src.MVP.views.ui_utils import format_text, TRANSLATIONS

def show_exam_popup(parent, exam_data: dict, current_lang: str):
    if hasattr(parent, 'popup_box') and parent.popup_box.winfo_exists():
        parent.popup_box.destroy()

    # Saved so it can be rebuilt in another language when switching language while the window is open
    parent._last_exam_data = exam_data

    # No fixed height and no pack_propagate(False) — so the window grows with the content and isn't clipped (like the date-edit modal)
    parent.popup_box = ctk.CTkFrame(parent, fg_color=("gray90", "gray15"), border_width=2, border_color="#3b8ed0", corner_radius=15, width=420)
    parent.popup_box.place(relx=0.5, rely=0.5, anchor="center")
    parent.popup_box.lift()

    f_title, f_reg = ctk.CTkFont(family="Rubik", size=18, weight="bold"), ctk.CTkFont(family="Rubik", size=14)
    WRAP = 360  # Wrap width — long text (e.g. a program list) wraps to a new line instead of being clipped
    just = "right" if current_lang == "he" else "left"  # The label leads from the correct side, even when a line wraps

    def detail_line(label_key, value):
        # In Hebrew, wrap the whole line in RLM so it reads "label: value" and doesn't flip under BiDi
        label = TRANSLATIONS[label_key][current_lang]
        if current_lang == "he":
            return f"\u200F{label} {value}\u200F"
        return f"{label} {value}"

    # Title — the full course name (centered)
    title_text = exam_data.get('short_name', 'N/A')
    ctk.CTkLabel(
        parent.popup_box,
        text=f"\u200F{title_text}\u200F" if current_lang == "he" else title_text,
        font=f_title, text_color="#3b8ed0", wraplength=WRAP, justify="center",
    ).pack(pady=(20, 15), padx=20)

    # Course code
    ctk.CTkLabel(
        parent.popup_box, text=detail_line("course_id", exam_data.get('course_id', 'N/A')),
        font=f_reg, wraplength=WRAP, justify=just,
    ).pack(pady=3, padx=20, fill="x")

    # Type (Mandatory / Elective)
    c_type = TRANSLATIONS["type_hova"][current_lang] if exam_data.get('type') == "ח" else TRANSLATIONS["type_bhira"][current_lang]
    ctk.CTkLabel(
        parent.popup_box, text=detail_line("type", c_type),
        font=f_reg, wraplength=WRAP, justify=just,
    ).pack(pady=3, padx=20, fill="x")

    # Program/Prog — the programs the course belongs to; "Program:" on the right and the programs flow and wrap to the left
    ctk.CTkLabel(
        parent.popup_box, text=detail_line("program", exam_data.get('program', 'N/A')),
        font=f_reg, wraplength=WRAP, justify=just,
    ).pack(pady=3, padx=20, fill="x")

    ctk.CTkButton(
        parent.popup_box, text=format_text("close", current_lang),
        command=parent.popup_box.destroy, width=120,
    ).pack(pady=(20, 15))