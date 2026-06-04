# src/MVP/app_window.py

import customtkinter as ctk
import sys
import os
import ctypes
from typing import Callable

from src.MVP.views import theme

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASE_DIR)

# קבועי Win32 עבור נראות בשורת המשימות + מזעור
GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
SW_MINIMIZE = 6


def load_custom_fonts():
    if os.name != "nt":
        return

    fonts_dir = os.path.join(BASE_DIR, "assets", "fonts")
    if not os.path.exists(fonts_dir):
        return

    for font_file in os.listdir(fonts_dir):
        if font_file.endswith((".ttf", ".otf")):
            font_path = os.path.join(fonts_dir, font_file)
            ctypes.windll.gdi32.AddFontResourceExW(font_path, 0x10 | 0x20, 0)


load_custom_fonts()

from src.MVP.views.input_view import InputConfigurationView
from src.MVP.views.calendar_view import CalendarGridView
from src.MVP.views.monthly_view import MonthlyGridView
from src.MVP.views.components.sidebar import Sidebar


class AppWindow(ctk.CTk):
    SIDEBAR_WIDTH = 240
    TOP_STRIP = 48  # רצועה עליונה לכפתורי החלון, כדי שה-toolbar לא יתנגש בהם

    def __init__(self):
        super().__init__()

        self.title("Planix")
        self.overrideredirect(True)          # מסיר את שורת הכותרת של Windows
        self.geometry("1400x800")
        self.minsize(1100, 700)

        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.configure(fg_color=theme.BG_MAIN)

        self.sidebar_visible = False
        self.sidebar_width = self.SIDEBAR_WIDTH
        self.is_maximized = False
        self.normal_geometry = "1400x800"
        self.on_navigation_requested: Callable[[str], None] = None

        self._build_layout()
        self._build_views()
        self._build_top_controls()
        self._wire_views()

        self.bind("<Motion>", self._check_hover_close)
        self.switch_view("input")
        self.after(100, self._lift_floating_controls)

        # מחזיר את החלון לשורת המשימות למרות overrideredirect
        if os.name == "nt":
            self.after(50, self._enable_taskbar)

    # ----------------------------------------------------------------- בנייה

    def _build_layout(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_container.pack(fill="both", expand=True)

        # הרצועה העליונה לכפתורי החלון מוחלת כאן (פעם אחת), כך שכל המסכים
        # מתחילים מתחתיה ואין צורך ב-pady שונה לכל מסך. בזכות זה כשמסך מסוים
        # נמצא בחזית, לא "מציץ" מסך אחר ברצועה שמעליו.
        self.views_container = ctk.CTkFrame(
            self.main_container, fg_color="transparent", corner_radius=0
        )
        self.views_container.pack(fill="both", expand=True, pady=(self.TOP_STRIP, 0))

        # כל המסכים נערמים באותו תא; המעבר נעשה ב-tkraise (כמו טאבים בדפדפן)
        self.views_container.grid_rowconfigure(0, weight=1)
        self.views_container.grid_columnconfigure(0, weight=1)

        # Sidebar נפתח מעל התוכן, מ-(0,0). הרוחב נקבע בבנאי של Sidebar (240).
        self.sidebar = Sidebar(self.main_container, base_dir=BASE_DIR)
        self.sidebar.on_nav_click = self._handle_sidebar_click
        self.sidebar.on_theme_toggle = self._toggle_theme
        self.sidebar.on_lang_toggle = self._toggle_language

    def _build_views(self):
        self.input_view = InputConfigurationView(self.views_container)
        self.calendar_view = CalendarGridView(self.views_container)
        self.monthly_view = MonthlyGridView(self.views_container)

        # כל המסכים נפרסים ונצבעים כבר עכשיו (גם אלה שמאחור), באותו תא.
        # לכן המעבר ביניהם הוא מיידי — רק הבאה לחזית, בלי פריסה/צביעה מחדש.
        for v in (self.input_view, self.calendar_view, self.monthly_view):
            v.grid(row=0, column=0, sticky="nsew")

        self.input_view.tkraise()
        self._hide_inner_hamburger_buttons()

    def _build_top_controls(self):
        # המבורגר גלובלי בפינה השמאלית העליונה, מ-(0,0)
        self.global_hamburger_btn = ctk.CTkButton(
            self, text="☰", width=44, height=44, corner_radius=0,
            fg_color="transparent", hover_color=("gray85", "gray20"),
            text_color=("black", "white"),
            font=ctk.CTkFont(size=30, weight="bold"),
            command=self._toggle_sidebar,
        )
        self.global_hamburger_btn.place(x=0, y=0)
        self.global_hamburger_btn.bind("<Enter>", self._open_sidebar)

        # כפתורי חלון צפים בפינה הימנית — בלי פס עליון מלא
        btn = 34
        gap = 4
        common = dict(
            width=btn, height=btn, corner_radius=8,
            fg_color="transparent", text_color=("black", "white"),
        )

        self.close_btn = ctk.CTkButton(
            self, text="✕", hover_color="#e74c3c",
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.destroy, **common,
        )
        self.max_btn = ctk.CTkButton(
            self, text="▢", hover_color=("gray80", "gray25"),
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._toggle_maximize, **common,
        )
        self.min_btn = ctk.CTkButton(
            self, text="—", hover_color=("gray80", "gray25"),
            font=ctk.CTkFont(size=18, weight="bold"),
            command=self._minimize_window, **common,
        )

        self.close_btn.place(relx=1.0, x=-(btn + gap), y=4, anchor="ne")
        self.max_btn.place(relx=1.0, x=-(btn * 2 + gap * 2), y=4, anchor="ne")
        self.min_btn.place(relx=1.0, x=-(btn * 3 + gap * 3), y=4, anchor="ne")

        # אזור גרירה שקוף במרכז העליון
        self.drag_area = ctk.CTkFrame(
            self, width=420, height=36, fg_color="transparent", corner_radius=0
        )
        self.drag_area.place(relx=0.5, y=0, anchor="n")
        self.drag_area.bind("<Button-1>", self._start_move)
        self.drag_area.bind("<B1-Motion>", self._do_move)
        self.drag_area.bind("<Double-Button-1>", lambda e: self._toggle_maximize())

    def _wire_views(self):
        self.input_view.on_run_clicked = lambda: self._handle_sidebar_click("run")
        self.calendar_view.set_monthly_view(self.monthly_view)

        mt = getattr(self.monthly_view, "toolbar", None)
        ct = getattr(self.calendar_view, "toolbar", None)
        if mt and ct:
            mt.on_next = lambda: ct.on_next() if ct.on_next else None
            mt.on_prev = lambda: ct.on_prev() if ct.on_prev else None
            mt.on_page_jump = lambda p: ct.on_page_jump(p) if ct.on_page_jump else None
            mt.on_exclude = lambda: ct.on_exclude() if ct.on_exclude else None
            mt.on_export = lambda: ct.on_export() if ct.on_export else None
            mt.on_filter = lambda: ct.on_filter() if ct.on_filter else None

        self.monthly_view.on_cell_clicked = (
            lambda key: self.calendar_view._handle_cell_click(key)
        )

        # מאפשר לכפתור "עריכת תאריכים" במסך החודשי והשנתי להשתמש באותו
        # מקור נתונים של מסך הקלט, כך שייפתח אותו חלון עם אותם נתונים
        self.calendar_view.get_exam_periods_callback = (
            lambda: self.input_view.get_exam_periods_callback()
            if self.input_view.get_exam_periods_callback else None
        )
        self.monthly_view.get_exam_periods_callback = (
            lambda: self.input_view.get_exam_periods_callback()
            if self.input_view.get_exam_periods_callback else None
        )

    # ------------------------------------------------- נראות בשורת המשימות

    def _hwnd(self):
        return ctypes.windll.user32.GetParent(self.winfo_id())

    def _enable_taskbar(self):
        """מחזיר את החלון לשורת המשימות למרות overrideredirect."""
        if os.name != "nt":
            return
        try:
            hwnd = self._hwnd()
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = (style & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            # רענון קצר כדי שהשינוי ייכנס לתוקף
            self.wm_withdraw()
            self.after(10, self.wm_deiconify)
            self.after(40, self._lift_floating_controls)
        except Exception:
            pass

    # ------------------------------------------------------- כפתורים עליונים

    def _lift_floating_controls(self):
        for w in (
            self.global_hamburger_btn, self.close_btn,
            self.max_btn, self.min_btn, self.drag_area,
        ):
            w.lift()

    def _hide_inner_hamburger_buttons(self):
        """מסתיר המבורגרים פנימיים מתוך ה-Views כדי שיהיה רק אחד גלובלי."""
        candidates = []
        if hasattr(self.input_view, "hamburger_btn"):
            candidates.append(self.input_view.hamburger_btn)
        for view in (self.calendar_view, self.monthly_view):
            tb = getattr(view, "toolbar", None)
            if tb and hasattr(tb, "hamburger_btn"):
                candidates.append(tb.hamburger_btn)

        for btn in candidates:
            for forget in (btn.place_forget, btn.pack_forget, btn.grid_forget):
                try:
                    forget()
                except Exception:
                    pass

    # ------------------------------------------------------- גרירת החלון

    def _start_move(self, event):
        if self.is_maximized:
            return
        self._drag_start_x = event.x_root
        self._drag_start_y = event.y_root
        self._window_start_x = self.winfo_x()
        self._window_start_y = self.winfo_y()

    def _do_move(self, event):
        if self.is_maximized:
            return
        new_x = self._window_start_x + (event.x_root - self._drag_start_x)
        new_y = self._window_start_y + (event.y_root - self._drag_start_y)
        self.geometry(f"+{new_x}+{new_y}")

    def _toggle_maximize(self):
        if not self.is_maximized:
            self.normal_geometry = self.geometry()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            self.geometry(f"{sw}x{sh}+0+0")
            self.is_maximized = True
            self.max_btn.configure(text="❐")
        else:
            self.geometry(self.normal_geometry)
            self.is_maximized = False
            self.max_btn.configure(text="▢")
        self.after(20, self._lift_floating_controls)

    def _minimize_window(self):
        # עם WS_EX_APPWINDOW המזעור עובד נקי דרך Windows עצמו
        if os.name == "nt":
            try:
                ctypes.windll.user32.ShowWindow(self._hwnd(), SW_MINIMIZE)
                return
            except Exception:
                pass
        self.iconify()

    # ------------------------------------------------------- ניווט / Views

    def _handle_sidebar_click(self, action: str):
        if action == "run":
            self._show_monthly_on_run = True
            # מעלים וצובעים את המסך החודשי מיד (כולל הסרגל) לפני שהבקרה עוברת
            # ל-controller שמפעיל את המנוע. update_idletasks מאלץ ציור מיידי, כך
            # שהסרגל כבר יציב על המסך והמנוע מתחיל רק אחריו — בלי "טעינה" מרצדת.
            self.switch_view("monthly")
            self.update_idletasks()
            self._switch_view("calendar")
        elif action == "input":
            self._switch_view("input")
        elif action == "monthly":
            self.switch_view("monthly")
        elif action == "annual":
            self.switch_view("annual")
        self._close_sidebar()

    def switch_view(self, view_name: str) -> None:
        # מעבר מיידי בהבאה לחזית בלבד (tkraise), בלי pack_forget/pack שגורם
        # לפריסה וצביעה מחדש. כל המסכים כבר טעונים ברקע, אז אין ריצוד ואין
        # תחושת "טעינה" — בדיוק כמו מעבר בין טאבים.
        if view_name == "calendar":
            view_name = "monthly" if getattr(self, "_show_monthly_on_run", True) else "annual"

        if view_name == "input":
            self.input_view.tkraise()
        elif view_name == "monthly":
            self._show_monthly_on_run = True
            self.monthly_view.tkraise()
        elif view_name == "annual":
            self._show_monthly_on_run = False
            self.calendar_view.tkraise()

        self.sidebar.update_active_btn(view_name)
        self.after(20, self._lift_floating_controls)

    def _switch_view(self, view_name: str) -> None:
        if self.on_navigation_requested:
            self.on_navigation_requested(view_name)

    # ------------------------------------------------------- Sidebar

    def _toggle_sidebar(self):
        self._close_sidebar() if self.sidebar_visible else self._open_sidebar()

    def _open_sidebar(self, event=None):
        if self.sidebar_visible:
            return
        self.sidebar.place(x=0, y=0, relheight=1.0, anchor="nw")
        self.sidebar.lift()
        self.global_hamburger_btn.place_forget()   # מעלים את ההמבורגר כשהתפריט פתוח
        self.sidebar_visible = True

    def _close_sidebar(self):
        if self.sidebar_visible:
            self.sidebar.place_forget()
            self.global_hamburger_btn.place(x=0, y=0)   # מחזיר את ההמבורגר
            self.sidebar_visible = False
        self.after(20, self._lift_floating_controls)

    def _check_hover_close(self, event):
        if not self.sidebar_visible:
            return
        mouse_x = event.x_root - self.winfo_rootx()
        if mouse_x > self.sidebar_width + 20:
            self._close_sidebar()

    # ------------------------------------------------------- שפה / ערכת נושא

    def _toggle_language(self, new_lang):
        self.sidebar.update_language(new_lang)
        self.input_view.update_language(new_lang)
        self.calendar_view.update_language(new_lang)
        self.monthly_view.update_language(new_lang)
        self.after(20, self._lift_floating_controls)

    def _toggle_theme(self, new_theme):
        # החלפת מצב יום/לילה מיידית, בלי fade שגורם לחלון להיראות שקוף.
        # CustomTkinter מעדכן אוטומטית את צבעי כל הווידג'טים, ולכן אין צורך
        # ברינדור מחדש של המסכים. מספיק לרענן את תווית מתג היום/לילה.
        ctk.set_appearance_mode(new_theme)
        self.sidebar.update_language(self.sidebar.lang_var.get())
        self.after(20, self._lift_floating_controls)


if __name__ == "__main__":
    app = AppWindow()
    app.mainloop()