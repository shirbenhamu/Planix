from datetime import date

import pytest

from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.manual_edit_session import ManualEditSession, MoveResult
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod, ExcludedDate
from src.MVP.models.schedule import Schedule, ScheduledExam


def _course(cid, program="83101", year=1, requirement="Obligatory"):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo(program, year, "FALL", requirement)])


def _fall_period(excluded=None):
    # FALL Aleph, 01-02-2026 .. 28-02-2026, optionally excluding a single day.
    excl = []
    if excluded:
        excl = [ExcludedDate(start_date=d, end_date=d) for d in excluded]
    return ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), excl)


def _session(exams, periods=None, constraints=None):
    schedule = Schedule(exams=[ScheduledExam(course=c, exam_date=d) for c, d in exams])
    return ManualEditSession(schedule, periods or [_fall_period()], constraints)


def _date_of(session, course_id):
    for e in session.current_board().exams:
        if e.course.course_id == course_id:
            return e.exam_date
    return None


# --- PLAN-558: original + current copies are independent ---------------------
def test_session_keeps_independent_copies():
    c1 = _course("11111")
    s = _session([(c1, date(2026, 2, 3))])
    # mutating the current board must not touch the original
    s.current_board().exams[0].exam_date = date(2026, 2, 9)
    assert s.original_board().exams[0].exam_date == date(2026, 2, 3)


# --- valid move -------------------------------------------------------------
def test_valid_move_within_semester_commits():
    c1, c2 = _course("11111"), _course("22222")
    s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])
    result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10))
    assert result.success is True
    assert _date_of(s, "11111") == date(2026, 2, 10)
    assert s.has_changes() is True


def test_noop_move_to_same_date_succeeds():
    c1 = _course("11111")
    s = _session([(c1, date(2026, 2, 3))])
    assert s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 3)).success is True
    assert s.has_changes() is False


# --- PLAN-561: snap-back cases (move rejected, board unchanged) --------------
def test_move_outside_semester_is_rejected():
    c1 = _course("11111")
    s = _session([(c1, date(2026, 2, 3))])
    result = s.move_exam("11111", date(2026, 2, 3), date(2026, 4, 1))  # past period end
    assert result.success is False
    assert result.reason == MoveResult.OUT_OF_SEMESTER
    assert _date_of(s, "11111") == date(2026, 2, 3)  # unchanged


def test_move_to_excluded_date_is_rejected():
    c1 = _course("11111")
    s = _session([(c1, date(2026, 2, 3))], periods=[_fall_period(excluded=[date(2026, 2, 10)])])
    result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10))
    assert result.success is False
    assert result.reason == MoveResult.EXCLUDED
    assert _date_of(s, "11111") == date(2026, 2, 3)


def test_move_violating_constraint_is_rejected():
    c1, c2 = _course("11111"), _course("22222")
    constraints = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
    s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))], constraints=constraints)
    # moving c1 to 02-18 would be 2 days from c2 (< 5) -> rejected
    result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 18))
    assert result.success is False
    assert result.reason == MoveResult.CONSTRAINT
    assert _date_of(s, "11111") == date(2026, 2, 3)


def test_move_onto_conflicting_day_is_rejected():
    c1, c2 = _course("11111"), _course("22222")  # same cohort, both mandatory
    s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])
    result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 20))  # onto c2's day
    assert result.success is False
    assert result.reason == MoveResult.CONSTRAINT
    assert _date_of(s, "11111") == date(2026, 2, 3)


def test_move_unknown_exam_is_rejected():
    c1 = _course("11111")
    s = _session([(c1, date(2026, 2, 3))])
    result = s.move_exam("99999", date(2026, 2, 3), date(2026, 2, 10))
    assert result.success is False
    assert result.reason == MoveResult.NOT_FOUND


# --- can_move: non-committing validation for live drag feedback ------------
def test_can_move_does_not_commit_but_matches_verdict():
    c1, c2 = _course("11111"), _course("22222")
    s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])

    # valid target: can_move says yes, but the board is NOT changed
    assert s.can_move("11111", date(2026, 2, 3), date(2026, 2, 10)).success is True
    assert _date_of(s, "11111") == date(2026, 2, 3)  # unchanged by can_move
    assert s.has_changes() is False

    # invalid target: can_move says no, agreeing with move_exam
    assert s.can_move("11111", date(2026, 2, 3), date(2026, 4, 1)).success is False
    assert s.move_exam("11111", date(2026, 2, 3), date(2026, 4, 1)).success is False


# --- PLAN-563: undo ---------------------------------------------------------
def test_undo_restores_original_board():
    c1, c2 = _course("11111"), _course("22222")
    s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])
    s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10))
    s.move_exam("22222", date(2026, 2, 20), date(2026, 2, 25))
    assert s.has_changes() is True

    s.undo()
    assert s.has_changes() is False
    assert _date_of(s, "11111") == date(2026, 2, 3)
    assert _date_of(s, "22222") == date(2026, 2, 20)
