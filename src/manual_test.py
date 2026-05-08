import os

from src.parsers.text_file_parser import TextFileParser
from src.data_manager import DataManager

def run_manual_check():
    parser = TextFileParser()
    manager = DataManager(parser)

    courses_path = 'data/courses.txt'
    exam_periods_path = 'data/exam_periods.txt'
    selected_programs_path = 'data/selected_programs.txt'

    for fp in [courses_path, exam_periods_path, selected_programs_path]:
        if not os.path.exists(fp):
            print(f"Error: File not found: {fp}")
            return

    try:
        manager.load_data(courses_path, exam_periods_path, selected_programs_path)
        print("\n--- Test Results ---")
        print(f"Loaded {len(manager.get_courses())} courses.")
        print(f"Loaded {len(manager.get_exam_periods())} exam periods.")
        print(f"Loaded selected programs: {manager.get_selected_programs()}")

        if manager.get_courses():
            course = manager.get_courses()[0]
            print(f"   sample course: {course.course_id} - {course.course_name}")
        
        if manager.get_exam_periods():
            exam_period = manager.get_exam_periods()[0]
            print(f"   sample exam period: {exam_period.semester} - {exam_period.moed} ({exam_period.start_date} to {exam_period.end_date})")

    except Exception as e:
        print(f"Error during manual check: {e}")

if __name__ == "__main__":
    run_manual_check()
