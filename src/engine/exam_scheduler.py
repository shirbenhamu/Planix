from typing import Dict, List, Tuple

from src.models.course import Course
from src.models.exam_period import ExamPeriod


class ExamScheduler:
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

    def group_exams_by_semester_and_moed(
        self,
        courses: List[Course],
        exam_periods: List[ExamPeriod]
    ) -> Dict[Tuple[str, str], Dict[str, object]]:
        grouped_exams = {}

        for exam_period in exam_periods:
            key = (exam_period.semester, exam_period.moed)

            grouped_exams[key] = {
                "exam_period": exam_period,
                "available_dates": exam_period.get_available_dates(),
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