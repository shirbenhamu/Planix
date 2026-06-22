# src/MVP/presenters/calendar_presenter.py

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.manual_edit.manual_edit_session import ManualEditSession


class CalendarPresenter:
    def __init__(self, view, model, collection_manager, controller=None):
        self.view = view
        self.model = model
        self.collection_manager = collection_manager
        self.controller = controller

        self.active_months: List[int] = []
        self.cell_to_date_mapping: Dict[str, date] = {}
        self.is_rendering = False

        # Manual drag & drop (PLAN-554): a per-board edit session holds the
        # original + currently-edited board. It is keyed to the on-disk board's
        # signature, so it rebuilds (edits reset) whenever the displayed schedule
        # changes — navigation, sort, regenerate — but survives a move/undo redraw.
        self._edit_session: Optional[ManualEditSession] = None
        self._session_base_sig = None

        # UI Event Binding
        self.view.on_next_clicked = self._handle_next_schedule
        self.view.on_prev_clicked = self._handle_prev_schedule
        self.view.on_page_jump = self._handle_page_jump
        self.view.on_exclude_clicked = self._handle_date_exclusion
        self.view.on_range_update_clicked = self._handle_range_update
        self.view.on_export_clicked = self._handle_export
        self.view.on_filter_clicked = self._handle_filter_click

        if hasattr(self.view, "on_load_more_clicked"):
            self.view.on_load_more_clicked = self._handle_load_more

        if hasattr(self.view, "on_sort_changed"):
            self.view.on_sort_changed = self._handle_sort_changed

        # Manual drag & drop callbacks (PLAN-560 / PLAN-563).
        if hasattr(self.view, "on_exam_dropped"):
            self.view.on_exam_dropped = self._handle_exam_dropped
        if hasattr(self.view, "on_undo_clicked"):
            self.view.on_undo_clicked = self._handle_undo
        # Live drop-validity preview for green/red feedback while dragging.
        if hasattr(self.view, "on_drag_validate"):
            self.view.on_drag_validate = self._validate_drop

        self.view.get_exam_periods_callback = lambda: list(self.model.get_exam_periods() or [])
        self.view.on_sync_clicked = self._handle_sync_action
        self.refresh_presenter_state()

    def _handle_load_more(self) -> None:
        try:
            import os
            current_count = 0
            if hasattr(self, "controller") and self.controller is not None:
                output_path = getattr(self.controller, "output_path", "output_results/final_schedules.txt")
                if os.path.exists(output_path):
                    with open(output_path, "r", encoding="utf-8") as f:
                        current_count = sum(1 for line in f if "--- FULL SYSTEM OPTION" in line)

            print(f"[CalendarPresenter] User clicked 'Load More'. Passing skip_count={current_count} to controller.")
            if hasattr(self, "controller") and self.controller is not None:
                self.controller.load_more_schedules(skip_count=current_count)
        except Exception as e:
            print(f"[CalendarPresenter] Error initializing load more pipeline: {e}")
                
    def _handle_sort_changed(self, sort_keys, ascending=None) -> None:
        try:
            self.collection_manager.sort_collection(sort_keys, ascending=ascending)
        except (ValueError, TypeError) as e:
            print(f"[CalendarPresenter] Ignoring invalid sort request: {e}")
            return
        self.refresh_presenter_state()

    def refresh_pagination_only(self) -> None:
        total_schedules = self.collection_manager.get_total_count()
        if total_schedules == 0:
            return
        current_idx = self.collection_manager.get_current_index()
        self.view.update_pagination(current_page=current_idx + 1, total_pages=total_schedules)

    def refresh_presenter_state(self) -> None:
        if self.is_rendering:
            return
        self.is_rendering = True
        try:
            # UI Lock Hook: Synchronize InputView lock state whenever calendar layout refreshes
            if self.controller and hasattr(self.controller, "input_presenter") and self.controller.input_presenter:
                self.controller.input_presenter.sync_ui_lock_state()

            total_schedules = self.collection_manager.get_total_count()
            if total_schedules == 0:
                self.view.show_empty_state()
                return

            current_idx = self.collection_manager.get_current_index()
            self.view.update_pagination(current_page=current_idx + 1, total_pages=total_schedules)

            try:
                active_schedule = self._active_board()
                self._setup_calendar_grid_dimensions(active_schedule)
                self._render_active_schedule(active_schedule)
                self._update_metrics_display()
                self._sync_undo_state()
            except Exception as e:
                print(f"Error refreshing calendar state: {e}")
                self.view.show_empty_state()
        finally:
            self.is_rendering = False

    # ===== Manual drag & drop (PLAN-554) =====================================

    @staticmethod
    def _board_signature(schedule: Schedule):
        return tuple(sorted(
            (exam.course.course_id, exam.exam_date) for exam in (schedule.exams or [])
        ))

    def _active_board(self) -> Schedule:
        """The board to display: the manual-edit session's current (possibly
        edited) board. The session is (re)built whenever the underlying on-disk
        board changes, so manual edits reset on paging/sort (PLAN-558)."""
        base = self.collection_manager.get_current_schedule()
        base_sig = self._board_signature(base)
        if self._edit_session is None or self._session_base_sig != base_sig:
            self._edit_session = ManualEditSession(
                base,
                exam_periods=self.model.get_exam_periods(),
                constraints=getattr(self.model, "constraints", None),
            )
            self._session_base_sig = base_sig
        return self._edit_session.current_board()

    def _handle_exam_dropped(self, course_id: str, source_cell_key: str, target_cell_key: str) -> None:
        """A card was dragged from source cell to target cell. Apply the move if
        valid; otherwise the board is left unchanged so the card snaps back
        (PLAN-560 / PLAN-561). No error dialog is shown."""
        old_date = self.cell_to_date_mapping.get(source_cell_key)
        new_date = self.cell_to_date_mapping.get(target_cell_key)
        if old_date is None or new_date is None:
            self.refresh_presenter_state()  # redraw -> snap back
            return

        self._active_board()  # ensure a session exists for the current board
        result = self._edit_session.move_exam(course_id, old_date, new_date)
        if not result.success:
            print(f"[CalendarPresenter] Move rejected ({result.reason}); snapping back.")
        self.refresh_presenter_state()

    def _validate_drop(self, course_id: str, source_cell_key: str, target_cell_key: str) -> bool:
        """Non-committing check used for live drag feedback (green/red target)."""
        old_date = self.cell_to_date_mapping.get(source_cell_key)
        new_date = self.cell_to_date_mapping.get(target_cell_key)
        if old_date is None or new_date is None:
            return False
        self._active_board()  # ensure a session exists
        return self._edit_session.can_move(course_id, old_date, new_date).success

    def _handle_undo(self) -> None:
        """Revert all manual changes for the current board (PLAN-563)."""
        if self._edit_session is not None:
            self._edit_session.undo()
        self.refresh_presenter_state()

    def _sync_undo_state(self) -> None:
        """Enable the Undo button only while the current board has manual edits."""
        if hasattr(self.view, "set_undo_enabled"):
            has_changes = self._edit_session is not None and self._edit_session.has_changes()
            self.view.set_undo_enabled(has_changes)

    def _setup_calendar_grid_dimensions(self, schedule: Schedule) -> None:
        unique_months: List[int] = []
        try:
            exam_periods = self.model.get_exam_periods()
            if exam_periods:
                min_date = min(ep.start_date for ep in exam_periods)
                max_date = max(ep.end_date for ep in exam_periods)
                cur_year = min_date.year
                cur_month = min_date.month
                while (cur_year, cur_month) <= (max_date.year, max_date.month):
                    unique_months.append(cur_month - 1)
                    if cur_month == 12:
                        cur_month = 1
                        cur_year += 1
                    else:
                        cur_month += 1
            else:
                if schedule and getattr(schedule, "exams", None):
                    unique_months = sorted(list(set(exam.exam_date.month - 1 for exam in schedule.exams)))

            if self.active_months != unique_months:
                self.active_months = unique_months
                self.view.init_grid(self.active_months)
        except Exception as e:
            print(f"Error computing calendar grid months from exam periods: {e}")

    def _render_active_schedule(self, schedule: Schedule) -> None:
        grid_data: Dict[str, dict] = {}
        self.cell_to_date_mapping.clear()
        
        course_to_programs = self._build_course_to_program_map()
        current_year = schedule.exams[0].exam_date.year if schedule.exams else datetime.now().year
        all_courses = {c.course_id: c for c in self.model.data_manager.get_courses()}

        for row_idx, month_idx in enumerate(self.active_months, start=1):
            for day_num in range(1, 32):
                col_idx = day_num - 1
                cell_key = f"{row_idx}-{col_idx}"
                grid_data[cell_key] = {"is_excluded": False, "day_text": "", "exams": []}
                try:
                    real_date = date(current_year, month_idx + 1, day_num)
                    self.cell_to_date_mapping[cell_key] = real_date
                    grid_data[cell_key]["day_text"] = str(day_num)
                except ValueError:
                    grid_data[cell_key]["day_text"] = ""

        excluded_dates = set(self.model.get_user_excluded_dates())
        for period in (self.model.get_exam_periods() or []):
            for excl in getattr(period, "excluded_dates", []) or []:
                current_excluded = excl.start_date
                while current_excluded <= excl.end_date:
                    excluded_dates.add(current_excluded)
                    current_excluded += timedelta(days=1)

        for cel_key, cell_date in self.cell_to_date_mapping.items():
            grid_data[cel_key]["is_excluded"] = cell_date in excluded_dates

        for exam in schedule.exams:
            exam_date = exam.exam_date
            month_idx = exam_date.month - 1
            day_num = exam_date.day

            if month_idx not in self.active_months:
                continue

            row_idx = self.active_months.index(month_idx) + 1
            col_idx = day_num - 1
            cell_key = f"{row_idx}-{col_idx}"

            real_c = all_courses.get(exam.course.course_id, exam.course)
            is_mandatory = getattr(real_c, "is_mandatory", True)
            exam_type_marker = "ח" if is_mandatory else "ב"

            course_id = str(getattr(exam.course, "course_id", "")).strip()
            linked_programs = course_to_programs.get(course_id, [])
            program_text = ", ".join(linked_programs) if linked_programs else "Prog"

            grid_data[cell_key]["exams"].append({
                "short_name": getattr(exam.course, "course_name", "")[:10],
                "course_id": getattr(exam.course, "course_id", ""),
                "type": exam_type_marker,
                "program": program_text,
            })

        self.view.render_calendar_data(grid_data)

    def _build_course_to_program_map(self) -> Dict[str, List[str]]:
        course_to_programs: Dict[str, List[str]] = {}
        try:
            for prog_id in self.model.get_selected_programs():
                hierarchy = self.model.get_program_course_hierarchy(prog_id)
                program_name = hierarchy.get("program_name") or prog_id
                for semesters in hierarchy.get("courses_by_year_and_semester", {}).values():
                    for course_list in semesters.values():
                        for course in course_list:
                            cid = course.get("course_id")
                            if cid is None:
                                continue
                            cid = str(cid).strip()
                            course_to_programs.setdefault(cid, [])
                            if program_name not in course_to_programs[cid]:
                                course_to_programs[cid].append(program_name)
        except Exception as e:
            print(f"[CalendarPresenter] Could not build course->program map: {e}")
        return course_to_programs

    def _handle_next_schedule(self) -> None:
        if self.collection_manager.get_total_count() == 0:
            self.refresh_presenter_state()
            return
        if self.collection_manager.next_schedule():
            self.refresh_presenter_state()
            return
        if self._engine_is_active():
            self.collection_manager.apply_sort_and_refresh()
            if self.collection_manager.next_schedule():
                self.refresh_presenter_state()
        else:
            self._show_end_of_results()

    def _update_metrics_display(self) -> None:
        if not hasattr(self.view, "update_metrics_display"):
            return
        try:
            metrics = self.collection_manager.get_current_metrics()
        except (ValueError, IndexError):
            metrics = None
        self.view.update_metrics_display(metrics)

    def auto_refresh_feed(self) -> bool:
        self.collection_manager.apply_sort_and_refresh()
        if self._engine_is_active():
            self.refresh_pagination_only()
            return True
        self.refresh_presenter_state()
        return False

    def _engine_is_active(self) -> bool:
        controller = getattr(self, "controller", None)
        adapter = getattr(controller, "engine_adapter", None) if controller else None
        if adapter is None:
            return False
        try:
            return bool(adapter.is_generation_active())
        except Exception:
            return False

    def _show_end_of_results(self) -> None:
        if hasattr(self.view, "show_no_more_results"):
            self.view.show_no_more_results()

    def _handle_prev_schedule(self) -> None:
        if self.collection_manager.get_total_count() == 0:
            self.refresh_presenter_state()
            return
        if self.collection_manager.prev_schedule():
            self.refresh_presenter_state()

    def _handle_page_jump(self, page_number: int) -> None:
        target_idx = page_number - 1
        if self.collection_manager.jump_to_schedule(target_idx):
            self.refresh_presenter_state()
        else:
            current_idx = self.collection_manager.get_current_index()
            total_pages = self.collection_manager.get_total_count()
            self.view.update_pagination(current_page=current_idx + 1, total_pages=total_pages)

    def _handle_date_exclusion(self, cell_key: str) -> None:
        target_date = self.cell_to_date_mapping.get(cell_key)
        if not target_date:
            return
        self.model.toggle_date_exclusion(target_date)
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
                if start_str == end_str and start_str:
                    try:
                        ex_date = datetime.strptime(start_str, "%d-%m-%Y").date()
                        exclusion_dates.append(ex_date)
                    except ValueError:
                        pass
                else:
                    if idx < len(exam_periods):
                        start_date = datetime.strptime(start_str, "%d-%m-%Y").date() if start_str else exam_periods[idx].start_date
                        end_date = datetime.strptime(end_str, "%d-%m-%Y").date() if end_str else exam_periods[idx].end_date
                        updated_ranges.append((start_date, end_date))

            if updated_ranges:
                if hasattr(self.model, "update_all_exam_periods"):
                    self.model.update_all_exam_periods(updated_ranges)
                else:
                    first_start, first_end = updated_ranges[0]
                    self.model.update_custom_exam_period(first_start, first_end)
            for ex_date in exclusion_dates:
                self.model.exclude_date(ex_date)
            self.collection_manager.clear_cache()
        except Exception as e:
            print(f"Error updating exam period range: {e}")

    def _handle_export(self, destination_file_path: str) -> None:
        try:
            # Export the currently displayed board including manual edits, not the
            # original on-disk one (PLAN-562).
            active_schedule = self._active_board()
            with open(destination_file_path, "w", encoding="utf-8") as out_file:
                out_file.write("--- EXPORTED EXAM SCHEDULE SYSTEM OPTION ---\n")
                for exam in active_schedule.exams:
                    formatted_line = f"Date: {exam.exam_date.strftime('%d-%m-%Y')} | Course: {exam.course.course_id} - {exam.course.course_name}\n"
                    out_file.write(formatted_line)
            print(f"Schedule exported successfully to {destination_file_path}")
        except Exception as e:
            print(f"Failed to export destination file: {e}")

    def _handle_filter_click(self) -> None:
        try:
            # Guard Clause: Block filtering actions if a background generation process is already active
            if self._engine_is_active():
                print("[CalendarPresenter][Block] Request denied. Background engine calculation is currently active.")
                return

            selected_programs = []
            if hasattr(self.view, "get_selected_programs"):
                raw_programs = self.view.get_selected_programs()
                cleaned_program_ids = []
                for prog in raw_programs:
                    if "(" in prog and ")" in prog:
                        try:
                            prog_id = prog.split("(")[-1].split(")")[0].strip()
                            cleaned_program_ids.append(prog_id)
                        except Exception:
                            cleaned_program_ids.append(prog.strip())
                    else:
                        cleaned_program_ids.append(prog.strip())
                if cleaned_program_ids:
                    if hasattr(self.model, "update_selected_programs"):
                        self.model.update_selected_programs(cleaned_program_ids)
                    elif hasattr(self.model, "set_selected_programs"):
                        self.model.set_selected_programs(cleaned_program_ids)
                    else:
                        self.model.selected_programs = cleaned_program_ids
            
            if hasattr(self, "controller") and self.controller is not None:
                self.controller.regenerate_schedules_snapshot()
        except Exception as e:
            print(f"Error handling filter execution pipeline: {e}")

    def _handle_sync_action(self):
        # Guard Clause: Block manual sync dispatch synchronization if background run is active
        if self._engine_is_active():
            print("[CalendarPresenter][Block] Request denied. Generation pipeline is currently active.")
            return

        self.collection_manager.clear_cache() 
        if self.controller:
            self.controller.regenerate_schedules_snapshot()