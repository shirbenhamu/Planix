
import customtkinter as ctk
import sys
from src.MVP.views import theme

# --- Official Unicode mappings for Bootstrap Icons ---
ICON_HAMBURGER = "\uF479"  # list
ICON_UPLOAD = "\uF1C6"     # box-arrow-in-up
ICON_TRASH = "\uF5DE"      # trash
ICON_EXPORT = "\uF1C3"     # box-arrow-down
ICON_EDIT = "\uF4CB"       # pencil
ICON_FILTER = "\uF3DE"     # filter
ICON_LOAD_MORE = "\uF130"  # arrow-clockwise
ICON_REFRESH_FEED = "\uF130"  # arrow-clockwise / refresh current sorted feed
ICON_EXCLUDE = "\uF831"    # x-circle
ICON_SEARCH = ""     # search (magnifying glass) - deep search
ICON_SETTINGS = "⚙"        # settings / constraints

class Tooltip:
    """A clean, elegant tooltip that floats above elements on mouse hover"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.id = None
        self.hide_id = None
        
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        # Close the tooltip on click (task 5). It also closes by itself after 3 seconds (failsafe in show()).
        # Warning: do NOT bind <Unmap>/<Destroy> here — when the window is minimized (overrideredirect +
        # ShowWindow) they fire from inside the Win32 call and run Python code on the message queue,
        # which causes a fatal GIL crash that closes the entire app.
        self.widget.bind("<ButtonPress>", self.leave, add="+")

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        try:
            self.id = self.widget.after(theme.TOOLTIP_DELAY_MS, self.show)
        except Exception:
            pass

    def unschedule(self):
        if self.id:
            try:
                self.widget.after_cancel(self.id)
            except Exception:
                pass
            self.id = None

    def show(self):
        # Critical guard to prevent a crash on minimize: draw only if the widget is actually viewable
        try:
            if not self.text or not self.widget.winfo_viewable():
                return
        except Exception:
            return
            
        try:
            x = self.widget.winfo_rootx() + theme.SPACING_COMPACT
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + theme.SPACING_TINY
            
            self.tip_window = ctk.CTkToplevel(self.widget)
            self.tip_window.wm_overrideredirect(True)
            self.tip_window.wm_geometry(f"+{x}+{y}")
            
            if sys.platform.startswith("win"):
                self.tip_window.attributes("-topmost", True)
                
            label = ctk.CTkLabel(
                self.tip_window, text=self.text, 
                fg_color=theme.TOOLTIP_BG, text_color=theme.TEXT_ON_ACCENT,
                corner_radius=theme.RADIUS_SMALL, padx=theme.SPACING_SMALL, pady=theme.SPACING_TINY,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight=theme.FONT_WEIGHT_BOLD)
            )
            label.pack()
            # Safety mechanism: auto-close the tooltip after 3 seconds
            self.hide_id = self.widget.after(theme.TOOLTIP_AUTO_HIDE_MS, self.hide)
        except Exception:
            self.hide()

    def hide(self):
        if hasattr(self, 'hide_id') and self.hide_id:
            try:
                self.widget.after_cancel(self.hide_id)
            except Exception:
                pass
            self.hide_id = None
            
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


class ToastNotification(ctk.CTkFrame):
    """Floating Toast component shown at the bottom of the screen without blocking the UI"""
    def __init__(self, master, message, level="success", **kwargs):
        bg = theme.TEXT_ACCENT if level == "success" else theme.DANGER
        super().__init__(master, fg_color=bg, corner_radius=theme.RADIUS_BUTTON, border_width=theme.BORDER_WIDTH_NONE, **kwargs)
        
        lbl = ctk.CTkLabel(
            self, text=message, text_color=theme.TEXT_ON_ACCENT, 
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight=theme.FONT_WEIGHT_BOLD)
        )
        lbl.pack(padx=theme.SPACING_REGULAR, pady=theme.RADIUS_SMALL)


def create_card(parent, **kwargs):
    """Creates a uniform card with rounded corners and subtle borders"""
    return ctk.CTkFrame(
        parent,
        fg_color=theme.BG_CARD,
        border_width=theme.BORDER_WIDTH_DEFAULT,
        border_color=theme.BORDER_DEFAULT,
        corner_radius=theme.RADIUS_CARD,
        **kwargs
    )

def add_card_hover(card):
    """Adds a highlight effect to a card's border on mouse hover"""
    def on_enter(event):
        try:
            card.configure(border_color=theme.BORDER_ACTIVE, fg_color=theme.BG_CARD_HOVER)
        except Exception: pass

    def on_leave(event):
        try:
            card.configure(border_color=theme.BORDER_DEFAULT, fg_color=theme.BG_CARD)
        except Exception: pass

    card.bind("<Enter>", on_enter)
    card.bind("<Leave>", on_leave)
    for child in card.winfo_children():
        child.bind("<Enter>", on_enter)
        child.bind("<Leave>", on_leave)

def create_icon_button(parent, text, command, **kwargs):
    """Large square button with a vector icon"""
    return ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family=theme.FONT_BOOTSTRAP_ICONS, size=theme.FONT_SIZE_MODAL_TITLE),
        fg_color=theme.TRANSPARENT,
        text_color=theme.TEXT_ACCENT,
        hover_color=theme.BG_CARD_HOVER,
        width=theme.CONTROL_WIDTH_SYNC, 
        height=theme.CONTROL_HEIGHT_ICON_LARGE, 
        corner_radius=theme.RADIUS_BUTTON,
        command=command,
        **kwargs
    )

def create_primary_action_button(parent, text, command, **kwargs):
    """Clean, elegant primary action button in Bootstrap style"""
    return ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_HERO, weight=theme.FONT_WEIGHT_BOLD),
        fg_color=theme.SUCCESS,
        hover_color=theme.SUCCESS_HOVER,
        text_color=theme.TEXT_ON_ACCENT,
        height=theme.CONTROL_HEIGHT_HERO,
        corner_radius=theme.RADIUS_BUTTON,
        command=command,
        **kwargs
    )

def create_secondary_button(parent, text, command, **kwargs):
    """Secondary (Outline) button in Bootstrap style - transparent background with a colored border"""
    return ctk.CTkButton(
        parent,
        text=text,
        font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BUTTON, weight=theme.FONT_WEIGHT_BOLD),
        fg_color=theme.TRANSPARENT,
        border_width=theme.BORDER_WIDTH_ACTIVE,
        border_color=theme.BORDER_ACTIVE,
        hover_color=theme.BG_CARD_HOVER,
        text_color=theme.TEXT_ACCENT,
        height=theme.CONTROL_HEIGHT_BUTTON,
        corner_radius=theme.RADIUS_BUTTON,
        command=command,
        **kwargs
    )