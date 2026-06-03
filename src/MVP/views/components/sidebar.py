# src/MVP/views/components/sidebar.py
import customtkinter as ctk
import os
from PIL import Image

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, base_dir, **kwargs):
        # מוגדר ברוחב 240, בדיוק כמו שהיה ב-AppWindow
        super().__init__(master, width=240, corner_radius=0, border_width=1, **kwargs)
        self.base_dir = base_dir
        self.current_lang = "he"

        # פונקציות Callback שיאפשרו לחלון הראשי להאזין ללחיצות
        self.on_nav_click = None
        self.on_theme_toggle = None
        self.on_lang_toggle = None

        self.f_logo = ctk.CTkFont(family="Bruno Ace SC", size=22, weight="bold")
        self.f_nav = ctk.CTkFont(family="Rubik", size=16, weight="bold")
        self.f_switch = ctk.CTkFont(family="Rubik", size=14, weight="bold")

        self._setup_ui()

    def _setup_ui(self):
        # כותרת לוגו
        ctk.CTkLabel(self, text="Planix", font=self.f_logo, text_color="#3b8ed0").pack(pady=(25, 20), padx=20)

        # תפריט ניווט מרכזי
        self.nav_menu = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_menu.pack(fill="x", pady=10)
        
        self.btn_load = self._create_nav_btn("טעינת נתונים", "input")
        self.btn_monthly = self._create_nav_btn("לוח מבחנים חודשי", "monthly")
        self.btn_annual = self._create_nav_btn("מבט-על שנתי", "annual")

        # אזור תחתון (תמונה ומתגים)
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(side="bottom", fill="x", pady=20)

        self._load_logo()

        # מתגי Theme & Language
        self.theme_var = ctk.StringVar(value="Dark")
        self.theme_switch = ctk.CTkSwitch(
            self.bottom_frame, text="מצב יום", variable=self.theme_var, onvalue="Light", offvalue="Dark", font=self.f_switch,
            command=lambda: self.on_theme_toggle(self.theme_var.get()) if self.on_theme_toggle else None
        )
        self.theme_switch.pack(pady=10, padx=20, anchor="w")

        self.lang_var = ctk.StringVar(value="he")
        self.lang_switch = ctk.CTkSwitch(
            self.bottom_frame, text="English", variable=self.lang_var, onvalue="en", offvalue="he", font=self.f_switch,
            command=lambda: self.on_lang_toggle(self.lang_var.get()) if self.on_lang_toggle else None
        )
        self.lang_switch.pack(pady=10, padx=20, anchor="w")

    def _create_nav_btn(self, text, action):
        btn = ctk.CTkButton(
            self.nav_menu, text=text, font=self.f_nav, anchor="w", 
            fg_color="transparent", text_color=("gray10", "gray90"), hover_color=("gray70", "gray30"),
            command=lambda: self.on_nav_click(action) if self.on_nav_click else None
        )
        btn.pack(fill="x", padx=10, pady=5)
        return btn

    def _load_logo(self):
        try:
            logo_path = os.path.join(self.base_dir, "assets", "logo.png")
            if os.path.exists(logo_path):
                img = ctk.CTkImage(light_image=Image.open(logo_path), dark_image=Image.open(logo_path), size=(130, 130))
                ctk.CTkLabel(self.bottom_frame, image=img, text="").pack(pady=(0, 20))
        except Exception: pass

    def update_active_btn(self, view_name: str):
        """צובע את הכפתור הפעיל ומאפס את השאר"""
        for btn in [self.btn_load, self.btn_monthly, self.btn_annual]:
            btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

        if view_name == "input": self.btn_load.configure(fg_color="#3b8ed0", text_color="white")
        elif view_name == "monthly": self.btn_monthly.configure(fg_color="#3b8ed0", text_color="white")
        elif view_name == "annual": self.btn_annual.configure(fg_color="#3b8ed0", text_color="white")

    def update_language(self, lang: str):
        self.current_lang = lang
        self.lang_switch.configure(text="עברית" if lang == "en" else "English")
        self.theme_switch.configure(text="מצב יום" if self.theme_var.get() == "Dark" else "מצב לילה" if lang == "he" else "Light Mode" if self.theme_var.get() == "Dark" else "Dark Mode")
        
        self.btn_load.configure(text="\u200Fטעינת נתונים\u200F" if lang == "he" else "Load Data")
        self.btn_monthly.configure(text="\u200Fלוח מבחנים חודשי\u200F" if lang == "he" else "Monthly Schedule")
        self.btn_annual.configure(text="\u200Fמבט-על שנתי\u200F" if lang == "he" else "Annual Overview")