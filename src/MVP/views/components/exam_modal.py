# src/MVP/views/components/exam_modal.py
import customtkinter as ctk
from src.MVP.views.ui_utils import format_text, TRANSLATIONS

def show_exam_popup(parent, exam_data: dict, current_lang: str):
    if hasattr(parent, 'popup_box') and parent.popup_box.winfo_exists():
        parent.popup_box.destroy()

    # נשמר כדי שאפשר יהיה לבנות מחדש בשפה אחרת כשמחליפים שפה בזמן שהחלון פתוח
    parent._last_exam_data = exam_data

    # בלי גובה קבוע ובלי pack_propagate(False) — כך החלון גדל לפי התוכן ולא נחתך (כמו מודאל עריכת התאריכים)
    parent.popup_box = ctk.CTkFrame(parent, fg_color=("gray90", "gray15"), border_width=2, border_color="#3b8ed0", corner_radius=15, width=420)
    parent.popup_box.place(relx=0.5, rely=0.5, anchor="center")
    parent.popup_box.lift()

    f_title, f_reg = ctk.CTkFont(family="Rubik", size=18, weight="bold"), ctk.CTkFont(family="Rubik", size=14)
    WRAP = 360  # רוחב גלישה — טקסט ארוך (למשל רשימת תוכניות) יירד שורה במקום להיחתך
    just = "right" if current_lang == "he" else "left"  # התווית מובילה מהצד הנכון, גם כששורה נגלשת

    def detail_line(label_key, value):
        # בעברית עוטף את כל השורה ב-RLM כדי שתיקרא "תווית: ערך" ולא תתהפך ב-BiDi
        label = TRANSLATIONS[label_key][current_lang]
        if current_lang == "he":
            return f"\u200F{label} {value}\u200F"
        return f"{label} {value}"

    # כותרת — שם הקורס המלא (במרכז)
    title_text = exam_data.get('short_name', 'N/A')
    ctk.CTkLabel(
        parent.popup_box,
        text=f"\u200F{title_text}\u200F" if current_lang == "he" else title_text,
        font=f_title, text_color="#3b8ed0", wraplength=WRAP, justify="center",
    ).pack(pady=(20, 15), padx=20)

    # קוד קורס
    ctk.CTkLabel(
        parent.popup_box, text=detail_line("course_id", exam_data.get('course_id', 'N/A')),
        font=f_reg, wraplength=WRAP, justify=just,
    ).pack(pady=3, padx=20, fill="x")

    # סוג (חובה / בחירה)
    c_type = TRANSLATIONS["type_hova"][current_lang] if exam_data.get('type') == "ח" else TRANSLATIONS["type_bhira"][current_lang]
    ctk.CTkLabel(
        parent.popup_box, text=detail_line("type", c_type),
        font=f_reg, wraplength=WRAP, justify=just,
    ).pack(pady=3, padx=20, fill="x")

    # תוכנית/Prog — התוכניות שהקורס משויך אליהן; "תוכנית:" מימין והתוכניות זורמות וגולשות שמאלה
    ctk.CTkLabel(
        parent.popup_box, text=detail_line("program", exam_data.get('program', 'N/A')),
        font=f_reg, wraplength=WRAP, justify=just,
    ).pack(pady=3, padx=20, fill="x")

    ctk.CTkButton(
        parent.popup_box, text=format_text("close", current_lang),
        command=parent.popup_box.destroy, width=120,
    ).pack(pady=(20, 15))