import pytest
from datetime import date
from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.manual_edit_session import ManualEditSession, MoveResult
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod, ExcludedDate
from src.MVP.models.schedule import Schedule, ScheduledExam

OBLIG = "Obligatory"
ELECT = "Elective"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
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

# ===========================================================================
# SANITY — basic happy-path behaviour
# ===========================================================================
class TestSanity:
    def test_session_keeps_independent_copies(self):
        # PLAN-558: mutating current must never leak into original.
        c1 = _course("11111")
        s = _session([(c1, date(2026, 2, 3))])
        s.current_board().exams[0].exam_date = date(2026, 2, 9)
        assert s.original_board().exams[0].exam_date == date(2026, 2, 3)

    def test_valid_move_within_semester_commits(self):
        c1, c2 = _course("11111"), _course("22222")
        s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])
        result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10))
        assert result.success is True
        assert _date_of(s, "11111") == date(2026, 2, 10)
        assert s.has_changes() is True

    def test_undo_restores_original_board(self):
        c1, c2 = _course("11111"), _course("22222")
        s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])
        s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10))
        s.move_exam("22222", date(2026, 2, 20), date(2026, 2, 25))
        assert s.has_changes() is True
        s.undo()
        assert s.has_changes() is False
        assert _date_of(s, "11111") == date(2026, 2, 3)
        assert _date_of(s, "22222") == date(2026, 2, 20)

    def test_can_move_does_not_commit_but_matches_verdict(self):
        c1, c2 = _course("11111"), _course("22222")
        s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])

        assert s.can_move("11111", date(2026, 2, 3), date(2026, 2, 10)).success is True
        assert _date_of(s, "11111") == date(2026, 2, 3)  # unchanged by can_move
        assert s.has_changes() is False

        assert s.can_move("11111", date(2026, 2, 3), date(2026, 4, 1)).success is False
        assert s.move_exam("11111", date(2026, 2, 3), date(2026, 4, 1)).success is False

# ===========================================================================
# BOUNDARY — empty data, zero-length gaps, period edges, exact k thresholds
# ===========================================================================
class TestBoundary:
    def test_noop_move_to_same_date_succeeds(self):
        c1 = _course("11111")
        s = _session([(c1, date(2026, 2, 3))])
        assert s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 3)).success is True
        assert s.has_changes() is False

    def test_move_to_period_start_and_end_is_allowed(self):
        m = _course("11111")
        s = _session([(m, date(2026, 2, 10))])
        _assert_accepted(s, "11111", date(2026, 2, 10), date(2026, 2, 1))    # start
        _assert_accepted(s, "11111", date(2026, 2, 1), date(2026, 2, 28))    # end

    def test_move_one_day_past_period_end_is_rejected(self):
        m = _course("11111")
        s = _session([(m, date(2026, 2, 10))])
        _assert_rejected(s, "11111", date(2026, 2, 10), date(2026, 3, 1),
                         MoveResult.OUT_OF_SEMESTER)

    def test_move_one_day_before_period_start_is_rejected(self):
        m = _course("11111")
        s = _session([(m, date(2026, 2, 10))])
        _assert_rejected(s, "11111", date(2026, 2, 10), date(2026, 1, 31),
                         MoveResult.OUT_OF_SEMESTER)

    def test_move_into_a_gap_between_periods_is_out_of_semester(self):
        m = _course("11111")
        s = _session([(m, date(2026, 2, 3))], periods=[_fall(), _spring()])
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 4, 15),
                         MoveResult.OUT_OF_SEMESTER)

    def test_min_days_mandatory_gap_exactly_at_k_is_allowed(self):
        # The constraint is ">= k", so a gap of EXACTLY k days must pass
        # (k-1 must fail) — the classic off-by-one boundary check.
        m1, m2 = _course("11111"), _course("22222")
        cons = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
        s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))], constraints=cons)
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 16),  # 4-day gap < 5
                         MoveResult.CONSTRAINT)
        # rejection left the card at its original date (2/3); now move it to a
        # date exactly k=5 days before 2/20.
        _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 15))  # 5-day gap == k

    def test_max_exams_per_day_allows_filling_up_to_exactly_k(self):
        a = _course("11111", program="A")
        b = _course("22222", program="B")
        cons = SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=2)
        s = _session([(a, date(2026, 2, 10)), (b, date(2026, 2, 3))], constraints=cons)
        _assert_accepted(s, "22222", date(2026, 2, 3), date(2026, 2, 10))  # day now holds 2

    def test_max_exams_per_day_blocks_one_past_k(self):
        a = _course("11111", program="A")
        b = _course("22222", program="B")
        c = _course("33333", program="C")
        cons = SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=2)
        s = _session([(a, date(2026, 2, 10)), (b, date(2026, 2, 10)), (c, date(2026, 2, 3))],
                     constraints=cons)
        _assert_rejected(s, "33333", date(2026, 2, 3), date(2026, 2, 10),  # would be 3
                         MoveResult.CONSTRAINT)

    def test_empty_board_has_no_changes_and_undo_is_a_safe_noop(self):
        s = ManualEditSession(Schedule(exams=[]), exam_periods=[_fall()])
        assert s.current_board().exams == []
        assert s.has_changes() is False
        s.undo()  # must not raise
        assert s.current_board().exams == []

    def test_none_schedule_is_treated_as_an_empty_board(self):
        # Defensive boundary: a None schedule must not crash session creation.
        s = ManualEditSession(None, exam_periods=[_fall()])
        assert s.current_board().exams == []

    def test_no_periods_means_no_move_is_in_semester(self):
        m = _course("11111")
        schedule = Schedule(exams=[ScheduledExam(course=m, exam_date=date(2026, 2, 3))])
        s = ManualEditSession(schedule, exam_periods=[], constraints=None)
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 10),
                         MoveResult.OUT_OF_SEMESTER)

# ===========================================================================
# NEGATIVE — invalid/unknown targets, excluded dates, stale drag sources
# ===========================================================================
class TestNegative:
    def test_move_outside_semester_is_rejected(self):
        c1 = _course("11111")
        s = _session([(c1, date(2026, 2, 3))])
        result = s.move_exam("11111", date(2026, 2, 3), date(2026, 4, 1))
        assert result.success is False
        assert result.reason == MoveResult.OUT_OF_SEMESTER
        assert _date_of(s, "11111") == date(2026, 2, 3)

    def test_spring_exam_cannot_move_into_fall(self):
        m = _course("11111")
        s = _session([(m, date(2026, 6, 10))], periods=[_fall(), _spring()])
        _assert_rejected(s, "11111", date(2026, 6, 10), date(2026, 2, 15),
                         MoveResult.OUT_OF_SEMESTER)

    def test_move_to_excluded_date_is_rejected(self):
        c1 = _course("11111")
        s = _session([(c1, date(2026, 2, 3))], periods=[_fall(excluded=[date(2026, 2, 10)])])
        result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10))
        assert result.success is False
        assert result.reason == MoveResult.EXCLUDED
        assert _date_of(s, "11111") == date(2026, 2, 3)

    def test_excluded_date_is_checked_before_constraints(self):
        # Even with no k-constraints active, an excluded in-range date is
        # rejected as EXCLUDED rather than silently accepted.
        m = _course("11111")
        s = _session([(m, date(2026, 2, 3))], periods=[_fall(excluded=[date(2026, 2, 4)])])
        res = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 4))
        assert res.reason == MoveResult.EXCLUDED

    def test_move_violating_constraint_is_rejected(self):
        c1, c2 = _course("11111"), _course("22222")
        constraints = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
        s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))], constraints=constraints)
        result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 18))
        assert result.success is False
        assert result.reason == MoveResult.CONSTRAINT
        assert _date_of(s, "11111") == date(2026, 2, 3)

    def test_move_onto_conflicting_day_is_rejected(self):
        c1, c2 = _course("11111"), _course("22222")  # same cohort, both mandatory
        s = _session([(c1, date(2026, 2, 3)), (c2, date(2026, 2, 20))])
        result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 20))  # onto c2's day
        assert result.success is False
        assert result.reason == MoveResult.CONSTRAINT
        assert _date_of(s, "11111") == date(2026, 2, 3)

    def test_move_of_unknown_exam_is_not_found(self):
        c1 = _course("11111")
        s = _session([(c1, date(2026, 2, 3))])
        result = s.move_exam("99999", date(2026, 2, 3), date(2026, 2, 10))
        assert result.success is False
        assert result.reason == MoveResult.NOT_FOUND

    def test_move_with_wrong_old_date_is_not_found(self):
        # The card claims an origin the board doesn't have -> treated as not found.
        m = _course("11111")
        s = _session([(m, date(2026, 2, 3))])
        res = s.move_exam("11111", date(2026, 2, 9), date(2026, 2, 10))
        assert res.reason == MoveResult.NOT_FOUND

    def test_move_on_an_empty_board_is_not_found(self):
        s = ManualEditSession(Schedule(exams=[]), exam_periods=[_fall()])
        result = s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10))
        assert result.success is False
        assert result.reason == MoveResult.NOT_FOUND

# ===========================================================================
# Critical-conflict semantics (electives vs. mandatory, projects, cohorts)
# ===========================================================================
class TestConflictSemantics:
    def test_two_electives_may_share_a_day_by_default(self):
        e1 = _course("11111", requirement=ELECT)
        e2 = _course("22222", requirement=ELECT)
        s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))])
        _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))
        assert _date_of(s, "22222") == date(2026, 2, 20)

    def test_two_electives_same_day_blocked_when_max_conflicts_zero(self):
        e1 = _course("11111", requirement=ELECT)
        e2 = _course("22222", requirement=ELECT)
        cons = SchedulingConstraints(max_elective_conflicts_enabled=True,
                                     max_elective_conflicts_k=0)
        s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                         MoveResult.CONSTRAINT)

    def test_two_electives_same_day_allowed_when_max_conflicts_one(self):
        e1 = _course("11111", requirement=ELECT)
        e2 = _course("22222", requirement=ELECT)
        cons = SchedulingConstraints(max_elective_conflicts_enabled=True,
                                     max_elective_conflicts_k=1)
        s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
        _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))

    def test_electives_in_different_cohorts_never_conflict_on_a_day(self):
        e1 = _course("11111", program="83101", requirement=ELECT)
        e2 = _course("22222", program="99999", requirement=ELECT)
        cons = SchedulingConstraints(max_elective_conflicts_enabled=True,
                                     max_elective_conflicts_k=0)
        s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
        _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))

    def test_mandatory_onto_mandatory_same_cohort_rejected(self):
        m1, m2 = _course("11111"), _course("22222")
        s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                         MoveResult.CONSTRAINT)

    def test_mandatory_onto_elective_same_cohort_rejected(self):
        m = _course("11111", requirement=OBLIG)
        e = _course("22222", requirement=ELECT)
        s = _session([(m, date(2026, 2, 3)), (e, date(2026, 2, 20))])
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                         MoveResult.CONSTRAINT)

    def test_mandatory_exams_different_cohorts_may_share_a_day(self):
        m1 = _course("11111", program="83101")
        m2 = _course("22222", program="99999")
        s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
        _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))

    def test_project_elective_may_share_day_with_exam_elective(self):
        # evaluation_method differs ("Project" vs "Exam") but both are
        # electives in the same cohort -> still allowed (eval method is
        # irrelevant to the conflict rule, only requirement + cohort matter).
        proj = _course("11111", requirement=ELECT, evaluation="Project")
        exam = _course("22222", requirement=ELECT, evaluation="Exam")
        s = _session([(proj, date(2026, 2, 3)), (exam, date(2026, 2, 20))])
        _assert_accepted(s, "11111", date(2026, 2, 3), date(2026, 2, 20))

    def test_project_mandatory_conflicts_like_any_mandatory(self):
        proj = _course("11111", requirement=OBLIG, evaluation="Project")
        exam = _course("22222", requirement=OBLIG, evaluation="Exam")
        s = _session([(proj, date(2026, 2, 3)), (exam, date(2026, 2, 20))])
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                         MoveResult.CONSTRAINT)

    def test_multi_cohort_course_rejected_if_any_cohort_conflicts(self):
        # Course X belongs to cohort (A,1) and (B,1). Moving it onto a day
        # holding a mandatory of cohort (B,1) must be rejected even though
        # (A,1) is clear.
        x = _multi_course("11111", [("A", 1, OBLIG), ("B", 1, OBLIG)])
        b_mand = _course("22222", program="B", year=1, requirement=OBLIG)
        s = _session([(x, date(2026, 2, 3)), (b_mand, date(2026, 2, 20))])
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                         MoveResult.CONSTRAINT)

# ===========================================================================
# The remaining k-constraints (2.2 / 2.4) gate a move, mirrored from board level
# ===========================================================================
class TestRemainingConstraintsGateMoves:
    def test_min_days_any_gap_blocks_move_for_electives_too(self):
        e1 = _course("11111", requirement=ELECT)
        e2 = _course("22222", requirement=ELECT)
        cons = SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=4)
        s = _session([(e1, date(2026, 2, 3)), (e2, date(2026, 2, 20))], constraints=cons)
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 22),  # 2-day gap < 4
                         MoveResult.CONSTRAINT)

    def test_span_mandatory_blocks_move_that_stretches_window(self):
        m1, m2 = _course("11111"), _course("22222")
        # inclusive span allowed = 7 days. 03 -> 20 stretches span to 18 days.
        cons = SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=7)
        s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 6))], constraints=cons)
        _assert_rejected(s, "11111", date(2026, 2, 3), date(2026, 2, 20),
                         MoveResult.CONSTRAINT)

# ===========================================================================
# Idempotence / signature semantics (has_changes / undo across many moves)
# ===========================================================================
class TestIdempotence:
    def test_moving_there_and_back_clears_has_changes(self):
        m1, m2 = _course("11111"), _course("22222")
        s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
        assert s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 10)).success
        assert s.has_changes() is True
        assert s.move_exam("11111", date(2026, 2, 10), date(2026, 2, 3)).success
        assert s.has_changes() is False  # signature matches the original again

    def test_undo_after_several_moves_restores_everything(self):
        m1, m2 = _course("11111"), _course("22222")
        s = _session([(m1, date(2026, 2, 3)), (m2, date(2026, 2, 20))])
        s.move_exam("11111", date(2026, 2, 3), date(2026, 2, 8))
        s.move_exam("22222", date(2026, 2, 20), date(2026, 2, 25))
        s.undo()
        assert _date_of(s, "11111") == date(2026, 2, 3)
        assert _date_of(s, "22222") == date(2026, 2, 20)
        assert s.has_changes() is False

    def test_undo_with_no_changes_is_safe(self):
        m = _course("11111")
        s = _session([(m, date(2026, 2, 3))])
        s.undo()
        assert _date_of(s, "11111") == date(2026, 2, 3)
        assert s.has_changes() is False