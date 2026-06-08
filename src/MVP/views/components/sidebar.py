# src/MVP/views/components/sidebar.py
import customtkinter as ctk
import os
from PIL import Image
from src.MVP.views import theme

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, base_dir, **kwargs):
        super().__init__(master, width=240, corner_radius=0, border_width=1, border_color=theme.BORDER_DEFAULT, fg_color=theme.BG_CARD, **kwargs)
        self.base_dir = base_dir
        self.current_lang = "he"

        self.on_nav_click = None
        self.on_theme_toggle = None
        self.on_lang_toggle = None

        self.f_logo = ctk.CTkFont(family="Bruno Ace SC", size=24, weight="bold")
        self.f_nav = ctk.CTkFont(family=theme.FONT_FAMILY, size=16, weight="bold")
        self.f_switch = ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold")

        self._setup_ui()

    def _setup_ui(self):
        ctk.CTkLabel(self, text="Planix", font=self.f_logo, text_color=theme.TEXT_ACCENT).pack(pady=(35, 25), padx=20)

        self.nav_menu = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_menu.pack(fill="x", pady=10)
        
        self.btn_load = self._create_nav_btn("טעינת נתונים", "input")
        self.btn_monthly = self._create_nav_btn("לוח מבחנים חודשי", "monthly")
        self.btn_annual = self._create_nav_btn("מבט-על שנתי", "annual")

        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.pack(side="bottom", fill="x", pady=20)

        self._load_logo()

        self.theme_var = ctk.StringVar(value="Dark")
        self.theme_switch = ctk.CTkSwitch(
            self.bottom_frame, text="מצב יום", variable=self.theme_var, onvalue="Light", offvalue="Dark", font=self.f_switch,
            progress_color=theme.TEXT_ACCENT,
            command=lambda: self.on_theme_toggle(self.theme_var.get()) if self.on_theme_toggle else None
        )
        self.theme_switch.pack(pady=10, padx=25, anchor="w")

        self.lang_var = ctk.StringVar(value="he")
        self.lang_switch = ctk.CTkSwitch(
            self.bottom_frame, text="English", variable=self.lang_var, onvalue="en", offvalue="he", font=self.f_switch,
            progress_color=theme.TEXT_ACCENT,
            command=lambda: self.on_lang_toggle(self.lang_var.get()) if self.on_lang_toggle else None
        )
        self.lang_switch.pack(pady=10, padx=25, anchor="w")

    def _create_nav_btn(self, text, action):
        btn = ctk.CTkButton(
            self.nav_menu, text=text, font=self.f_nav, anchor="w", 
            fg_color="transparent", text_color=theme.TEXT_MAIN, hover_color=theme.BG_CARD_HOVER,
            height=45, corner_radius=8,
            command=lambda: self.on_nav_click(action) if self.on_nav_click else None
        )
        btn.pack(fill="x", padx=15, pady=4)
        return btn

    def _load_logo(self):
        try:
            logo_path = os.path.join(self.base_dir, "assets", "logo.png")
            if os.path.exists(logo_path):
                img = ctk.CTkImage(light_image=Image.open(logo_path), dark_image=Image.open(logo_path), size=(120, 120))
                # Clean logo directly on the sidebar background, without an unnecessary frame
                ctk.CTkLabel(self.bottom_frame, image=img, text="").pack(pady=(0, 15))
        except Exception: pass

    def update_active_btn(self, view_name: str):
        for btn in [self.btn_load, self.btn_monthly, self.btn_annual]:
            btn.configure(fg_color="transparent", text_color=theme.TEXT_MAIN)

        if view_name == "input": self.btn_load.configure(fg_color=theme.TEXT_ACCENT, text_color="white")
        elif view_name == "monthly": self.btn_monthly.configure(fg_color=theme.TEXT_ACCENT, text_color="white")
        elif view_name == "annual": self.btn_annual.configure(fg_color=theme.TEXT_ACCENT, text_color="white")

    def update_language(self, lang: str):
        self.current_lang = lang
        self.lang_switch.configure(text="עברית" if lang == "en" else "English")
        self.theme_switch.configure(text="מצב יום" if self.theme_var.get() == "Dark" else "מצב לילה" if lang == "he" else "Light Mode" if self.theme_var.get() == "Dark" else "Dark Mode")
        
        self.btn_load.configure(text="\u200Fטעינת נתונים\u200F" if lang == "he" else "Load Data")
        self.btn_monthly.configure(text="\u200Fלוח מבחנים חודשי\u200F" if lang == "he" else "Monthly Schedule")
        self.btn_annual.configure(text="\u200Fמבט-על שנתי\u200F" if lang == "he" else "Annual Overview")