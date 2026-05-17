import pytest
from datetime import date

#importing the parser and the relevant models to be used in the tests
from src.parsers.text_file_parser import TextFileParser
from src.models.course import Course
from src.models.exam_period import ExamPeriod

# =========================================================================
# 1. tests for parse_selected_programs
# =========================================================================

def test_parse_selected_programs_happy_path(tmp_path):
    """verifies that parsing a valid program file works and trims leading/trailing whitespace"""
    parser = TextFileParser()
    p = tmp_path / "selected_programs.txt"
    p.write_text("83101,  83102 , 83108", encoding="utf-8")

    programs = parser.parse_selected_programs(str(p))
    assert programs == ["83101", "83102", "83108"]


def test_parse_selected_programs_too_many_programs(tmp_path):
    """verifies that an error is raised if more than 5 programs are selected (requirement 1.1)"""
    parser = TextFileParser()
    p = tmp_path / "selected_programs.txt"
    p.write_text("83101,83102,83104,83107,83108,83109", encoding="utf-8")

    with pytest.raises(ValueError, match="More than 5 programs selected"):
        parser.parse_selected_programs(str(p))


def test_parse_selected_programs_invalid_id_format(tmp_path):
    """verifies that an error is raised if a program ID is not exactly 5 digits (requirement 1.2)"""
    parser = TextFileParser()
    p = tmp_path / "selected_programs.txt"
    p.write_text("83101,8310,ABCDE", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid program ID"):
        parser.parse_selected_programs(str(p))


def test_parse_selected_programs_duplicates(tmp_path):
    """verifies that an error is raised if there are duplicate program IDs in the selection file"""
    parser = TextFileParser()
    p = tmp_path / "selected_programs.txt"
    p.write_text("83108,83101,83108", encoding="utf-8")

    with pytest.raises(ValueError, match="Duplicate program IDs found"):
        parser.parse_selected_programs(str(p))


# =========================================================================
# 2. tests for parse_courses
# =========================================================================

def test_parse_courses_happy_path(tmp_path):
    """verifies that parsing a valid course record works and trims leading/trailing whitespace"""
    parser = TextFileParser()
    p = tmp_path / "courses.txt"
    
    # constructing a valid record exactly according to the format you specified
    content = """$$$$
Physics 1
83102
Prof. O. Some
83101,1,FALL,Obligatory
83102,1,FALL,Obligatory
Exam"""
    p.write_text(content, encoding="utf-8")

    courses = parser.parse_courses(str(p))
    
    assert len(courses) == 1
    course = courses[0]
    assert course.course_name == "Physics 1"
    assert course.course_id == "83102"
    assert course.instructor == "Prof. O. Some"
    assert course.evaluation_method == "Exam"
    assert len(course.program_info) == 2
    
    # checking the first program info line
    prog_1 = course.program_info[0]
    assert prog_1.program_id == "83101"
    assert prog_1.year == 1
    assert prog_1.semester == "FALL"
    assert prog_1.requirement == "Obligatory"


def test_parse_courses_invalid_evaluation_method(tmp_path):
    """verifies that an error is raised if the evaluation method is not Exam or Project"""
    parser = TextFileParser()
    p = tmp_path / "courses.txt"
    content = """$$$$
Invalid Course
12345
Dr. Evil
83108,2,SPRI,Elective
Homework"""  # invalid evaluation method (should be "Exam" or "Project")
    p.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid evaluation method"):
        parser.parse_courses(str(p))


def test_parse_courses_missing_program_info(tmp_path):
    """verifies that an error is raised if the record is too short and does not contain program information lines"""
    parser = TextFileParser()
    p = tmp_path / "courses.txt"
    content = """$$$$
Short Course
12345
Dr. Short
Exam"""  # missing ProgramCourseInfo lines between instructor and evaluation method
    p.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Course record must contain program information lines"):
        parser.parse_courses(str(p))


# =========================================================================
# 3. tests for parse_exam_periods
# =========================================================================

def test_parse_exam_periods_happy_path(tmp_path):
    """verifies that parsing a valid exam period record works and handles different date formats"""
    parser = TextFileParser()
    p = tmp_path / "exam_periods.txt"
    
    # record containing a single day exclusion with text, and a date range exclusion with text
    content = """$$$$
FALL, Aleph
29-01-2026, 11-03-2026
- 31-01-2026 Saturday
- 02-03-2026, 04-03-2026 Purim"""
    p.write_text(content, encoding="utf-8")

    periods = parser.parse_exam_periods(str(p))
    
    assert len(periods) == 1
    period = periods[0]
    assert period.semester == "FALL"
    assert period.moed == "Aleph"
    assert period.start_date == date(2026, 1, 29)
    assert period.end_date == date(2026, 3, 11)
    
    assert len(period.excluded_dates) == 2
    
    # checking the first exclusion (single day)
    excl_1 = period.excluded_dates[0]
    assert excl_1.start_date == date(2026, 1, 31)
    assert excl_1.end_date == date(2026, 1, 31)
    assert excl_1.comment == "Saturday"
    
    # checking the second exclusion (date range)
    excl_2 = period.excluded_dates[1]
    assert excl_2.start_date == date(2026, 3, 2)
    assert excl_2.end_date == date(2026, 3, 4)
    assert excl_2.comment == "Purim"


def test_parse_exam_periods_start_after_end_date(tmp_path):
    """verifies that an error is raised if the start date of the period is after the end date"""
    parser = TextFileParser()
    p = tmp_path / "exam_periods.txt"
    content = """$$$$
FALL, Aleph
11-03-2026, 29-01-2026"""  # start date is after end date
    p.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="cannot be after end date"):
        parser.parse_exam_periods(str(p))


def test_parse_exam_periods_invalid_header(tmp_path):
# verifies that an error is raised if the header line does not contain a valid semester (requirement 3.1)
    parser = TextFileParser()
    p = tmp_path / "exam_periods.txt"
    content = """$$$$
WINTER, Aleph
29-01-2026, 11-03-2026"""  # winter is not a valid semester according to the requirements (should be "FALL" or "SPRI")
    p.write_text(content, encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid semester"):
        parser.parse_exam_periods(str(p))


# =========================================================================
# 5. tests for general file operations
# =========================================================================

def test_parser_file_not_found():
    """verifies that the methods raise FileNotFoundError when the file does not exist"""

    parser = TextFileParser()
    non_existent_path = "this_file_does_not_exist_at_all.txt"
    
    with pytest.raises(FileNotFoundError, match="not found"):
        parser.extract_records(non_existent_path)
        
    with pytest.raises(FileNotFoundError, match="not found"):
        parser.parse_selected_programs(non_existent_path)