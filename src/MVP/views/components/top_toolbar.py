# src/MVP/views/components/top_toolbar.py

import customtkinter as ctk
from src.MVP.views.ui_utils import TRANSLATIONS
from src.MVP.views import theme
from src.MVP.views.components.ui_components import (
    Tooltip, ICON_EDIT, ICON_LOAD_MORE, ICON_REFRESH_FEED, ICON_EXCLUDE, ICON_EXPORT, ICON_SETTINGS, ICON_SEARCH
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
        # Kept for toggling the deep-search button between an icon glyph (search)
        # and a plain bold "✕" (cancel) which renders in the regular font.
        self._f_icon = f_icon
        self._f_btn = f_btn

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
        self.on_load_all = None
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

        # "Dirty" = the user is typing an unsubmitted jump target into the page
        # box. While dirty, a background pagination refresh (e.g. the 500ms poll
        # while the engine keeps generating) must NOT overwrite the box, or the
        # user can never finish entering a jump. It is set ONLY by real
        # keystrokes — NOT by mere focus — so plain prev/next browsing (no typing)
        # still keeps the page counter in sync.
        self._page_current = 1
        self._page_total = 1
        self._page_entry_dirty = False
        # How many schedules are still in the warehouse (unbuilt). Shown on the
        # Load More hover tooltip so the user can see when it reaches 0.
        self._load_more_remaining = None
        # Whether a deep search is running (button shows 'Cancel deep search').
        self._load_all_running = False

        self.page_entry = ctk.CTkEntry(self.nav_frame, width=theme.CONTROL_WIDTH_PAGE_ENTRY, height=theme.CONTROL_HEIGHT_TINY, justify="center", font=f_btn,
                                       fg_color=theme.BG_CARD, border_color=theme.BORDER_DEFAULT, text_color=theme.TEXT_MAIN)
        self.page_entry.pack(side="left", padx=theme.SPACING_XS)
        self.page_entry.bind("<Return>", self._on_page_entry_return)
        self.page_entry.bind("<KeyRelease>", self._on_page_entry_key)
        self.page_entry.bind("<FocusOut>", self._on_page_entry_focus_out)

        self.out_of_lbl = ctk.CTkLabel(
            self.nav_frame, text="", font=f_btn, width=theme.CONTROL_WIDTH_PAGE_LABEL, anchor="w", text_color=theme.TEXT_MUTED)
        self.out_of_lbl.pack(side="left", padx=theme.SPACING_XS)
        ctk.CTkButton(self.nav_frame, text=">", font=f_btn, width=theme.CONTROL_WIDTH_NAV, height=theme.CONTROL_HEIGHT_TINY,
                      command=lambda: self.on_next() if self.on_next else None).pack(side="left", padx=theme.SPACING_XS)

        self.refresh_feed_btn = ctk.CTkButton(
            self.nav_frame,
            # Text-only (no icon): the Load More button already uses the refresh
            # icon, so a plain label keeps the two actions visually distinct.
            text="רענן",
            font=f_btn,
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

        # Deep search: a magnifying-glass icon button. Hover shows 'Deep search';
        # while running it turns red (cancel). Opens a warning first via on_load_all.
        self.load_all_btn = ctk.CTkButton(
            self, text=ICON_SEARCH, font=f_icon,
            fg_color=theme.SUCCESS, hover_color=theme.ACCENT_HOVER,
            text_color=theme.TEXT_ON_ACCENT, height=theme.CONTROL_HEIGHT_SMALL,
            width=theme.CONTROL_WIDTH_ICON, corner_radius=theme.RADIUS_SMALL,
            command=lambda: self.on_load_all() if self.on_load_all else None,
        )
        self.load_all_btn.pack(side="left", padx=theme.SPACING_TINY)
        self.tip_load_all = Tooltip(self.load_all_btn, TRANSLATIONS["load_all_tooltip"][self.current_lang])

        # Small "X schedules remain to load" indicator next to the load buttons.
        self.remaining_lbl = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_XS),
            text_color=theme.TEXT_MUTED, anchor="w",
        )
        self.remaining_lbl.pack(side="left", padx=theme.SPACING_XS)

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
        self.sync_btn = ctk.CTkButton(
            self,
            text="Sync",
            width=theme.CONTROL_WIDTH_SYNC,
            fg_color=theme.SUCCESS,
            command=self._on_sync_btn_click
        )
        self.sync_btn.pack(side="right", padx=theme.SPACING_COMPACT)

    def _on_sync_btn_click(self):
        if self.on_sync_clicked:
            self.on_sync_clicked()

    def set_sync_enabled(self, enabled: bool):
        if hasattr(self, "sync_btn"):
            self.sync_btn.configure(state="normal" if enabled else "disabled")

    def set_undo_enabled(self, enabled: bool):
        self.undo_btn.configure(state="normal" if enabled else "disabled")

    def set_load_more_enabled(self, enabled: bool):
        if hasattr(self, "load_more_btn"):
            self.load_more_btn.configure(state="normal" if enabled else "disabled")

    def set_load_all_enabled(self, enabled: bool):
        if hasattr(self, "load_all_btn"):
            self.load_all_btn.configure(state="normal" if enabled else "disabled")

    def set_load_all_running(self, running: bool):
        """Toggle the deep-search icon button: magnifying glass (idle, green) vs
        x-circle (running, red). A running search is cancelled with a second
        click. The tooltip text switches accordingly (bilingual)."""
        self._load_all_running = running
        if not hasattr(self, "load_all_btn"):
            return
        if running:
            self.load_all_btn.configure(
                text="✕", font=self._f_btn,   # plain X -> cancel
                fg_color=theme.DANGER, hover_color=theme.DANGER_HOVER,
            )
            self.tip_load_all.text = TRANSLATIONS["load_all_cancel"][self.current_lang]
        else:
            self.load_all_btn.configure(
                text=ICON_SEARCH, font=self._f_icon,   # magnifying glass -> deep search
                fg_color=theme.SUCCESS, hover_color=theme.ACCENT_HOVER,
            )
            self.tip_load_all.text = TRANSLATIONS["load_all_tooltip"][self.current_lang]

    def set_remaining_text(self, text: str):
        """Side meter text (used for the Load All progress percentage)."""
        if hasattr(self, "remaining_lbl"):
            self.remaining_lbl.configure(text=text)

    def _render_load_more_tooltip(self):
        if getattr(self, "_load_more_remaining", None) is None:
            self.tip_load_more.text = TRANSLATIONS["load_more_tooltip"][self.current_lang]
        elif self._load_more_remaining <= 0:
            self.tip_load_more.text = TRANSLATIONS["load_more_stock_none"][self.current_lang]
        else:
            self.tip_load_more.text = TRANSLATIONS["load_more_stock"][self.current_lang].format(
                n=f"{self._load_more_remaining:,}")

    def set_load_more_remaining(self, remaining):
        """How many schedules remain in the warehouse; rendered on the Load More
        hover tooltip so the user can see it count down toward 0."""
        self._load_more_remaining = remaining
        self._render_load_more_tooltip()

    def set_load_more_calculating(self):
        """Shown on the Load More tooltip while the total is being counted, so
        the number isn't blank until the background count finishes."""
        self.tip_load_more.text = TRANSLATIONS["load_more_calc"][self.current_lang]

    _NON_TYPING_KEYS = {"Return", "KP_Enter", "Tab", "Escape", "Up", "Down", "Left", "Right"}

    def _on_page_entry_key(self, event=None):
        # A real edit keystroke: the box now holds an unsubmitted jump target,
        # so guard it against background refreshes. Navigation/submit keys don't
        # count as composing a jump.
        if event is not None and getattr(event, "keysym", "") in self._NON_TYPING_KEYS:
            return
        self._page_entry_dirty = self.page_entry.get().strip() != str(self._page_current)

    def _on_page_entry_return(self, _event=None):
        # Submitting the jump clears the dirty guard so the box resyncs to the
        # page actually shown afterwards.
        self._page_entry_dirty = False
        if not self.on_page_jump:
            return
        try:
            self.on_page_jump(int(self.page_entry.get()))
        except (ValueError, TypeError):
            # Non-numeric / empty input: just restore the current page number.
            self._write_page_entry(self._page_current)

    def _on_page_entry_focus_out(self, _event=None):
        # Leaving the box discards any half-typed value and shows the real page.
        self._page_entry_dirty = False
        self._write_page_entry(self._page_current)

    def _write_page_entry(self, current: int) -> None:
        self.page_entry.delete(0, "end")
        self.page_entry.insert(0, str(current))

    def set_pagination(self, current: int, total: int):
        self._page_current = current
        self._page_total = total
        # Skip the rewrite ONLY while the user is mid-typing a jump target, so a
        # background poll can't wipe their input. Plain prev/next browsing sets
        # no keystrokes, so the counter still tracks the displayed schedule.
        if not self._page_entry_dirty:
            self._write_page_entry(current)
        self.out_of_lbl.configure(text=f" / {total}")

    def update_language(self, lang: str):
        self.current_lang = lang
        # Update the tooltips according to the UI language
        # Load All / Cancel button + tooltip track the language and run state.
        if hasattr(self, "load_all_btn"):
            self.set_load_all_running(self._load_all_running)
        # Load More tooltip re-renders from the stored remaining count.
        self._render_load_more_tooltip()
        if lang == "he":
            self.tip_edit.text = "עריכת תאריכים"
            self.refresh_feed_btn.configure(text="רענן")
            self.tip_refresh_feed.text = TRANSLATIONS["refresh_feed_tooltip"]["he"]
            self.tip_constraints.text = "הגדרות אילוצים"
            self.tip_exclude.text = "החרג יום נבחר"
            self.tip_undo.text = "בטל שינויים ידניים"
            self.tip_export.text = "ייצוא לוח זמנים"
        else:
            self.tip_edit.text = "Edit Dates"
            self.refresh_feed_btn.configure(text="Refresh")
            self.tip_refresh_feed.text = TRANSLATIONS["refresh_feed_tooltip"]["en"]
            self.tip_constraints.text = "Constraints Settings"
            self.tip_exclude.text = "Exclude Date"
            self.tip_undo.text = "Undo manual changes"
            self.tip_export.text = "Export Schedule"