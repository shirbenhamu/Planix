import pytest
import time
import os
from datetime import date

# importing the necessary modules and classes from the project to perform the performance test
#  on the exam scheduling system, including the scheduler, output writer, and data models
#  for courses and exam periods.
from src.engine.exam_scheduler import ExamScheduler
from src.output.file_output_writer import FileOutputWriter
from src.models.course import Course, ProgramCourseInfo
from src.models.exam_period import ExamPeriod

MAX_ALLOWED_DURATION_SECONDS = 30.5  #    

# =========================================================================
# 1. performance and stress tests
# =========================================================================

def test_system_performance_under_stress(tmp_path):
    """
    tests the performance of the engine and the writer together under extreme load (Stress Test).
    checking if the system can handle a large number of courses and exam periods, 
    and if the total execution time (including writing to file) is under 30 seconds.
    """
    scheduler = ExamScheduler()
    writer = FileOutputWriter(max_time_seconds=29)  # setting a slightly lower time limit for the writer to ensure the entire process stays within the overall limit of 30 seconds.  
    
    #tempory output path for performance test results
    output_path = tmp_path / "output_results" / "performance_output.txt"

    courses = []
    
    # fall semester - 6 obligatory courses
    for i in range(6):
        courses.append(Course(
            course_id=f"100{i}", 
            course_name=f"Fall heavy {i}", 
            instructor="Dr. Autumn", 
            evaluation_method="Exam", 
            program_info=[ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")]
        ))
        
    # spring semester - 5 obligatory courses
    for i in range(5):
        courses.append(Course(
            course_id=f"200{i}", 
            course_name=f"Spring heavy {i}", 
            instructor="Prof. Bloom", 
            evaluation_method="Exam", 
            program_info=[ProgramCourseInfo(program_id="83108", year=1, semester="SPRI", requirement="Obligatory")]
        ))

    # summer semester - 4 obligatory courses
    for i in range(4):
        courses.append(Course(
            course_id=f"300{i}", 
            course_name=f"Summer heavy {i}", 
            instructor="Dr. Sun", 
            evaluation_method="Exam", 
            program_info=[ProgramCourseInfo(program_id="83108", year=1, semester="SUMM", requirement="Obligatory")]
        ))

    # array of 5 exam periods, covering all semesters, with different date ranges to create a complex scheduling scenario
    exam_periods = [
        ExamPeriod("FALL", "Aleph", date(2026, 1, 1), date(2026, 1, 20), []), 
        ExamPeriod("FALL", "Bet", date(2026, 3, 1), date(2026, 3, 10), []),   
        ExamPeriod("SPRI", "Aleph", date(2026, 6, 1), date(2026, 6, 20), []), 
        ExamPeriod("SPRI", "Bet", date(2026, 8, 1), date(2026, 8, 10), []),  
        ExamPeriod("SUMM", "Aleph", date(2026, 9, 15), date(2026, 9, 30), []) 
    ]

    # counting the time from the start of the scheduling process to the end of writing the output file, to ensure the entire process is efficient and meets the performance criteria.
    start_time = time.perf_counter()

    # algorithm execution - generating schedules for the given courses and exam periods, specifically for the program "83108" which has a heavy load of courses across all semesters.
    generated_schedules = scheduler.generate_schedules(courses, exam_periods, ["83108"])

    # 2. runnung millions of iterations to simulate a heavy load and ensure the system's stability and performance under stress.
    writer.write_schedules(generated_schedules, str(output_path))

    # calculating the total elapsed time for the entire process, from scheduling to writing the output file, to verify that it meets the performance requirements.
    elapsed_time = time.perf_counter() - start_time

    # validating that the total execution time is within the defined limit, ensuring that the system can handle the stress test efficiently without significant performance degradation.
    assert elapsed_time < MAX_ALLOWED_DURATION_SECONDS, \
        f"Performance test failed! Total duration was {elapsed_time:.2f} seconds, which exceeds the 30s limit."

    # validating that the output file was created and contains data
    assert output_path.exists()
    assert os.path.getsize(output_path) > 0