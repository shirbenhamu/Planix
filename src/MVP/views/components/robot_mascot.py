# src/MVP/views/components/robot_mascot.py
import math
import random
import tkinter as tk
import customtkinter as ctk
from src.MVP.views import theme

class RobotMascot(ctk.CTkFrame):
    """
    רובוט-סטודנט קטן, צף ודינמי. מציג פנים מסוג מסך (Visor) עם עיניים זוהרות,
    ידיים מרחפות, כובע בוגרים אלגנטי וצללית על הקרקע. עוקב אחרי העכבר ומרחף בעדינות.
    אופציונלי: בועת דיבור מעל הראש (פרמטר speech / set_speech).
    מרכיב ויזואלי בלבד להעשרת חוויית המשתמש.
    """

    W = 150
    BUBBLE_H = 104    # גובה אזור בועת הדיבור (כשהיא מוצגת) — מספיק לכמה שורות
    HEAD_MAX = 5      # כמה הראש זז לכיוון העכבר (פיקסלים)
    PUPIL_MAX = 5     # כמה האישונים זזים לכיוון העכבר (פיקסלים)
    FRAME_MS = 33     # ~30fps

    def __init__(self, master, speech=None, reserve_bubble=False, **kwargs):
        self._base_speech = speech          # בועת הקבע (אם יש)
        self._speech = speech               # מה שמוצג כרגע (יכול להיות בועה זמנית)
        self._temp_timer = None             # טיימר לבועה זמנית
        # שומרים מקום לבועה אם יש בועת קבע או אם ביקשו לשמור מקום (לבועות זמניות)
        self._oy = self.BUBBLE_H if (speech or reserve_bubble) else 0
        h = 150 + self._oy
        super().__init__(master, fg_color="transparent", width=self.W, height=h, **kwargs)
        self.grid_propagate(False)
        self.pack_propagate(False)

        self._mode = ctk.get_appearance_mode()
        self._palette = self._build_palette(self._mode)

        self.canvas = tk.Canvas(
            self, width=self.W, height=h,
            bg=self._palette["bg"], highlightthickness=0, bd=0,
        )
        self.canvas.place(relx=0.5, rely=0.5, anchor="center")

        self._mouse_xy = None
        self._head = [0.0, 0.0]
        self._pupil = [0.0, 0.0]
        self._float_ang = 0.0

        self._blinking = False
        self._blink_frames = 0
        self._blink_count = random.randint(60, 150)

        self.after(150, self._bind_mouse)
        self.after(200, self._tick)

    def set_speech(self, text):
        """עדכון בועת הקבע (למשל בעת החלפת שפה). לא דורס בועה זמנית פעילה."""
        self._base_speech = text
        if self._temp_timer is None:
            self._speech = text

    def show_speech(self, text, duration=2000):
        """מציג בועת דיבור זמנית למשך duration מילישניות, ואז חוזר לבועת הקבע."""
        self._speech = text
        if self._temp_timer is not None:
            try:
                self.after_cancel(self._temp_timer)
            except Exception:
                pass
        self._temp_timer = self.after(duration, self._revert_speech)

    def _revert_speech(self):
        self._temp_timer = None
        self._speech = self._base_speech
        # ציור מיידי כדי שהבועה תיעלם מיד בתום הזמן
        if self.winfo_exists():
            try:
                self._render_robot()
            except Exception:
                pass

    # ---------- צבעים לפי מצב יום/לילה ----------
    def _build_palette(self, mode):
        dark = mode != "Light"
        bg = theme.BG_MAIN[1] if dark else theme.BG_MAIN[0]

        if dark:
            return {
                "bg": bg,
                "body": "#eef6fb",
                "body_outline": "#cde1f0",
                "visor": "#1a2530",
                "eye_glow": "#00f0ff",
                "cap": "#22344a",
                "cap_band": "#16243a",
                "cap2": "#0d1b26",
                "tassel": "#f4c145",
                "tassel_dark": "#caa030",
                "shadow": "#151e28",
                "bubble": "#eef6fb",
                "bubble_outline": "#cde1f0",
                "bubble_text": "#1a2530",
            }
        else:
            return {
                "bg": bg,
                "body": "#2b3a4a",
                "body_outline": "#1e2936",
                "visor": "#111820",
                "eye_glow": "#00f0ff",
                "cap": "#22344a",
                "cap_band": "#16243a",
                "cap2": "#0d1b26",
                "tassel": "#f4c145",
                "tassel_dark": "#caa030",
                "shadow": "#c2d1e0",
                "bubble": "#ffffff",
                "bubble_outline": "#b9c9d6",
                "bubble_text": "#1e2936",
            }

    # ---------- מעקב עכבר ----------
    def _bind_mouse(self):
        try:
            self.winfo_toplevel().bind("<Motion>", self._on_motion, add="+")
        except Exception:
            pass

    def _on_motion(self, event):
        self._mouse_xy = (event.x_root, event.y_root)

    # ---------- לולאת אנימציה ----------
    def _tick(self):
        if not self.winfo_exists():
            return

        self._float_ang += 0.12

        mode = ctk.get_appearance_mode()
        if mode != self._mode:
            self._mode = mode
            self._palette = self._build_palette(mode)
            try:
                self.canvas.configure(bg=self._palette["bg"])
            except Exception:
                pass

        nx = ny = 0.0
        if self._mouse_xy is not None:
            try:
                cx = self.canvas.winfo_rootx() + self.W / 2
                cy = self.canvas.winfo_rooty() + 64 + self._oy
                dx = self._mouse_xy[0] - cx
                dy = self._mouse_xy[1] - cy
                dist = math.hypot(dx, dy)
                if dist > 4:
                    nx, ny = dx / dist, dy / dist
            except Exception:
                pass

        for cur, target in ((self._head, (nx * self.HEAD_MAX, ny * self.HEAD_MAX)),
                            (self._pupil, (nx * self.PUPIL_MAX, ny * self.PUPIL_MAX))):
            cur[0] += (target[0] - cur[0]) * 0.22
            cur[1] += (target[1] - cur[1]) * 0.22

        if self._blinking:
            self._blink_frames -= 1
            if self._blink_frames <= 0:
                self._blinking = False
                self._blink_count = random.randint(60, 150)
        else:
            self._blink_count -= 1
            if self._blink_count <= 0:
                self._blinking = True
                self._blink_frames = 5

        self._render_robot()
        self.after(self.FRAME_MS, self._tick)

    # ---------- עזר: מלבן מעוגל ----------
    @staticmethod
    def _round_rect(c, x0, y0, x1, y1, r, **kw):
        pts = [x0 + r, y0, x1 - r, y0, x1, y0, x1, y0 + r, x1, y1 - r, x1, y1,
               x1 - r, y1, x0 + r, y1, x0, y1, x0, y1 - r, x0, y0 + r, x0, y0]
        return c.create_polygon(pts, smooth=True, **kw)

    # ---------- ציור ----------
    def _render_robot(self):
        c = self.canvas
        c.delete("all")
        p = self._palette
        oy = self._oy

        fy = math.sin(self._float_ang) * 4
        head_fy = math.sin(self._float_ang + 0.6) * 3

        hx, hy = self._head[0], self._head[1] + head_fy
        pdx, pdy = self._pupil[0], self._pupil[1]

        def X(x): return x + hx
        def Y(y): return y + hy + oy
        def BY(y): return y + oy   # קואורדינטות גוף (בלי תזוזת ראש)

        # ====== בועת דיבור (אופציונלי) — דינמית, מתאימה את גובהה לטקסט ======
        if self._speech:
            import tkinter.font as tkfont
            bubble_w = 130          # רוחב הבועה
            pad_x, pad_y = 12, 9    # ריווח פנימי
            wrap_w = bubble_w - pad_x * 2
            f_bubble = tkfont.Font(family=theme.FONT_FAMILY, size=11, weight="bold")

            # פירוק הטקסט לשורות לפי רוחב הגלישה (כדי לדעת כמה שורות וגובה צריך)
            words = str(self._speech).split()
            lines, cur = [], ""
            for w in words:
                trial = (cur + " " + w).strip()
                if f_bubble.measure(trial) <= wrap_w or not cur:
                    cur = trial
                else:
                    lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)
            if not lines:
                lines = [""]

            line_h = f_bubble.metrics("linespace")
            text_h = line_h * len(lines)
            bubble_h = text_h + pad_y * 2
            bx0 = 75 - bubble_w / 2
            bx1 = 75 + bubble_w / 2
            by1 = self.BUBBLE_H - 14        # תחתית הבועה (מעט מעל הראש)
            by0 = by1 - bubble_h
            if by0 < 2:                     # ביטחון: לא לחרוג מעבר לראש ה-Canvas
                by0 = 2
                by1 = by0 + bubble_h

            # זנב שמצביע אל הראש (מאחורי הבועה)
            c.create_polygon(69, by1 - 2, 75, by1 + 16, 81, by1 - 2,
                             fill=p["bubble"], outline=p["bubble_outline"], width=2)
            # גוף הבועה
            self._round_rect(c, bx0, by0, bx1, by1, 12, fill=p["bubble"], outline=p["bubble_outline"], width=2)
            # הטקסט במרכז הבועה
            c.create_text(75, (by0 + by1) / 2, text=self._speech, fill=p["bubble_text"],
                          font=f_bubble, width=wrap_w, justify="center")

        # ====== צללית 3D ======
        shadow_w = 16 - (fy * 1.5)
        c.create_oval(75 - shadow_w, BY(142), 75 + shadow_w, BY(148), fill=p["shadow"], outline="")

        # ====== ידיים צפות ======
        c.create_oval(22, BY(105 + fy), 38, BY(122 + fy), fill=p["body"], outline=p["body_outline"], width=2)
        c.create_oval(112, BY(105 + fy), 128, BY(122 + fy), fill=p["body"], outline=p["body_outline"], width=2)

        # ====== גוף ======
        c.create_oval(45, BY(90 + fy), 105, BY(138 + fy), fill=p["body"], outline=p["body_outline"], width=2)
        c.create_oval(71, BY(108 + fy), 79, BY(116 + fy), fill=p["eye_glow"], outline="")

        # ====== ראש ======
        c.create_oval(X(30), Y(35), X(120), Y(95), fill=p["body"], outline=p["body_outline"], width=2)

        c.create_oval(X(26), Y(55), X(34), Y(75), fill=p["body_outline"], outline="", width=0)
        c.create_oval(X(116), Y(55), X(124), Y(75), fill=p["body_outline"], outline="", width=0)

        c.create_oval(X(40), Y(45), X(110), Y(85), fill=p["visor"], outline="", width=0)

        # ====== כובע בוגרים אלגנטי ======
        c.create_polygon(X(60), Y(30), X(90), Y(30), X(86), Y(42), X(64), Y(42), fill=p["cap_band"], outline="")
        c.create_oval(X(62), Y(38), X(88), Y(46), fill=p["cap_band"], outline="")
        c.create_polygon(X(75), Y(20), X(120), Y(31), X(75), Y(42), X(30), Y(31), fill=p["cap2"], outline="")
        c.create_polygon(X(75), Y(13), X(118), Y(28), X(75), Y(39), X(32), Y(28), fill=p["cap"], outline=p["cap2"], width=1)
        c.create_oval(X(71), Y(24), X(79), Y(32), fill=p["tassel"], outline=p["tassel_dark"], width=1)

        sway = math.sin(self._float_ang) * 3
        c.create_line(X(75), Y(28), X(108), Y(30), X(110 + sway), Y(50), fill=p["tassel"], width=2, smooth=True)
        c.create_oval(X(106 + sway), Y(50), X(114 + sway), Y(58), fill=p["tassel"], outline=p["tassel_dark"], width=1)

        # ====== עיניים זוהרות במסך ======
        ex_l, ex_r, ey = 60, 90, 65
        px = max(-6, min(6, pdx))
        py = max(-6, min(6, pdy))

        if self._blinking:
            c.create_line(X(ex_l - 8 + px), Y(ey + py), X(ex_l + 8 + px), Y(ey + py), fill=p["eye_glow"], width=3, capstyle=tk.ROUND)
            c.create_line(X(ex_r - 8 + px), Y(ey + py), X(ex_r + 8 + px), Y(ey + py), fill=p["eye_glow"], width=3, capstyle=tk.ROUND)
        else:
            c.create_oval(X(ex_l - 6 + px), Y(ey - 7 + py), X(ex_l + 6 + px), Y(ey + 7 + py), fill=p["eye_glow"], outline="")
            c.create_oval(X(ex_r - 6 + px), Y(ey - 7 + py), X(ex_r + 6 + px), Y(ey + 7 + py), fill=p["eye_glow"], outline="")
            c.create_oval(X(ex_l - 4 + px), Y(ey - 5 + py), X(ex_l - 1 + px), Y(ey - 2 + py), fill="#ffffff", outline="")
            c.create_oval(X(ex_r - 4 + px), Y(ey - 5 + py), X(ex_r - 1 + px), Y(ey - 2 + py), fill="#ffffff", outline="")