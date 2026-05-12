from typing import List

from src.models.course import Course


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