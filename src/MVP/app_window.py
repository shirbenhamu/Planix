import customtkinter as ctk
import sys
import os
import ctypes
from PIL import Image 
from typing import Callable

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.append(BASE_DIR)

def load_custom_fonts():
    if os.name == 'nt': 
        fonts_dir = os.path.join(BASE_DIR, 'assets', 'fonts')
        if not os.path.exists(fonts_dir):
            print(f"Fonts directory not found at {fonts_dir}")
            return
        for font_file in os.listdir(fonts_dir):
            if font_file.endswith(".ttf") or font_file.endswith(".otf"):
                font_path = os.path.join(fonts_dir, font_file)
                ctypes.windll.gdi32.AddFontResourceExW(font_path, 0x10 | 0x20, 0)

load_custom_fonts()

from src.MVP.views.input_view import InputConfigurationView
from src.MVP.views.calendar_view import CalendarGridView 

class AppWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("Planix")
        self.geometry("1400x800") 
        
        ctk.set_appearance_mode("Dark") 
        ctk.set_default_color_theme("blue")
        
        self.f_logo = ctk.CTkFont(family="Bruno Ace SC", size=22, weight="bold")
        self.f_nav = ctk.CTkFont(family="Rubik", size=16, weight="bold")
        self.f_switch = ctk.CTkFont(family="Rubik", size=14, weight="bold")

        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True)
        
        self.content_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_frame.pack(fill="both", expand=True)

        self.sidebar_visible = False
        self.sidebar_width = 240
        self.sidebar_frame = ctk.CTkFrame(self.main_container, width=self.sidebar_width, corner_radius=0, border_width=1)
        
        self.sidebar_title = ctk.CTkLabel(self.sidebar_frame, text="Planix", font=self.f_logo, text_color="#3b8ed0")
        self.sidebar_title.pack(pady=(25, 20), padx=20)

        self.nav_menu_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.nav_menu_frame.pack(fill="x", pady=10)
        
        self.btn_load_data = ctk.CTkButton(
            self.nav_menu_frame, text="טעינת נתונים", font=self.f_nav, anchor="w", 
            fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
            command=lambda: self._switch_view("input")
        )
        self.btn_load_data.pack(fill="x", padx=10, pady=5)
        
        self.btn_calendar = ctk.CTkButton(
            self.nav_menu_frame, text="לוח מבחנים שנתי", font=self.f_nav, anchor="w", 
            fg_color="#3b8ed0", text_color="white", hover_color="#2a6d9e",
            command=lambda: self._switch_view("calendar")
        )
        self.btn_calendar.pack(fill="x", padx=10, pady=5)

        self.bottom_sidebar_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.bottom_sidebar_frame.pack(side="bottom", fill="x", pady=20)

        try:
            logo_path = os.path.join(BASE_DIR, "assets", "logo.png")
            if os.path.exists(logo_path):
                my_logo = ctk.CTkImage(light_image=Image.open(logo_path), dark_image=Image.open(logo_path), size=(130, 130))
                self.logo_label = ctk.CTkLabel(self.bottom_sidebar_frame, image=my_logo, text="")
                self.logo_label.pack(pady=(0, 20))
        except Exception as e:
            print(f"No logo found or error loading logo: {e}")

        self.theme_var = ctk.StringVar(value="Dark")
        self.theme_switch = ctk.CTkSwitch(
            self.bottom_sidebar_frame, text="מצב יום", command=self._toggle_theme,
            variable=self.theme_var, onvalue="Light", offvalue="Dark", font=self.f_switch
        )
        self.theme_switch.pack(pady=10, padx=20, anchor="w")

        self.lang_var = ctk.StringVar(value="he")
        self.lang_switch = ctk.CTkSwitch(
            self.bottom_sidebar_frame, text="English", command=self._toggle_language,
            variable=self.lang_var, onvalue="en", offvalue="he", font=self.f_switch
        )
        self.lang_switch.pack(pady=10, padx=20, anchor="w")

        self.bind("<Motion>", self._check_hover_close) 

        self.views_container = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.views_container.pack(fill="both", expand=True, padx=0, pady=0)

        # 1. Instantiate the passive UI views
        self.input_view = InputConfigurationView(self.views_container)
        self.calendar_view = CalendarGridView(self.views_container)
        
        # 2. Bind the hover action to open the sidebar dynamically
        self.calendar_view.hamburger_btn.bind("<Enter>", self._open_sidebar)
        self.input_view.hamburger_btn.bind("<Enter>", self._open_sidebar)

        # 3. Dynamic layout navigation trigger for the central controller to hook into
        self.on_navigation_requested: Callable[[str], None] = None

    def switch_view(self, view_name: str) -> None:
        """
        Purely toggles visibility coordinates between frames without manipulating core business state.
        """
        if view_name == "input":
            self.calendar_view.pack_forget()
            self.input_view.pack(fill="both", expand=True)
            self.btn_load_data.configure(fg_color="#3b8ed0", text_color="white")
            self.btn_calendar.configure(fg_color="transparent", text_color=("gray10", "gray90"))
        else:
            self.input_view.pack_forget()
            self.calendar_view.pack(fill="both", expand=True)
            self.btn_calendar.configure(fg_color="#3b8ed0", text_color="white")
            self.btn_load_data.configure(fg_color="transparent", text_color=("gray10", "gray90"))

    def _switch_view(self, view_name: str) -> None:
        """Internal interceptor to forward user click parameters up to the controller layer."""
        if self.on_navigation_requested:
            self.on_navigation_requested(view_name)

    def _open_sidebar(self, event=None):
        if not self.sidebar_visible:
            self.sidebar_frame.place(relx=0.0, rely=0.0, relheight=1.0, anchor="nw")
            self.sidebar_frame.lift()
            self.sidebar_visible = True

    def _check_hover_close(self, event):
        if not self.sidebar_visible: return
        mouse_x_in_window = event.x_root - self.winfo_rootx()
        if mouse_x_in_window > (self.sidebar_width + 10):
            self.sidebar_frame.place_forget()
            self.sidebar_visible = False

    def _toggle_language(self):
        new_lang = self.lang_var.get()
        self.lang_switch.configure(text="עברית" if new_lang == "en" else "English")
        self.theme_switch.configure(text="מצב יום" if self.theme_var.get() == "Dark" else "מצב לילה" if new_lang == "he" else "Light Mode" if self.theme_var.get() == "Dark" else "Dark Mode")
        self.btn_load_data.configure(text="\u200Fטעינת נתונים\u200F" if new_lang == "he" else "Load Data")
        self.btn_calendar.configure(text="\u200Fלוח מבחנים שנתי\u200F" if new_lang == "he" else "Annual Schedule")
        
        self.input_view.update_language(new_lang)
        self.calendar_view.update_language(new_lang)

    def _toggle_theme(self):
        self._fade_out(1.0, 0.90, self._apply_theme_switch)

    def _apply_theme_switch(self):
        new_theme = self.theme_var.get()
        ctk.set_appearance_mode(new_theme)
        is_hebrew = self.lang_var.get() == "he"
        if new_theme == "Light":
            self.theme_switch.configure(text="מצב לילה" if is_hebrew else "Dark Mode")
        else:
            self.theme_switch.configure(text="מצב יום" if is_hebrew else "Light Mode")
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