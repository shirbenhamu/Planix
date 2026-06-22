from datetime import date

import pytest

from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.manual_edit_session import ManualEditSession, MoveResult
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod, ExcludedDate
from src.MVP.models.schedule import Schedule, ScheduledExam

# ---------------------------------------------------------------------------
# Exhaustive edge-case coverage for the manual drag & drop story (PLAN-554).
#
# These tests lock down EVERY move outcome the feature must respect:
#   * two electives may share a day (no critical conflict);
#   * a mandatory exam may never share a cohort-day;
#   * a "project" (evaluation_method != "Exam") behaves like any other exam —
#     only the requirement + cohort decide conflicts, never the eval method;
#   * dragging between semesters / outside any period is rejected;
#   * period boundaries (start/end) are inclusive, one day past is rejected;
#   * the five k-constraints each gate a move; and
#   * every rejection is a silent no-op (board + has_changes untouched), with
#     can_move() agreeing with move_exam() but never committing.
# ---------------------------------------------------------------------------

OBLIG = "Obligatory"
ELECT = "Elective"


def _course(cid, program="83101", year=1, requirement=OBLIG, evaluation="Exam"):
    """A single-program course. `evaluation` lets us model a project ('Project')."""
    return Course(cid, f"C{cid}", "T", evaluation,
                  [ProgramCourseInfo(program, year, "FALL", requirement)])


def _multi_course(cid, infos, evaluation="Exam"):
    """A course that belongs to several (program, year, requirement) cohorts."""
    program_info = [ProgramCourseInfo(p, y, "FALL", r) for p, y, r in infos]
    return Course(cid, f"C{cid}", "T", evaluation, program_info)


def _fall(excluded=None):
    # FALL Aleph: 01-02-2026 .. 28-02-2026.
    excl = [ExcludedDate(start_date=d, end_date=d) for d in (excluded or [])]
    return ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), excl)


def _spring():
    # SPRING Aleph: 01-06-2026 .. 30-06-2026 (a second, separate semester).
    return ExamPeriod("SPRING", "Aleph", date(2026, 6, 1), date(2026, 6, 30), [])


def _session(exams, periods=None, constraints=None):
    schedule = Schedule(exams=[ScheduledExam(course=c, exam_date=d) for c, d in exams])
    return ManualEditSession(schedule, periods or [_fall()], constraints)


def _date_of(session, course_id):
    for e in session.current_board().exams:
        if e.course.course_id == course_id:
            return e.exam_date
    return None


def _assert_rejected(session, course_id, old, new, reason):
    """A rejected move must report `reason`, leave the card put, and not dirty
    the board. can_move must agree and must itself never commit."""
    before = _date_of(session, course_id)
    assert session.can_move(course_id, old, new).success is False
    assert _date_of(session, course_id) == before          # can_move did not commit
    result = session.move_exam(course_id, old, new)
    assert result.success is False
    assert result.reason == reason
    assert _date_of(session, course_id) == before          # snapped back
    assert session.has_changes() is False


def _assert_accepted(session, course_id, old, new):
    assert session.can_move(course_id, old, new).success is True
    assert _date_of(session, course_id) == old             # can_move did not commit
    assert session.move_exam(course_id, old, new).success is True
    assert _date_of(session, course_id) == new


# === Two electives sharing a day ===========================================
def test_two_electives_may_share_a_day_by_default():
    # Same cohort, both elective -> NOT a critical conflict -> allowed.
    e1 = _course("11111", requirement=ELECT)
    e2 = _course("22222", requirement=ELECT)
    s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))])
    _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))
    # both now sit on the 20th
    assert _date_of(s, "22222") == date(2026, 2, 20)


def test_two_electives_same_day_blocked_when_max_conflicts_zero():
    # 2.3 enabled with k=0 forbids ANY elective-elective same-day pair.
    e1 = _course("11111", requirement=ELECT)
    e2 = _course("22222", requirement=ELECT)
    cons = SchedulingConstraints(max_elective_conflicts_enabled=True,
                                 max_elective_conflicts_k=0)
    s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                     MoveResult.CONSTRAINT)


def test_two_electives_same_day_allowed_when_max_conflicts_one():
    e1 = _course("11111", requirement=ELECT)
    e2 = _course("22222", requirement=ELECT)
    cons = SchedulingConstraints(max_elective_conflicts_enabled=True,
                                 max_elective_conflicts_k=1)
    s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
    _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))


def test_electives_in_different_cohorts_never_conflict_on_a_day():
    # Different (program/year) cohorts -> not even counted as an elective conflict.
    e1 = _course("11111", program="83101", requirement=ELECT)
    e2 = _course("22222", program="99999", requirement=ELECT)
    cons = SchedulingConstraints(max_elective_conflicts_enabled=True,
                                 max_elective_conflicts_k=0)
    s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
    _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))


# === Mandatory exams may never share a cohort-day ==========================
def test_mandatory_onto_mandatory_same_cohort_rejected():
    m1, m2 = _course("11111"), _course("22222")  # both obligatory, same cohort
    s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                     MoveResult.CONSTRAINT)


def test_mandatory_onto_elective_same_cohort_rejected():
    # Not "both elective" -> critical conflict.
    m = _course("11111", requirement=OBLIG)
    e = _course("22222", requirement=ELECT)
    s = _session([(m, date(2026, 2, 3)), (e, date(2026, 2, 20))])
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                     MoveResult.CONSTRAINT)


def test_mandatory_exams_different_cohorts_may_share_a_day():
    m1 = _course("11111", program="83101")
    m2 = _course("22222", program="99999")
    s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
    _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))


# === A "project" (not an exam) follows the same rules ======================
def test_project_elective_may_share_day_with_exam_elective():
    # evaluation_method differs ("Project" vs "Exam") but both are electives
    # in the same cohort -> still allowed.
    proj = _course("11111", requirement=ELECT, evaluation="Project")
    exam = _course("22222", requirement=ELECT, evaluation="Exam")
    s = _session([(proj, date(2026, 2, 3)), (exam, date(2026, 2, 20))])
    _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))


def test_project_mandatory_conflicts_like_any_mandatory():
    # A mandatory project still cannot share a cohort-day with another mandatory.
    proj = _course("11111", requirement=OBLIG, evaluation="Project")
    exam = _course("22222", requirement=OBLIG, evaluation="Exam")
    s = _session([(proj, date(2026, 2, 3)), (exam, date(2026, 2, 20))])
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                     MoveResult.CONSTRAINT)


# === Dragging between semesters ============================================
def test_move_into_a_different_semester_is_out_of_semester():
    # The exam lives in FALL; a SPRING date is inside another period, never FALL.
    m = _course("11111")
    s = _session([(m, date(2026, 2, 3))], periods=[_fall(), _spring()])
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 6, 10),
                     MoveResult.OUT_OF_SEMESTER)


def test_move_into_a_gap_between_periods_is_out_of_semester():
    m = _course("11111")
    s = _session([(m, date(2026, 2, 3))], periods=[_fall(), _spring()])
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 4, 15),
                     MoveResult.OUT_OF_SEMESTER)


def test_spring_exam_cannot_move_into_fall():
    # Symmetric check: an exam that belongs to SPRING cannot jump back to FALL.
    m = _course("11111")
    s = _session([(m, date(2026, 6, 10))], periods=[_fall(), _spring()])
    _assert_rejected(s, "11111", date(2026, 6, 10), date(2026, 2, 15),
                     MoveResult.OUT_OF_SEMESTER)


# === Period boundaries are inclusive =======================================
def test_move_to_period_start_and_end_is_allowed():
    m = _course("11111")
    s = _session([(m, date(2026, 2, 10))])
    _assert_accepted(s, "11111", date(2026, 2, 10), date(2026, 2, 1))    # start
    _assert_accepted(s, "11111", date(2026, 2, 1), date(2026, 2, 28))    # end


def test_move_one_day_past_period_end_is_rejected():
    m = _course("11111")
    s = _session([(m, date(2026, 2, 10))])
    _assert_rejected(s, "11111", date(2026, 2, 10), date(2026, 3, 1),
                     MoveResult.OUT_OF_SEMESTER)


def test_move_one_day_before_period_start_is_rejected():
    m = _course("11111")
    s = _session([(m, date(2026, 2, 10))])
    _assert_rejected(s, "11111", date(2026, 2, 10), date(2026, 1, 31),
                     MoveResult.OUT_OF_SEMESTER)


# === Excluded date =========================================================
def test_move_to_excluded_date_is_rejected():
    m = _course("11111")
    s = _session([(m, date(2026, 2, 3))], periods=[_fall(excluded=[date(2026, 2, 14)])])
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 14),
                     MoveResult.EXCLUDED)


def test_excluded_date_is_checked_before_constraints():
    # Even with no constraints, an excluded in-range date is rejected as EXCLUDED.
    m = _course("11111")
    s = _session([(m, date(2026, 2, 3))], periods=[_fall(excluded=[date(2026, 2, 4)])])
    res = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 4))
    assert res.reason == MoveResult.EXCLUDED


# === The five k-constraints each gate a move ===============================
def test_min_days_mandatory_gap_blocks_move():
    m1, m2 = _course("11111"), _course("22222")
    cons = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
    s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))], constraints=cons)
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 18),  # 2-day gap < 5
                     MoveResult.CONSTRAINT)
    _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 13))  # 7-day gap ok


def test_min_days_any_gap_blocks_move_for_electives_too():
    e1 = _course("11111", requirement=ELECT)
    e2 = _course("22222", requirement=ELECT)
    cons = SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=4)
    s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 22),  # 2-day gap < 4
                     MoveResult.CONSTRAINT)


def test_span_mandatory_blocks_move_that_stretches_window():
    m1, m2 = _course("11111"), _course("22222")
    # inclusive span allowed = 7 days. 03 -> 20 stretches span to 18 days.
    cons = SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=7)
    s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 6))], constraints=cons)
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                     MoveResult.CONSTRAINT)


def test_max_exams_per_day_blocks_third_exam_on_a_full_day():
    # Three different cohorts so the only thing stopping them is the per-day cap.
    a = _course("11111", program="A")
    b = _course("22222", program="B")
    c = _course("33333", program="C")
    cons = SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=2)
    s = _session([(a, date(2026, 2, 10)), (b, date(2026, 2, 10)), (c, date(2026, 2, 3))],
                 constraints=cons)
    _assert_rejected(s, "33333", date(2026, 2, 3), date(2026, 2, 10),  # would be 3
                     MoveResult.CONSTRAINT)


def test_max_exams_per_day_allows_filling_up_to_k():
    a = _course("11111", program="A")
    b = _course("22222", program="B")
    cons = SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=2)
    s = _session([(a, date(2026, 2, 10)), (b, date(2026, 2, 3))], constraints=cons)
    _assert_accepted(s, "22222", date(2026, 2, 3), date(2026, 2, 10))  # day now holds 2


# === Multi-cohort course: a move must satisfy ALL its cohorts ==============
def test_multi_cohort_course_rejected_if_any_cohort_conflicts():
    # Course X belongs to cohort (A,1) and (B,1). Moving it onto a day that holds
    # a mandatory of cohort (B,1) must be rejected even though (A,1) is clear.
    x = _multi_course("11111", [("A", 1, OBLIG), ("B", 1, OBLIG)])
    b_mand = _course("22222", program="B", year=1, requirement=OBLIG)
    s = _session([(x, date(2026, 2, 3)), (b_mand, date(2026, 2, 20))])
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                     MoveResult.CONSTRAINT)


# === Idempotence / signature semantics =====================================
def test_moving_there_and_back_clears_has_changes():
    m1, m2 = _course("11111"), _course("22222")
    s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
    assert s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10)).success
    assert s.has_changes() is True
    assert s.move_exam("11111", date(2026, 2, 10), date(2026, 2, 3)).success
    assert s.has_changes() is False  # signature matches the original again


def test_undo_after_several_moves_restores_everything():
    m1, m2 = _course("11111"), _course("22222")
    s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
    s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 8))
    s.move_exam("22222", date(2026, 2, 20), date(2026, 2, 25))
    s.undo()
    assert _date_of(s, "11111") == date(2026, 2, 3)
    assert _date_of(s, "22222") == date(2026, 2, 20)
    assert s.has_changes() is False


def test_undo_with_no_changes_is_safe():
    m = _course("11111")
    s = _session([(m, date(2026, 2, 3))])
    s.undo()
    assert _date_of(s, "11111") == date(2026, 2, 3)
    assert s.has_changes() is False


# === No periods configured: every move is out of semester ==================
def test_no_periods_means_no_move_is_in_semester():
    # Built directly (not via _session, whose `periods or [_fall()]` would turn an
    # empty list back into the default period).
    m = _course("11111")
    schedule = Schedule(exams=[ScheduledExam(course=m, exam_date=date(2026, 2, 3))])
    s = ManualEditSession(schedule, exam_periods=[], constraints=None)
    _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 10),
                     MoveResult.OUT_OF_SEMESTER)


# === Unknown / stale drag source ===========================================
def test_move_of_unknown_course_is_not_found():
    m = _course("11111")
    s = _session([(m, date(2026, 2, 3))])
    res = s.move_exam("00000", date(2026, 2, 3), date(2026, 2, 10))
    assert res.reason == MoveResult.NOT_FOUND


def test_move_with_wrong_old_date_is_not_found():
    # The card claims an origin the board doesn't have -> treated as not found.
    m = _course("11111")
    s = _session([(m, date(2026, 2, 3))])
    res = s.move_exam("11111", date(2026, 2, 9), date(2026, 2, 10))
    assert res.reason == MoveResult.NOT_FOUND
