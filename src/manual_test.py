import os

from src.engine.exam_scheduler import ExamScheduler
from src.parsers.parser_factory import ParserFactory
from src.data_manager import DataManager


def run_manual_check():
    # Create the main objects used for the manual test.
    parser = ParserFactory.create_parser("txt")
    manager = DataManager(parser)
    scheduler = ExamScheduler()

    courses_path = "data/courses.txt"
    exam_periods_path = "data/exam_periods.txt"
    selected_programs_path = "data/selected_programs.txt"

    # Make sure all input files exist before running the test.
    for fp in [courses_path, exam_periods_path, selected_programs_path]:
        if not os.path.exists(fp):
            print(f"Error: File not found: {fp}")
            return

    try:
        # Load all input data through the unified data manager.
        manager.load_data(courses_path, exam_periods_path, selected_programs_path)

        print("\n--- Input Loading Test Results ---")
        print(f"Loaded {len(manager.get_courses())} courses.")
        print(f"Loaded {len(manager.get_exam_periods())} exam periods.")
        print(f"Loaded selected programs: {manager.get_selected_programs()}")

        # Print one sample course to verify parsing.
        if manager.get_courses():
            course = manager.get_courses()[0]
            print(f"Sample course: {course.course_id} - {course.course_name}")

        # Print one sample exam period to verify date parsing.
        if manager.get_exam_periods():
            exam_period = manager.get_exam_periods()[0]
            print(
                f"Sample exam period: {exam_period.semester} - {exam_period.moed} "
                f"({exam_period.start_date} to {exam_period.end_date})"
            )

        print("\n--- Relevant Exam Courses Test Results ---")

        # Keep only selected-program courses that have an exam.
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

        # Get all usable dates after excluded dates are removed.
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

        # Group courses by the matching semester and moed.
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

        print("\n--- Valid Exam Schedules Test Results ---")

        # Generate all valid schedules from the grouped data (Returns Generators!)
        schedules_by_group = scheduler.generate_all_valid_exam_schedules(grouped_exams)

        for key, schedules_generator in schedules_by_group.items():
            semester, moed = key
            print(f"\n{semester} - {moed}")

            try:
                first_schedule = next(schedules_generator)
                print("Sample schedule:")
                for scheduled_exam in first_schedule.exams:
                    print(
                        f"   {scheduled_exam.course.course_id} - "
                        f"{scheduled_exam.course.course_name} - "
                        f"{scheduled_exam.exam_date}"
                    )
                
            except StopIteration:
                print("No valid schedules found for this period.")

        print("\n--- Scheduling Engine Public Interface Test Results ---")

        # Test the public interface that connects all scheduling steps.
        generated_schedules = scheduler.generate_schedules(
            manager.get_courses(),
            manager.get_exam_periods(),
            manager.get_selected_programs()
        )

        for key, schedule_generator in generated_schedules.items():
            semester, moed = key
            
            count = sum(1 for _ in schedule_generator)
            print(f"{semester} - {moed}: {count} schedules generated.")

    except Exception as e:
        print(f"Error during manual check: {e}")


if __name__ == "__main__":
    run_manual_check()