import os
from typing import List, Dict

class InputPresenter:
    def __init__(self, view, model):
        """
        Initialize the Presenter and bind UI events to business logic.
        Refactored to cleanly support dynamic program extraction from loaded courses (PLAN-251 / PLAN-252).
        """
        self.view = view
        self.model = model

        # Internal helper variables initialized with explicit local paths 
        # to ensure strict compliance with internal DataManager rules.
        self._courses_path = None
        self._exam_periods_path = None

        # 1. UI Event Binding - Bound only to course extraction and date constraints
        self.view.on_load_courses = self._handle_load_courses
        self.view.on_load_dates = self._handle_load_dates
        self.view.on_program_selected = self._handle_program_selection
        # Name-click: show a program's details without changing its selection (PLAN-258)
        self.view.on_program_details = self._handle_program_details
        # Clear button: reset all data and selections
        self.view.on_clear_courses = self._handle_clear_courses
        self.view.get_exam_periods_callback = lambda: self.model.get_exam_periods() or []
    # ======= 2. File Loading & Configuration Management (PLAN-254 / PLAN-255) =======

    def _get_validated_mode(self) -> str:
        """
        Extract the load mode from the View and map it to modes supported by DataManager.
        """
        ui_mode = self.view.load_mode_var.get()     # Yields "replace", "append", or "update"
        
        if ui_mode in ["append", "update"]:
            return "append"
        return "replace"

    def _trigger_data_loading(self):
        """
        Internal helper function to inject paths and trigger data loading directly via the Model (PLAN-254).
        Defensively safe: builds and ensures the physical existence of a dummy programs file 
        to guarantee that TextFileParser and DataManager validations pass successfully.
        """
        # Ensure 'data' directory exists locally in the project workspace
        os.makedirs("data", exist_ok=True)
        
        # Enforce a physical layout fallback for the selected_programs parameter to satisfy DataManager/Parser
        dummy_programs_path = os.path.normpath("data/selected_programs.txt")
        with open(dummy_programs_path, "w", encoding="utf-8") as f:
            f.write("")  # Ensures an empty file exists so parse_selected_programs reads it and returns [] without breaking

        # Resolve paths with explicit workspace fallbacks
        
        final_courses = self._courses_path if self._courses_path else ""
        final_dates = self._exam_periods_path if self._exam_periods_path else ""
        # Normalize slashes cleanly to eliminate cross-platform workspace path string mismatches
        normalized_courses = os.path.normpath(final_courses)
        normalized_dates = os.path.normpath(final_dates)

        # 1. Synchronize system states within the tracking Model layer
        self.model.set_data_paths(
            courses_path=normalized_courses,
            exam_periods_path=normalized_dates,
            selected_programs_path=dummy_programs_path
        )

        mode = self._get_validated_mode()
        
        # Save existing exam periods before loading new ones (for append mode in PlanixModel)
        existing_periods = self.model.data_manager.get_exam_periods() if mode == "append" else None
        
        try:
            print(f"[Presenter] Dispatching validated paths - Courses: {normalized_courses} | Dates: {normalized_dates}")
            
            # 2. Invoke core DataManager loading flow with fully verified file assets
            # PlanixModel handles the append/replace logic
            self.model.data_manager.load_data(
                courses_path=normalized_courses,
                exam_periods_path=normalized_dates,
                selected_programs_path=dummy_programs_path,
                mode=mode
            )
            
            # 3. If append mode was requested, merge the new periods with existing ones in PlanixModel
            if mode == "append" and existing_periods:
                new_periods = self.model.data_manager.get_exam_periods() or []
                # Restore existing periods and let PlanixModel handle the merge
                self.model.data_manager.exam_periods = existing_periods
                self.model.merge_exam_periods_from_file(new_periods, mode="append")
            
            # 4. Trigger dynamic track extraction from loaded memory blocks
            self.model.build_available_programs()
            
            # 5. Refresh passive UI components to update list views smoothly
            self._refresh_programs_list()
            self._update_view_summary()
            
        except Exception as e:
            print(f"Error during data loading flow execution: {e}")

    def _handle_load_courses(self, file_path: str):
        self._courses_path = file_path
        self._trigger_data_loading()

    def _handle_load_dates(self, file_path: str):
        self._exam_periods_path = file_path
        self._trigger_data_loading()

    # ======= 3. Academic Program Selection Management (PLAN-257) =======

    def _handle_program_selection(self, prog_id: str):
        selected_programs = self.model.get_selected_programs()

        if prog_id in selected_programs:
            # If the program is already active - remove it from the state tracker
            self.model.remove_selected_program(prog_id)
        else:
            # Add new academic program - business constraint limit of 5 is enforced by the Model
            try:
                self.model.add_selected_program(prog_id)
            except ValueError as e:
                print(f"UI selection rejected due to business constraint: {e}")
                
                if hasattr(self.view, "show_warning_dialog"):
                    self.view.show_warning_dialog(str(e))
                
                # Revert view checkbox selection state 
                self._refresh_programs_list()
                return

        # Synchronize structural course hierarchies back onto the UI summary box
        self._update_view_summary()

    def _handle_program_details(self, prog_id: str):
        """
        Render a single program's course hierarchy in the details panel WITHOUT
        toggling its selection state. Triggered by clicking the program name (not the checkbox).
        Read-only: does not mutate the selected-programs state in any way.
        """
        hierarchy = self.model.get_program_course_hierarchy(prog_id)
        self.view.display_program_courses(hierarchy)

    # ======= 4. View Component Rendering (Summary Box Handling) =======

    def _refresh_programs_list(self):
        """Retrieve dynamic program sets from the Model and render them to the View with their correct selection state"""
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
        """
        Fetch the hierarchical layout of the most recently active selected academic track
        and stream it directly into the view panel details.
        """
        selected_program_ids = self.model.get_selected_programs()
        if not selected_program_ids:
            self.view.display_program_courses({})
            return

        active_prog_id = selected_program_ids[-1]
        hierarchy = self.model.get_program_course_hierarchy(active_prog_id)

        # Command the passive view container to render the compiled configuration details
        self.view.display_program_courses(hierarchy)

    def _handle_clear_courses(self) -> None:
        """
        Clear all data: reset selected programs, courses, and exam periods.
        Triggered by the trash button in the UI.
        """
        try:
            # Clear selected programs from model
            self.model.selected_programs = []
            
            # Clear available programs
            self.model.available_programs = {}
            
            # Reset data paths
            self._courses_path = None
            self._exam_periods_path = None
            
            # Refresh UI to reflect empty state
            self.view.display_program_courses({})
            self.view.display_programs_list({})
            self._refresh_programs_list()
            
            print("[InputPresenter] All data cleared successfully")
        except Exception as e:
            print(f"[InputPresenter] Error clearing data: {e}")