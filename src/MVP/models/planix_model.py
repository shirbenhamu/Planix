from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Set

from src.data_manager import DataManager
from src.MVP.models.course import Course
from src.MVP.models.exam_period import ExamPeriod

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
    _is_generating: bool = field(default=False, init=False, repr=False)
    _generation_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _user_excluded_dates: Set[date] = field(default_factory=set, init=False, repr=False)

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

        existing_exam_periods = self.data_manager.get_exam_periods()
        if existing_exam_periods:
            template_exam_period = existing_exam_periods[0]
            semester = template_exam_period.semester
            moed = template_exam_period.moed
            excluded_dates = list(template_exam_period.excluded_dates)
        else:
            semester = ""
            moed = ""
            excluded_dates = []

        new_exam_period = ExamPeriod(
            semester=semester,
            moed=moed,
            start_date=start_date,
            end_date=end_date,
            excluded_dates=excluded_dates,
        )
        self.data_manager.exam_periods = [new_exam_period]

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

    def include_date(self, d: date) -> None:
        self._validate_date_value(d)
        self._user_excluded_dates.discard(d)

    def toggle_date_exclusion(self, d: date) -> None:
        self._validate_date_value(d)
        if d in self._user_excluded_dates:
            self._user_excluded_dates.remove(d)
        else:
            self._user_excluded_dates.add(d)

    def get_user_excluded_dates(self) -> List[date]:
        return sorted(self._user_excluded_dates)

    #  This method validates that the model's data is properly configured and that the selected programs are valid before schedule generation can proceed.
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
            raise ValueError(
                f"Cannot select more than {self.max_selected_programs} programs."
            )

        if not self.available_programs:
            self.build_available_programs()

        missing_programs = [
            program_id
            for program_id in self.selected_programs
            if program_id not in self.available_programs
        ]
        if missing_programs:
            raise ValueError(
                "Selected programs are not available in the loaded course data: "
                + ", ".join(missing_programs)
            )

        for excluded_date in self._user_excluded_dates:
            self._validate_date_value(excluded_date)

    #  This method generates a structured representation of the courses organized by the selected program, which can be used for UI display or further processing.
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