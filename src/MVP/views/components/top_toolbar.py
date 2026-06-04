import customtkinter as ctk
from src.MVP.views.ui_utils import format_text
from src.MVP.views import theme

# צבעי הלחצנים: תכלת אחיד שמסתגל ליום/לילה, פרט להחרגה שאדומה
ACCENT = ("#0077b6", "#3b8ed0")
ACCENT_HOVER = ("#005f8a", "#2f7ab0")


class TopToolbar(ctk.CTkFrame):
    def __init__(self, master, is_monthly=False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.current_lang = "he"
        self.is_monthly = is_monthly
        
        f_title = ctk.CTkFont(family="Rubik", size=18 if is_monthly else 16, weight="bold")
        f_btn = ctk.CTkFont(family="Rubik", size=12, weight="bold")

        # Callbacks
        self.on_hamburger = None
        self.on_prev = None
        self.on_next = None
        self.on_page_jump = None
        self.on_export = None
        self.on_exclude = None
        self.on_filter = None
        self.on_month_prev = None
        self.on_month_next = None
        self.on_load_more = None
        self.on_edit_dates = None  # פתיחת חלון עריכת התאריכים

        self.hamburger_btn = ctk.CTkLabel(self, text="☰", font=("Arial", 22), cursor="hand2")
        self.hamburger_btn.pack(side="left", padx=(5, 10))
        self.hamburger_btn.bind("<Enter>", lambda e: self.on_hamburger() if self.on_hamburger else None)

        if self.is_monthly:
            self.month_nav = ctk.CTkFrame(self, fg_color="transparent")
            self.month_nav.pack(side="left", padx=20)
            ctk.CTkButton(self.month_nav, text="<", font=f_btn, width=30, height=26, command=lambda: self.on_month_prev() if self.on_month_prev else None).pack(side="left", padx=2)
            self.month_year_lbl = ctk.CTkLabel(self.month_nav, text="", font=f_title, width=120)
            self.month_year_lbl.pack(side="left", padx=5)
            ctk.CTkButton(self.month_nav, text=">", font=f_btn, width=30, height=26, command=lambda: self.on_month_next() if self.on_month_next else None).pack(side="left", padx=2)

        # מד עמודים: חץ, מספר נוכחי / סך הכל, חץ
        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(side="left", padx=15)
        ctk.CTkButton(self.nav_frame, text="<", font=f_btn, width=30, height=26, command=lambda: self.on_prev() if self.on_prev else None).pack(side="left", padx=2)

        self.page_entry = ctk.CTkEntry(self.nav_frame, width=45, height=26, justify="center", font=f_btn)
        self.page_entry.pack(side="left", padx=2)
        self.page_entry.bind("<Return>", lambda e: self.on_page_jump(int(self.page_entry.get())) if self.on_page_jump else None)

        # רוחב קבוע (מספיק ל-"/ 100000") כדי ששינוי המספר ב-set_pagination לא
        # ישנה את רוחב התווית ולא יאלץ פריסה מחדש של כל הסרגל (מקור החפיפה בטעינה)
        self.out_of_lbl = ctk.CTkLabel(self.nav_frame, text="", font=f_btn, width=80, anchor="w")
        self.out_of_lbl.pack(side="left", padx=2)
        ctk.CTkButton(self.nav_frame, text=">", font=f_btn, width=30, height=26, command=lambda: self.on_next() if self.on_next else None).pack(side="left", padx=2)

        # --- כל לחצני הפעולה בצד שמאל (צד ההמבורגר) ---
        self.edit_dates_btn = ctk.CTkButton(
            self, text="", font=f_btn, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="white", height=26, width=110,
            command=lambda: self.on_edit_dates() if self.on_edit_dates else None,
        )
        self.edit_dates_btn.pack(side="left", padx=5)

        self.load_more_btn = ctk.CTkButton(
            self, text=format_text("load_more", self.current_lang), font=f_btn,
            fg_color=ACCENT, hover_color=ACCENT_HOVER, text_color="white",
            height=26, width=80,
            command=lambda: self.on_load_more() if self.on_load_more else None,
        )
        self.load_more_btn.pack(side="left", padx=5)

        self.filter_btn = ctk.CTkButton(
            self, text="", font=f_btn, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="white", height=26, width=90,
            command=lambda: self.on_filter() if self.on_filter else None,
        )
        self.filter_btn.pack(side="left", padx=5)

        self.exclude_btn = ctk.CTkButton(
            self, text="", font=f_btn, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            text_color="white", height=26, width=90,
            command=lambda: self.on_exclude() if self.on_exclude else None,
        )
        self.exclude_btn.pack(side="left", padx=5)

        # --- כפתור ההורדה/ייצוא — היחיד בצד ימין, נפרד משאר הלחצנים ---
        ctk.CTkButton(
            self, text="📥", fg_color="#28a745", hover_color="#218838",
            font=("Arial", 16), height=26, width=35,
            command=lambda: self.on_export() if self.on_export else None,
        ).pack(side="right", padx=5)

    def set_pagination(self, current: int, total: int):
        self.page_entry.delete(0, "end")
        self.page_entry.insert(0, str(current))
        self.out_of_lbl.configure(text=f" / {total}")

    def update_language(self, lang: str):
        self.current_lang = lang
        self.exclude_btn.configure(text=format_text("exclude_btn", lang))
        self.filter_btn.configure(text=format_text("filter_btn", lang))
        self.load_more_btn.configure(text=format_text("load_more", lang))
        self.edit_dates_btn.configure(text=format_text("edit_dates", lang))