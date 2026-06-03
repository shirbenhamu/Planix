import customtkinter as ctk
from src.MVP.views.ui_utils import format_text

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
        self.on_update_range = None
        self.on_export = None
        self.on_exclude = None
        self.on_filter = None
        self.on_month_prev = None
        self.on_month_next = None
        self.on_load_more = None  # החדש

        self.hamburger_btn = ctk.CTkLabel(self, text="☰", font=("Arial", 22), cursor="hand2")
        self.hamburger_btn.pack(side="left", padx=(5, 10))
        self.hamburger_btn.bind("<Enter>", lambda e: self.on_hamburger() if self.on_hamburger else None)
        
        self.view_title = ctk.CTkLabel(self, text="", font=f_title, text_color="#3b8ed0")
        self.view_title.pack(side="left", padx=10)

        if self.is_monthly:
            self.month_nav = ctk.CTkFrame(self, fg_color="transparent")
            self.month_nav.pack(side="left", padx=20)
            ctk.CTkButton(self.month_nav, text="<", font=f_btn, width=30, height=26, command=lambda: self.on_month_prev() if self.on_month_prev else None).pack(side="left", padx=2)
            self.month_year_lbl = ctk.CTkLabel(self.month_nav, text="", font=f_title, width=120)
            self.month_year_lbl.pack(side="left", padx=5)
            ctk.CTkButton(self.month_nav, text=">", font=f_btn, width=30, height=26, command=lambda: self.on_month_next() if self.on_month_next else None).pack(side="left", padx=2)

        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(side="left", padx=15)
        ctk.CTkButton(self.nav_frame, text="<", font=f_btn, width=30, height=26, command=lambda: self.on_prev() if self.on_prev else None).pack(side="left", padx=2)
        self.schedule_lbl = ctk.CTkLabel(self.nav_frame, text="", font=f_btn)
        self.schedule_lbl.pack(side="left", padx=2)
        
        self.page_entry = ctk.CTkEntry(self.nav_frame, width=35, height=26, justify="center", font=f_btn)
        self.page_entry.pack(side="left", padx=2)
        self.page_entry.bind("<Return>", lambda e: self.on_page_jump(int(self.page_entry.get())) if self.on_page_jump else None)
        
        self.out_of_lbl = ctk.CTkLabel(self.nav_frame, text="", font=f_btn)
        self.out_of_lbl.pack(side="left", padx=2)
        ctk.CTkButton(self.nav_frame, text=">", font=f_btn, width=30, height=26, command=lambda: self.on_next() if self.on_next else None).pack(side="left", padx=2)

        if not self.is_monthly:
            self.range_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.range_frame.pack(side="left", padx=15)
            self.start_entry = ctk.CTkEntry(self.range_frame, width=70, height=26, font=f_btn)
            self.end_entry = ctk.CTkEntry(self.range_frame, width=70, height=26, font=f_btn)
            self.start_entry.pack(side="left", padx=2)
            self.end_entry.pack(side="left", padx=2)
            self.update_range_btn = ctk.CTkButton(self.range_frame, text="", font=f_btn, width=50, height=26, command=lambda: self.on_update_range(self.start_entry.get(), self.end_entry.get()) if self.on_update_range else None)
            self.update_range_btn.pack(side="left", padx=2)

        # כפתורים בצד ימין
        self.filter_btn = ctk.CTkButton(self, text="", font=f_btn, fg_color="#4B0082", hover_color="#300052", height=26, width=90, command=lambda: self.on_filter() if self.on_filter else None)
        self.filter_btn.pack(side="right", padx=5)
        self.exclude_btn = ctk.CTkButton(self, text="", font=f_btn, fg_color="#b22222", hover_color="#8b0000", height=26, width=80, command=lambda: self.on_exclude() if self.on_exclude else None)
        self.exclude_btn.pack(side="right", padx=5)
        
        # כפתור טען עוד - צבע כתום בולט
        self.load_more_btn = ctk.CTkButton(self, text=format_text("load_more", self.current_lang), font=f_btn, fg_color="#d35400", hover_color="#e67e22", height=26, width=80, command=lambda: self.on_load_more() if self.on_load_more else None)
        self.load_more_btn.pack(side="right", padx=5)
        
        ctk.CTkButton(self, text="📥", fg_color="#28a745", hover_color="#218838", font=("Arial", 16), height=26, width=35, command=lambda: self.on_export() if self.on_export else None).pack(side="right", padx=5)

    def set_pagination(self, current: int, total: int):
        self.page_entry.delete(0, "end")
        self.page_entry.insert(0, str(current))
        self.out_of_lbl.configure(text=f" {format_text('out_of_lbl', self.current_lang)} {total}")

    def update_language(self, lang: str):
        self.current_lang = lang
        self.view_title.configure(text=format_text("monthly_title" if self.is_monthly else "title", lang))
        self.schedule_lbl.configure(text=format_text("schedule_lbl", lang))
        self.exclude_btn.configure(text=format_text("exclude_btn", lang))
        self.filter_btn.configure(text=format_text("filter_btn", lang))
        self.load_more_btn.configure(text=format_text("load_more", lang))
        if not self.is_monthly:
            self.update_range_btn.configure(text=format_text("update_range", lang))
            self.start_entry.configure(placeholder_text=format_text("start_date", lang))
            self.end_entry.configure(placeholder_text=format_text("end_date", lang))