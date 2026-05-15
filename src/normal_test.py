import time
from datetime import date
from src.models.course import Course, ProgramCourseInfo
from src.models.exam_period import ExamPeriod
from src.engine.exam_scheduler import ExamScheduler
from src.output.file_output_writer import FileOutputWriter

def run_normal_test():
    print("--- Starting Normal Academic Year Test ---")
    scheduler = ExamScheduler()
    writer = FileOutputWriter()

    courses = [
        # Fall Courses
        Course("101", "Linear Algebra", "Dr. A", "Exam", [ProgramCourseInfo("12345", 1, "FALL", "Obligatory")]),
        Course("102", "Physics 1", "Dr. B", "Exam", [ProgramCourseInfo("12345", 1, "FALL", "Obligatory")]),
        
        # Spring Courses
        Course("201", "Calculus 2", "Dr. C", "Exam", [ProgramCourseInfo("12345", 1, "SPRI", "Obligatory")]),
        Course("202", "Data Structures", "Dr. D", "Exam", [ProgramCourseInfo("12345", 1, "SPRI", "Obligatory")])
    ]

    exam_periods = [
        ExamPeriod("FALL", "Aleph", date(2026, 1, 1), date(2026, 1, 4), []), 
        ExamPeriod("FALL", "Bet", date(2026, 2, 1), date(2026, 2, 4), []),   
        ExamPeriod("SPRI", "Aleph", date(2026, 6, 1), date(2026, 6, 4), []), 
        ExamPeriod("SPRI", "Bet", date(2026, 7, 1), date(2026, 7, 4), [])    
    ]

    print("Generating normal-sized schedules...")
    start_time = time.time()

    generated_schedules = scheduler.generate_schedules(courses, exam_periods, ["12345"])
    
    output_path = "output_results/normal_output.txt"
    writer.write_schedules(generated_schedules, output_path)

    elapsed_time = time.time() - start_time
    print(f"\n Normal Test Finished in {elapsed_time:.2f} seconds.")
    print(f"Check the file: {output_path}")

if __name__ == "__main__":
    run_normal_test()