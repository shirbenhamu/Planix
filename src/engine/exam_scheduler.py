import heapq
import itertools
import time
from typing import Dict, List, Optional, Tuple, Iterator, Set

from src.MVP.models.course import Course
from src.MVP.models.exam_period import ExamPeriod
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.engine.i_scheduling_engine import ISchedulingEngine
from src.metrics.metrics_calculator import MetricsCalculator


class _BestHeapItem:
    """Wrapper that turns heapq's min-heap into a bounded max-heap on the sort
    key: the item with the LARGEST (worst) key compares as the smallest, so it
    sits at heap[0] and is the one evicted when a better schedule arrives.
    'Better' = smaller key (matching ScheduleCollectionManager's convention)."""

    __slots__ = ("key", "schedule", "metrics")

    def __init__(self, key, schedule, metrics):
        self.key = key
        self.schedule = schedule
        self.metrics = metrics

    def __lt__(self, other):
        return self.key > other.key

class ExamScheduler(ISchedulingEngine):
    def generate_schedules(
        self,
        courses: List[Course],
        exam_periods: List[ExamPeriod],
        selected_programs: List[str]
    ) -> Dict[Tuple[str, str], Iterator[Schedule]]:
        relevant_courses = self.filter_relevant_exam_courses(courses, selected_programs)
        grouped_exams = self.group_exams_by_semester_and_moed(relevant_courses, exam_periods)
        return self.generate_all_valid_exam_schedules(grouped_exams)

    def count_total_schedules(
        self,
        courses: List[Course],
        exam_periods: List[ExamPeriod],
        selected_programs: List[str],
        max_per_period: Optional[int] = None,
    ) -> int:
        """Count the total number of valid full-year schedules WITHOUT building
        them all.

        A full-year schedule pairs one valid per-period schedule from every
        period (an ``itertools.product`` of the per-period generators), so the
        total equals the PRODUCT of the per-period valid counts. Counting each
        period independently is the *sum* of the per-period sizes — dramatically
        cheaper than enumerating the full cartesian product (e.g. 2000 + 2000
        instead of 2000 * 2000). Passing ``max_per_period`` caps each period the
        same way generation does; ``None`` counts the true, uncapped total.
        """
        generators = self.generate_schedules(courses, exam_periods, selected_programs)
        total = 1
        for generator in generators.values():
            if max_per_period is not None:
                generator = itertools.islice(generator, max_per_period)
            period_count = sum(1 for _ in generator)
            if period_count == 0:
                return 0
            total *= period_count
        return total

    @staticmethod
    def _deep_search_sort_key(metrics: Tuple[float, ...], sort_spec):
        # 'better' = smaller key. Descending metrics are negated so a single
        # ascending tuple comparison yields the requested per-key direction —
        # identical to ScheduleCollectionManager._build_sort_key.
        return tuple(
            metrics[index] if ascending else -metrics[index]
            for index, ascending in sort_spec
        )

    def find_best_schedules(
        self,
        courses: List[Course],
        exam_periods: List[ExamPeriod],
        selected_programs: List[str],
        sort_spec,
        top_n: int,
        max_scan: Optional[int] = None,
        max_seconds: Optional[float] = None,
        progress_callback=None,
        cancel_callback=None,
        progress_every: int = 50000,
    ):
        """Deep search: stream full-year combinations and keep ONLY the top_n
        best by the active sort, never holding more than top_n in memory.

        The full solution space can be astronomically large, so the scan is
        bounded by a TIME budget (``max_seconds``) and/or a count cap
        (``max_scan``) — whichever is hit first, or the space being exhausted.
        This both finishes and lets the caller drive a real 0->100% progress
        bar. ``sort_spec`` is a list of ``(metric_index, ascending)`` pairs
        ('better' = smaller key). ``cancel_callback`` is polled periodically; if
        it returns True the scan stops early and returns the best found so far.

        Returns ``(best, scanned)`` where ``best`` is a list of
        ``(Schedule, metrics_tuple)`` pairs ordered best-first. Metrics are
        carried through so the writer need not recompute them for the kept set.
        """
        generators = self.generate_schedules(courses, exam_periods, selected_programs)
        period_keys = sorted(generators.keys())
        # Materialize each period's schedules (bounded by the per-period count,
        # which is what made counting feasible); the explosion is only in their
        # product, which we stream and never materialize.
        pools = [list(generators[key]) for key in period_keys]

        calculator = MetricsCalculator()
        # The sort only needs these metric indices — computing just them per
        # scanned schedule is far cheaper than all five. The full five are
        # computed ONLY for the rare schedules that actually enter the heap.
        needed = sorted({index for index, _ascending in sort_spec})
        heap: List[_BestHeapItem] = []
        scanned = 0
        start_time = time.time()

        for combo in itertools.product(*pools):
            if max_scan is not None and scanned >= max_scan:
                break
            exams = [exam for sub_schedule in combo for exam in sub_schedule.exams]
            schedule = Schedule(exams=exams)
            partial = calculator.calculate_indices(schedule, needed)
            key = tuple(
                partial[index] if ascending else -partial[index]
                for index, ascending in sort_spec
            )
            scanned += 1

            if len(heap) < top_n:
                metrics = calculator.compute(schedule).as_tuple()
                heapq.heappush(heap, _BestHeapItem(key, schedule, metrics))
            elif key < heap[0].key:  # better than the current worst kept
                metrics = calculator.compute(schedule).as_tuple()
                heapq.heapreplace(heap, _BestHeapItem(key, schedule, metrics))

            # Time / cancel checks are batched to keep the hot loop cheap.
            if scanned % progress_every == 0:
                if progress_callback is not None:
                    progress_callback(scanned)
                if cancel_callback is not None and cancel_callback():
                    break
                if max_seconds is not None and (time.time() - start_time) >= max_seconds:
                    break

        if progress_callback is not None:
            progress_callback(scanned)

        best = sorted(heap, key=lambda item: item.key)
        return [(item.schedule, item.metrics) for item in best], scanned

    def filter_relevant_exam_courses(
        self,
        courses: List[Course],
        selected_programs: List[str]
    ) -> List[Course]:
        relevant_courses = []
        for course in courses:
            if course.evaluation_method != "Exam":
                continue

            relevant_program_info = []
            for info in course.program_info:
                if info.program_id in selected_programs:
                    relevant_program_info.append(info)

            if relevant_program_info:
                relevant_courses.append(
                    Course(
                        course_id=course.course_id,
                        course_name=course.course_name,
                        instructor=course.instructor,
                        evaluation_method=course.evaluation_method,
                        program_info=relevant_program_info
                    )
                )

        if not relevant_courses:
            raise ValueError("No relevant exam courses found for the selected programs.")
        return relevant_courses

    def generate_available_exam_dates(
        self,
        exam_periods: List[ExamPeriod]
    ) -> Dict[Tuple[str, str], List[object]]:
        available_dates_by_period = {}
        for exam_period in exam_periods:
            key = (exam_period.semester, exam_period.moed)
            available_dates = exam_period.get_available_dates()
            if available_dates:
                available_dates_by_period[key] = available_dates

        if not available_dates_by_period:
            raise ValueError("No available exam dates found for scheduling.")
        return available_dates_by_period

    def group_exams_by_semester_and_moed(
        self,
        courses: List[Course],
        exam_periods: List[ExamPeriod]
    ) -> Dict[Tuple[str, str], Dict[str, object]]:
        available_dates_by_period = self.generate_available_exam_dates(exam_periods)
        grouped_exams = {}

        for exam_period in exam_periods:
            key = (exam_period.semester, exam_period.moed)
            if key not in available_dates_by_period:
                continue

            grouped_exams[key] = {
                "exam_period": exam_period,
                "available_dates": available_dates_by_period[key],
                "courses": []
            }

        for course in courses:
            course_semesters = set(info.semester for info in course.program_info)
            for semester in course_semesters:
                for key, group in grouped_exams.items():
                    period_semester, _ = key
                    if period_semester == semester:
                        group["courses"].append(course)

        grouped_exams = {k: v for k, v in grouped_exams.items() if v["courses"]}
        if not grouped_exams:
            raise ValueError("No matching exam periods found for the relevant exam courses.")
        return grouped_exams

    def has_critical_exam_conflict(
        self,
        first_course: Course,
        second_course: Course
    ) -> bool:
        for first_info in first_course.program_info:
            for second_info in second_course.program_info:
                same_program = first_info.program_id == second_info.program_id
                same_year = first_info.year == second_info.year

                both_elective = (
                    first_info.requirement == "Elective"
                    and second_info.requirement == "Elective"
                )

                if same_program and same_year and not both_elective:
                    return True
        return False

    def build_conflict_matrix(self, courses: List[Course]) -> Set[Tuple[str, str]]:
        conflicts = set()
        num_courses = len(courses)
        for i in range(num_courses):
            for j in range(i + 1, num_courses):
                if self.has_critical_exam_conflict(courses[i], courses[j]):
                    conflicts.add((courses[i].course_id, courses[j].course_id))
                    conflicts.add((courses[j].course_id, courses[i].course_id))
        return conflicts

    def generate_all_valid_exam_schedules(
        self,
        grouped_exams: Dict[Tuple[str, str], Dict[str, object]]
    ) -> Dict[Tuple[str, str], Iterator[Schedule]]:
        schedules_generators_by_group = {}

        for key, group in grouped_exams.items():
            courses = group["courses"]
            available_dates = sorted(group["available_dates"])
            
            schedules_generators_by_group[key] = self.generate_valid_schedules_for_group(
                courses,
                available_dates
            )

        return schedules_generators_by_group

    def generate_valid_schedules_for_group(
        self,
        courses: List[Course],
        available_dates: List[object]
    ) -> Iterator[Schedule]:
        if not courses:
            raise ValueError("No courses provided for schedule generation.")
        if not available_dates:
            raise ValueError("No available dates provided for schedule generation.")

        conflict_matrix = self.build_conflict_matrix(courses)

        conflict_counts = {c.course_id: 0 for c in courses}
        for c1, c2 in conflict_matrix:
            conflict_counts[c1] += 1
            
        sorted_courses = sorted(
            courses, 
            key=lambda c: conflict_counts[c.course_id], 
            reverse=True
        )

        current_scheduled_exams = []

        yield from self._generate_schedule_combinations(
            sorted_courses,
            available_dates,
            0,
            current_scheduled_exams,
            conflict_matrix
        )

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
            if self._can_add_exam_to_schedule(
                current_course,
                exam_date,
                current_scheduled_exams,
                conflict_matrix
            ):
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

                current_scheduled_exams.pop()

    def _can_add_exam_to_schedule(
        self,
        course: Course,
        exam_date,
        scheduled_exams: List[ScheduledExam],
        conflict_matrix: Set[Tuple[str, str]]
    ) -> bool:
        for scheduled_exam in scheduled_exams:
            if scheduled_exam.exam_date == exam_date:
                if (course.course_id, scheduled_exam.course.course_id) in conflict_matrix:
                    return False
        return True