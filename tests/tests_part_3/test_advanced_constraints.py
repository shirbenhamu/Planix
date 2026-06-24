import pytest
from datetime import date, timedelta
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import ScheduledExam, Schedule
from src.engine.advanced_exam_scheduler import AdvancedExamScheduler
from src.engine.scheduling_constraints import SchedulingConstraints

"""
Tests verifying that the engine enforces the SRS section-2 threshold
constraints (2.1-2.5) while generating an exam schedule.

NOTE on the conflict_matrix: an elective-elective conflict is defined
structurally as "two distinct elective courses in the same program on the same
date" (identical to metric 3.3 in MetricsCalculator). It is NOT read from an
external matrix, so the matrix passed below is intentionally empty and only
satisfies the _can_add_exam_to_schedule signature. If your engine instead reads
conflicts from a populated matrix, seed it here for the 2.3 tests.
"""

# --- Core Fixtures and Mocks for Testing ---


@pytest.fixture
def mock_context():
    """
    Courses spanning two mandatory programs and two elective programs so the
    tests can isolate the per-(program, year) scoping the SRS requires.

      course_a, course_b -> mandatory, program 83101, year 1   (same group)
      course_c           -> mandatory, program 83102, year 1   (different group)
      elective_x, _y     -> elective,  program 83108, year 1   (conflicting pair)
      elective_z         -> elective,  program 83109, year 1   (non-conflicting)
    """
    obligatory_83101 = ProgramCourseInfo(
        program_id="83101", year=1, semester="FALL", requirement="Obligatory")
    obligatory_83102 = ProgramCourseInfo(
        program_id="83102", year=1, semester="FALL", requirement="Obligatory")
    elective_83108 = ProgramCourseInfo(
        program_id="83108", year=1, semester="FALL", requirement="Elective")
    elective_83109 = ProgramCourseInfo(
        program_id="83109", year=1, semester="FALL", requirement="Elective")

    course_a = Course(course_id="11111", course_name="Data Structures",
                      instructor="Dr. Code", evaluation_method="Exam", program_info=[obligatory_83101])
    course_b = Course(course_id="22222", course_name="Algorithms", instructor="Prof. Graph",
                      evaluation_method="Exam", program_info=[obligatory_83101])
    course_c = Course(course_id="55555", course_name="Operating Systems", instructor="Dr. Kernel",
                      evaluation_method="Exam", program_info=[obligatory_83102])
    elective_x = Course(course_id="33333", course_name="Physics 1",
                        instructor="Dr. Newton", evaluation_method="Exam", program_info=[elective_83108])
    elective_y = Course(course_id="44444", course_name="Physics 2",
                        instructor="Dr. Einstein", evaluation_method="Exam", program_info=[elective_83108])
    elective_z = Course(course_id="66666", course_name="Chemistry 1",
                        instructor="Dr. Curie", evaluation_method="Exam", program_info=[elective_83109])

    # Intentionally empty: conflicts are derived structurally (see module docstring).
    conflict_matrix = set()

    return {
        "course_a": course_a,
        "course_b": course_b,
        "course_c": course_c,
        "elective_x": elective_x,
        "elective_y": elective_y,
        "elective_z": elective_z,
        "conflict_matrix": conflict_matrix,
    }


@pytest.fixture
def scheduler():
    """A clean, isolated AdvancedExamScheduler engine instance."""
    return AdvancedExamScheduler()


# --- Constraint 2.1: Minimum Day Intervals for Obligatory Courses ---

def test_constraint_min_days_mandatory_flag_off(mock_context):
    """
    Flag Off: when the constraint is disabled, a sub-k spacing between mandatory
    courses must still be accepted.
    """
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=False, min_days_mandatory_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    start_date = date(2026, 1, 1)
    invalid_date = date(2026, 1, 2)  # would fail if enabled

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], invalid_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_mandatory(mock_context):
    """
    Flag On, passing/failing input: spacing between obligatory courses in the
    same program and year must satisfy the minimum requirement 'k'.
    """
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 1)
    invalid_date = date(2026, 1, 3)   # gap 2 (< k) -> reject
    valid_date = date(2026, 1, 5)     # gap 4 (>= k) -> accept

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], invalid_date, scheduled_exams, mock_context["conflict_matrix"]) is False
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], valid_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_mandatory_exact_boundary(mock_context):
    """Edge case: exactly k days apart is accepted (gap == k satisfies >= k)."""
    k_value = 3
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=k_value)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 1)
    exact_boundary_date = start_date + timedelta(days=k_value)  # 2026-01-04

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], exact_boundary_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_mandatory_past_date(mock_context):
    """Edge case: a target date earlier than the scheduled exam, within the
    forbidden window, is still rejected (the gap is symmetric)."""
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    existing_exam_date = date(2026, 1, 10)
    past_invalid_date = date(2026, 1, 8)  # 2 days before, inside the window

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=existing_exam_date)]
    scheduler._push_state(mock_context["course_a"], existing_exam_date,
                          scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], past_invalid_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_min_days_mandatory_different_program_is_not_blocked(mock_context):
    """
    Scoping (negative): 2.1 applies only within the same (program, year). Two
    mandatory courses in DIFFERENT programs may sit closer than k days apart.
    """
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 1)
    near_date = date(2026, 1, 2)  # gap 1 (< k) but different program -> allowed

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]  # program 83101
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    # course_c is program 83102 -> outside course_a's group -> constraint must not fire.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_c"], near_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_mandatory_invalid_k():
    """Validation: a non-positive or non-integer 'k' raises during init."""
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            min_days_mandatory_enabled=True, min_days_mandatory_k=-1)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            min_days_mandatory_enabled=True, min_days_mandatory_k=2.5)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_mandatory_enabled=True,
                              min_days_mandatory_k="three")


# --- Constraint 2.2: Minimum Day Intervals Between ANY Exam ---

def test_constraint_min_days_any_exam_flag_off(mock_context):
    """
    Flag Off: two same-program exams on the exact same date are accepted when
    the global spacing constraint is disabled.
    """
    constraints = SchedulingConstraints(min_days_any_enabled=False, min_days_any_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 15)

    scheduled_exams = [ScheduledExam(course=mock_context["course_a"], exam_date=test_date)]
    scheduler._push_state(mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])

    # course_b shares program 83101 with course_a -> would fail if enabled.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_any_exam(mock_context):
    """
    Flag On, failing input: any exam on the exact same date as another exam in
    the same (program, year) is blocked when global spacing is enabled (k=1).
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
    Flag On, passing input: a same-(program, year) exam comfortably outside the
    spacing window is accepted. Uses course_b (program 83101, like course_a) so
    the gap rule is actually exercised rather than skipped by program scoping.
    """
    constraints = SchedulingConstraints(
        min_days_any_enabled=True, min_days_any_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 15)
    valid_future_date = date(2026, 1, 20)  # 5 days apart, well outside k=1

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], valid_future_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_any_exam_exact_boundary(mock_context):
    """
    Edge case: exactly k days apart within the same (program, year). With k=1
    the next calendar day satisfies the >= k rule and is accepted. Uses course_b
    (same program as course_a) so the boundary is genuinely tested.
    """
    k_value = 1
    constraints = SchedulingConstraints(
        min_days_any_enabled=True, min_days_any_k=k_value)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    start_date = date(2026, 1, 15)
    exact_boundary_date = start_date + timedelta(days=k_value)  # 2026-01-16

    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=start_date)]
    scheduler._push_state(
        mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], exact_boundary_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_any_different_program_is_not_blocked(mock_context):
    """
    Scoping (negative): 2.2 is also per-(program, year). Two exams in DIFFERENT
    programs may share a date even with global spacing enabled.
    """
    constraints = SchedulingConstraints(
        min_days_any_enabled=True, min_days_any_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 15)
    scheduled_exams = [ScheduledExam(
        course=mock_context["course_a"], exam_date=test_date)]  # program 83101
    scheduler._push_state(
        mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])

    # course_c (program 83102) -> different group -> same-day placement allowed.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_c"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_min_days_any_invalid_k_raises_error():
    """Validation: a non-positive or non-integer global 'k' raises during init."""
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=-5)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=1.2)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(min_days_any_enabled=True, min_days_any_k="1")


# --- Constraint 2.3: Concurrent Elective Course Conflicts ---

def test_constraint_max_elective_conflicts_flag_off(mock_context):
    """
    Flag Off: two conflicting electives (same program, same day) are accepted
    when the elective-conflict constraint is disabled.
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
    Flag On, failing input: two distinct electives in the same program (83108)
    on the same day form one conflict. With k=0 this must be rejected.
    """
    constraints = SchedulingConstraints(
        max_elective_conflicts_enabled=True, max_elective_conflicts_k=0)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 20)
    scheduled_exams = [ScheduledExam(
        course=mock_context["elective_x"], exam_date=test_date)]

    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_y"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_max_elective_conflicts_sanity(mock_context):
    """
    Flag On, passing input: two electives in DIFFERENT programs (83108 vs 83109)
    on the same day do not conflict, so the placement is accepted even at k=0.
    """
    constraints = SchedulingConstraints(
        max_elective_conflicts_enabled=True, max_elective_conflicts_k=0)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 20)
    scheduled_exams = [ScheduledExam(
        course=mock_context["elective_x"], exam_date=test_date)]  # program 83108

    # elective_z is program 83109 -> not the same program -> no conflict.
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_z"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_max_elective_conflicts_boundary_allowance(mock_context):
    """
    Boundary value: raising the allowance to k=1 permits exactly one same-program
    elective overlap on the same date.
    """
    constraints = SchedulingConstraints(
        max_elective_conflicts_enabled=True, max_elective_conflicts_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)

    test_date = date(2026, 1, 20)
    scheduled_exams = [ScheduledExam(
        course=mock_context["elective_x"], exam_date=test_date)]

    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_y"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_max_elective_invalid_k_raises_error():
    """Validation: a negative or non-integer elective limit raises during init.
    (k == 0 is intentionally NOT tested here: 2.3 allows a non-negative k.)"""
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_elective_conflicts_enabled=True, max_elective_conflicts_k=-1)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_elective_conflicts_enabled=True, max_elective_conflicts_k=0.7)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_elective_conflicts_enabled=True, max_elective_conflicts_k="zero")


# --- Constraint 2.4: Date Range (Span) of mandatory exams ---
#
# !!! SPEC DISCREPANCY -- READ BEFORE TRUSTING THESE TESTS !!!
# SRS 2.4 reads "...לא יהיה קטן מ k", i.e. the first-to-last span must be
# >= k (a MINIMUM spread), and metric 3.4 sorts span descending ("higher is
# better"), which corroborates that reading. The tests below assert the OPPOSITE
# (span <= k, a maximum), matching the current engine. Direction was left as-is
# on purpose: flipping it here would silently break the suite while the real
# fix, if needed, belongs in the engine. Decide which side is correct, then make
# the engine and these tests agree.

def test_constraint_span_mandatory_flag_off(scheduler, mock_context):
    """Flag Off: an exam outside the span window is accepted when 2.4 is disabled."""
    scheduler.constraints = SchedulingConstraints(span_mandatory_enabled=False, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], date(2026, 7, 25), [], mock_context["conflict_matrix"]
    ) is True


def test_constraint_span_mandatory_sanity(scheduler, mock_context):
    """Flag On, passing input: a date well within the window passes."""
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 3)) is True


def test_constraint_span_mandatory_negative(scheduler, mock_context):
    """Flag On, failing input: a date far outside the window is blocked."""
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 15)) is False


def test_constraint_span_mandatory_blocked_through_main_gate(scheduler, mock_context):
    """
    Wiring: a span violation must also be rejected through the main admission
    gate (_can_add_exam_to_schedule), not only the _check_span_mandatory helper.
    Only the span constraint is enabled so nothing else can mask the result.
    """
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], date(2026, 7, 15), [], mock_context["conflict_matrix"]) is False


def test_constraint_span_mandatory_boundary_limits(scheduler, mock_context):
    """Edge case: exactly at the window boundary vs one day past it."""
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    # July 5 -> inclusive span 5 (== k) -> valid
    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 5)) is True
    # July 6 -> inclusive span 6 (> k) -> invalid
    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 6)) is False


def test_constraint_span_mandatory_same_day_edge(scheduler, mock_context):
    """Edge case: same day as the first exam (span of 1 inclusive day) is valid."""
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    assert scheduler._check_span_mandatory(
        mock_context["course_b"], date(2026, 7, 1)) is True


def test_constraint_span_mandatory_different_program_is_not_blocked(scheduler, mock_context):
    """
    Scoping (negative): the span is measured per (program, year). A mandatory
    exam in a different program is unaffected by another program's span window.
    """
    scheduler.constraints = SchedulingConstraints(
        span_mandatory_enabled=True, span_mandatory_k=5)
    scheduler._exam_dates_by_program_year[("83101", 1)] = [date(2026, 7, 1)]

    # course_c is program 83102; its own group is empty -> no span violation.
    assert scheduler._check_span_mandatory(
        mock_context["course_c"], date(2026, 7, 25)) is True


def test_constraint_span_mandatory_invalid_k_raises_error():
    """Validation: a negative or non-integer span 'k' raises during init."""
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=-7)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(span_mandatory_enabled=True,
                              span_mandatory_k=4.2)


# --- Constraint 2.5: Maximum Exams Per Day Capacity ---

def test_constraint_max_exams_per_day_flag_off(mock_context):
    """Flag Off: the daily-capacity check is bypassed when 2.5 is disabled."""
    constraints = SchedulingConstraints(max_exams_per_day_enabled=False, max_exams_per_day_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)

    scheduled_exams = [ScheduledExam(course=mock_context["course_a"], exam_date=test_date)]
    scheduler._push_state(mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True


def test_constraint_max_exams_per_day_sanity(mock_context):
    """
    Flag On, passing/failing input: with the cap set to 1, the first exam on an
    empty day is accepted and a second exam on that day is rejected.
    """
    constraints = SchedulingConstraints(
        max_exams_per_day_enabled=True, max_exams_per_day_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)
    scheduled_exams = []

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True

    scheduled_exams.append(ScheduledExam(
        course=mock_context["course_a"], exam_date=test_date))
    scheduler._exams_per_day[test_date] = 1

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_max_exams_per_day_extended_boundary(mock_context):
    """Edge case: with the cap at k=2, a second exam fits but a third is blocked."""
    constraints = SchedulingConstraints(
        max_exams_per_day_enabled=True, max_exams_per_day_k=2)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)
    scheduled_exams = []

    scheduled_exams.append(ScheduledExam(
        course=mock_context["course_a"], exam_date=test_date))
    scheduler._exams_per_day[test_date] = 1

    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True

    scheduled_exams.append(ScheduledExam(
        course=mock_context["course_b"], exam_date=test_date))
    scheduler._exams_per_day[test_date] = 2

    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_x"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False


def test_constraint_max_exams_per_day_invalid_k_raises_error():
    """Validation: a negative or non-integer daily cap 'k' raises during init."""
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_exams_per_day_enabled=True, max_exams_per_day_k=-2)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_exams_per_day_enabled=True, max_exams_per_day_k=1.5)
    with pytest.raises((ValueError, TypeError)):
        SchedulingConstraints(
            max_exams_per_day_enabled=True, max_exams_per_day_k="2")