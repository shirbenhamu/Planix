import pytest
from datetime import date, timedelta
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import ScheduledExam, Schedule
from src.engine.advanced_exam_scheduler import AdvancedExamScheduler
from src.engine.scheduling_constraints import SchedulingConstraints

"""
Tests to verify that the system correctly implements additional scheduling constraints
when generating an exam schedule.
"""

# --- Core Fixtures and Mocks for Testing ---


@pytest.fixture
def mock_context():
    """
    Generates diverse courses and a conflict matrix matching the real system models.
    Provides 2 Obligatory courses, 2 elective courses, and an explicit conflict pair.
    """
    Obligatory_info = ProgramCourseInfo(
        program_id="83101", year=1, semester="FALL", requirement="Obligatory")
    elective_info = ProgramCourseInfo(
        program_id="83108", year=1, semester="FALL", requirement="Elective")

    course_a = Course(course_id="11111", course_name="Data Structures",
                      instructor="Dr. Code", evaluation_method="Exam", program_info=[Obligatory_info])
    course_b = Course(course_id="22222", course_name="Algorithms", instructor="Prof. Graph",
                      evaluation_method="Exam", program_info=[Obligatory_info])
    elective_x = Course(course_id="33333", course_name="Physics 1",
                        instructor="Dr. Newton", evaluation_method="Exam", program_info=[elective_info])
    elective_y = Course(course_id="44444", course_name="Physics 2",
                        instructor="Dr. Einstein", evaluation_method="Exam", program_info=[elective_info])

    conflict_matrix = set() 
    
    return {
        "course_a": course_a,
        "course_b": course_b,
        "elective_x": elective_x,
        "elective_y": elective_y,
        "conflict_matrix": conflict_matrix
    }


@pytest.fixture
def scheduler():
    """
    Generates a clean, isolated instance of the AdvancedExamScheduler engine.
    """
    return AdvancedExamScheduler()


# --- Constraint 2.1: Minimum Day Intervals for Obligatory Courses ---

def test_constraint_min_days_mandatory_flag_off(mock_context):
    """
    Flag Off: Verifies that when the constraint flag is disabled, the system always accepts
    the scheduling attempt even if the distance between mandatory courses is less than k.
    """
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=False, min_days_mandatory_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    start_date = date(2026, 1, 1)
    # Failing input if enabled, must accept because flag is off
    invalid_date = date(2026, 1, 2)

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], invalid_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_mandatory(mock_context):
    """
    Flag On with Passing/Failing Input: Verifies that the spacing between obligatory courses
    in the same program and academic year satisfies the minimum requirement 'k'.
    """
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 1)
    # Difference of only 2 days - Must be rejected (Failing input)
    invalid_date = date(2026, 1, 3)
    # Difference of 4 days (k+1 days boundary) - Must be accepted (Passing input)
    valid_date = date(2026, 1, 5)

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], invalid_date, scheduled_exams, mock_context["conflict_matrix"]) is False
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], valid_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_mandatory_exact_boundary(mock_context):
    """
    Edge Case: Verifies system behavior exactly on the boundary threshold (exactly k days apart).
    """
    k_value = 3
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=k_value)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 1)
    # Exactly 3 days apart (2026-01-04)
    exact_boundary_date = start_date + timedelta(days=k_value)

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], exact_boundary_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_mandatory_past_date(mock_context):
    """
    Edge Case: Verifies scheduling when the target date is in the past relative to the already scheduled exam.
    """
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    existing_exam_date = date(2026, 1, 10)
    # Chronologically before, within the 3-day forbidden window
    past_invalid_date = date(2026, 1, 8)

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=existing_exam_date)]
    scheduler._push_state(mock_context["course_a"], existing_exam_date,
                          scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], past_invalid_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_min_days_mandatory_invalid_k():
    """
    Validation Case: Verifies that passing a non-positive or non-integer value for 'k'
    correctly raises an exception during initialization.
    """
    # Case 1: Negative integer
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            min_days_mandatory_enabled=True, min_days_mandatory_k=-1)

    # Case 2: Float (Non-integer)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            min_days_mandatory_enabled=True, min_days_mandatory_k=2.5)

    # Case 3: String (Invalid type)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_mandatory_enabled=True,
                              min_days_mandatory_k="three")


# --- Constraint 2.2: Minimum Day Intervals Between ANY Exam ---

def test_constraint_min_days_any_exam_flag_off(mock_context):
    """
    Flag Off: Verifies that scheduling an exam on the exact same date as an already
    scheduled exam is accepted when the global spacing constraint flag is turned off.
    """
    constraints = SchedulingConstraints(min_days_any_enabled=False, min_days_any_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 15)

    scheduled_exams = [ScheduledExam(course=mock_context["course_a"], exam_date=test_date)]
    scheduler._push_state(mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_x"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True
    
def test_constraint_min_days_any_exam(mock_context):
    """
Flag On with Failing Input: Verifies that scheduling any exam on the exact same date 
    as an already scheduled exam is blocked when global spacing is enabled (min_days_any_k=1).
    """
    constraints = SchedulingConstraints(
        min_days_any_enabled=True, min_days_any_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 15)
    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=test_date)]
    scheduler._push_state(
        mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False

def test_constraint_min_days_any_exam_sanity(mock_context):
    """
    Flag On with Passing Input: Verifies that an exam can be successfully scheduled when the date 
    safely satisfies the global minimum spacing interval constraint.
    """
    constraints = SchedulingConstraints(
        min_days_any_enabled=True, min_days_any_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 15)
    # 5 days apart - Well outside the forbidden window
    valid_future_date = date(2026, 1, 20)

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    # Valid Placement: The date sequence satisfies the global 'min_days_any' required gap.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_x"], valid_future_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_any_exam_exact_boundary(mock_context):
    """
    Edge Case: Verifies system behavior exactly on the global boundary threshold (exactly k days apart).
    With k=1, this checks if an exam can be scheduled exactly on the next calendar day.
    """
    k_value = 1
    constraints = SchedulingConstraints(
        min_days_any_enabled=True, min_days_any_k=k_value)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 15)
    # Exactly 1 day later (2026-01-16)
    exact_boundary_date = start_date + timedelta(days=k_value)

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_x"], exact_boundary_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_any_invalid_k_raises_error():
    """
    Validation Case: Verifies that passing a non-positive or non-integer value for global 'k'
    correctly raises an exception during initialization.
    """
    # Case 1: Negative integer
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=-5)

    # Case 2: Float 
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=1.2)

    # Case 3: String (Invalid type)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_any_enabled=True, min_days_any_k="1")


# --- Constraint 2.3: Concurrent Elective Course Conflicts ---

def test_constraint_max_elective_conflicts_flag_off(mock_context):
    """
    Flag Off: Verifies that scheduling a conflicting elective course is allowed on the exact same day
    when the elective conflict limitation framework flag is turned off.
    """
    constraints = SchedulingConstraints(max_elective_conflicts_enabled=False, max_elective_conflicts_k=0)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 20)

    scheduled_exams = [ScheduledExam(course=mock_context["elective_x"], exam_date=test_date)]
    scheduler._push_state(mock_context["elective_x"], test_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_y"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True
    
    
def test_constraint_max_elective_conflicts_negative(mock_context):
    """
    Flag On with Failing Input: Verifies that scheduling a conflicting elective course on the exact same day
    is blocked when the allowed conflict threshold is zero (max_elective_conflicts_k=0).
    """
    constraints = SchedulingConstraints(
        max_elective_conflicts_enabled=True, max_elective_conflicts_k=0)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 20)
    scheduled_exams = [ScheduledExam(
        course=mock_context["elective_x"], exam_date=test_date)]

    # Physics 2 (elective_y) conflicts with Physics 1 (elective_x) per matrix. Since k=0, this must be rejected.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_y"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_max_elective_conflicts_sanity(mock_context):
    """
    Flag On with Passing Input: Verifies that two elective courses CAN be scheduled on the same day 
    if there is no recorded conflict between them in the conflict matrix.
    """
    constraints = SchedulingConstraints(
        max_elective_conflicts_enabled=True, max_elective_conflicts_k=0)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 20)
    scheduled_exams = [ScheduledExam(
        course=mock_context["elective_x"], exam_date=test_date)]

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_max_elective_conflicts_boundary_allowance(mock_context):
    """
    Boundary Value: Verifies that if the allowed conflict threshold is increased (k=1), 
    the engine successfully permits a single dynamic matrix conflict on the same date.
    """
    # Allowing up to 1 conflict between elective options
    constraints = SchedulingConstraints(
        max_elective_conflicts_enabled=True, max_elective_conflicts_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 20)
    scheduled_exams = [ScheduledExam(
        course=mock_context["elective_x"], exam_date=test_date)]

    # Even though Physics 2 conflicts with Physics 1, k=1 accommodates this single overlap.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_y"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_max_elective_invalid_k_raises_error():
    """
    Validation Case: Verifies that passing a negative or non-integer value for elective conflict limits
    correctly raises an exception during instance initialization.
    """
    # Case 1: Negative integer limit
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_elective_conflicts_enabled=True, max_elective_conflicts_k=-1)

    # Case 2: Float
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_elective_conflicts_enabled=True, max_elective_conflicts_k=0.7)

    # Case 3: Invalid string type
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_elective_conflicts_enabled=True, max_elective_conflicts_k="zero")


# --- Constraint 2.4: Maximum Date Range (Span) ---

def test_constraint_span_mandatory_flag_off(scheduler, mock_context):
    """
Flag Off: Verifies that scheduling an exam outside the maximum allowed span window is allowed
    when the span constraint flag is disabled.
    """
    constraints = SchedulingConstraints(span_mandatory_enabled=False, span_mandatory_k=5)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]
    
    # July 25th heavily exceeds the maximum 5-day span, but flag is off so it must accept via the main core checks
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], date(2026, 7, 25), [], mock_context["conflict_matrix"]
    ) is True
        
def test_constraint_span_mandatory_sanity(scheduler, mock_context):
    """
    Flag On with Passing Input: Verifies that scheduling an exam well within the 
    maximum allowed date range (Span) window passes successfully.
    """
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)

    # Simulating an initial exam placed on July 1st
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    # July 3rd is only 3 days into the window (Span <= 5) - Safe and Valid
    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 3)) is True


def test_constraint_span_mandatory_negative(scheduler, mock_context):
    """
    Flag On with Failing Input: Verifies that scheduling an exam way outside the 
    maximum allowed span window is strictly blocked.
    """
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)

    # Simulating an initial exam placed on July 1st
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    # July 15th heavily exceeds the maximum 5-day span constraint - Must be rejected
    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 15)) is False


def test_constraint_span_mandatory_boundary_limits(scheduler, mock_context):
    """
    Edge Case: Tests the upper boundary limits of the maximum allowed window (Span) 
    between the first exam and the last exam of a mandatory track.
    """
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)

    # Simulating a state where an exam is already recorded on July 1st
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    # Exact Boundary: July 5th yields a span of exactly 5 days (Inclusive boundary - Valid)
    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 5)) is True

    # Exceeding Boundary: July 6th expands the span window to 6 days (Out of bounds - Invalid)
    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 6)) is False


def test_constraint_span_mandatory_same_day_edge(scheduler, mock_context):
    """
    Edge Case: Tests scheduling another exam on the exact same day as the first exam (Span of 1 day / 0 days difference).
    Checks if the span validation logic safely permits concurrent or identical start date range entries.
    """
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    # Same day placement evaluation (Span window is exactly 1 day long here - Valid)
    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 1)) is True


def test_constraint_span_mandatory_invalid_k_raises_error():
    """
    Verifies that passing a non-positive or non-integer value for max span 'k'
    correctly raises an exception during initialization.
    """
    # Case 1: Negative span range
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=-7)

    # Case 2: Float assignment
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(span_mandatory_enabled=True,
                              span_mandatory_k=4.2)


# --- Constraint 2.5: Maximum Exams Per Day Capacity ---

def test_constraint_max_exams_per_day_flag_off(mock_context):
    """
    Flag Off: Verifies that the daily capacity verification steps are bypassed entirely
    and accept placements when the max exams feature flag is turned off.
    """
    constraints = SchedulingConstraints(max_exams_per_day_enabled=False, max_exams_per_day_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)
    
    scheduled_exams = [ScheduledExam(course=mock_context["course_a"], exam_date=test_date)]
    scheduler._push_state(mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])
    
    # Failing input if enabled, must accept because flag is off
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True
    
def test_constraint_max_exams_per_day_sanity(mock_context):
    """
    Flag On with Passing/Failing Input: Verifies that the daily capacity cap per calendar date 
    cannot be exceeded when the limit is strictly set to 1 exam per day (max_exams_per_day_k=1).
    """
    constraints = SchedulingConstraints(
        max_exams_per_day_enabled=True, max_exams_per_day_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)
    scheduled_exams = []

    # Positive check: The day is empty, so adding the first exam must be allowed.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True

    scheduled_exams.append(ScheduledExam(
        course=mock_context["course_a"], exam_date=test_date))
    scheduler._exams_per_day[test_date] = 1

    # Negative check: Attempting to add a second exam (Algorithms) on the same day when the capacity cap is strictly 1.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_max_exams_per_day_extended_boundary(mock_context):
    """
    Edge Case: Verifies that if the daily capacity cap is expanded (k=2), 
    the engine successfully permits a second exam but correctly blocks a third exam on that same day.
    """
    constraints = SchedulingConstraints(
        max_exams_per_day_enabled=True, max_exams_per_day_k=2)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)
    scheduled_exams = []

    # First exam placement - Valid (1/2 filled)
    scheduled_exams.append(ScheduledExam(
        course=mock_context["course_a"], exam_date=test_date))
    scheduler._exams_per_day[test_date] = 1

    # Second exam placement - Valid boundary check (2/2 filled)
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True

    # Simulating the state update for the second exam
    scheduled_exams.append(ScheduledExam(
        course=mock_context["course_b"], exam_date=test_date))
    scheduler._exams_per_day[test_date] = 2

    # Third exam placement - Out of bounds (Exceeds k=2, must fail)
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_x"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_max_exams_per_day_invalid_k_raises_error():
    """
    Validation Case: Verifies that passing a non-positive or non-integer value for max daily exams 'k'
    correctly raises an exception during initialization.
    """
    # Case 1: Negative daily limit
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_exams_per_day_enabled=True, max_exams_per_day_k=-2)

    # Case 2: Float
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_exams_per_day_enabled=True, max_exams_per_day_k=1.5)

    # Case 3: String
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_exams_per_day_enabled=True, max_exams_per_day_k="2")