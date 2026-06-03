# src/MVP/views/components/ui_components.py

import customtkinter as ctk
from src.MVP.views import theme

def create_card(parent, **kwargs):
    """יוצר כרטיסייה (Card) אחידה עם פינות מעוגלות וגבולות עדינים"""
    return ctk.CTkFrame(
        parent,
        fg_color=theme.BG_CARD,
        border_width=1,
        border_color=theme.BORDER_DEFAULT,
        corner_radius=theme.RADIUS_CARD,
        **kwargs
    )

def add_card_hover(card):
    """מוסיף אפקט הארה למסגרת של כרטיסייה במעבר עכבר"""
    def on_enter(event):
        card.configure(border_color=theme.BORDER_ACTIVE, fg_color=theme.BG_CARD_HOVER)

    def on_leave(event):
        card.configure(border_color=theme.BORDER_DEFAULT, fg_color=theme.BG_CARD)

    card.bind("<Enter>", on_enter)
    card.bind("<Leave>", on_leave)
    for child in card.winfo_children():
        child.bind("<Enter>", on_enter)
        child.bind("<Leave>", on_leave)

def create_icon_button(parent, text, command, **kwargs):
    """כפתור מרובע גדול עם אייקון"""
    return ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family=theme.FONT_ICON, size=32),
        fg_color=theme.TRANSPARENT,
        text_color=theme.TEXT_MAIN,
        hover_color=theme.BG_CARD_HOVER,
        width=60, 
        height=60, 
        corner_radius=theme.RADIUS_BUTTON,
        command=command,
        **kwargs
    )

def create_primary_action_button(parent, text, command, **kwargs):
    """כפתור פעולה ראשי אלגנטי ונקי בסגנון Bootstrap"""
    return ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=28, weight="bold"),
        fg_color=theme.SUCCESS,
        hover_color=theme.SUCCESS_HOVER,
        text_color="white",
        height=64,
        corner_radius=theme.RADIUS_BUTTON,
        command=command,
        **kwargs
    )

def create_secondary_button(parent, text, command, **kwargs):
    """כפתור משני (Outline) בסגנון Bootstrap - רקע שקוף עם מסגרת צבעונית"""
    return ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold"),
        fg_color=theme.TRANSPARENT,
        border_width=2,
        border_color=theme.BORDER_ACTIVE,
        hover_color=theme.BG_CARD_HOVER,
        text_color=theme.TEXT_ACCENT,
        height=40,
        corner_radius=theme.RADIUS_BUTTON,
        command=command,
        **kwargs
    )