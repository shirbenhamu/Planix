import customtkinter as ctk
import sys
import os
import ctypes
from typing import Callable

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(BASE_DIR)

def load_custom_fonts():
    if os.name == 'nt': 
        fonts_dir = os.path.join(BASE_DIR, 'assets', 'fonts')
        if not os.path.exists(fonts_dir): return
        for font_file in os.listdir(fonts_dir):
            if font_file.endswith(".ttf") or font_file.endswith(".otf"):
                ctypes.windll.gdi32.AddFontResourceExW(os.path.join(fonts_dir, font_file), 0x10 | 0x20, 0)

load_custom_fonts()

from src.MVP.views.input_view import InputConfigurationView
from src.MVP.views.calendar_view import CalendarGridView 
from src.MVP.views.monthly_view import MonthlyGridView 
from src.MVP.views.components.sidebar import Sidebar # <-- ייבוא הסיידבר החדש

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Planix")
        self.geometry("1400x800") 
        ctk.set_appearance_mode("Dark") 
        ctk.set_default_color_theme("blue")
        
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)
        
        self.content_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        # אתחול הסיידבר כקומפוננטה עצמאית
        self.sidebar_visible = False
        self.sidebar_width = 240
        self.sidebar = Sidebar(self.main_container, base_dir=BASE_DIR)
        
        # חיבור הפונקציות של הסיידבר לחלון הראשי
        self.sidebar.on_nav_click = self._handle_sidebar_click
        self.sidebar.on_theme_toggle = self._toggle_theme
        self.sidebar.on_lang_toggle = self._toggle_language

        self.bind("<Motion>", self._check_hover_close) 

        self.views_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.views_container.pack(fill="both", expand=True, padx=0, pady=0)

        self.input_view = InputConfigurationView(self.views_container)
        self.calendar_view = CalendarGridView(self.views_container)
        self.monthly_view = MonthlyGridView(self.views_container)
        
        # מפעיל את פתיחת הסיידבר בלחיצה/ריחוף על ההמבורגר של הלוחות (בהנחה ששמת את ה-TopToolbar)
        if hasattr(self.calendar_view, 'toolbar'):
            self.calendar_view.toolbar.hamburger_btn.bind("<Enter>", self._open_sidebar)
            self.monthly_view.toolbar.hamburger_btn.bind("<Enter>", self._open_sidebar)
        self.input_view.hamburger_btn.bind("<Enter>", self._open_sidebar)

        self.on_navigation_requested: Callable[[str], None] = None
        self.input_view.on_run_clicked = lambda: self._handle_sidebar_click("run")

        # חיבור בין התצוגה החודשית לשנתית
        self.calendar_view.set_monthly_view(self.monthly_view)
        
        # אם עשית את המעבר ל-TopToolbar:
        if hasattr(self.monthly_view, 'toolbar'):
            self.monthly_view.toolbar.on_next = lambda: self.calendar_view.toolbar.on_next() if self.calendar_view.toolbar.on_next else None
            self.monthly_view.toolbar.on_prev = lambda: self.calendar_view.toolbar.on_prev() if self.calendar_view.toolbar.on_prev else None
            self.monthly_view.toolbar.on_page_jump = lambda p: self.calendar_view.toolbar.on_page_jump(p) if self.calendar_view.toolbar.on_page_jump else None
            self.monthly_view.toolbar.on_exclude = lambda: self.calendar_view.toolbar.on_exclude() if self.calendar_view.toolbar.on_exclude else None
            self.monthly_view.toolbar.on_export = lambda: self.calendar_view.toolbar.on_export() if self.calendar_view.toolbar.on_export else None
            self.monthly_view.toolbar.on_filter = lambda: self.calendar_view.toolbar.on_filter() if self.calendar_view.toolbar.on_filter else None
        
        self.monthly_view.on_cell_clicked = lambda key: self.calendar_view._handle_cell_click(key)

    def _handle_sidebar_click(self, action: str):
        if action == "run":
            self._show_monthly_on_run = True
            self._switch_view("calendar") 
        elif action == "input":
            self._switch_view("input")
        elif action == "monthly":
            self.switch_view("monthly") 
        elif action == "annual":
            self.switch_view("annual") 

    def switch_view(self, view_name: str) -> None:
        self.input_view.pack_forget()
        self.calendar_view.pack_forget()
        self.monthly_view.pack_forget()

        if view_name == "calendar":
            view_name = "monthly" if getattr(self, '_show_monthly_on_run', True) else "annual"

        if view_name == "input":
            self.input_view.pack(fill="both", expand=True)
        elif view_name == "monthly":
            self._show_monthly_on_run = True 
            self.monthly_view.pack(fill="both", expand=True)
        elif view_name == "annual":
            self._show_monthly_on_run = False 
            self.calendar_view.pack(fill="both", expand=True)
            
        self.sidebar.update_active_btn(view_name)

    def _switch_view(self, view_name: str) -> None:
        if self.on_navigation_requested: self.on_navigation_requested(view_name)

    def _open_sidebar(self, event=None):
        if not self.sidebar_visible:
            self.sidebar.place(relx=0.0, rely=0.0, relheight=1.0, anchor="nw")
            self.sidebar.lift()
            self.sidebar_visible = True

    def _check_hover_close(self, event):
        if not self.sidebar_visible: return
        mouse_x_in_window = event.x_root - self.winfo_rootx()
        if mouse_x_in_window > (self.sidebar_width + 10):
            self.sidebar.place_forget()
            self.sidebar_visible = False

    def _toggle_language(self, new_lang):
        self.sidebar.update_language(new_lang)
        self.input_view.update_language(new_lang)
        self.calendar_view.update_language(new_lang)
        self.monthly_view.update_language(new_lang)

    def _toggle_theme(self, new_theme):
        self._fade_out(1.0, 0.90, lambda: self._apply_theme_switch(new_theme))

    def _apply_theme_switch(self, new_theme):
        ctk.set_appearance_mode(new_theme)
        self.sidebar.update_language(self.sidebar.lang_var.get()) # רענון צבעים לטקסט
        self.update_idletasks() 
        self._fade_in(0.90, 1.0)

    def _fade_out(self, current_alpha, target_alpha, callback):
        if current_alpha > target_alpha:
            current_alpha -= 0.05 
            self.attributes("-alpha", current_alpha)
            self.after(10, lambda: self._fade_out(current_alpha, target_alpha, callback)) 
        else: callback()

    def _fade_in(self, current_alpha, target_alpha):
        if current_alpha < target_alpha:
            current_alpha += 0.05
            self.attributes("-alpha", current_alpha)
            self.after(10, lambda: self._fade_in(current_alpha, target_alpha))
        else: self.attributes("-alpha", 1.0)

if __name__ == "__main__":
    app = AppWindow()
    app.mainloop()