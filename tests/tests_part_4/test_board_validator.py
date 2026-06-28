import pytest
from datetime import date
from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.board_validator import BoardConstraintValidator
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam

# --- Helper Utilities ---

def _course(cid, program="83101", year=1, requirement="Obligatory"):
    """Factory helper to create consistent Course objects for testing."""
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo(program, year, "FALL", requirement)])

def _board(*pairs):
    """Factory helper to wrap courses and dates into a Schedule object."""
    return Schedule(exams=[ScheduledExam(course=c, exam_date=d) for c, d in pairs])

# --- base critical-conflict rule (always enforced) ---
def test_two_mandatory_same_cohort_same_day_is_invalid():
    """Ensure that the hardcoded 'critical_conflict' rule cannot be bypassed."""
    c1, c2 = _course("11111"), _course("22222")
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 1)))
    v = BoardConstraintValidator()  # no k-constraints enabled
    assert v.is_satisfied(board) is False
    assert "critical_conflict" in v.violations(board)

def test_two_electives_same_day_is_allowed_by_base_rule():
    """Verify that the base rule only targets mandatory exams."""
    e1 = _course("11111", requirement="Elective")
    e2 = _course("22222", requirement="Elective")
    board = _board((e1, date(2026, 2, 1)), (e2, date(2026, 2, 1)))
    assert BoardConstraintValidator().is_satisfied(board) is True

def test_same_day_different_program_is_allowed():
    """Verify that different academic programs do not trigger inter-program conflicts."""
    a = _course("11111", program="83101")
    b = _course("22222", program="83102")
    board = _board((a, date(2026, 2, 1)), (b, date(2026, 2, 1)))
    assert BoardConstraintValidator().is_satisfied(board) is True

# --- 2.1 min days between mandatory exams ---
def test_min_days_mandatory():
    """Validates the 'k' day gap requirement for mandatory exams."""
    c1, c2 = _course("11111"), _course("22222")
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 4)))  # 3-day gap
    c = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.min_days_mandatory_k = 3
    assert BoardConstraintValidator(c).is_satisfied(board) is True

# --- 2.2 min days between any two exams ---
def test_min_days_any_counts_electives_too():
    """Checks that 'any' exam constraint correctly includes elective coursework."""
    e1 = _course("11111", requirement="Elective")
    e2 = _course("22222", requirement="Elective")
    board = _board((e1, date(2026, 2, 1)), (e2, date(2026, 2, 2)))  # 1-day gap
    c = SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=3)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.min_days_any_k = 1
    assert BoardConstraintValidator(c).is_satisfied(board) is True

# --- 2.3 max elective-elective conflicts ---
def test_max_elective_conflicts():
    """Validates the threshold for elective-to-elective scheduling conflicts."""
    e1 = _course("11111", requirement="Elective")
    e2 = _course("22222", requirement="Elective")
    board = _board((e1, date(2026, 2, 1)), (e2, date(2026, 2, 1)))  # 1 conflict
    c = SchedulingConstraints(max_elective_conflicts_enabled=True, max_elective_conflicts_k=0)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.max_elective_conflicts_k = 1
    assert BoardConstraintValidator(c).is_satisfied(board) is True

# --- 2.4 span between first and last mandatory exam ---
    """Ensures span calculation (first to last) is inclusive of both endpoints."""
    c1, c2 = _course("11111"), _course("22222")
    # 1 -> 10 inclusive span = 10 days
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 10)))
    c = SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=9)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.span_mandatory_k = 10
    assert BoardConstraintValidator(c).is_satisfied(board) is True

# --- 2.5 max exams per day ---
def test_max_exams_per_day():
    """Verifies that total exam volume per day obeys configured capacity limits."""
    # three different programs on the same day -> no critical conflict, count = 3
    a = _course("1", program="P1")
    b = _course("2", program="P2")
    cc = _course("3", program="P3")
    board = _board((a, date(2026, 2, 1)), (b, date(2026, 2, 1)), (cc, date(2026, 2, 1)))
    c = SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=2)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.max_exams_per_day_k = 3
    assert BoardConstraintValidator(c).is_satisfied(board) is True

def test_disabled_constraints_are_skipped():
    """Ensures the validator ignores constraints that are not explicitly enabled."""
    c1, c2 = _course("11111"), _course("22222")
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 2)))  # 1-day gap
    # min_days_mandatory NOT enabled -> close mandatory exams are fine
    assert BoardConstraintValidator(SchedulingConstraints()).is_satisfied(board) is True

# --- additional boundary / negative coverage ---

def test_empty_board_is_always_satisfied():
    """Confirms that an empty schedule does not trigger any false-positive violations."""
    c = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=10,
        max_exams_per_day_enabled=True, max_exams_per_day_k=1,   
    )
    board = _board()
    assert BoardConstraintValidator(c).is_satisfied(board) is True
    assert BoardConstraintValidator(c).violations(board) == []

def test_single_exam_board_is_always_satisfied():
    """A lone exam can never violate a pairwise or per-day constraint."""
    c1 = _course("11111")
    board = _board((c1, date(2026, 2, 1)))
    c = SchedulingConstraints(
        min_days_mandatory_enabled=True, min_days_mandatory_k=30,
        max_exams_per_day_enabled=True, max_exams_per_day_k=1,
    )
    assert BoardConstraintValidator(c).is_satisfied(board) is True

def test_multiple_simultaneous_violations_are_all_reported():
    """violations() must report every failing constraint key, not just the first."""
    c1, c2 = _course("11111"), _course("22222")
    # same day (critical conflict) AND violates max_exams_per_day(k=1)
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 1)))
    c = SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=1)
    failed = BoardConstraintValidator(c).violations(board)
    assert "critical_conflict" in failed
    assert "max_exams_per_day" in failed
    assert len(failed) == 2

def test_min_days_mandatory_boundary_gap_equal_to_k_passes():
    """The constraint is '>= k': a gap of exactly k days must pass, k-1 must fail."""
    c1, c2 = _course("11111"), _course("22222")
    c = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
    exact = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 6)))   # exactly 5 days
    one_short = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 5)))  # 4 days
    assert BoardConstraintValidator(c).is_satisfied(exact) is True
    assert BoardConstraintValidator(c).is_satisfied(one_short) is False

def test_max_exams_per_day_zero_is_rejected():
    """k=0 is NOT a valid configuration in this domain: enabling the rule
    while permitting zero exams per day is refused up front."""
    with pytest.raises(ValueError):
        SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=0)

def test_constructor_with_no_constraints_arg_defaults_safely():
    """Negative/defensive: instantiating with no args must not crash and must
    fall back to an all-disabled SchedulingConstraints()."""
    v = BoardConstraintValidator()
    assert isinstance(v.constraints, SchedulingConstraints)
    assert v.constraints.min_days_mandatory_enabled is False

def test_violations_on_a_valid_board_returns_empty_list_not_none():
    """Ensure consistent return type for empty violation lists (api stability)."""
    c1 = _course("11111")
    board = _board((c1, date(2026, 2, 1)))
    result = BoardConstraintValidator().violations(board)
    assert result == []
    assert result is not None