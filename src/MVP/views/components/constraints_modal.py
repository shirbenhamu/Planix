# src/MVP/views/components/constraints_modal.py

import tkinter as tk
from typing import Callable, Dict, Optional, Union, List

import customtkinter as ctk

from src.MVP.views import theme
from src.MVP.views.ui_utils import format_text
from src.MVP.views.components.ui_components import create_secondary_button


CONSTRAINT_FIELDS = [
    {
        "enabled": "min_days_mandatory_enabled",
        "k": "min_days_mandatory_k",
        "label": "constraint_min_days_mandatory",
        "default_enabled": False,
        "default_k": 0,
    },
    {
        "enabled": "min_days_any_enabled",
        "k": "min_days_any_k",
        "label": "constraint_min_days_any",
        "default_enabled": False,
        "default_k": 0,
    },
    {
        "enabled": "max_elective_conflicts_enabled",
        "k": "max_elective_conflicts_k",
        "label": "constraint_max_elective_conflicts",
        "default_enabled": False,
        "default_k": 0,
    },
    {
        "enabled": "span_mandatory_enabled",
        "k": "span_mandatory_k",
        "label": "constraint_span_mandatory",
        "default_enabled": False,
        "default_k": 0,
    },
    {
        "enabled": "max_exams_per_day_enabled",
        "k": "max_exams_per_day_k",
        "label": "constraint_max_exams_per_day",
        "default_enabled": False,
        "default_k": 1,
    },
]


def default_constraints_data() -> Dict[str, Union[int, bool, list]]:
    data: Dict[str, Union[int, bool, list]] = {}
    for field in CONSTRAINT_FIELDS:
        data[field["enabled"]] = field["default_enabled"]
        data[field["k"]] = field["default_k"]
    # PLAN-555: Baseline system configuration default initialization
    data["selected_religions"] = []
    return data


def normalize_constraints_data(data: Optional[dict]) -> Dict[str, Union[int, bool, list]]:
    normalized = default_constraints_data()
    if not data:
        return normalized

    for field in CONSTRAINT_FIELDS:
        normalized[field["enabled"]] = bool(data.get(field["enabled"], field["default_enabled"]))
        normalized[field["k"]] = _safe_non_negative_int(data.get(field["k"], field["default_k"]), field["default_k"])
    
    # PLAN-555: Persist selected religions array directly within normalized system state config
    normalized["selected_religions"] = list(data.get("selected_religions", []))
    return normalized


def _safe_non_negative_int(value, default: int = 0) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return max(0, parsed)


def _is_non_negative_int_candidate(value: str) -> bool:
    return value == "" or value.isdigit()


class ConstraintsSettingsModal(ctk.CTkToplevel):
    """Modal settings window for the five pruning constraints."""

    def __init__(
        self,
        parent,
        current_lang: str = "he",
        constraints_data: Optional[dict] = None,
        on_save_callback: Optional[Callable[[dict], None]] = None,
        on_close_callback: Optional[Callable[[dict], None]] = None,
        save_enabled: bool = True,
    ):
        super().__init__(parent)
        self.parent = parent
        self.current_lang = current_lang
        self.on_save_callback = on_save_callback
        self.on_close_callback = on_close_callback
        self.save_enabled = save_enabled
        self._row_refs = []
        self._religion_boxes: Dict[str, tk.BooleanVar] = {}  # PLAN-555: Religion checkboxes tracking variables mapping
        self._vars: Dict[str, tk.Variable] = {}
        self._state = normalize_constraints_data(constraints_data)
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Match the application's custom modal style instead of showing the
        # native Windows title bar/frame.
        self.overrideredirect(True)
        self.title(format_text("constraints_title", current_lang))
        self.configure(fg_color=theme.BG_CARD)
        self.geometry(theme.CONSTRAINTS_MODAL_GEOMETRY)
        self.minsize(theme.CONSTRAINTS_MODAL_MIN_WIDTH, theme.CONSTRAINTS_MODAL_MIN_HEIGHT)
        self.transient(parent)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close_without_saving)

        self._build_ui()
        self._center_on_parent()
        self.lift()
        self.focus_force()

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        outer = ctk.CTkFrame(
            self,
            fg_color=theme.BG_CARD,
            border_width=theme.BORDER_WIDTH_ACTIVE,
            border_color=theme.TEXT_ACCENT,
            corner_radius=theme.RADIUS_CARD,
        )
        outer.grid(row=0, column=0, sticky="nsew", padx=theme.SPACING_NONE, pady=theme.SPACING_NONE)
        outer.grid_columnconfigure(0, weight=1)
        outer.grid_rowconfigure(1, weight=1)
        self.outer_frame = outer

        title_bar = ctk.CTkFrame(outer, fg_color=theme.TRANSPARENT)
        title_bar.grid(row=0, column=0, sticky="ew", padx=theme.SPACING_LARGE, pady=(theme.SPACING_LARGE, theme.SPACING_COMPACT))
        title_bar.grid_columnconfigure(0, weight=1)
        title_bar.bind("<ButtonPress-1>", self._start_drag)
        title_bar.bind("<B1-Motion>", self._on_drag)

        title = ctk.CTkLabel(
            title_bar,
            text=format_text("constraints_title", self.current_lang),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_MODAL_TITLE, weight=theme.FONT_WEIGHT_BOLD),
            text_color=theme.TEXT_ACCENT,
        )
        title.grid(row=0, column=0, sticky="ew")
        title.bind("<ButtonPress-1>", self._start_drag)
        title.bind("<B1-Motion>", self._on_drag)

        body = ctk.CTkScrollableFrame(
            outer,
            fg_color=theme.BG_CARD,
            border_width=theme.BORDER_WIDTH_DEFAULT,
            border_color=theme.BORDER_DEFAULT,
            corner_radius=theme.RADIUS_CARD,
        )
        body.grid(row=1, column=0, sticky="nsew", padx=theme.SPACING_XL, pady=(theme.RADIUS_SMALL, theme.FONT_SIZE_TITLE))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=0)
        body.grid_columnconfigure(2, weight=0)

        header_anchor = "e" if self.current_lang == "he" else "w"
        ctk.CTkLabel(
            body,
            text=format_text("constraints_header_name", self.current_lang),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY, weight=theme.FONT_WEIGHT_BOLD),
            text_color=theme.TEXT_MUTED,
            anchor=header_anchor,
        ).grid(row=0, column=0, sticky="ew", padx=theme.SPACING_REGULAR, pady=(theme.SPACING_REGULAR, theme.SPACING_SMALL))
        ctk.CTkLabel(
            body,
            text=format_text("constraints_header_enabled", self.current_lang),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY, weight=theme.FONT_WEIGHT_BOLD),
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=1, padx=theme.SPACING_REGULAR, pady=(theme.SPACING_REGULAR, theme.SPACING_SMALL))
        ctk.CTkLabel(
            body,
            text=format_text("constraints_header_k", self.current_lang),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BODY, weight=theme.FONT_WEIGHT_BOLD),
            text_color=theme.TEXT_MUTED,
        ).grid(row=0, column=2, padx=theme.SPACING_REGULAR, pady=(theme.SPACING_REGULAR, theme.SPACING_SMALL))

        vcmd = (self.register(_is_non_negative_int_candidate), "%P")
        for row_idx, field in enumerate(CONSTRAINT_FIELDS, start=1):
            enabled_key = field["enabled"]
            k_key = field["k"]

            enabled_var = tk.BooleanVar(master=self, value=bool(self._state[enabled_key]))
            k_var = tk.StringVar(master=self, value=str(self._state[k_key]))
            self._vars[enabled_key] = enabled_var
            self._vars[k_key] = k_var

            label = ctk.CTkLabel(
                body,
                text=format_text(field["label"], self.current_lang),
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BUTTON, weight=theme.FONT_WEIGHT_BOLD),
                text_color=theme.TEXT_MAIN,
                anchor=header_anchor,
                justify="right" if self.current_lang == "he" else "left",
                wraplength=theme.CONTROL_WRAP_CONSTRAINT_LABEL,
            )
            label.grid(row=row_idx, column=0, sticky="ew", padx=theme.SPACING_REGULAR, pady=theme.FONT_SIZE_XS)

            switch = ctk.CTkSwitch(
                body,
                text="",
                width=theme.CONTROL_WIDTH_SWITCH,
                variable=enabled_var,
                fg_color=theme.BORDER_DEFAULT,
                progress_color=theme.TEXT_ACCENT,
                button_color=theme.BG_CARD,
                button_hover_color=theme.TEXT_ACCENT,
                command=lambda key=enabled_key: self._refresh_entry_states(),
            )
            switch.grid(row=row_idx, column=1, padx=theme.SPACING_REGULAR, pady=theme.FONT_SIZE_XS)

            entry = ctk.CTkEntry(
                body,
                width=theme.CONTROL_WIDTH_CONSTRAINT_ENTRY,
                height=theme.CONTROL_HEIGHT_ENTRY,
                justify="center",
                textvariable=k_var,
                validate="key",
                validatecommand=vcmd,
                fg_color=theme.BG_MAIN,
                border_color=theme.BORDER_DEFAULT,
                text_color=theme.TEXT_MAIN,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BUTTON, weight=theme.FONT_WEIGHT_BOLD),
            )
            entry.grid(row=row_idx, column=2, padx=theme.SPACING_REGULAR, pady=theme.FONT_SIZE_XS)

            self._row_refs.append({
                "field": field,
                "label": label,
                "switch": switch,
                "entry": entry,
            })

        # -----------------------------------------------------------------
        # PLAN-555: New Multi-Select UI Section Block Component Injection
        # -----------------------------------------------------------------
        start_religion_row = len(CONSTRAINT_FIELDS) + 1
        
        # Spacer Line Separator block structure layout
        divider = ctk.CTkFrame(body, height=2, fg_color=theme.BORDER_DEFAULT)
        divider.grid(row=start_religion_row, column=0, columnspan=3, sticky="ew", padx=14, pady=16)
        
        # Section Header Text label widget
        religions_title = ctk.CTkLabel(
            body,
            text=format_text("religion_section_title", self.current_lang),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=16, weight="bold"),
            text_color=theme.TEXT_ACCENT,
            anchor=header_anchor,
        )
        religions_title.grid(row=start_religion_row + 1, column=0, columnspan=3, sticky="ew", padx=14, pady=(4, 8))

        # Core container grouping box component wrapper
        religions_container = ctk.CTkFrame(
            body, 
            fg_color=theme.BG_CARD, 
            corner_radius=theme.RADIUS_CARD, 
            border_width=1, 
            border_color=theme.BORDER_DEFAULT
        )
        religions_container.grid(row=start_religion_row + 2, column=0, columnspan=3, sticky="ew", padx=14, pady=4)
        religions_container.grid_columnconfigure((0, 1, 2), weight=1, uniform="religion_cols")

        religions_list = [
            ("Jewish", "religion_jewish"),
            ("Christian", "religion_christian"),
            ("Muslim", "religion_muslim")
        ]

        # Multi-select alignment loop setup grid layer lines
        for idx, (internal_name, lang_key) in enumerate(religions_list):
            is_checked = internal_name in self._state.get("selected_religions", [])
            box_var = tk.BooleanVar(master=self, value=is_checked)
            self._religion_boxes[internal_name] = box_var

            cb = ctk.CTkCheckBox(
                religions_container,
                text=format_text(lang_key, self.current_lang),
                variable=box_var,
                font=ctk.CTkFont(family=theme.FONT_FAMILY, size=13),
                text_color=theme.TEXT_MAIN,
                fg_color=theme.BORDER_ACTIVE,
                hover_color=theme.BORDER_ACTIVE
            )
            
            # Align items grid side layout elements properly satisfying language context
            grid_col = (2 - idx) if self.current_lang == "he" else idx
            cb.grid(row=0, column=grid_col, padx=15, pady=12, sticky="ew")

        # Footer Frame rendering block areas layout
        footer = ctk.CTkFrame(outer, fg_color=theme.TRANSPARENT)
        footer.grid(row=2, column=0, sticky="ew", padx=theme.SPACING_XL, pady=(theme.SPACING_NONE, theme.SPACING_LARGE))

        self.error_label = ctk.CTkLabel(
            footer,
            text="",
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_SMALL, weight=theme.FONT_WEIGHT_BOLD),
            text_color=theme.DANGER,
        )
        self.error_label.pack(side="top", fill="x", pady=(theme.SPACING_NONE, theme.SPACING_SMALL))

        buttons = ctk.CTkFrame(footer, fg_color=theme.TRANSPARENT)
        buttons.pack(side="bottom", fill="x")

        self.cancel_btn = create_secondary_button(
            buttons,
            text=format_text("cancel", self.current_lang),
            command=self._close_without_saving,
        )
        self.save_btn = ctk.CTkButton(
            buttons,
            text=format_text("save", self.current_lang),
            font=ctk.CTkFont(family=theme.FONT_FAMILY, size=theme.FONT_SIZE_BUTTON, weight=theme.FONT_WEIGHT_BOLD),
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_HOVER,
            text_color=theme.TEXT_ON_ACCENT,
            height=theme.CONTROL_HEIGHT_ACTION,
            corner_radius=theme.RADIUS_BUTTON,
            command=self._save_and_close,
        )

        if self.current_lang == "he":
            self.save_btn.pack(side="left", padx=(theme.SPACING_SMALL, theme.SPACING_NONE))
            self.cancel_btn.pack(side="left")
        else:
            self.cancel_btn.pack(side="left", padx=(theme.SPACING_NONE, theme.SPACING_SMALL))
            self.save_btn.pack(side="left")

        if not self.save_enabled:
            self.save_btn.configure(state="disabled", fg_color=theme.BORDER_DEFAULT)
            self.error_label.configure(text=format_text("constraints_locked", self.current_lang))

        self._refresh_entry_states()

    def _refresh_entry_states(self) -> None:
        for row in self._row_refs:
            enabled_key = row["field"]["enabled"]
            is_enabled = bool(self._vars[enabled_key].get())
            entry = row["entry"]
            label = row["label"]
            if is_enabled:
                entry.configure(
                    state="normal",
                    fg_color=theme.BG_MAIN,
                    border_color=theme.TEXT_ACCENT,
                    text_color=theme.TEXT_MAIN,
                )
                label.configure(text_color=theme.TEXT_MAIN)
            else:
                entry.configure(
                    state="disabled",
                    fg_color=theme.BG_CARD_HOVER,
                    border_color=theme.BORDER_DEFAULT,
                    text_color=theme.TEXT_MUTED,
                )
                label.configure(text_color=theme.TEXT_MUTED)

    def _collect_data(self) -> Dict[str, Union[int, bool, list]]:
        data: Dict[str, Union[int, bool, list]] = {}
        for field in CONSTRAINT_FIELDS:
            enabled_key = field["enabled"]
            k_key = field["k"]
            data[enabled_key] = bool(self._vars[enabled_key].get())
            data[k_key] = _safe_non_negative_int(self._vars[k_key].get(), field["default_k"])
            
        # PLAN-555: Pack currently checked elements array back to output data structures dictionary payload
        selected_religions_list = [name for name, var in self._religion_boxes.items() if var.get()]
        data["selected_religions"] = selected_religions_list
        return data

    def _validate_before_save(self) -> bool:
        for field in CONSTRAINT_FIELDS:
            raw_value = str(self._vars[field["k"]].get()).strip()
            if bool(self._vars[field["enabled"]].get()) and raw_value == "":
                self.error_label.configure(text=format_text("constraints_invalid", self.current_lang))
                return False
            if raw_value and not raw_value.isdigit():
                self.error_label.configure(text=format_text("constraints_invalid", self.current_lang))
                return False
        self.error_label.configure(text="")
        return True

    def _save_and_close(self) -> None:
        if not self.save_enabled:
            return
        if not self._validate_before_save():
            return
        data = self._collect_data()
        if self.on_save_callback:
            self.on_save_callback(data)
        self.destroy()

    def _close_without_saving(self) -> None:
        if self.on_close_callback:
            self.on_close_callback(self._collect_data())
        self.destroy()

    def _start_drag(self, event) -> None:
        self._drag_start_x = event.x_root - self.winfo_x()
        self._drag_start_y = event.y_root - self.winfo_y()

    def _on_drag(self, event) -> None:
        x = event.x_root - self._drag_start_x
        y = event.y_root - self._drag_start_y
        self.geometry(f"+{x}+{y}")

    def _center_on_parent(self) -> None:
        try:
            self.update_idletasks()
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_w = self.parent.winfo_width()
            parent_h = self.parent.winfo_height()
            modal_w = self.winfo_width()
            modal_h = self.winfo_height()
            x = parent_x + max(0, (parent_w - modal_w) // 2)
            y = parent_y + max(0, (parent_h - modal_h) // 2)
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass


def show_constraints_popup(
    parent,
    current_lang: str = "he",
    constraints_data: Optional[dict] = None,
    on_save_callback: Optional[Callable[[dict], None]] = None,
    on_close_callback: Optional[Callable[[dict], None]] = None,
    save_enabled: bool = True,
):
    return ConstraintsSettingsModal(
        parent=parent,
        current_lang=current_lang,
        constraints_data=constraints_data,
        on_save_callback=on_save_callback,
        on_close_callback=on_close_callback,
        save_enabled=save_enabled,
    )