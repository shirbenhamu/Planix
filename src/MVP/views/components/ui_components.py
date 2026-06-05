# src/MVP/views/components/ui_components.py

import customtkinter as ctk
import sys
from src.MVP.views import theme

# --- מיפויי יוניקוד רשמיים עבור Bootstrap Icons ---
ICON_HAMBURGER = "\uF479"  # list
ICON_UPLOAD = "\uF1C6"     # box-arrow-in-up
ICON_TRASH = "\uF5DE"      # trash
ICON_EXPORT = "\uF1C3"     # box-arrow-down
ICON_EDIT = "\uF4CB"       # pencil
ICON_FILTER = "\uF3DE"     # filter
ICON_LOAD_MORE = "\uF130"  # arrow-clockwise
ICON_EXCLUDE = "\uF831"    # x-circle

class Tooltip:
    """בועת מידע אלגנטית ונקייה הצפה מעל אלמנטים בריחוף עכבר"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(400, self.show)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show(self):
        if not self.text:
            return
        x = self.widget.winfo_rootx() + 10
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        
        self.tip_window = ctk.CTkToplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        
        if sys.platform.startswith("win"):
            self.tip_window.attributes("-topmost", True)
            
        label = ctk.CTkLabel(
            self.tip_window, text=self.text, 
            fg_color=("#2c3e50", "#1a252f"), text_color="white",
            corner_radius=6, padx=8, pady=4,
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold")
        )
        label.pack()

    def hide(self):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ToastNotification(ctk.CTkFrame):
    """קומפוננטת Toast צפה המופיעה בחלק התחתון של המסך ללא חסימת ממשק"""
    def __init__(self, master, message, level="success", **kwargs):
        bg = theme.TEXT_ACCENT if level == "success" else theme.DANGER
        super().__init__(master, fg_color=bg, corner_radius=8, border_width=0, **kwargs)
        
        lbl = ctk.CTkLabel(
            self, text=message, text_color="white", 
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=12, weight="bold")
        )
        lbl.pack(padx=14, pady=6)


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
    """כפתור מרובע גדול עם אייקון וקטורי"""
    return ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family="bootstrap-icons", size=24),
        fg_color=theme.TRANSPARENT,
        text_color=theme.TEXT_ACCENT,
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