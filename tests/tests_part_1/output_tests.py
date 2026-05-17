import pytest
from datetime import date

#importing the relevant classes for testing
from src.output.file_output_writer import FileOutputWriter
from src.models.schedule import Schedule, ScheduledExam
from src.models.course import Course, ProgramCourseInfo

# =========================================================================
# Function Fixture (Fixture) for Creating Sample Courses for Testing
# =========================================================================
@pytest.fixture
def sample_courses():
    info_fall = [ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")]
    info_spri = [ProgramCourseInfo(program_id="83108", year=1, semester="SPRI", requirement="Obligatory")]
    
    c1 = Course("83102", "Physics 1", "Prof. O. Some", "Exam", info_fall)
    c2 = Course("83112", "Calculus 1", "Prof. Erez Scheiner", "Exam", info_fall)
    c3 = Course("83533", "Software Project", "Dr. Terry Bell", "Exam", info_spri)
    return c1, c2, c3

# =========================================================================
# 1. tests for the happy path - data integrity, sorting, and period separation
# =========================================================================

def test_write_schedules_happy_path(tmp_path, sample_courses):
    """ verifies correct writing of the output: chronological sorting, data integrity, and period separation """
    c1, c2, c3 = sample_courses
    writer = FileOutputWriter()
    output_file = tmp_path / "output" / "schedules.txt"

    # building sample scheduled exams with specific dates to test sorting and formatting
    exam_physics = ScheduledExam(course=c1, exam_date=date(2026, 2, 15))
    exam_calculus = ScheduledExam(course=c2, exam_date=date(2026, 2, 1))
    exam_project = ScheduledExam(course=c3, exam_date=date(2026, 7, 5))

    # creating schedules for two different periods to test separation and labeling
    fall_schedule = Schedule(exams=[exam_physics, exam_calculus])
    spri_schedule = Schedule(exams=[exam_project])

    # preparing the dictionary exactly as the Writer expects to receive
    schedules_generators = {
        ("FALL", "Aleph"): iter([fall_schedule]),
        ("SPRI", "Aleph"): iter([spri_schedule])
    }

    # starting the writing process - this should create the output file with the schedules formatted as specified
    writer.write_schedules(schedules_generators, str(output_file))

    # reading the output file to verify its content
    assert output_file.exists()
    file_content = output_file.read_text(encoding="utf-8")

    # checking that the main header and period labels are correctly included in the output
    assert "=== Complete Academic Year Schedules ===" in file_content
    assert "--- FULL SYSTEM OPTION 1 ---" in file_content

    # checking that the course details are correctly formatted and included in the output
    assert "Date: 01-02-2026 | Course: 83112 - Calculus 1 | Instructor: Prof. Erez Scheiner" in file_content

    # checking that the exams are sorted chronologically by date within the period
    idx_calculus = file_content.find("Calculus 1")
    idx_physics = file_content.find("Physics 1")
    assert idx_calculus < idx_physics, "Exams must be sorted chronologically by date"

    #checking that the two periods are correctly separated and labeled in the output
    assert "[FALL - Aleph]" in file_content
    assert "[SPRI - Aleph]" in file_content


# =========================================================================
# 2. tests for edge cases - no valid solutions available in the system
# =========================================================================

def test_write_schedules_no_combinations(tmp_path):
    """ verifies appropriate message output when generators are empty and no valid combinations exist """
    writer = FileOutputWriter()
    output_file = tmp_path / "schedules_empty.txt"

    # dictionary with empty generators to simulate no valid combinations scenario
    schedules_generators = {
        ("FALL", "Aleph"): iter([])
    }

    writer.write_schedules(schedules_generators, str(output_file))
    file_content = output_file.read_text(encoding="utf-8")

    assert "No valid full-year combinations could be formed." in file_content


# =========================================================================
# 3. tests for edge cases - dynamic execution timeout protection
# =========================================================================

def test_write_schedules_timeout_protection(tmp_path, sample_courses):
    """ verifies that the timeout protection mechanism works and prints a safe completion message if execution time exceeds the limit """
    c1, _, _ = sample_courses
    
    # setting a maximum time of 0 seconds to force an immediate stop in the loop
    writer = FileOutputWriter(max_time_seconds=0)
    output_file = tmp_path / "schedules_timeout.txt"

    # creating a large number of schedules to ensure that the loop would exceed the time limit if it were to run through them all
    exam = ScheduledExam(course=c1, exam_date=date(2026, 2, 1))
    schedule = Schedule(exams=[exam])
    
    # creating a large list of schedules to simulate a long-running process
    many_schedules = [schedule for _ in range(50)]

    schedules_generators = {
        ("FALL", "Aleph"): iter(many_schedules),
        ("FALL", "Bet"): iter(many_schedules)
    }

    writer.write_schedules(schedules_generators, str(output_file))
    file_content = output_file.read_text(encoding="utf-8")

    # verifies that the loop was stopped and the warning message was written to the file
    assert "Execution stopped dynamically to guarantee meeting performance requirements." in file_content


def test_write_schedules_utf8_encoding_support(tmp_path):
    """
    verifies that the file output writer supports UTF-8 encoding correctly  .
    """
    from src.models.course import Course
    from src.models.schedule import Schedule, ScheduledExam
    
    writer = FileOutputWriter()
    output_path = tmp_path / "utf8_test_output.txt"

    # creating a course with Hebrew characters to test UTF-8 encoding support in the output file
    hebrew_course = Course(
        course_id="83111",
        course_name="מבוא למדעי המחשב א'",
        instructor="ד''ר אבנר לוי",
        evaluation_method="Exam",
        program_info=[]
    )

    # building the exam array structure for the writer
    scheduled_exam = ScheduledExam(course=hebrew_course, exam_date=date(2026, 2, 1))
    single_schedule = Schedule(exams=[scheduled_exam])
    
    # defining the structure that the system expects in the dictionary (semester, session) -> generator of schedules
    key = ("FALL", "Aleph")
    generated_schedules = {key: iter([single_schedule])}

    # running the output writing step
    writer.write_schedules(generated_schedules, str(output_path))

    # verifying that the file was created
    assert output_path.exists()

    # reading the file with UTF-8 encoding to ensure no corruption
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()

    # checking that the Hebrew characters are correctly preserved in the output file, indicating proper UTF-8 encoding support
    assert "מבוא למדעי המחשב א'" in content, "Hebrew course name was corrupted in output file!"
    assert "ד''ר אבנר לוי" in content, "Hebrew instructor name was corrupted in output file!"
    