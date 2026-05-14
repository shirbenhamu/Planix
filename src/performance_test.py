import time
from datetime import date
from src.models.course import Course, ProgramCourseInfo
from src.models.exam_period import ExamPeriod
from src.engine.exam_scheduler import ExamScheduler
from src.output.file_output_writer import FileOutputWriter

def run_stress_and_limit_test():
    print("--- Starting ULTIMATE Performance & Multi-Period Test ---")
    scheduler = ExamScheduler()
    
    # Using the default limit (2,000,000) from FileOutputWriter
    writer = FileOutputWriter()

    courses = []
    
    # 1. FALL SEMESTER - 6 Courses (Will generate > 2M options in Aleph)
    for i in range(6):
        courses.append(Course(f"100{i}", f"Fall heavy {i}", "Dr. Autumn", "Exam", 
                             [ProgramCourseInfo("83108", 1, "FALL", "Obligatory")]))
        
    # 2. SPRING SEMESTER - 5 Courses
    for i in range(5):
        courses.append(Course(f"200{i}", f"Spring heavy {i}", "Prof. Bloom", "Exam", 
                             [ProgramCourseInfo("83108", 1, "SPRI", "Obligatory")]))

    # 3. SUMMER SEMESTER - 4 Courses
    for i in range(4):
        courses.append(Course(f"300{i}", f"Summer heavy {i}", "Dr. Sun", "Exam", 
                             [ProgramCourseInfo("83108", 1, "SUMM", "Obligatory")]))

    # Define a complex set of exam periods
    exam_periods = [
        # Fall periods
        ExamPeriod("FALL", "Aleph", date(2026, 1, 1), date(2026, 1, 20), []), # 20 days
        ExamPeriod("FALL", "Bet", date(2026, 3, 1), date(2026, 3, 10), []),   # 10 days
        
        # Spring periods
        ExamPeriod("SPRI", "Aleph", date(2026, 6, 1), date(2026, 6, 20), []), # 20 days
        ExamPeriod("SPRI", "Bet", date(2026, 8, 1), date(2026, 8, 10), []),   # 10 days
        
        # Summer period
        ExamPeriod("SUMM", "Aleph", date(2026, 9, 15), date(2026, 9, 30), []) # 15 days
    ]

    print("Stress test: Generating millions of schedules across 3 semesters...")
    start_time = time.time()

    # Generate schedules (grouped internally)
    generated_schedules = scheduler.generate_schedules(courses, exam_periods, ["83108"])

    # Write results using the Pipe formatting and internal sorting
    output_path = "output_results/performance_output.txt"
    writer.write_schedules(generated_schedules, output_path)

    elapsed_time = time.time() - start_time
    print(f"\n✅ Ultimate Test Finished in {elapsed_time:.2f} seconds.")
    print(f"Results with headers and pipes saved to: {output_path}")

if __name__ == "__main__":
    run_stress_and_limit_test()