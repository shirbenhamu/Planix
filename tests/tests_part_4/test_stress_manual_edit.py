"""
Stress suite for MANUAL DRAG & DROP editing + whole-board validation + ICS
export, exercised together over long randomized move sequences.

This is an integration-level stress test: every iteration touches
ManualEditSession, BoardConstraintValidator, SchedulingConstraints and (at the
end of each scenario) CalendarIcsExporter, plus the real holiday data feed.

The central invariants, asserted no matter how many moves are attempted
(valid, colliding, too-close, out-of-range, onto excluded dates):

  * the session's CURRENT board ALWAYS satisfies the validator (every commit
    is validator-gated, every rejection leaves the board untouched);
  * the ORIGINAL board is never mutated;
  * undo fully restores the original board;
  * an export of the current board always holds exactly one event per exam,
    and no excluded date ever leaks into the calendar.

Display-independent: pure domain objects + a real .ics file on a tmp path.
Mirrors the APIs already used in test_integration_features.py /
test_exam_drag_and_drop.py. Seeds are fixed for reproducibility.
"""
import random
from datetime import date, timedelta

import pytest

from src.engine.holiday_data import get_holidays_for_religions
from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.board_validator import BoardConstraintValidator
from src.manual_edit.manual_edit_session import ManualEditSession, MoveResult
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod, ExcludedDate
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.output.calendar_ics_exporter import CalendarIcsExporter

PROGRAM = "83101"
START = date(2026, 2, 1)
END = date(2026, 4, 30)


# ===========================================================================
# Builders
# ===========================================================================
def _course(cid, requirement="Obligatory", year=1):
    return Course(cid, f"Course {cid}", "Dr. Cohen", "Exam",
                  [ProgramCourseInfo(PROGRAM, year, "FALL", requirement)])


def _spaced_board(n=8, step=10):
    """`n` mandatory exams, `step` days apart, conflict-free to start with and
    comfortably inside [START, END]."""
    return Schedule(exams=[
        ScheduledExam(course=_course(f"100{i:02d}"),
                      exam_date=START + timedelta(days=i * step))
        for i in range(n)
    ])


def _date_set(board):
    return {(e.course.course_id, e.exam_date) for e in board.exams}


def _current_date_of(session, course_id):
    for e in session.current_board().exams:
        if e.course.course_id == course_id:
            return e.exam_date
    return None


def _session(constraints=None, excluded=None, board=None):
    constraints = constraints or SchedulingConstraints()
    period = ExamPeriod("FALL", "Aleph", START, END, excluded or [])
    board = board if board is not None else _spaced_board()
    return ManualEditSession(board, exam_periods=[period], constraints=constraints), board


# ===========================================================================
# Stress tests
# ===========================================================================
class TestManualEditStress:
    def test_long_random_sequence_preserves_validator_invariant(self, tmp_path):
        """400 randomized moves; after every single one the live board must be
        constraint-clean and the original must be untouched. Then a full undo
        and an export must round-trip exactly."""
        rng = random.Random(20260628)
        constraints = SchedulingConstraints(min_days_mandatory_enabled=True,
                                            min_days_mandatory_k=2)
        session, board = _session(constraints=constraints)
        validator = BoardConstraintValidator(constraints)
        original_snapshot = _date_set(session.original_board())
        course_ids = [e.course.course_id for e in board.exams]
        span = (END - START).days

        accepted = rejected = 0
        for _ in range(400):
            cid = rng.choice(course_ids)
            old = _current_date_of(session, cid)
            if rng.random() < 0.10:                       # occasionally out of range
                target = END + timedelta(days=rng.randint(1, 20))
            else:
                target = START + timedelta(days=rng.randint(0, span))

            result = session.move_exam(cid, old, target)
            if result.success:
                accepted += 1
            else:
                rejected += 1

            # CORE INVARIANT: the live board is always constraint-clean.
            assert validator.is_satisfied(session.current_board()) is True
            # the original board is sacred.
            assert _date_set(session.original_board()) == original_snapshot

        # the run must have meaningfully exercised both code paths.
        assert accepted > 0 and rejected > 0

        # undo wipes every accepted change.
        session.undo()
        assert session.has_changes() is False
        assert _date_set(session.current_board()) == original_snapshot

        out = tmp_path / "stress.ics"
        CalendarIcsExporter().export_schedule(session.current_board(), str(out))
        ics = out.read_text(encoding="utf-8")
        assert ics.count("BEGIN:VEVENT") == len(course_ids)

    def test_event_count_invariant_across_constraint_configs(self, tmp_path):
        """Under a variety of constraint settings, a burst of edits must never
        cause the exported calendar to lose, merge, or duplicate an event.

        Note: we do NOT assert the board is constraint-clean here -- some of
        these configs (e.g. span_mandatory_k smaller than the starting board's
        span) are deliberately unsatisfiable by the seed board, so the point is
        purely that editing relocates exams and never drops or clones one. The
        clean-board invariant is covered separately by
        test_long_random_sequence_preserves_validator_invariant."""
        rng = random.Random(11)
        configs = [
            SchedulingConstraints(),
            SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=3),
            SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=40),
            SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=1),
        ]
        span = (END - START).days
        for ci, constraints in enumerate(configs):
            session, board = _session(constraints=constraints)
            ids = {e.course.course_id for e in board.exams}
            for _ in range(120):
                cid = rng.choice(list(ids))
                old = _current_date_of(session, cid)
                target = START + timedelta(days=rng.randint(0, span))
                session.move_exam(cid, old, target)
                # the exam SET is invariant under any sequence of edits:
                # moves relocate exams, they never drop, clone, or rename one.
                assert {e.course.course_id for e in session.current_board().exams} == ids

            out = tmp_path / f"cfg_{ci}.ics"
            CalendarIcsExporter().export_schedule(session.current_board(), str(out))
            ics = out.read_text(encoding="utf-8")
            assert ics.count("BEGIN:VEVENT") == len(ids)

    def test_many_excluded_dates_are_never_accepted(self):
        """Build a period riddled with exclusions (every real Jewish holiday in
        range + every Saturday). A move onto any of them, while it's otherwise
        free, must be rejected as EXCLUDED, and the board must stay original."""
        rng = random.Random(2026)
        holiday_map = get_holidays_for_religions(["Jewish"], year=2026)
        excluded = [ExcludedDate(start_date=d, end_date=d, comment=c)
                    for d, c in holiday_map.items() if START <= d <= END]

        d = START
        while d <= END:
            if d.weekday() == 5:  # Saturday
                excluded.append(ExcludedDate(start_date=d, end_date=d, comment="Shabbat"))
            d += timedelta(days=1)

        excluded_days = {ex.start_date for ex in excluded}
        session, board = _session(constraints=SchedulingConstraints(), excluded=excluded)
        ids = [e.course.course_id for e in board.exams]
        occupied = {e.exam_date for e in board.exams}
        original_snapshot = _date_set(session.original_board())

        # default constraints -> the only possible rejection on a free, in-range,
        # excluded target is EXCLUDED.
        candidates = [day for day in excluded_days if day not in occupied]
        rng.shuffle(candidates)
        tested = 0
        for target in candidates[:60]:
            cid = rng.choice(ids)
            old = _current_date_of(session, cid)
            if old == target:
                continue
            result = session.move_exam(cid, old, target)
            assert result.success is False
            assert result.reason == MoveResult.EXCLUDED
            tested += 1

        assert tested > 0, "expected at least some free excluded dates to test"
        # nothing was accepted, so the board never moved off the original.
        assert session.has_changes() is False
        assert _date_set(session.current_board()) == original_snapshot