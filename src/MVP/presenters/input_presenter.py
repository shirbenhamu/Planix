# src/MVP/presenters/input_presenter.py

import os
from typing import List, Dict
from src.engine.scheduling_constraints import SchedulingConstraints

class InputPresenter:
    def __init__(self, view, model):
        self.view = view
        self.model = model
        self.controller = None  # Reference to AppController for pipeline triggers

        self._courses_path = None
        self._exam_periods_path = None

        # Bind existing view actions
        self.view.on_load_courses = self._handle_load_courses
        self.view.on_load_dates = self._handle_load_dates
        self.view.on_program_selected = self._handle_program_selection
        self.view.on_program_details = self._handle_program_details
        self.view.on_clear_courses = self._handle_clear_courses
        self.view.get_exam_periods_callback = lambda: self.model.get_exam_periods() or []

        # PLAN-405: Intercept and wire constraint save notification from the View
        if hasattr(self.view, "on_save_constraints"):
            self.view.on_save_constraints = self._handle_save_constraints
        else:
            # Inject dynamic hook placeholder to support seamlessly whenever the save button is active
            self.view.on_save_constraints = self._handle_save_constraints

    def sync_ui_lock_state(self) -> None:
        """
        Monitors engine execution state via controller adapter and toggles 
        the View's constraint save button availability accordingly (UI Lock solution).
        """
        if self.controller and self.controller.engine_adapter:
            is_active = self.controller.engine_adapter.is_generation_active()
            
            if is_active:
                if hasattr(self.view, "disable_save_constraints"):
                    self.view.disable_save_constraints()
                elif hasattr(self.view, "set_save_button_state"):
                    self.view.set_save_button_state(enabled=False)
            else:
                if hasattr(self.view, "enable_save_constraints"):
                    self.view.enable_save_constraints()
                elif hasattr(self.view, "set_save_button_state"):
                    self.view.set_save_button_state(enabled=True)

    def _safe_int_conversion(self, raw_value) -> int:
        """
        Helper method to secure integer parsing from text entry views.
        Prevents critical ValueError crashes when fields are empty ("") or corrupted.
        """
        if raw_value is None:
            return 0
        
        # Convert to string to safely run text stripping operations
        clean_str = str(raw_value).strip()
        if not clean_str:
            return 0
            
        try:
            return int(clean_str)
        except ValueError:
            print(f"[InputPresenter][Warning] Failed converting custom K-value text '{raw_value}'. Falling back to 0.")
            return 0

    def _handle_save_constraints(self, ui_constraints_data: dict = None) -> None:
        """
        Acceptance Criteria Met: Input Presenter reads toggle and k-value state from the settings view.
        Maintains decoupling and long-lived model instance storage mapping.
        """
        # Guard Clause: Prevent saving updates if the background engine process is currently active
        if self.controller and self.controller.engine_adapter and self.controller.engine_adapter.is_generation_active():
            print("[InputPresenter][Block] Request denied. Cannot mutate system configuration while execution is active.")
            self.sync_ui_lock_state()
            return

        # If the view doesn't explicitly pass a dictionary (legacy/mock integration step), 
        # extract safely from view property fields or fallback to functional default system state config.
        if ui_constraints_data is None:
            if hasattr(self.view, "get_constraints_data") and callable(self.view.get_constraints_data):
                ui_constraints_data = self.view.get_constraints_data()
            else:
                # Dynamic decoupling fallback: Ensures existing pipeline remains functional when constraints are at defaults
                ui_constraints_data = {
                    "min_days_mandatory_enabled": getattr(self.view, "min_days_mandatory_enabled", False),
                    "min_days_mandatory_k": getattr(self.view, "min_days_mandatory_k", 4),
                    "min_days_any_enabled": getattr(self.view, "min_days_any_enabled", False),
                    "min_days_any_k": getattr(self.view, "min_days_any_k", 2),
                    "max_elective_conflicts_enabled": getattr(self.view, "max_elective_conflicts_enabled", False),
                    "max_elective_conflicts_k": getattr(self.view, "max_elective_conflicts_k", 0),
                    "span_mandatory_enabled": getattr(self.view, "span_mandatory_enabled", False),
                    "span_mandatory_k": getattr(self.view, "span_mandatory_k", 14),
                    "max_exams_per_day_enabled": getattr(self.view, "max_exams_per_day_enabled", True), 
                    "max_exams_per_day_k": getattr(self.view, "max_exams_per_day_k", 1),
                }

        print(f"[InputPresenter] Save Action detected. Reading fields from view: {ui_constraints_data}")
        
        # Mapping properties securely using safe helper conversions to prevent input runtime exceptions
        self.model.constraints.min_days_mandatory_enabled = bool(ui_constraints_data.get("min_days_mandatory_enabled", False))
        self.model.constraints.min_days_mandatory_k = self._safe_int_conversion(ui_constraints_data.get("min_days_mandatory_k", 0))
        
        self.model.constraints.min_days_any_enabled = bool(ui_constraints_data.get("min_days_any_enabled", False))
        self.model.constraints.min_days_any_k = self._safe_int_conversion(ui_constraints_data.get("min_days_any_k", 0))
        
        self.model.constraints.max_elective_conflicts_enabled = bool(ui_constraints_data.get("max_elective_conflicts_enabled", False))
        self.model.constraints.max_elective_conflicts_k = self._safe_int_conversion(ui_constraints_data.get("max_elective_conflicts_k", 0))
        
        self.model.constraints.span_mandatory_enabled = bool(ui_constraints_data.get("span_mandatory_enabled", False))
        self.model.constraints.span_mandatory_k = self._safe_int_conversion(ui_constraints_data.get("span_mandatory_k", 0))
        
        self.model.constraints.max_exams_per_day_enabled = bool(ui_constraints_data.get("max_exams_per_day_enabled", False))
        self.model.constraints.max_exams_per_day_k = self._safe_int_conversion(ui_constraints_data.get("max_exams_per_day_k", 0))

        print("[InputPresenter] Model constraint layout updated successfully.")

        # Triggers clean engine snapshot calculation via the Controller
        if self.controller is not None:
            self.controller.regenerate_schedules_snapshot()

    def _get_validated_mode(self) -> str:
        ui_mode = self.view.load_mode_var.get()     
        if ui_mode in ["append", "update"]:
            return "append"
        return "replace"

    def _resolve_load_path(self, path: str, empty_placeholder_name: str) -> str:
        if path:
            return os.path.normpath(path)
        placeholder = os.path.normpath(os.path.join("data", empty_placeholder_name))
        if not os.path.exists(placeholder):
            with open(placeholder, "w", encoding="utf-8") as f:
                f.write("")
        return placeholder

    def _trigger_data_loading(self, rollback_courses_path: str = None, rollback_dates_path: str = None) -> bool:
        os.makedirs("data", exist_ok=True)
        dummy_programs_path = os.path.normpath("data/selected_programs.txt")
        with open(dummy_programs_path, "w", encoding="utf-8") as f:
            f.write("")

        normalized_courses = self._resolve_load_path(self._courses_path, "_empty_courses.txt")
        normalized_dates = self._resolve_load_path(self._exam_periods_path, "_empty_dates.txt")

        self.model.set_data_paths(
            courses_path=normalized_courses,
            exam_periods_path=normalized_dates,
            selected_programs_path=dummy_programs_path
        )

        mode = self._get_validated_mode()
        existing_periods = self.model.data_manager.get_exam_periods() if mode == "append" else None
        
        try:
            print(f"[Presenter] Dispatching validated paths - Courses: {normalized_courses} | Dates: {normalized_dates}")
            self.model.data_manager.load_data(
                courses_path=normalized_courses,
                exam_periods_path=normalized_dates,
                selected_programs_path=dummy_programs_path,
                mode=mode
            )
            
            if mode == "append" and existing_periods:
                new_periods = self.model.data_manager.get_exam_periods() or []
                self.model.data_manager.exam_periods = existing_periods
                self.model.merge_exam_periods_from_file(new_periods, mode="append")
            
            if mode == "replace":
                if hasattr(self.model, "clear_user_exclusions"):
                    self.model.clear_user_exclusions()

            self.model.build_available_programs()
            self._refresh_programs_list()
            self._update_view_summary()
            return True
            
        except Exception as e:
            print(f"Error during data loading flow execution: {e}")
            self._courses_path = rollback_courses_path
            self._exam_periods_path = rollback_dates_path
            return False

    def _handle_load_courses(self, file_path: str) -> bool:
        old_courses = self._courses_path
        old_dates = self._exam_periods_path
        self._courses_path = file_path
        return self._trigger_data_loading(old_courses, old_dates)

    def _handle_load_dates(self, file_path: str) -> bool:
        old_courses = self._courses_path
        old_dates = self._exam_periods_path
        self._exam_periods_path = file_path
        return self._trigger_data_loading(old_courses, old_dates)

    def _handle_program_selection(self, prog_id: str):
        selected_programs = self.model.get_selected_programs()
        if prog_id in selected_programs:
            self.model.remove_selected_program(prog_id)
        else:
            try:
                self.model.add_selected_program(prog_id)
            except ValueError as e:
                print(f"UI selection rejected due to business constraint: {e}")
                if hasattr(self.view, "show_warning_dialog"):
                    self.view.show_warning_dialog(str(e))
                self._refresh_programs_list()
                return
        self._update_view_summary()

    def _handle_program_details(self, prog_id: str):
        hierarchy = self.model.get_program_course_hierarchy(prog_id)
        self.view.display_program_courses(hierarchy)

    def _refresh_programs_list(self):
        available_programs = self.model.get_available_programs()
        self.view.display_programs_list(available_programs)
        
        selected_programs = self.model.get_selected_programs()
        for cb in self.view.checkboxes:
            cb_text = cb.cget("text")
            if any(prog_id in cb_text for prog_id in selected_programs):
                cb.select()   
            else:
                cb.deselect() 

    def _update_view_summary(self):
        selected_program_ids = self.model.get_selected_programs()
        if not selected_program_ids:
            self.view.display_program_courses({})
            return

        active_prog_id = selected_program_ids[-1]
        hierarchy = self.model.get_program_course_hierarchy(active_prog_id)
        self.view.display_program_courses(hierarchy)

    def _handle_clear_courses(self) -> None:
        try:
            self.model.selected_programs = []
            self.model.available_programs = {}
            self._courses_path = None
            try:
                self.model.data_manager.courses.clear()
            except Exception:
                pass
            self.view.display_program_courses({})
            self.view.display_programs_list({})
            self._refresh_programs_list()
            print("[InputPresenter] Courses cleared successfully (dates preserved)")
        except Exception as e:
            print(f"[InputPresenter] Error clearing courses: {e}")