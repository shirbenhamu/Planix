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
        # Always expose a list-producing callback to the view.
        self.view.get_exam_periods_callback = lambda: list(self.model.get_exam_periods() or [])
        self.view.on_sync_clicked = self._handle_sync_action
        self.refresh_presenter_state()


    def _handle_load_more(self) -> None:
            """Handles the 'Load More' UI event by delegating to the AppController with current count"""
            try:
                import os
                current_count = 0

                # Determine the total number of options currently written to the persistent output file
                if hasattr(self, "controller") and self.controller is not None:
                    output_path = getattr(
                        self.controller, "output_path", "output_results/final_schedules.txt")
                    if os.path.exists(output_path):
                        with open(output_path, "r", encoding="utf-8") as f:
                            # Count the occurrences of full system option header tokens
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
        # Computing the displayed months from the configured ExamPeriods
        # so the calendar always shows the full academic range regardless of
        # whether exams have been scheduled into those months yet.
        unique_months: List[int] = []

        try:
            exam_periods = self.model.get_exam_periods()

            if exam_periods:
                # compute continuous month sequence from earliest start_date to latest end_date
                min_date = min(ep.start_date for ep in exam_periods)
                max_date = max(ep.end_date for ep in exam_periods)

                # iterate month-by-month to preserve ordering across year boundaries
                cur_year = min_date.year
                cur_month = min_date.month
                while (cur_year, cur_month) <= (max_date.year, max_date.month):
                    unique_months.append(cur_month - 1)
                    # advance month
                    if cur_month == 12:
                        cur_month = 1
                        cur_year += 1
                    else:
                        cur_month += 1
            else:
                # Fall back to deriving months from scheduled exams (legacy behavior)
                if schedule and getattr(schedule, "exams", None):
                    unique_months = sorted(list(set(exam.exam_date.month - 1 for exam in schedule.exams)))

            # Avoid breaking structural drawing cycles if the grid is already configured identically
            if self.active_months != unique_months:
                self.active_months = unique_months
                self.view.init_grid(self.active_months)
        except Exception as e:
            print(f"Error computing calendar grid months from exam periods: {e}")
            # On error, keep existing active_months (do not overwrite with possibly invalid data)

    def _render_active_schedule(self, schedule: Schedule) -> None:
        """
        Transforms Model-generated raw schedule entries into grid-renderable cell properties.
        """
        # Initialize a clean slate for the grid data structure and coordinate mapping for the current render cycle
        grid_data: Dict[str, dict] = {}
        self.cell_to_date_mapping.clear()
        
        # Build a mapping from course IDs to their associated program names for efficient lookup during exam processing
        course_to_programs = self._build_course_to_program_map()
        current_year = schedule.exams[0].exam_date.year if schedule.exams else datetime.now().year

        # Systematically initialize the grid data structure with empty properties for all potential date cells within the active month range
        for row_idx, month_idx in enumerate(self.active_months, start=1):
            for day_num in range(1, 32):
                col_idx = day_num - 1
                cell_key = f"{row_idx}-{col_idx}"

                grid_data[cell_key] = {
                    "is_excluded": False,
                    "day_text": "",
                    "exams": []
                }

                try:
                    real_date = date(current_year, month_idx + 1, day_num)
                    self.cell_to_date_mapping[cell_key] = real_date
                    grid_data[cell_key]["day_text"] = str(day_num)
                except ValueError:
                    grid_data[cell_key]["day_text"] = ""


        # Query all globally locked excluded dates directly from primary Model context
        excluded_dates = self.model.get_user_excluded_dates()
        
        # Mark all cells corresponding to excluded dates with the appropriate flag for the View to render with exclusion styling
        for cel_key, cell_date in self.cell_to_date_mapping.items():
            grid_data[cel_key]["is_excluded"] = cell_date in excluded_dates

        # Map schedule array contents systematically onto coordinates
        for exam in schedule.exams:
            exam_date = exam.exam_date
            month_idx = exam_date.month - 1
            day_num = exam_date.day

            if month_idx not in self.active_months:
                continue

            # Calculate grid coordinates based on the active month index and the day number, ensuring alignment with the View's expected layout structure
            row_idx = self.active_months.index(month_idx) + 1
            col_idx = day_num - 1
            cell_key = f"{row_idx}-{col_idx}"

            # Determine the exam type marker based on whether the course is mandatory or elective.
            real_c = next((c for c in self.model.data_manager.get_courses() if c.course_id == exam.course.course_id), exam.course)
            is_mandatory = getattr(real_c, "is_mandatory", True)
            exam_type_marker = "ח" if is_mandatory else "ב"

            # Format the program text for display on the exam card, defaulting to a generic placeholder if no linked programs are found.
            course_id = str(getattr(exam.course, "course_id", "")).strip()
            linked_programs = course_to_programs.get(course_id, [])
            program_text = ", ".join(linked_programs) if linked_programs else "Prog"

            # Parse structural payload matching exact card specifications of inside View layout
            grid_data[cell_key]["exams"].append({
                "short_name": getattr(exam.course, "course_name", "")[:10],  # Clamp length for clean card display
                "course_id": getattr(exam.course, "course_id", ""),
                "type": exam_type_marker,
                "program": program_text,  # Extensible placeholder text parameter matching View definitions
            })

        self.view.render_calendar_data(grid_data)

    # Helper method to build a mapping from course IDs to their associated program names based on the currently selected programs in the model
    def _build_course_to_program_map(self) -> Dict[str, List[str]]:
        course_to_programs: Dict[str, List[str]] = {}
        try:
            # Iterate through all selected programs in the model and build a reverse mapping of course_id -> [program_names]
            for prog_id in self.model.get_selected_programs():
                # Fetch the full course hierarchy for the program to access course details and names
                hierarchy = self.model.get_program_course_hierarchy(prog_id)
                program_name = hierarchy.get("program_name") or prog_id
                # Traverse the hierarchy to find all courses linked to this program and populate the mapping
                for semesters in hierarchy.get("courses_by_year_and_semester", {}).values():
                    for course_list in semesters.values():
                        for course in course_list:
                            cid = course.get("course_id")
                            if cid is None:
                                continue
                            # Normalize course_id to string and strip whitespace to ensure consistent mapping keys
                            cid = str(cid).strip()
                            course_to_programs.setdefault(cid, [])
                            # Avoid duplicate program entries for the same course
                            if program_name not in course_to_programs[cid]:
                                course_to_programs[cid].append(program_name)
        except Exception as e:
            print(f"[CalendarPresenter] Could not build course->program map: {e}")
        return course_to_programs

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

    def _handle_range_update(self, date_pairs: List[tuple]) -> None:
        try:
            exam_periods = self.model.get_exam_periods() or []
            if not exam_periods:
                return

            updated_ranges: List[tuple] = []
            exclusion_dates = []
            
            for idx, pair in enumerate(date_pairs):
                if not isinstance(pair, (list, tuple)) or len(pair) < 2:
                    continue
                    
                start_str = str(pair[0]).strip()
                end_str = str(pair[1]).strip()
                
                # Check if this is an exclusion (start == end)
                if start_str == end_str and start_str:
                    try:
                        ex_date = datetime.strptime(start_str, "%d-%m-%Y").date()
                        exclusion_dates.append(ex_date)
                    except ValueError:
                        pass
                else:
                    # Regular exam period range
                    if idx < len(exam_periods):
                        start_date = datetime.strptime(start_str, "%d-%m-%Y").date() if start_str else exam_periods[idx].start_date
                        end_date = datetime.strptime(end_str, "%d-%m-%Y").date() if end_str else exam_periods[idx].end_date
                        updated_ranges.append((start_date, end_date))

            # Update exam period ranges if any exist
            if updated_ranges:
                if hasattr(self.model, "update_all_exam_periods"):
                    self.model.update_all_exam_periods(updated_ranges)
                else:
                    # Compatibility fallback for legacy model API
                    first_start, first_end = updated_ranges[0]
                    self.model.update_custom_exam_period(first_start, first_end)
            
            # Add exclusion dates
            for ex_date in exclusion_dates:
                self.model.exclude_date(ex_date)
            self.collection_manager.clear_cache()

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

    def _handle_sync_action(self):
        # clear the collection manager's cache to force it to re-scan the output file and update its internal index, 
        # then trigger a refresh of the presenter state to reflect any new or updated schedules that may have been generated since the last scan.
        self.collection_manager.clear_cache() 
        
        # After clearing the cache, we need to refresh the presenter state to trigger a new scan of the output file and update the displayed schedules accordingly.
        if self.controller:
            self.controller.regenerate_schedules_snapshot()