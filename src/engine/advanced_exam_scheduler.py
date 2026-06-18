from typing import Dict, List, Tuple, Iterator, Set
from datetime import date

from src.MVP.models.course import Course
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.engine.exam_scheduler import ExamScheduler
from src.engine.scheduling_constraints import SchedulingConstraints

# AdvancedExamScheduler extends the original ExamScheduler with new constraints and optimizations.

class AdvancedExamScheduler(ExamScheduler):
    def __init__(self, constraints: SchedulingConstraints = None) -> None:
        super().__init__()
        self.constraints = constraints if constraints is not None else SchedulingConstraints()
        
        # High-performance lookup structures for O(1) constraints validation
        self._exams_per_day: Dict[date, int] = {}
        # Group by (program_id, year) tuple for requirements 2.1, 2.2, 2.4
        self._exam_dates_by_program_year: Dict[Tuple[str, int], List[date]] = {}

    # --- Core Backtracking Algorithm with Integrated Constraints ---

    def _generate_schedule_combinations(
        self,
        courses: List[Course],
        available_dates: List[object],
        course_index: int,
        current_scheduled_exams: List[ScheduledExam],
        conflict_matrix: Set[Tuple[str, str]]
    ) -> Iterator[Schedule]:
        if course_index == len(courses):
            yield Schedule(exams=current_scheduled_exams.copy())
            return

        current_course = courses[course_index]

        for exam_date in available_dates:
            # 1. CHECKS: Evaluate all active constraints dynamically
            if self._can_add_exam_to_schedule(
                current_course,
                exam_date,
                current_scheduled_exams,
                conflict_matrix
            ):
                # 2. PUSH: Update state before diving deeper into recursion
                self._push_state(current_course, exam_date, current_scheduled_exams, conflict_matrix)
                
                current_scheduled_exams.append(
                    ScheduledExam(course=current_course, exam_date=exam_date)
                )

                yield from self._generate_schedule_combinations(
                    courses,
                    available_dates,
                    course_index + 1,
                    current_scheduled_exams,
                    conflict_matrix
                )

                # 3. POP: Revert state during backtrack
                current_scheduled_exams.pop()
                self._pop_state(current_course, exam_date, current_scheduled_exams, conflict_matrix)

    # --- O(1) Constraints Validation Implementation ---

    def _can_add_exam_to_schedule(
        self,
        course: Course,
        exam_date,
        scheduled_exams: List[ScheduledExam],
        conflict_matrix: Set[Tuple[str, str]]
    ) -> bool:

        # Enforce original V1.0 engine core constraints first (CONSTRAINTS CHECKS 1.0)
        if not super()._can_add_exam_to_schedule(course, exam_date, scheduled_exams, conflict_matrix):
            return False

        # 2.1 Min days between mandatory exams
        if self.constraints.min_days_mandatory_enabled:
            if not self._check_min_days_mandatory(course, exam_date):
                return False

        # 2.2 Min days between any two exams in same (program, year)
        if self.constraints.min_days_any_enabled:
            k = self.constraints.min_days_any_k
            for info in course.program_info:
                key = (info.program_id, info.year)
                existing_dates = self._exam_dates_by_program_year.get(key, [])
                for existing_date in existing_dates:
                    if abs((exam_date - existing_date).days) < k:
                        return False

        # 2.3 Max elective-elective conflicts (Calculated dynamically via the active branch)
        if self.constraints.max_elective_conflicts_enabled:
            current_day_conflicts = 0
            is_current_elective = any(info.requirement == "Elective" for info in course.program_info)
            if is_current_elective:
                for info in course.program_info:
                    # Only consider elective courses for this constraint
                    if info.requirement == "Elective":
                        for prev_exam in scheduled_exams:
                            # Check if the previous exam is on the same day
                            if prev_exam.exam_date == exam_date:
                                # Check if the previous exam is also an elective and belongs to the same (program_id, year)
                                for prev_info in prev_exam.course.program_info:
                                    if prev_info.requirement == "Elective":
                                        if info.program_id == prev_info.program_id and info.year == prev_info.year:
                                            # This is a conflict between two elective exams for the same (program_id, year) cohort on the same day
                                            current_day_conflicts += 1
            if current_day_conflicts > self.constraints.max_elective_conflicts_k:
                return False

        # 2.4 Span between first and last mandatory exam
        if self.constraints.span_mandatory_enabled:
            if not self._check_span_mandatory(course, exam_date):
                return False

        # 2.5 Max exams per day
        if self.constraints.max_exams_per_day_enabled:
            if not self._check_max_exams_per_day(exam_date):
                return False

        return True

    # --- O(1) State Management Implementation ---

    def _push_state(self, course: Course, exam_date: date, scheduled_exams: List[ScheduledExam], conflict_matrix: Set[Tuple[str, str]]) -> None:
        # 2.5 Track exams per day
        self._exams_per_day[exam_date] = self._exams_per_day.get(exam_date, 0) + 1
        
        # 2.1, 2.2, 2.4 Track dates grouped by (program_id, year) for cohort-level constraints
        for info in course.program_info:
            key = (info.program_id, info.year)
            if key not in self._exam_dates_by_program_year:
                self._exam_dates_by_program_year[key] = []
            self._exam_dates_by_program_year[key].append(exam_date)

    def _pop_state(self, course: Course, exam_date: date, scheduled_exams: List[ScheduledExam], conflict_matrix: Set[Tuple[str, str]]) -> None:
        # 2.5 Revert exams per day
        if exam_date in self._exams_per_day:
            self._exams_per_day[exam_date] -= 1
            if self._exams_per_day[exam_date] == 0:
                del self._exams_per_day[exam_date]
        
        # 2.1, 2.2, 2.4 Revert dates from (program_id, year) grouping
        for info in course.program_info:
            key = (info.program_id, info.year)
            if key in self._exam_dates_by_program_year and exam_date in self._exam_dates_by_program_year[key]:
                self._exam_dates_by_program_year[key].remove(exam_date)

    # --- O(1) High-Performance Checks Implementation ---

    # 2.1: Min days between mandatory exams in same (program, year) >= k
    def _check_min_days_mandatory(self, course: Course, exam_date: date) -> bool:
        """2.1: Min days between mandatory exams in same (program, year) >= k"""
        k = self.constraints.min_days_mandatory_k
        for info in course.program_info:
            if info.requirement != "Elective":
                # Query dates for this specific (program_id, year) cohort
                key = (info.program_id, info.year)
                existing_dates = self._exam_dates_by_program_year.get(key, [])
                for existing_date in existing_dates:
                    if abs((exam_date - existing_date).days) < k:
                        return False
        return True

    # 2.2: Min days between any exams in same (program, year) >= k
    def _check_min_days_any(self, exam_date: date) -> bool:
        """2.2: Min days between any exams in same (program, year) >= k"""
        k = self.constraints.min_days_any_k
        # Check all (program, year) groups the current exam belongs to (implicitly via _check_min_days_mandatory logic)
        # We need to check from the course context, so this is a placeholder that returns True
        # The actual check happens per-course in _can_add_exam_to_schedule via inline logic below
        return True

    # 2.3: Max elective-elective conflicts check is calculated dynamically in the main loop, so this is a placeholder to satisfy signature contracts.
    def _check_max_elective_conflicts(self, course: Course, exam_date: date) -> bool:
        """Required placeholder to satisfy signature contracts. Logic is calculated dynamically above."""
        return True

    # 2.4: Span between first→last mandatory exams in same (program, year) <= k
    def _check_span_mandatory(self, course: Course, exam_date: date) -> bool:
        """2.4: Maximum span between first→last mandatory exams in same (program, year) <= k"""
        k = self.constraints.span_mandatory_k
        for info in course.program_info:
            if info.requirement != "Elective":
                # Query dates for this specific (program_id, year) cohort
                key = (info.program_id, info.year)
                existing_dates = self._exam_dates_by_program_year.get(key, [])
                if not existing_dates:
                    continue
                all_dates = existing_dates + [exam_date]
                current_span = (max(all_dates) - min(all_dates)).days + 1
                if current_span > k:
                    return False
        return True

    # 2.5: Max exams per day check
    def _check_max_exams_per_day(self, exam_date: date) -> bool:
        current_count = self._exams_per_day.get(exam_date, 0)
        return current_count < self.constraints.max_exams_per_day_k