import os
import time
from src.parsers.text_file_parser import TextFileParser
from src.data_manager import DataManager
from src.engine.exam_scheduler import ExamScheduler
from src.output.file_output_writer import FileOutputWriter
from src.parsers.parser_factory import ParserFactory
from MVP.app_window import AppWindow


def main():
    print("Planix Exam Scheduler - Initializing...")
    start_time = time.time()

    # Initialize core components
    parser = ParserFactory.create_parser("txt")
    manager = DataManager(parser)
    scheduler = ExamScheduler()
    writer = FileOutputWriter()

    # Define input and output paths
    courses_path = "data/courses.txt"
    exam_periods_path = "data/exam_periods.txt"
    selected_programs_path = "data/selected_programs.txt"
    output_path = "output_results/final_schedules.txt"

    # Verify input files exist
    for path in [courses_path, exam_periods_path, selected_programs_path]:
        if not os.path.exists(path):
            print(f"Critical Error: Missing file {path}")
            return

    try:
        # Load and parse input data
        print("Loading data...")
        manager.load_data(courses_path, exam_periods_path, selected_programs_path)

        # Launch the UI and leave engine execution for the future presenter layer.
        print("Launching UI...")
        app = AppWindow()
        app.mainloop()

        # Performance summary
        duration = time.time() - start_time
        print(f"\nUI session ended after {duration:.2f} seconds.")

    except Exception as e:
        print(f"\nExecution failed: {e}")

if __name__ == "__main__":
    main()