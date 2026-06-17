from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Set

from src.data_manager import DataManager
from src.engine.scheduling_constraints import SchedulingConstraints  # Imported constraints
from src.MVP.models.course import Course
from src.MVP.models.exam_period import ExcludedDate, ExamPeriod

PROGRAM_MAPPING = {
    "83101": "Computer Engineering",
    "83102": "Electrical Engineering",
    "83104": "Industrial and Information Systems Engineering",
    "83107": "Data Engineering",
    "83108": "Software Engineering",
    "83109": "Materials Engineering",
    "83105": "Computer Engineering - Computer Hardware Track",
    "83182": "Electrical Engineering - Quantum Engineering Track",
    "83103": "Electrical Engineering - Neuro-engineering Track",
    "83115": "Electrical Engineering - Biomedical Engineering Track",
}


@dataclass(frozen=True)
class AcademicProgram:
    program_id: str
    program_name: str


@dataclass
class PlanixModel:
    data_manager: DataManager
    courses_path: Optional[str] = None
    exam_periods_path: Optional[str] = None
    selected_programs_path: Optional[str] = None
    selected_programs: List[str] = field(default_factory=list)
    available_programs: Dict[str, str] = field(default_factory=dict)
    max_selected_programs: int = 5
    constraints: SchedulingConstraints = field(default_factory=SchedulingConstraints)  # Injected constraints field
    _is_generating: bool = field(default=False, init=False, repr=False)
    _generation_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _user_excluded_dates: Set[date] = field(default_factory=set, init=False, repr=False)
    _current_start_date: Optional[date] = field(default=None, init=False, repr=False)
    _current_end_date: Optional[date] = field(default=None, init=False, repr=False)

    # The is_generating property provides a thread-safe way to track whether the engine is currently 
    # running a generation process, allowing the UI to react accordingly (e.g., by showing loading 
    # indicators or preventing multiple concurrent runs).
    @property
    def is_generating(self) -> bool:
        with self._generation_lock:
            return self._is_generating

    #  The setter for is_generating ensures that the value is a boolean and updates the internal state in a thread-safe manner.
    @is_generating.setter
    def is_generating(self, value: bool) -> None:
        if not isinstance(value, bool):
            raise TypeError("is_generating must be a boolean value.")

        with self._generation_lock:
            self._is_generating = value
  
    def set_data_paths(
        self,
        courses_path: Optional[str] = None,
        exam_periods_path: Optional[str] = None,
        selected_programs_path: Optional[str] = None,
    ) -> None:
        self.courses_path = courses_path
        self.exam_periods_path = exam_periods_path
        self.selected_programs_path = selected_programs_path

    def build_available_programs(self) -> Dict[str, str]:
        programs: Dict[str, str] = {}

        for course in self.data_manager.get_courses():
            self._collect_programs_from_course(course, programs)

        self.available_programs = programs
        return self.available_programs

    def _collect_programs_from_course(
        self,
        course: Course,
        programs: Dict[str, str],
    ) -> None:
        for program_info in course.program_info:
            program_id = program_info.program_id
            if program_id in programs:
                continue

            program_name = self._resolve_program_name(course, program_id)
            programs[program_id] = program_name

    def _resolve_program_name(self, course: Course, program_id: str) -> str:
        return PROGRAM_MAPPING.get(program_id, program_id)

    def add_selected_program(self, program_id: str) -> None:
        normalized_program_id = self._normalize_program_id(program_id)

        if normalized_program_id in self.selected_programs:
            return

        if len(self.selected_programs) >= self.max_selected_programs:
            raise ValueError(
                f"Cannot select more than {self.max_selected_programs} programs."
            )

        self.selected_programs.append(normalized_program_id)

    def remove_selected_program(self, program_id: str) -> None:
        normalized_program_id = self._normalize_program_id(program_id)

        try:
            self.selected_programs.remove(normalized_program_id)
        except ValueError as exc:
            raise ValueError(
                f"Program '{normalized_program_id}' is not currently selected."
            ) from exc

    def set_selected_programs(self, program_ids: List[str]) -> None:
        normalized_programs = self._normalize_program_list(program_ids)
        if len(normalized_programs) > self.max_selected_programs:
            raise ValueError(
                f"Cannot select more than {self.max_selected_programs} programs."
            )

        self.selected_programs = normalized_programs

    def get_available_programs(self) -> Dict[str, str]:
        return dict(self.available_programs)

    def get_selected_programs(self) -> List[str]:
        return list(self.selected_programs)

    def get_courses_path(self) -> Optional[str]:
        return self.courses_path

    def get_exam_periods_path(self) -> Optional[str]:
        return self.exam_periods_path

    def get_selected_programs_path(self) -> Optional[str]:
        return self.selected_programs_path

    def update_custom_exam_period(self, start_date: date, end_date: date) -> None:
        self._validate_date_value(start_date)
        self._validate_date_value(end_date)

        if start_date > end_date:
            raise ValueError("start_date cannot be after end_date.")

        # Update the model's current date range state, which will be used during the next synchronization with the DataManager before generation.
        self._current_start_date = start_date
        self._current_end_date = end_date
        
        # Enforce the updated state to the DataManager immediately to ensure that any subsequent operations (like schedule generation)
        # will use the most current date range and exclusions configured by the user.
        self.enforce_state_to_data_manager()

    def update_all_exam_periods(self, updated_ranges: List[tuple]) -> None:
        if not self.data_manager:
            return

        existing_periods = self.data_manager.get_exam_periods() or []
        if not existing_periods:
            return

        if len(updated_ranges) != len(existing_periods):
            raise ValueError("updated_ranges length must match existing exam periods length.")

        new_periods: List[ExamPeriod] = []
        for idx, period in enumerate(existing_periods):
            start_date, end_date = updated_ranges[idx]
            self._validate_date_value(start_date)
            self._validate_date_value(end_date)

            if start_date > end_date:
                raise ValueError(f"start_date cannot be after end_date for period index {idx}.")

            original_exclusions = []
            for ex in period.excluded_dates:
                dt_val = getattr(ex, "start_date", ex) 
                if dt_val not in self._user_excluded_dates and start_date <= dt_val <= end_date:
                    original_exclusions.append(ex)


            user_exclusions = [
                ExcludedDate(start_date=dt, end_date=dt, comment="User Excluded")
                for dt in sorted(self._user_excluded_dates)
                if start_date <= dt <= end_date
            ]

            combined_exclusions = original_exclusions + user_exclusions

            new_periods.append(
                ExamPeriod(
                    semester=period.semester,
                    moed=period.moed,
                    start_date=start_date,
                    end_date=end_date,
                    excluded_dates=combined_exclusions,
                )
            )

        self.data_manager.exam_periods = new_periods
        print(f"[PlanixModel] Updated all exam periods. Count: {len(new_periods)}")
    
    def _normalize_program_id(self, program_id: str) -> str:
        if not isinstance(program_id, str):
            raise TypeError("program_id must be a string.")

        normalized_program_id = program_id.strip()
        if not normalized_program_id:
            raise ValueError("program_id cannot be empty.")
        return normalized_program_id

    def _normalize_program_list(self, program_ids: List[str]) -> List[str]:
        normalized_programs: List[str] = []
        seen_programs: Set[str] = set()

        for program_id in program_ids:
            normalized_program_id = self._normalize_program_id(program_id)
            if normalized_program_id in seen_programs:
                continue
            seen_programs.add(normalized_program_id)
            normalized_programs.append(normalized_program_id)

        return normalized_programs

    def exclude_date(self, d: date) -> None:
        self._validate_date_value(d)
        self._user_excluded_dates.add(d)
        self._sync_excluded_dates_to_data_manager()

    def include_date(self, d: date) -> None:
        self._validate_date_value(d)
        self._user_excluded_dates.discard(d)
        self._sync_excluded_dates_to_data_manager()

    def toggle_date_exclusion(self, d: date) -> None:
        self._validate_date_value(d)
        if d in self._user_excluded_dates:
            self._user_excluded_dates.remove(d)
        else:
            self._user_excluded_dates.add(d)
        self._sync_excluded_dates_to_data_manager()

    def _sync_excluded_dates_to_data_manager(self) -> None:
        if not self.data_manager:
            return
        try:
            exam_periods = self.data_manager.get_exam_periods() or []
            for period in exam_periods:
                original_exclusions = [
                    ex for ex in period.excluded_dates
                    if isinstance(ex, ExcludedDate)
                    and getattr(ex, "comment", "") != "User Excluded"
                ]
                user_exclusions = [
                    ExcludedDate(start_date=dt, end_date=dt, comment="User Excluded")
                    for dt in self._user_excluded_dates
                    if period.start_date <= dt <= period.end_date
                ]
                period.excluded_dates = original_exclusions + user_exclusions
        except Exception as e:
            print(f"Error syncing excluded dates to data manager: {e}")

    def _periods_overlap(self, period1: ExamPeriod, period2: ExamPeriod) -> bool:
        if period1.semester != period2.semester or period1.moed != period2.moed:
            return False
        overlap_start = max(period1.start_date, period2.start_date)
        overlap_end = min(period1.end_date, period2.end_date)
        return overlap_start <= overlap_end

    def merge_exam_periods_from_file(self, new_periods: List[ExamPeriod], mode: str = "replace") -> None:
        if not self.data_manager:
            return
        
        if mode == "replace":
            self.data_manager.exam_periods = new_periods
            print(f"[PlanixModel] Replaced exam periods. New count: {len(new_periods)}")
        else:
            existing_periods = self.data_manager.get_exam_periods() or []
            for period in new_periods:
                has_overlap = any(self._periods_overlap(period, ex) for ex in existing_periods)
                if has_overlap:
                    print(f"[PlanixModel] Skipping overlapping exam period: {period.semester} {period.moed}")
                elif period not in existing_periods:
                    existing_periods.append(period)
            self.data_manager.exam_periods = existing_periods
            print(f"[PlanixModel] Merged exam periods. Final count: {len(existing_periods)}")

    def get_user_excluded_dates(self) -> List[date]:
        return sorted(self._user_excluded_dates)

    def validate_scheduling_constraints(self) -> None:
        if self.data_manager is None:
            raise ValueError("Data manager is not configured.")

        courses = self.data_manager.get_courses()
        exam_periods = self.data_manager.get_exam_periods()

        if not courses:
            raise ValueError("No courses have been loaded.")

        if not exam_periods:
            raise ValueError("No exam periods have been loaded.")

        if not self.selected_programs:
            raise ValueError("No selected programs are configured.")

        if len(self.selected_programs) > self.max_selected_programs:
            raise ValueError(f"Cannot select more than {self.max_selected_programs} programs.")

        if not self.available_programs:
            self.build_available_programs()

        missing_programs = [
            program_id
            for program_id in self.selected_programs
            if program_id not in self.available_programs
        ]
        if missing_programs:
            raise ValueError("Selected programs are not available in data: " + ", ".join(missing_programs))

        for excluded_date in self._user_excluded_dates:
            self._validate_date_value(excluded_date)

    def get_program_course_hierarchy(self, program_id: str) -> dict:
        normalized_program_id = self._normalize_program_id(program_id)
        program_name = PROGRAM_MAPPING.get(normalized_program_id, normalized_program_id)

        hierarchy: Dict[int, Dict[str, List[dict]]] = {}

        for course in self.data_manager.get_courses():
            matched_program_info = None
            for info in getattr(course, "program_info", []):
                if getattr(info, "program_id", None) == normalized_program_id:
                    matched_program_info = info
                    break
            if matched_program_info is None:
                continue

            year = getattr(matched_program_info, "year", None)
            semester = getattr(matched_program_info, "semester", None)
            requirement = getattr(matched_program_info, "requirement", None)

            if year is None or semester is None:
                continue

            year_group = hierarchy.setdefault(year, {})
            semester_group = year_group.setdefault(semester, [])

            semester_group.append(
                {
                    "course_id": getattr(course, "course_id", ""),
                    "course_name": getattr(course, "course_name", ""),
                    "requirement": requirement,
                    "evaluation_method": getattr(course, "evaluation_method", ""),
                }
            )

        return {
            "program_id": normalized_program_id,
            "program_name": program_name,
            "courses_by_year_and_semester": hierarchy,
        }

    def _validate_date_value(self, value: date) -> None:
        if not isinstance(value, date):
            raise TypeError("Expected a datetime.date value.")

    def get_exam_periods(self) -> list:
        if self.data_manager:
            return self.data_manager.get_exam_periods() or []
        return []

    def enforce_state_to_data_manager(self) -> None:
        if not self.data_manager:
            return
            
        existing_periods = self.data_manager.get_exam_periods() or []
        if not existing_periods:
            return
        
        for period in existing_periods:
            original_exclusions = []
            for ex in period.excluded_dates:
                dt_val = getattr(ex, "start_date", ex)
                if dt_val not in self._user_excluded_dates:
                    original_exclusions.append(ex)
            
            user_exclusions = [
                ExcludedDate(start_date=dt, end_date=dt, comment="User Excluded")
                for dt in sorted(self._user_excluded_dates)
                if period.start_date <= dt <= period.end_date
            ]
            period.excluded_dates = original_exclusions + user_exclusions

        print(f"[PlanixModel] State enforced successfully. Synced user exclusions to DataManager.")

    def clear_user_exclusions(self) -> None:
        self._user_excluded_dates.clear()
        self._sync_excluded_dates_to_data_manager()