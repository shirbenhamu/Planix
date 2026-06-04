# src/MVP/views/components/top_toolbar.py

import customtkinter as ctk
from src.MVP.views.ui_utils import format_text
from src.MVP.views import theme
from src.MVP.views.components.ui_components import (
    Tooltip, ICON_EDIT, ICON_LOAD_MORE, ICON_FILTER, ICON_EXCLUDE, ICON_EXPORT
)

ACCENT = ("#0077b6", "#3b8ed0")
ACCENT_HOVER = ("#005f8a", "#2f7ab0")

class TopToolbar(ctk.CTkFrame):
    def __init__(self, master, is_monthly=False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.current_lang = "he"
        self.is_monthly = is_monthly
        
        f_title = ctk.CTkFont(family=theme.FONT_FAMILY, size=18 if is_monthly else 16, weight="bold")
        f_btn = ctk.CTkFont(family=theme.FONT_FAMILY, size=14, weight="bold")
        f_icon = ctk.CTkFont(family="bootstrap-icons", size=15)

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
        self.on_edit_dates = None

        self.hamburger_btn = ctk.CTkLabel(self, text="☰", font=("Arial", 22), cursor="hand2", text_color=theme.TEXT_ACCENT)
        self.hamburger_btn.pack(side="left", padx=(5, 10))
        self.hamburger_btn.bind("<Enter>", lambda e: self.on_hamburger() if self.on_hamburger else None)

        if self.is_monthly:
            self.month_nav = ctk.CTkFrame(self, fg_color="transparent")
            self.month_nav.pack(side="left", padx=20)
            ctk.CTkButton(self.month_nav, text="<", font=f_btn, width=30, height=26, command=lambda: self.on_month_prev() if self.on_month_prev else None).pack(side="left", padx=2)
            self.month_year_lbl = ctk.CTkLabel(self.month_nav, text="", font=f_title, width=120, text_color=theme.TEXT_MAIN)
            self.month_year_lbl.pack(side="left", padx=5)
            ctk.CTkButton(self.month_nav, text=">", font=f_btn, width=30, height=26, command=lambda: self.on_month_next() if self.on_month_next else None).pack(side="left", padx=2)

        self.nav_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.nav_frame.pack(side="left", padx=15)
        ctk.CTkButton(self.nav_frame, text="<", font=f_btn, width=30, height=26, command=lambda: self.on_prev() if self.on_prev else None).pack(side="left", padx=2)

        self.page_entry = ctk.CTkEntry(self.nav_frame, width=45, height=26, justify="center", font=f_btn, fg_color=theme.BG_CARD, border_color=theme.BORDER_DEFAULT, text_color=theme.TEXT_MAIN)
        self.page_entry.pack(side="left", padx=2)
        self.page_entry.bind("<Return>", lambda e: self.on_page_jump(int(self.page_entry.get())) if self.on_page_jump else None)

        self.out_of_lbl = ctk.CTkLabel(self.nav_frame, text="", font=f_btn, width=80, anchor="w", text_color=theme.TEXT_MUTED)
        self.out_of_lbl.pack(side="left", padx=2)
        ctk.CTkButton(self.nav_frame, text=">", font=f_btn, width=30, height=26, command=lambda: self.on_next() if self.on_next else None).pack(side="left", padx=2)

        # --- כפתורי פעולה מבוססי גופן האייקונים החדש ---
        self.edit_dates_btn = ctk.CTkButton(
            self, text=f" {ICON_EDIT} ", font=f_icon, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="white", height=28, width=35,
            command=lambda: self.on_edit_dates() if self.on_edit_dates else None,
        )
        self.edit_dates_btn.pack(side="left", padx=4)
        self.tip_edit = Tooltip(self.edit_dates_btn, "עריכת תאריכים")

        self.load_more_btn = ctk.CTkButton(
            self, text=f" {ICON_LOAD_MORE} ", font=f_icon, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="white", height=28, width=35,
            command=lambda: self.on_load_more() if self.on_load_more else None,
        )
        self.load_more_btn.pack(side="left", padx=4)
        self.tip_load = Tooltip(self.load_more_btn, "טען מערכות נוספות")

        self.filter_btn = ctk.CTkButton(
            self, text=f" {ICON_FILTER} ", font=f_icon, fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="white", height=28, width=35,
            command=lambda: self.on_filter() if self.on_filter else None,
        )
        self.filter_btn.pack(side="left", padx=4)
        self.tip_filter = Tooltip(self.filter_btn, "מסננים")

        self.exclude_btn = ctk.CTkButton(
            self, text=f" {ICON_EXCLUDE} ", font=f_icon, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            text_color="white", height=28, width=35,
            command=lambda: self.on_exclude() if self.on_exclude else None,
        )
        self.exclude_btn.pack(side="left", padx=4)
        self.tip_exclude = Tooltip(self.exclude_btn, "החרג יום נבחר")

        # כפתור הורדה אלגנטי וממותג בצד ימין
        self.export_btn = ctk.CTkButton(
            self, text=ICON_EXPORT, fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
            font=ctk.CTkFont(family="bootstrap-icons", size=16), height=28, width=40,
            text_color="white", corner_radius=6,
            command=lambda: self.on_export() if self.on_export else None,
        )
        self.export_btn.pack(side="right", padx=5)
        self.tip_export = Tooltip(self.export_btn, "ייצוא לוח זמנים")

    def set_pagination(self, current: int, total: int):
        self.page_entry.delete(0, "end")
        self.page_entry.insert(0, str(current))
        self.out_of_lbl.configure(text=f" / {total}")

    def update_language(self, lang: str):
        self.current_lang = lang
        # עדכון בועות המידע בהתאם לשפת הממשק
        if lang == "he":
            self.tip_edit.text = "עריכת תאריכים"
            self.tip_load.text = "טען מערכות נוספות"
            self.tip_filter.text = "מסננים"
            self.tip_exclude.text = "החרג יום נבחר"
            self.tip_export.text = "ייצוא לוח זמנים"
        else:
            self.tip_edit.text = "Edit Dates"
            self.tip_load.text = "Load More"
            self.tip_filter.text = "Filters"
            self.tip_exclude.text = "Exclude Date"
            self.tip_export.text = "Export Schedule"