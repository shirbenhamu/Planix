# src/MVP/views/components/exam_modal.py
import customtkinter as ctk
from src.MVP.views.ui_utils import format_text

def show_exam_popup(parent, exam_data: dict, current_lang: str):
    if hasattr(parent, 'popup_box') and parent.popup_box.winfo_exists():
        parent.popup_box.destroy()
        
    parent.popup_box = ctk.CTkFrame(parent, fg_color=("gray90", "gray15"), border_width=2, border_color="#3b8ed0", corner_radius=15, width=350, height=220)
    parent.popup_box.place(relx=0.5, rely=0.5, anchor="center")
    parent.popup_box.pack_propagate(False) 
    
    c_type = format_text("type_hova", current_lang) if exam_data.get('type') == "ח" else format_text("type_bhira", current_lang)
    
    f_title, f_reg = ctk.CTkFont(family="Rubik", size=18, weight="bold"), ctk.CTkFont(family="Rubik", size=14)
    
    title_text = exam_data.get('short_name', 'N/A')
    ctk.CTkLabel(parent.popup_box, text=f"\u200F{title_text}\u200F" if current_lang == "he" else title_text, font=f_title, text_color="#3b8ed0").pack(pady=(20, 15))
    ctk.CTkLabel(parent.popup_box, text=f"{format_text('course_id', current_lang)} {exam_data.get('course_id', 'N/A')}", font=f_reg).pack(pady=3)
    ctk.CTkLabel(parent.popup_box, text=f"{format_text('type', current_lang)} {c_type}", font=f_reg).pack(pady=3)
    ctk.CTkLabel(parent.popup_box, text=f"{format_text('program', current_lang)} {exam_data.get('program', 'N/A')}", font=f_reg).pack(pady=3)
    
    ctk.CTkButton(parent.popup_box, text=format_text("close", current_lang), command=parent.popup_box.destroy, width=120).pack(pady=(20, 10))