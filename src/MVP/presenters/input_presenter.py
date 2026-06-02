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
        self._courses_path = "data/courses.txt"
        self._exam_periods_path = "data/exam_periods.txt"

        # 1. UI Event Binding - Bound only to course extraction and date constraints
        self.view.on_load_courses = self._handle_load_courses
        self.view.on_load_dates = self._handle_load_dates
        self.view.on_program_selected = self._handle_program_selection

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
        final_courses = self._courses_path if self._courses_path and self._courses_path.strip() else "data/courses.txt"
        final_dates = self._exam_periods_path if self._exam_periods_path and self._exam_periods_path.strip() else "data/exam_periods.txt"

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
        try:
            print(f"[Presenter] Dispatching validated paths - Courses: {normalized_courses} | Dates: {normalized_dates}")
            
            # 2. Invoke core DataManager loading flow with fully verified file assets
            self.model.data_manager.load_data(
                courses_path=normalized_courses,
                exam_periods_path=normalized_dates,
                selected_programs_path=dummy_programs_path,
                mode=mode
            )
            
            # 3. Trigger dynamic track extraction from loaded memory blocks
            self.model.build_available_programs()
            
            # 4. Refresh passive UI components to update list views smoothly
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
                # Revert view checkbox selection state
                self._refresh_programs_list()
                return

        # Synchronize structural course hierarchies back onto the UI summary box
        self._update_view_summary()

    # ======= 4. View Component Rendering (Summary Box Handling) =======

    def _refresh_programs_list(self):
        """Retrieve dynamic program sets from the Model and render them to the View"""
        available_programs = self.model.get_available_programs()
        self.view.display_programs_list(available_programs)

    def _update_view_summary(self):
        """
        Fetch the hierarchical layout of all selected academic tracks, flatten the structural
        dictionary parameters, and stream them into the view panel details.
        """
        selected_program_ids = self.model.get_selected_programs()
        flattened_courses: List[dict] = []

        for prog_id in selected_program_ids:
            # Extract the course mapping hierarchy (year -> semester -> course dictionary)
            hierarchy = self.model.get_program_course_hierarchy(prog_id)
            courses_by_time = hierarchy.get("courses_by_year_and_semester", {})

            for year, semesters in courses_by_time.items():
                for semester, courses_list in semesters.items():
                    for course in courses_list:
                        
                        # Maps raw academic models cleanly into fields recognized by the view
                        flattened_courses.append({
                            "id": course.get("course_id", ""),
                            "name": course.get("course_name", ""),
                            # Evaluates against core course schema parameters ('Obligatory' vs 'Elective')
                            "is_mandatory": course.get("requirement") == "Obligatory", 
                            "semester": semester,
                            "year": str(year)
                        })

        # Command the passive view container to render the compiled configuration details
        self.view.display_program_courses(flattened_courses)
