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
        self.constraints = constraints if constraints is not None else SchedulingConstraints()
        
        # High-performance lookup structures for O(1) constraints validation
        self._exams_per_day: Dict[date, int] = {}
        self._all_scheduled_dates: Set[date] = set()
        self._mandatory_dates_by_program: Dict[str, Set[date]] = {}  # program_id -> set of dates
        
        # For tracking elective conflict counts per course dynamically
        self._elective_conflicts_count: Dict[str, int] = {}

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
            # 1. CHECKS: Evaluate all active constraints in O(1)
            if self._can_add_exam_to_schedule(
                current_course,
                exam_date,
                current_scheduled_exams,
                conflict_matrix
            ):
                # 2. PUSH: Update state before diving deeper
                self._push_state(current_course, exam_date, conflict_matrix, current_scheduled_exams)
                
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
                self._pop_state(current_course, exam_date, conflict_matrix, current_scheduled_exams)

    def _can_add_exam_to_schedule(
        self,
        course: Course,
        exam_date: date,
        scheduled_exams: List[ScheduledExam],
        conflict_matrix: Set[Tuple[str, str]]
    ) -> bool:
        # Enforce original V1.0 engine constraints first
        if not super()._can_add_exam_to_schedule(course, exam_date, scheduled_exams, conflict_matrix):
            return False

        # 2.1 Min days between mandatory exams
        if self.constraints.min_days_mandatory_enabled:
            if not self._check_min_days_mandatory(course, exam_date):
                return False

        # 2.2 Min days between any two exams
        if self.constraints.min_days_any_enabled:
            if not self._check_min_days_any(exam_date):
                return False

        # 2.3 Max elective-elective conflicts
        if self.constraints.max_elective_conflicts_enabled:
            if not self._check_max_elective_conflicts(course):
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
    
    def _push_state(self, course: Course, exam_date: date, conflict_matrix: Set[Tuple[str, str]], scheduled_exams: List[ScheduledExam]) -> None:
        # 2.5 Track exams per day
        self._exams_per_day[exam_date] = self._exams_per_day.get(exam_date, 0) + 1
        
        # 2.2 Track all scheduled dates
        self._all_scheduled_dates.add(exam_date)
        
        # 2.1 & 2.4 Track mandatory dates per program
        if course.is_mandatory and course.program_id:
            if course.program_id not in self._mandatory_dates_by_program:
                self._mandatory_dates_by_program[course.program_id] = set()
            self._mandatory_dates_by_program[course.program_id].add(exam_date)
            
        # 2.3 Track elective conflicts dynamically
        if not course.is_mandatory:
            conflicts = 0
            for prev_exam in scheduled_exams:
                if not prev_exam.course.is_mandatory:
                    pair = (course.id, prev_exam.course.id)
                    rev_pair = (prev_exam.course.id, course.id)
                    if pair in conflict_matrix or rev_pair in conflict_matrix:
                        conflicts += 1
            self._elective_conflicts_count[course.id] = conflicts

    def _pop_state(self, course: Course, exam_date: date, conflict_matrix: Set[Tuple[str, str]], scheduled_exams: List[ScheduledExam]) -> None:
        # 2.5 Revert exams per day
        if exam_date in self._exams_per_day:
            self._exams_per_day[exam_date] -= 1
            
        # 2.2 Revert all scheduled dates
        self._all_scheduled_dates.remove(exam_date)
        
        # 2.1 & 2.4 Revert mandatory dates per program
        if course.is_mandatory and course.program_id and course.program_id in self._mandatory_dates_by_program:
            self._mandatory_dates_by_program[course.program_id].discard(exam_date)
            
        # 2.3 Revert elective conflicts tracking
        if course.id in self._elective_conflicts_count:
            del self._elective_conflicts_count[course.id]

    # --- O(1) High-Performance Checks Implementation ---

    def _check_min_days_mandatory(self, course: Course, exam_date: date) -> bool:
        if not course.is_mandatory or not course.program_id:
            return True
        program_dates = self._mandatory_dates_by_program.get(course.program_id, set())
        k = self.constraints.min_days_mandatory_k
        for existing_date in program_dates:
            if abs((exam_date - existing_date).days) < k:
                return False
        return True

    def _check_min_days_any(self, exam_date: date) -> bool:
        k = self.constraints.min_days_any_k
        for existing_date in self._all_scheduled_dates:
            if abs((exam_date - existing_date).days) < k:
                return False
        return True

    def _check_max_elective_conflicts(self, course: Course) -> bool:
        if course.is_mandatory:
            return True
        current_conflicts = self._elective_conflicts_count.get(course.id, 0)
        return current_conflicts <= self.constraints.max_elective_conflicts_k

    def _check_span_mandatory(self, course: Course, exam_date: date) -> bool:
        if not course.is_mandatory or not course.program_id:
            return True
        program_dates = self._mandatory_dates_by_program.get(course.program_id, set())
        if not program_dates:
            return True
            
        all_dates = list(program_dates) + [exam_date]
        current_span = (max(all_dates) - min(all_dates)).days + 1
        return current_span <= self.constraints.span_mandatory_k

    def _check_max_exams_per_day(self, exam_date: date) -> bool:
        current_count = self._exams_per_day.get(exam_date, 0)
        return current_count < self.constraints.max_exams_per_day_k