import os
import time
from src.parsers.text_file_parser import TextFileParser
from src.data_manager import DataManager
from src.engine.exam_scheduler import ExamScheduler
from src.output.file_output_writer import FileOutputWriter

def main():
    print("Planix Exam Scheduler - Initializing...")
    start_time = time.time()

    # Initialize core components
    parser = TextFileParser()
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

        # Generate schedules using the generator-based engine
        print("Generating schedules (using lazy evaluation)...")
        generated_schedules = scheduler.generate_schedules(
            manager.get_courses(),
            manager.get_exam_periods(),
            manager.get_selected_programs()
        )

        # Stream results directly to the output file
        print("Writing results...")
        writer.write_schedules(generated_schedules, output_path)

        # Performance summary
        duration = time.time() - start_time
        print(f"\nExecution successful in {duration:.2f} seconds.")
        print(f"Result file: {output_path}")

    except Exception as e:
        print(f"\nExecution failed: {e}")

if __name__ == "__main__":
    main()