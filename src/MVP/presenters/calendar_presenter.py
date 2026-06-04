from datetime import date, datetime
from typing import Dict, List, Optional
from src.MVP.models.schedule import Schedule, ScheduledExam


class CalendarPresenter:
    def __init__(self, view, model, collection_manager, controller=None):
        """
        Initialize the CalendarPresenter and bind UI components to the schedule collection.
        """
        self.view = view
        self.model = model
        self.collection_manager = collection_manager
        self.controller = controller

        # Track the active months currently initialized in the View grid
        self.active_months: List[int] = []
        # Reverse mapping from matrix coordinates back to specific dates for interactive manipulation
        self.cell_to_date_mapping: Dict[str, date] = {}

        # 1. UI Event Binding - Tasks PLAN-258 and PLAN-261
        self.view.on_next_clicked = self._handle_next_schedule
        self.view.on_prev_clicked = self._handle_prev_schedule
        self.view.on_page_jump = self._handle_page_jump
        self.view.on_exclude_clicked = self._handle_date_exclusion
        self.view.on_range_update_clicked = self._handle_range_update
        self.view.on_export_clicked = self._handle_export
        self.view.on_filter_clicked = self._handle_filter_click

        if hasattr(self.view, "on_load_more_clicked"):
            self.view.on_load_more_clicked = self._handle_load_more

        # Initialize display if schedules are already generated and available
        self.refresh_presenter_state()


    def _handle_load_more(self) -> None:
            """Handles the 'Load More' UI event by delegating to the AppController with current count."""
            try:
                import os
                current_count = 0

                # נבדוק כמה אופציות רשומות כרגע פיזית בקובץ התוצאות
                if hasattr(self, "controller") and self.controller is not None:
                    output_path = getattr(
                        self.controller, "output_path", "output_results/final_schedules.txt")
                    if os.path.exists(output_path):
                        with open(output_path, "r", encoding="utf-8") as f:
                            # סופרים כמה פעמים מופיעה הכותרת של אופציות מערכת מלאות
                            current_count = sum(1 for line in f if "--- FULL SYSTEM OPTION" in line)

                print(
                    f"[CalendarPresenter] User clicked 'Load More'. Passing skip_count={current_count} to controller.")

                if hasattr(self, "controller") and self.controller is not None:
                    self.controller.load_more_schedules(skip_count=current_count)
            except Exception as e:
                print(
                    f"[CalendarPresenter] Error initializing load more pipeline: {e}")
                
    def refresh_presenter_state(self) -> None:
        """
        Scans the manager context, initializes layout structure if data exists, and triggers render cycle.
        """
        total_schedules = self.collection_manager.get_total_count()
        if total_schedules == 0:
            self.view.show_empty_state()
            return

        # Synchronize pagination view context
        current_idx = self.collection_manager.get_current_index()
        self.view.update_pagination(current_page=current_idx + 1, total_pages=total_schedules)

        # Pull active schedule structure
        try:
            active_schedule = self.collection_manager.get_current_schedule()
            self._setup_calendar_grid_dimensions(active_schedule)
            self._render_active_schedule(active_schedule)
        except Exception as e:
            print(f"Error refreshing calendar state: {e}")
            self.view.show_empty_state()

    # ======= 2. Grid Optimization & Transformation (PLAN-258) =======

    def _setup_calendar_grid_dimensions(self, schedule: Schedule) -> None:
        """
        Determines the unique collection of months spanning across the current schedule block,
        initializes the View layout dimensions, and populates mapping coordinates.
        """
        if not schedule.exams:
            return

        # Extract sorted, unique month indices (0-11) present in the schedule block
        unique_months = sorted(list(set(exam.exam_date.month - 1 for exam in schedule.exams)))
        
        # Avoid breaking structural drawing cycles if the grid is already configured identically
        if self.active_months != unique_months:
            self.active_months = unique_months
            self.view.init_grid(self.active_months)

    def _render_active_schedule(self, schedule: Schedule) -> None:
        """
        Transforms Model-generated raw schedule entries into grid-renderable cell properties.
        """
        grid_data: Dict[str, dict] = {}
        self.cell_to_date_mapping.clear()

        # Pre-populate fallback base state structures for all initialized view grids
        for row_idx, month_idx in enumerate(self.active_months, start=1):
            for col_idx in range(31):
                cell_key = f"{row_idx}-{col_idx}"
                grid_data[cell_key] = {
                    "is_excluded": False,
                    "day_text": "",
                    "exams": []
                }

        # Query all globally locked excluded dates directly from primary Model context
        excluded_dates = self.model.get_user_excluded_dates()

        # Map schedule array contents systematically onto coordinates
        for exam in schedule.exams:
            exam_date = exam.exam_date
            month_idx = exam_date.month - 1
            day_num = exam_date.day

            if month_idx not in self.active_months:
                continue

            row_idx = self.active_months.index(month_idx) + 1
            col_idx = day_num - 1
            cell_key = f"{row_idx}-{col_idx}"

            # Link coordinate reference to actual date to handle interactive feedback clicks
            self.cell_to_date_mapping[cell_key] = exam_date

            # Populate cell contextual properties
            grid_data[cell_key]["day_text"] = str(day_num)
            grid_data[cell_key]["is_excluded"] = exam_date in excluded_dates

            # Determine course type visualization mapping rule ("ח" for mandatory, "ב" for elective)
            # The View uses 'is_mandatory' to dynamically alter layout elements
            is_mandatory = getattr(exam.course, "is_mandatory", True)
            exam_type_marker = "ח" if is_mandatory else "ב"

            # Parse structural payload matching exact card specifications of inside View layout
            grid_data[cell_key]["exams"].append({
                "short_name": getattr(exam.course, "course_name", "")[:10],  # Clamp length for clean card display
                "course_id": getattr(exam.course, "course_id", ""),
                "type": exam_type_marker,
                "program": "Prog"  # Extensible placeholder text parameter matching View definitions
            })

        self.view.render_calendar_data(grid_data)

    # ======= 3. Multi-Schedule Document Traversal (PLAN-260) =======

    def _handle_next_schedule(self) -> None:
        """
        Advances to the next schedule option. If the collection is currently empty, 
        attempts a fresh counter scan in case the background file worker just finished writing.
        """
        if self.collection_manager.get_total_count() == 0:
            self.refresh_presenter_state()
            return

        if self.collection_manager.next_schedule():
            self.refresh_presenter_state()

    def _handle_prev_schedule(self) -> None:
        """
        Navigates to the previous schedule option. If the collection is currently empty, 
        attempts a fresh counter scan in case the background file worker just finished writing.
        """
        if self.collection_manager.get_total_count() == 0:
            self.refresh_presenter_state()
            return

        if self.collection_manager.prev_schedule():
            self.refresh_presenter_state()

    def _handle_page_jump(self, page_number: int) -> None:
        # Re-align UI indexing boundaries to match file byte offset index constraints (0-indexed)
        target_idx = page_number - 1
        if self.collection_manager.jump_to_schedule(target_idx):
            self.refresh_presenter_state()
        else:
            # Force restore previous text input values in case page number arguments are out of range
            current_idx = self.collection_manager.get_current_index()
            total_pages = self.collection_manager.get_total_count()
            self.view.update_pagination(current_page=current_idx + 1, total_pages=total_pages)

    # ======= 4. Interactive Constraints Modification (PLAN-259 / PLAN-261) =======

    def _handle_date_exclusion(self, cell_key: str) -> None:
        """
        Processes grid frame context triggers to apply global exclusion constraints on the Model data layer.
        """
        target_date = self.cell_to_date_mapping.get(cell_key)
        if not target_date:
            print(f"Warning: Clicked grid cell {cell_key} has no date context attached.")
            return

        # Direct execution of transactional updates into the data layer
        self.model.toggle_date_exclusion(target_date)

        # Trigger redraw of active data metrics to keep presentation state in sync
        try:
            active_schedule = self.collection_manager.get_current_schedule()
            self._render_active_schedule(active_schedule)
        except Exception as e:
            print(f"Error updating layout following exclusion change: {e}")

    def _handle_range_update(self, start_str: str, end_str: str) -> None:
        try:
            # 1. Update period if fields are not blank
            if start_str.strip() and end_str.strip():
                start_date = datetime.strptime(start_str.strip(), "%d-%m-%Y").date()
                end_date = datetime.strptime(end_str.strip(), "%d-%m-%Y").date()
                self.model.update_custom_exam_period(start_date, end_date)

            # 2. Sync program IDs to prevent empty schedule bug
            if hasattr(self.view, "get_selected_programs"):
                raw_programs = self.view.get_selected_programs()
                cleaned_ids = [p.split("(")[-1].split(")")[0].strip() for p in raw_programs if "(" in p and ")" in p]
                if cleaned_ids:
                    if hasattr(self.model, "update_selected_programs"):
                        self.model.update_selected_programs(cleaned_ids)
                    else:
                        self.model.selected_programs = cleaned_ids

            # 3. Trigger engine
            if hasattr(self, "controller") and self.controller is not None:
                self.controller.regenerate_schedules_snapshot()
        except Exception as e:
            print(f"Error updating exam period range: {e}")

    # ======= 5. Data Layer Exporting & Stub Filtering Actions (PLAN-262 / PLAN-263) =======

    def _handle_export(self, destination_file_path: str) -> None:
        """
        Writes out the active visualized system schema parameters into text-file data formats.
        """
        try:
            active_schedule = self.collection_manager.get_current_schedule()
            with open(destination_file_path, "w", encoding="utf-8") as out_file:
                out_file.write("--- EXPORTED EXAM SCHEDULE SYSTEM OPTION ---\n")
                for exam in active_schedule.exams:
                    formatted_line = f"Date: {exam.exam_date.strftime('%d-%m-%Y')} | Course: {exam.course.course_id} - {exam.course.course_name}\n"
                    out_file.write(formatted_line)
            print(f"Schedule exported successfully to {destination_file_path}")
        except Exception as e:
            print(f"Failed to export destination file: {e}")

    def _handle_filter_click(self) -> None:
        """
        Gathers checked programs from the view context, cleans and extracts the numerical IDs,
        updates the core planix model layer, and requests an asynchronous engine rebuild.
        """
        try:
            selected_programs = []
            if hasattr(self.view, "get_selected_programs"):
                raw_programs = self.view.get_selected_programs()
                cleaned_program_ids = []

                # Extract only the numerical program ID inside the parentheses (e.g., "83108")
                for prog in raw_programs:
                    if "(" in prog and ")" in prog:
                        try:
                            prog_id = prog.split("(")[-1].split(")")[0].strip()
                            cleaned_program_ids.append(prog_id)
                        except Exception:
                            cleaned_program_ids.append(prog.strip())
                    else:
                        cleaned_program_ids.append(prog.strip())

                selected_programs = cleaned_program_ids

                # Only update the model if we actually gathered checked elements from the active screen
                if cleaned_program_ids:
                    if hasattr(self.model, "update_selected_programs"):
                        self.model.update_selected_programs(cleaned_program_ids)
                    elif hasattr(self.model, "set_selected_programs"):
                        self.model.set_selected_programs(cleaned_program_ids)
                    else:
                        self.model.selected_programs = cleaned_program_ids
                    print(f"[CalendarPresenter] Synced cleaned program IDs back to model format: {cleaned_program_ids}")
                else:
                    print("[CalendarPresenter] Local view filter scan empty. Preserving existing model programs.")

            if hasattr(self, "controller") and self.controller is not None:
                self.controller.regenerate_schedules_snapshot()

            print(f"[CalendarPresenter] Filter execution triggered pipeline update. Reloading engine...")
        except Exception as e:
            print(f"Error handling filter execution pipeline: {e}")