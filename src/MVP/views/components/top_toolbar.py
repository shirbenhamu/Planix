# src/MVP/views/components/top_toolbar.py

import customtkinter as ctk
from src.MVP.views.ui_utils import TRANSLATIONS
from src.MVP.views import theme
from src.MVP.views.components.ui_components import (
    Tooltip, ICON_EDIT, ICON_LOAD_MORE, ICON_REFRESH_FEED, ICON_EXCLUDE, ICON_EXPORT, ICON_SETTINGS
)


class TopToolbar(ctk.CTkFrame):
    def __init__(self, master, is_monthly=False, **kwargs):
        super().__init__(master, fg_color=theme.TRANSPARENT, **kwargs)
        self.current_lang = "he"
        self.is_monthly = is_monthly

        f_title = ctk.CTkFont(family=theme.FONT_FAMILY,
                              size=theme.FONT_SIZE_TITLE if is_monthly else theme.FONT_SIZE_HEADER, weight=theme.FONT_WEIGHT_BOLD)
        f_btn = ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BUTTON, weight=theme.FONT_WEIGHT_BOLD)
        f_icon = ctk.CTkFont(family=theme.FONT_BOOTSTRAP_ICONS, size=theme.FONT_SIZE_ICON)

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
        self.on_refresh_feed = None
        self.on_edit_dates = None
        self.on_constraints_settings = None
        self.on_undo = None

        self.hamburger_btn = ctk.CTkLabel(self, text="☰", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SECTION, weight=theme.FONT_WEIGHT_BOLD), cursor="hand2", text_color=theme.TEXT_ACCENT)
        self.hamburger_btn.pack(side="left", padx=(theme.RADIUS_SMALL, theme.SPACING_COMPACT))
        self.hamburger_btn.bind(
            "<Enter>", lambda e: self.on_hamburger() if self.on_hamburger else None)

        if self.is_monthly:
            self.month_nav = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
            self.month_nav.pack(side="left", padx=theme.SPACING_MEDIUM)
            ctk.CTkButton(self.month_nav, text="<", font=f_btn, width=theme.CONTROL_WIDTH_NAV, height=theme.CONTROL_HEIGHT_TINY, command=lambda: self.on_month_prev(
            ) if self.on_month_prev else None).pack(side="left", padx=theme.SPACING_XS)
            self.month_year_lbl = ctk.CTkLabel(
                self.month_nav, text="", font=f_title, width=theme.CONTROL_WIDTH_MONTH_LABEL, text_color=theme.TEXT_MAIN)
            self.month_year_lbl.pack(side="left", padx=theme.RADIUS_SMALL)
            ctk.CTkButton(self.month_nav, text=">", font=f_btn, width=theme.CONTROL_WIDTH_NAV, height=theme.CONTROL_HEIGHT_TINY, command=lambda: self.on_month_next(
            ) if self.on_month_next else None).pack(side="left", padx=theme.SPACING_XS)

        self.nav_frame = ctk.CTkFrame(self, fg_color=theme.TRANSPARENT)
        self.nav_frame.pack(side="left", padx=theme.FONT_SIZE_ICON)
        ctk.CTkButton(self.nav_frame, text="<", font=f_btn, width=theme.CONTROL_WIDTH_NAV, height=theme.CONTROL_HEIGHT_TINY,
                      command=lambda: self.on_prev() if self.on_prev else None).pack(side="left", padx=theme.SPACING_XS)

        self.page_entry = ctk.CTkEntry(self.nav_frame, width=theme.CONTROL_WIDTH_PAGE_ENTRY, height=theme.CONTROL_HEIGHT_TINY, justify="center", font=f_btn,
                                       fg_color=theme.BG_CARD, border_color=theme.BORDER_DEFAULT, text_color=theme.TEXT_MAIN)
        self.page_entry.pack(side="left", padx=theme.SPACING_XS)
        self.page_entry.bind("<Return>", lambda e: self.on_page_jump(
            int(self.page_entry.get())) if self.on_page_jump else None)

        self.out_of_lbl = ctk.CTkLabel(
            self.nav_frame, text="", font=f_btn, width=theme.CONTROL_WIDTH_PAGE_LABEL, anchor="w", text_color=theme.TEXT_MUTED)
        self.out_of_lbl.pack(side="left", padx=theme.SPACING_XS)
        ctk.CTkButton(self.nav_frame, text=">", font=f_btn, width=theme.CONTROL_WIDTH_NAV, height=theme.CONTROL_HEIGHT_TINY,
                      command=lambda: self.on_next() if self.on_next else None).pack(side="left", padx=theme.SPACING_XS)

        self.refresh_feed_btn = ctk.CTkButton(
            self.nav_frame,
            text=f"{ICON_REFRESH_FEED}  רענן",
            font=f_icon,
            width=theme.CONTROL_WIDTH_REFRESH,
            height=theme.CONTROL_HEIGHT_TINY,
            fg_color=theme.TEXT_ACCENT,
            hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT,
            corner_radius=theme.RADIUS_SMALL,
            command=lambda: self.on_refresh_feed() if self.on_refresh_feed else None,
        )
        self.refresh_feed_btn.pack(side="left", padx=(theme.SPACING_SMALL, theme.SPACING_XS))
        self.tip_refresh_feed = Tooltip(self.refresh_feed_btn, "רענן את חלון התוצאות לפי המיון הפעיל")

        # --- Action buttons based on the new icon font ---
        self.edit_dates_btn = ctk.CTkButton(
            self, text=f" {ICON_EDIT} ", font=f_icon, fg_color=theme.TEXT_ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT, height=theme.CONTROL_HEIGHT_SMALL, width=theme.CONTROL_WIDTH_ICON_SMALL,
            command=lambda: self.on_edit_dates() if self.on_edit_dates else None,
        )
        self.edit_dates_btn.pack(side="left", padx=theme.SPACING_TINY)
        self.tip_edit = Tooltip(self.edit_dates_btn, "עריכת תאריכים")

        self.constraints_btn = ctk.CTkButton(
            self, text=ICON_SETTINGS, font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_ICON, weight=theme.FONT_WEIGHT_BOLD),
            fg_color=theme.TEXT_ACCENT, hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT, height=theme.CONTROL_HEIGHT_SMALL, width=theme.CONTROL_WIDTH_ICON, corner_radius=theme.RADIUS_SMALL,
            command=lambda: self.on_constraints_settings() if self.on_constraints_settings else None,
        )
        self.constraints_btn.pack(side="left", padx=theme.SPACING_TINY)
        self.tip_constraints = Tooltip(self.constraints_btn, "הגדרות אילוצים")

        self.load_more_btn = ctk.CTkButton(
            self, text=ICON_LOAD_MORE, fg_color=theme.TEXT_ACCENT, hover_color=theme.ACCENT_HOVER,
            font=f_icon, height=theme.CONTROL_HEIGHT_SMALL, width=theme.CONTROL_WIDTH_ICON, text_color=theme.TEXT_ON_ACCENT, corner_radius=theme.RADIUS_SMALL,
            command=lambda: self.on_load_more() if self.on_load_more else None
        )
        self.load_more_btn.pack(side="left", padx=theme.SPACING_TINY)
        self.tip_load_more = Tooltip(self.load_more_btn, "טען מערכות נוספות")

        self.exclude_btn = ctk.CTkButton(
            self, text=f" {ICON_EXCLUDE} ", font=f_icon, fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            text_color=theme.TEXT_ON_ACCENT, height=theme.CONTROL_HEIGHT_SMALL, width=theme.CONTROL_WIDTH_ICON_SMALL,
            command=lambda: self.on_exclude() if self.on_exclude else None,
        )
        self.exclude_btn.pack(side="left", padx=theme.SPACING_TINY)
        self.tip_exclude = Tooltip(self.exclude_btn, "החרג יום נבחר")

        # Undo manual drag & drop changes (PLAN-563). Disabled until an edit exists.
        self.undo_btn = ctk.CTkButton(
            self, text="↩", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_HEADER, weight=theme.FONT_WEIGHT_BOLD),
            fg_color=theme.TEXT_ACCENT, hover_color=theme.ACCENT_HOVER, text_color=theme.TEXT_ON_ACCENT,
            height=theme.CONTROL_HEIGHT_SMALL, width=theme.CONTROL_WIDTH_ICON_SMALL, corner_radius=theme.RADIUS_SMALL, state="disabled",
            command=lambda: self.on_undo() if self.on_undo else None,
        )
        self.undo_btn.pack(side="left", padx=theme.SPACING_TINY)
        self.tip_undo = Tooltip(self.undo_btn, "בטל שינויים ידניים")

        # Elegant, branded download button on the right side
        self.export_btn = ctk.CTkButton(
            self, text=ICON_EXPORT, fg_color=theme.SUCCESS, hover_color=theme.SUCCESS_HOVER,
            font=ctk.CTkFont(family=theme.FONT_BOOTSTRAP_ICONS, size=theme.FONT_SIZE_HEADER), height=theme.CONTROL_HEIGHT_SMALL, width=theme.CONTROL_WIDTH_ICON,
            text_color=theme.TEXT_ON_ACCENT, corner_radius=theme.RADIUS_SMALL,
            command=lambda: self.on_export() if self.on_export else None,
        )
        self.export_btn.pack(side="right", padx=theme.RADIUS_SMALL)
        self.tip_export = Tooltip(self.export_btn, "ייצוא לוח זמנים")

        self.on_sync_clicked = None 

        # Sync button
        btn_run = ctk.CTkButton(
            self, 
            text="Sync", 
            width=theme.CONTROL_WIDTH_SYNC,
            fg_color=theme.SUCCESS, 
            command=self._on_sync_btn_click
        )
        btn_run.pack(side="right", padx=theme.SPACING_COMPACT)

    def _on_sync_btn_click(self):
        if self.on_sync_clicked:
            self.on_sync_clicked()

    def set_undo_enabled(self, enabled: bool):
        self.undo_btn.configure(state="normal" if enabled else "disabled")

    def set_pagination(self, current: int, total: int):
        self.page_entry.delete(0, "end")
        self.page_entry.insert(0, str(current))
        self.out_of_lbl.configure(text=f" / {total}")

    def update_language(self, lang: str):
        self.current_lang = lang
        # Update the tooltips according to the UI language
        if lang == "he":
            self.tip_edit.text = "עריכת תאריכים"
            self.refresh_feed_btn.configure(text=f"{ICON_REFRESH_FEED}  רענן")
            self.tip_refresh_feed.text = TRANSLATIONS["refresh_feed_tooltip"]["he"]
            self.tip_load_more.text = "טען מערכות נוספות"
            self.tip_constraints.text = "הגדרות אילוצים"
            self.tip_exclude.text = "החרג יום נבחר"
            self.tip_undo.text = "בטל שינויים ידניים"
            self.tip_export.text = "ייצוא לוח זמנים"
        else:
            self.tip_edit.text = "Edit Dates"
            self.refresh_feed_btn.configure(text=f"{ICON_REFRESH_FEED}  Refresh")
            self.tip_refresh_feed.text = TRANSLATIONS["refresh_feed_tooltip"]["en"]
            self.tip_load_more.text = "Load More"
            self.tip_constraints.text = "Constraints Settings"
            self.tip_exclude.text = "Exclude Date"
            self.tip_undo.text = "Undo manual changes"
            self.tip_export.text = "Export Schedule"