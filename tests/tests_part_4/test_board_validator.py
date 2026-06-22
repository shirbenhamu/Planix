from datetime import date

import pytest

from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.board_validator import BoardConstraintValidator
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam


def _course(cid, program="83101", year=1, requirement="Obligatory"):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo(program, year, "FALL", requirement)])


def _board(*pairs):
    # pairs: (course, date)
    return Schedule(exams=[ScheduledExam(course=c, exam_date=d) for c, d in pairs])


# --- base critical-conflict rule (always enforced) --------------------------
def test_two_mandatory_same_cohort_same_day_is_invalid():
    c1, c2 = _course("11111"), _course("22222")
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 1)))
    v = BoardConstraintValidator()  # no k-constraints enabled
    assert v.is_satisfied(board) is False
    assert "critical_conflict" in v.violations(board)


def test_two_electives_same_day_is_allowed_by_base_rule():
    e1 = _course("11111", requirement="Elective")
    e2 = _course("22222", requirement="Elective")
    board = _board((e1, date(2026, 2, 1)), (e2, date(2026, 2, 1)))
    assert BoardConstraintValidator().is_satisfied(board) is True


def test_same_day_different_program_is_allowed():
    a = _course("11111", program="83101")
    b = _course("22222", program="83102")
    board = _board((a, date(2026, 2, 1)), (b, date(2026, 2, 1)))
    assert BoardConstraintValidator().is_satisfied(board) is True


# --- 2.1 min days between mandatory exams -----------------------------------
def test_min_days_mandatory():
    c1, c2 = _course("11111"), _course("22222")
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 4)))  # 3-day gap
    c = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.min_days_mandatory_k = 3
    assert BoardConstraintValidator(c).is_satisfied(board) is True


# --- 2.2 min days between any two exams -------------------------------------
def test_min_days_any_counts_electives_too():
    e1 = _course("11111", requirement="Elective")
    e2 = _course("22222", requirement="Elective")
    board = _board((e1, date(2026, 2, 1)), (e2, date(2026, 2, 2)))  # 1-day gap
    c = SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=3)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.min_days_any_k = 1
    assert BoardConstraintValidator(c).is_satisfied(board) is True


# --- 2.3 max elective-elective conflicts ------------------------------------
def test_max_elective_conflicts():
    e1 = _course("11111", requirement="Elective")
    e2 = _course("22222", requirement="Elective")
    board = _board((e1, date(2026, 2, 1)), (e2, date(2026, 2, 1)))  # 1 conflict
    c = SchedulingConstraints(max_elective_conflicts_enabled=True, max_elective_conflicts_k=0)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.max_elective_conflicts_k = 1
    assert BoardConstraintValidator(c).is_satisfied(board) is True


# --- 2.4 span between first and last mandatory exam -------------------------
def test_span_mandatory_inclusive():
    c1, c2 = _course("11111"), _course("22222")
    # 1 -> 10 inclusive span = 10 days
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 10)))
    c = SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=9)
    assert BoardConstraintValidator(c).is_satisfied(board) is False
    c.span_mandatory_k = 10
    assert BoardConstraintValidator(c).is_satisfied(board) is True


# --- 2.5 max exams per day --------------------------------------------------
def test_max_exams_per_day():
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
    c1, c2 = _course("11111"), _course("22222")
    board = _board((c1, date(2026, 2, 1)), (c2, date(2026, 2, 2)))  # 1-day gap
    # min_days_mandatory NOT enabled -> close mandatory exams are fine
    assert BoardConstraintValidator(SchedulingConstraints()).is_satisfied(board) is True
