import pytest
from datetime import date

from src.engine.exam_scheduler import ExamScheduler
from src.models.course import Course, ProgramCourseInfo
from src.models.exam_period import ExamPeriod, ExcludedDate
from src.models.schedule import Schedule, ScheduledExam


# =========================================================================
# checking inner logic of the engine, not performance or file output
# =========================================================================

def test_exam_period_get_available_dates_filters_exclusions():
    # set up an exam period with a range of dates and some exclusions
    start = date(2026, 1, 1)
    end = date(2026, 1, 4)
    
    # exclude January 2nd, 2026
    excl = ExcludedDate(start_date=date(2026, 1, 2), end_date=date(2026, 1, 2), comment="Holiday")
    
    period = ExamPeriod(
        semester="FALL",
        moed="Aleph",
        start_date=start,
        end_date=end,
        excluded_dates=[excl]
    )
    
    available = period.get_available_dates()
    
    # expect to get 3 days (without January 2nd)
    assert len(available) == 3
    assert date(2026, 1, 1) in available
    assert date(2026, 1, 2) not in available
    assert date(2026, 1, 3) in available
    assert date(2026, 1, 4) in available


# =========================================================================
# 2. tests for filtering relevant courses (filter_relevant_exam_courses)
# =========================================================================

def test_filter_relevant_exam_courses_ignores_projects():
    scheduler = ExamScheduler()
    
    prog_info = [ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")]
    course_exam = Course("11111", "Calculus", "Dr. Levy", "Exam", prog_info)
    course_project = Course("22222", "Intro to CS", "Dr. Cohen", "Project", prog_info)
    
    filtered = scheduler.filter_relevant_exam_courses([course_exam, course_project], ["83108"])
    
    assert len(filtered) == 1
    assert filtered[0].course_id == "11111"


def test_filter_relevant_exam_courses_raises_value_error_when_no_match():
    """ verifies that a ValueError is raised when no relevant exam courses are found for the selected programs """
    scheduler = ExamScheduler()
    prog_info = [ProgramCourseInfo(program_id="83101", year=1, semester="FALL", requirement="Obligatory")]
    course = Course("11111", "Digital Systems", "Dr. Smith", "Exam", prog_info)
    
    with pytest.raises(ValueError, match="No relevant exam courses found for the selected programs."):
        scheduler.filter_relevant_exam_courses([course], ["83108"])


# =========================================================================
# 3. tests for identifying conflicts (has_critical_exam_conflict)
# =========================================================================

def test_conflict_same_program_year_and_both_obligatory():
    # conflict case: two obligatory courses in the same year and program - they must conflict
    scheduler = ExamScheduler()
    
    info_a = ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")
    info_b = ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")
    
    course_a = Course("11111", "Linear Algebra", "Prof. A", "Exam", [info_a])
    course_b = Course("22222", "Discrete Math", "Prof. B", "Exam", [info_b])
    
    assert scheduler.has_critical_exam_conflict(course_a, course_b) is True


def test_no_conflict_same_program_year_and_both_elective():
    """no conflict case: two elective courses in the same year and program - they are allowed to conflict"""
    scheduler = ExamScheduler()
    
    info_a = ProgramCourseInfo(program_id="83108", year=3, semester="FALL", requirement="Elective")
    info_b = ProgramCourseInfo(program_id="83108", year=3, semester="FALL", requirement="Elective")
    
    course_a = Course("33333", "Compilation", "Prof. C", "Exam", [info_a])
    course_b = Course("44444", "Graphics", "Prof. D", "Exam", [info_b])
    
    assert scheduler.has_critical_exam_conflict(course_a, course_b) is False


def test_conflict_one_obligatory_one_elective():
    """conflict case: one obligatory course and one elective course in the same year and program - they must conflict"""
    scheduler = ExamScheduler()
    
    info_a = ProgramCourseInfo(program_id="83108", year=2, semester="FALL", requirement="Obligatory")
    info_b = ProgramCourseInfo(program_id="83108", year=2, semester="FALL", requirement="Elective")
    
    course_a = Course("55555", "Algorithms 1", "Prof. E", "Exam", [info_a])
    course_b = Course("66666", "Data Science Introduction", "Prof. F", "Exam", [info_b])
    
    assert scheduler.has_critical_exam_conflict(course_a, course_b) is True


def test_no_conflict_different_years():
    """no conflict case: courses from different years in the same program - they are allowed to conflict"""
    scheduler = ExamScheduler()
    
    info_a = ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")
    info_b = ProgramCourseInfo(program_id="83108", year=3, semester="FALL", requirement="Obligatory")
    
    course_a = Course("11111", "Calculus 1", "Prof. A", "Exam", [info_a])
    course_b = Course("77777", "Software Architecture", "Prof. G", "Exam", [info_b])
    
    assert scheduler.has_critical_exam_conflict(course_a, course_b) is False


# =========================================================================
# 4. tests for the backtracking algorithm and combinations
# =========================================================================

def test_generate_schedules_no_solution_pigeonhole(monkeypatch):
    """
    pigeonhole test:
    3 obligatory courses conflict, but only 2 dates are available.
    The system should return 0 solutions.
    """
    scheduler = ExamScheduler()
    
    info = ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")
    c1 = Course("10001", "Course 1", "Teacher", "Exam", [info])
    c2 = Course("10002", "Course 2", "Teacher", "Exam", [info])
    c3 = Course("10003", "Course 3", "Teacher", "Exam", [info])
    
    # realistically, the engine would call get_available_dates on the period, but we can monkeypatch it here to control the test conditions
    period = ExamPeriod(semester="FALL", moed="Aleph", start_date=date(2026, 2, 1), end_date=date(2026, 2, 10), excluded_dates=[])
    monkeypatch.setattr(period, "get_available_dates", lambda: [date(2026, 2, 1), date(2026, 2, 2)])
    
    result_generators = scheduler.generate_schedules([c1, c2, c3], [period], ["83108"])
    
    schedules = list(result_generators[("FALL", "Aleph")])
    assert len(schedules) == 0


def test_generate_schedules_exact_combinations(monkeypatch):
    """
    exact combinations test:
    2 obligatory courses conflict and 2 available dates.
    The engine should generate exactly 2 scheduling options.
    """
    scheduler = ExamScheduler()
    
    info = ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")
    c1 = Course("10001", "Course 1", "Teacher", "Exam", [info])
    c2 = Course("10002", "Course 2", "Teacher", "Exam", [info])
    
    period = ExamPeriod(semester="FALL", moed="Aleph", start_date=date(2026, 2, 1), end_date=date(2026, 2, 10), excluded_dates=[])
    monkeypatch.setattr(period, "get_available_dates", lambda: [date(2026, 2, 1), date(2026, 2, 2)])
    
    result_generators = scheduler.generate_schedules([c1, c2], [period], ["83108"])
    schedules = list(result_generators[("FALL", "Aleph")])
    
    assert len(schedules) == 2
    for schedule in schedules:
        assert isinstance(schedule, Schedule)
        assert len(schedule.exams) == 2
        assert schedule.exams[0].exam_date != schedule.exams[1].exam_date


def test_generate_schedules_allows_same_day_for_electives(monkeypatch):
    """
    verifies that two elective courses in the same year and program can be scheduled on the same day
    if it is the only available date.
    """
    scheduler = ExamScheduler()
    
    info = ProgramCourseInfo(program_id="83108", year=3, semester="FALL", requirement="Elective")
    c1 = Course("30001", "Elective 1", "Teacher", "Exam", [info])
    c2 = Course("30002", "Elective 2", "Teacher", "Exam", [info])
    
    period = ExamPeriod(semester="FALL", moed="Aleph", start_date=date(2026, 2, 5), end_date=date(2026, 2, 5), excluded_dates=[])
    monkeypatch.setattr(period, "get_available_dates", lambda: [date(2026, 2, 5)])
    
    result_generators = scheduler.generate_schedules([c1, c2], [period], ["83108"])
    schedules = list(result_generators[("FALL", "Aleph")])
    
    assert len(schedules) == 1
    exams = schedules[0].exams
    assert exams[0].exam_date == date(2026, 2, 5)
    assert exams[1].exam_date == date(2026, 2, 5)


    # =========================================================================
# בדיקות מקרי קצה עבור תאריכים מוחרגים (Excluded Dates Edge Cases)
# =========================================================================

def test_generate_schedules_total_blockout_raises_value_error():
    """
   edge case 1: the exam period has a total blockout where all dates are excluded. verifies that the system correctly identifies that there are no available dates for scheduling and raises a ValueError indicating that no schedules can be generated.
    """
    scheduler = ExamScheduler()
    
    # set up a course that needs to be scheduled
    info = [ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")]
    courses = [Course("83102", "Physics 1", "Prof. O. Some", "Exam", info)]
    
    # setting up an exam period where all dates are excluded (January 1-3, 2026)
    full_exclusion = ExcludedDate(start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), comment="Total Lockdown")
    exam_periods = [
        ExamPeriod("FALL", "Aleph", date(2026, 1, 1), date(2026, 1, 3), [full_exclusion])
    ]
    
    # system should raise a ValueError because there are no available dates for scheduling the exam due to the total blockout
    with pytest.raises(ValueError, match="No available exam dates found for scheduling"):
        scheduler.generate_schedules(courses, exam_periods, ["83108"])


def test_generate_schedules_out_of_bounds_exclusion_ignored():
    """
    edge case 2: the exam period includes an excluded date that is completely outside the range of the period.
    verifies that the system ignores the out-of-bounds exclusion and still generates valid schedules based on the actual available dates within the period.
    """
    scheduler = Scheduler = ExamScheduler()
    
    info = [ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")]
    courses = [Course("83102", "Physics 1", "Prof. O. Some", "Exam", info)]
    
    # january 1-4 are available, but there is an out-of-bounds exclusion in august that should not affect the scheduling for january
    out_of_bounds_exclusion = ExcludedDate(start_date=date(2026, 8, 1), end_date=date(2026, 8, 5), comment="Summer Holiday")
    exam_periods = [
        ExamPeriod("FALL", "Aleph", date(2026, 1, 1), date(2026, 1, 2), [out_of_bounds_exclusion])
    ]
    
    # should generate schedules based on the available dates in january, ignoring the august exclusion
    schedules_dict = scheduler.generate_schedules(courses, exam_periods, ["83108"])
    
    #verify that we get schedules for the FALL Aleph period, and that they are valid (not empty)
    key = ("FALL", "Aleph")
    assert key in schedules_dict
    schedules = list(schedules_dict[key])
    assert len(schedules) > 0