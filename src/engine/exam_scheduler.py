from typing import Dict, List, Tuple

from src.models.course import Course
from src.models.exam_period import ExamPeriod
from src.models.schedule import Schedule, ScheduledExam


class ExamScheduler:
    def generate_schedules(
        self,
        courses: List[Course],
        exam_periods: List[ExamPeriod],
        selected_programs: List[str]
    ) -> Dict[Tuple[str, str], List[Schedule]]:
        relevant_courses = self.filter_relevant_exam_courses(
            courses,
            selected_programs
        )

        grouped_exams = self.group_exams_by_semester_and_moed(
            relevant_courses,
            exam_periods
        )

        return self.generate_all_valid_exam_schedules(grouped_exams)

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
            course_semesters = set()

            for info in course.program_info:
                course_semesters.add(info.semester)

            for semester in course_semesters:
                for key, group in grouped_exams.items():
                    period_semester, _ = key

                    if period_semester == semester:
                        group["courses"].append(course)

        grouped_exams = {
            key: group
            for key, group in grouped_exams.items()
            if group["courses"]
        }

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

    def has_same_date_critical_conflict(
        self,
        first_course: Course,
        first_date,
        second_course: Course,
        second_date
    ) -> bool:
        if first_date != second_date:
            return False

        return self.has_critical_exam_conflict(first_course, second_course)

    def generate_valid_schedules_for_group(
        self,
        courses: List[Course],
        available_dates: List[object]
    ) -> List[Schedule]:
        if not courses:
            raise ValueError("No courses provided for schedule generation.")

        if not available_dates:
            raise ValueError("No available dates provided for schedule generation.")

        valid_schedules = []
        current_scheduled_exams = []

        self._generate_schedule_combinations(
            courses,
            available_dates,
            0,
            current_scheduled_exams,
            valid_schedules
        )

        if not valid_schedules:
            raise ValueError("No valid exam schedules found.")

        return valid_schedules

    def _generate_schedule_combinations(
        self,
        courses: List[Course],
        available_dates: List[object],
        course_index: int,
        current_scheduled_exams: List[ScheduledExam],
        valid_schedules: List[Schedule]
    ) -> None:
        if course_index == len(courses):
            valid_schedules.append(
                Schedule(exams=current_scheduled_exams.copy())
            )
            return

        current_course = courses[course_index]

        for exam_date in available_dates:
            if self._can_add_exam_to_schedule(
                current_course,
                exam_date,
                current_scheduled_exams
            ):
                current_scheduled_exams.append(
                    ScheduledExam(
                        course=current_course,
                        exam_date=exam_date
                    )
                )

                self._generate_schedule_combinations(
                    courses,
                    available_dates,
                    course_index + 1,
                    current_scheduled_exams,
                    valid_schedules
                )

                current_scheduled_exams.pop()

    def _can_add_exam_to_schedule(
        self,
        course: Course,
        exam_date,
        scheduled_exams: List[ScheduledExam]
    ) -> bool:
        for scheduled_exam in scheduled_exams:
            if self.has_same_date_critical_conflict(
                course,
                exam_date,
                scheduled_exam.course,
                scheduled_exam.exam_date
            ):
                return False

        return True

    def generate_all_valid_exam_schedules(
        self,
        grouped_exams: Dict[Tuple[str, str], Dict[str, object]]
    ) -> Dict[Tuple[str, str], List[Schedule]]:
        schedules_by_group = {}

        for key, group in grouped_exams.items():
            courses = group["courses"]
            available_dates = group["available_dates"]

            schedules_by_group[key] = self.generate_valid_schedules_for_group(
                courses,
                available_dates
            )

        if not schedules_by_group:
            raise ValueError("No valid schedules were generated.")

        return schedules_by_group