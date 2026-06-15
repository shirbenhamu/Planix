from typing import Dict, List, Tuple, Iterator, Set
from datetime import date

from src.MVP.models.course import Course
from src.MVP.models.exam_period import ExamPeriod
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.engine.exam_scheduler import ExamScheduler
from src.engine.scheduling_constraints import SchedulingConstraints

class AdvancedExamScheduler(ExamScheduler):
    def __init__(self, constraints: SchedulingConstraints = None) -> None:
        super().__init__()
        # If no constraints are provided, initialize with a default instance (all flags False)
        self.constraints = constraints if constraints is not None else SchedulingConstraints()
        
        # High-performance lookup structures to ensure O(1) constraint validation during backtracking
        self._exams_per_day: Dict[date, int] = {}
        self._mandatory_exam_dates: Dict[str, List[date]] = {}       # program_id -> list of scheduled dates
        self._all_exam_dates_by_program: Dict[str, List[date]] = {}  # program_id -> list of scheduled dates
        self._elective_conflicts_count: Dict[str, int] = {}          # course_id -> conflict count

    def _generate_schedule_combinations(
        self,
        courses: List[Course],
        available_dates: List[object],
        course_index: int,
        current_scheduled_exams: List[ScheduledExam],
        conflict_matrix: Set[Tuple[str, str]]
    ) -> Iterator[Schedule]:
        """
        Overrides the base backtracking combination generator to maintain and update 
        the high-performance lookup structures as the recursion goes deeper or backtracks.
        """
        if course_index == len(courses):
            yield Schedule(exams=current_scheduled_exams.copy())
            return

        current_course = courses[course_index]

        for exam_date in available_dates:
            # 1. Evaluate suitability in O(1) - checks base constraints + active k-constraints
            if self._can_add_exam_to_schedule(
                current_course,
                exam_date,
                current_scheduled_exams,
                conflict_matrix
            ):
                # 2. State Mutation: Update tracking structures before diving deeper into recursion
                self._push_state(current_course, exam_date)
                
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

                # 3. Backtrack: Revert tracking structures to previous state when popping out
                current_scheduled_exams.pop()
                self._pop_state(current_course, exam_date)

    def _can_add_exam_to_schedule(
        self,
        course: Course,
        exam_date: date,
        scheduled_exams: List[ScheduledExam],
        conflict_matrix: Set[Tuple[str, str]]
    ) -> bool:
        # A) First, enforce original core legacy engine constraints
        if not super()._can_add_exam_to_schedule(course, exam_date, scheduled_exams, conflict_matrix):
            return False

        # B) Dynamic k-constraints gating (Supports 0 up to all 5 constraints simultaneously)
        
        # 2.1 Min days between mandatory exams
        if self.constraints.min_days_mandatory_enabled:
            if not self._check_min_days_mandatory(course, exam_date):
                return False

        # 2.2 Min days between any two exams
        if self.constraints.min_days_any_enabled:
            if not self._check_min_days_any(course, exam_date):
                return False

        # 2.3 Max elective-elective conflicts
        if self.constraints.max_elective_conflicts_enabled:
            if not self._check_max_elective_conflicts(course, exam_date):
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

    # --- O(1) State Management and Hook Placeholders for PLAN-424 ---
    
    def _push_state(self, course: Course, exam_date: date) -> None:
        """Increments tracking states when an exam is provisionally added."""
        self._exams_per_day[exam_date] = self._exams_per_day.get(exam_date, 0) + 1
        # Additional O(1) map mutations for requirements 2.1-2.4 will be added in PLAN-424

    def _pop_state(self, course: Course, exam_date: date) -> None:
        """Decrements tracking states when backtracking (popping) an exam choice."""
        if exam_date in self._exams_per_day:
            self._exams_per_day[exam_date] -= 1
        # Additional O(1) map rollbacks for requirements 2.1-2.4 will be added in PLAN-424

    def _check_min_days_mandatory(self, course: Course, exam_date: date) -> bool:
        # Placeholder logic - to be implemented in PLAN-424
        return True

    def _check_min_days_any(self, course: Course, exam_date: date) -> bool:
        # Placeholder logic - to be implemented in PLAN-424
        return True

    def _check_max_elective_conflicts(self, course: Course, exam_date: date) -> bool:
        # Placeholder logic - to be implemented in PLAN-424
        return True

    def _check_span_mandatory(self, course: Course, exam_date: date) -> bool:
        # Placeholder logic - to be implemented in PLAN-424
        return True

    def _check_max_exams_per_day(self, exam_date: date) -> bool:
        # Efficient O(1) dictionary evaluation bypassing schedule iteration
        current_count = self._exams_per_day.get(exam_date, 0)
        return current_count < self.constraints.max_exams_per_day_k