import os

from src.engine.exam_scheduler import ExamScheduler
from src.parsers.text_file_parser import TextFileParser
from src.data_manager import DataManager


def run_manual_check():
    parser = TextFileParser()
    manager = DataManager(parser)
    scheduler = ExamScheduler()

    courses_path = "data/courses.txt"
    exam_periods_path = "data/exam_periods.txt"
    selected_programs_path = "data/selected_programs.txt"

    for fp in [courses_path, exam_periods_path, selected_programs_path]:
        if not os.path.exists(fp):
            print(f"Error: File not found: {fp}")
            return

    try:
        manager.load_data(courses_path, exam_periods_path, selected_programs_path)

        print("\n--- Input Loading Test Results ---")
        print(f"Loaded {len(manager.get_courses())} courses.")
        print(f"Loaded {len(manager.get_exam_periods())} exam periods.")
        print(f"Loaded selected programs: {manager.get_selected_programs()}")

        if manager.get_courses():
            course = manager.get_courses()[0]
            print(f"Sample course: {course.course_id} - {course.course_name}")

        if manager.get_exam_periods():
            exam_period = manager.get_exam_periods()[0]
            print(
                f"Sample exam period: {exam_period.semester} - {exam_period.moed} "
                f"({exam_period.start_date} to {exam_period.end_date})"
            )

        print("\n--- Relevant Exam Courses Test Results ---")

        relevant_courses = scheduler.filter_relevant_exam_courses(
            manager.get_courses(),
            manager.get_selected_programs()
        )

        print(f"Loaded {len(relevant_courses)} relevant exam courses.")

        for course in relevant_courses:
            print(
                f"{course.course_id} - {course.course_name} - "
                f"{course.instructor} - {course.evaluation_method}"
            )

            for info in course.program_info:
                print(
                    f"   Program: {info.program_id}, "
                    f"Year: {info.year}, "
                    f"Semester: {info.semester}, "
                    f"Requirement: {info.requirement}"
                )

        print("\n--- Available Exam Dates Test Results ---")

        available_dates_by_period = scheduler.generate_available_exam_dates(
            manager.get_exam_periods()
        )

        for key, available_dates in available_dates_by_period.items():
            semester, moed = key

            print(f"\n{semester} - {moed}")
            print(f"Available dates: {len(available_dates)}")

            if available_dates:
                print(f"First date: {available_dates[0]}")
                print(f"Last date: {available_dates[-1]}")

        print("\n--- Grouped Exams Test Results ---")

        grouped_exams = scheduler.group_exams_by_semester_and_moed(
            relevant_courses,
            manager.get_exam_periods()
        )

        for key, group in grouped_exams.items():
            semester, moed = key

            print(f"\n{semester} - {moed}")
            print(f"Available dates: {len(group['available_dates'])}")
            print(f"Courses: {len(group['courses'])}")

            for course in group["courses"]:
                print(f"   {course.course_id} - {course.course_name}")

    except Exception as e:
        print(f"Error during manual check: {e}")


if __name__ == "__main__":
    run_manual_check()