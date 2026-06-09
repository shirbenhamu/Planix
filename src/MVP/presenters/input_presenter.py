import os
from typing import List, Dict

class InputPresenter:
    def __init__(self, view, model):
        self.view = view
        self.model = model

        self._courses_path = None
        self._exam_periods_path = None

        self.view.on_load_courses = self._handle_load_courses
        self.view.on_load_dates = self._handle_load_dates
        self.view.on_program_selected = self._handle_program_selection
        self.view.on_program_details = self._handle_program_details
        self.view.on_clear_courses = self._handle_clear_courses
        self.view.get_exam_periods_callback = lambda: self.model.get_exam_periods() or []

    def _get_validated_mode(self) -> str:
        ui_mode = self.view.load_mode_var.get()     
        if ui_mode in ["append", "update"]:
            return "append"
        return "replace"

    def _resolve_load_path(self, path: str, empty_placeholder_name: str) -> str:
        """Return the real path if a file was loaded; otherwise a path to a valid empty file
        that the parser reads as [] without raising (lets courses/dates be loaded separately)."""
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

        # A not-yet-loaded file -> path to an empty file (parsed as "no records") instead of
        # an empty string that normpath turns into "." and makes the parser raise PermissionError,
        # which would wrongly flag a valid file as failed. This lets courses/dates be loaded separately.
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
            
            self.model.build_available_programs()
            self._refresh_programs_list()
            self._update_view_summary()
            return True
            
        except Exception as e:
            print(f"Error during data loading flow execution: {e}")
            # Rollback paths on failure so state isn't corrupted
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
        """Trash button: clears only the courses file (courses + programs). Loaded dates are preserved."""
        try:
            self.model.selected_programs = []
            self.model.available_programs = {}
            self._courses_path = None
            # Keep self._exam_periods_path — clear courses only, not dates
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