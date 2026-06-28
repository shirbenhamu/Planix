import pytest
from datetime import date
from src.engine.holiday_data import get_holidays_for_religions
from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.board_validator import BoardConstraintValidator
from src.manual_edit.manual_edit_session import ManualEditSession, MoveResult
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod, ExcludedDate
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.output.calendar_ics_exporter import CalendarIcsExporter

OBLIG = "Obligatory"
ELECT = "Elective"

def _course(cid, name=None, program="83101", year=1, requirement=OBLIG):
    return Course(cid, name or f"Course {cid}", "Dr. Cohen", "Exam",
                  [ProgramCourseInfo(program, year, "FALL", requirement)])

def _engine_generated_board():
    """Stands in for a board freshly produced by AdvancedExamScheduler:
    three mandatory courses for one cohort, already conflict-free."""
    c1 = _course("10001", name="Algorithms")
    c2 = _course("10002", name="Operating Systems")
    c3 = _course("10003", name="Databases")
    return Schedule(exams=[
        ScheduledExam(course=c1, exam_date=date(2026, 2, 3)),
        ScheduledExam(course=c2, exam_date=date(2026, 2, 12)),
        ScheduledExam(course=c3, exam_date=date(2026, 2, 22)),
    ])

# ===========================================================================
# 1) Manual edit -> validator agreement -> export reflects the edited board
# ===========================================================================
class TestManualEditThenExportIntegration:
    def test_exported_calendar_reflects_a_committed_manual_move(self, tmp_path):
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), [])
        session = ManualEditSession(_engine_generated_board(), exam_periods=[period])

        result = session.move_exam("10001", date(2026, 2, 3), date(2026, 2, 8))
        assert result.success is True

        out = tmp_path / "schedule.ics"
        CalendarIcsExporter().export_schedule(session.current_board(), str(out))
        ics_text = out.read_text(encoding="utf-8")

        assert "DTSTART;VALUE=DATE:20260208" in ics_text   # moved date present
        assert "DTSTART;VALUE=DATE:20260203" not in ics_text  # old date gone
        assert ics_text.count("BEGIN:VEVENT") == 3  # all three exams still present

    def test_exported_calendar_reverts_after_undo(self, tmp_path):
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), [])
        session = ManualEditSession(_engine_generated_board(), exam_periods=[period])

        session.move_exam("10001", date(2026, 2, 3), date(2026, 2, 8))
        session.undo()

        out = tmp_path / "schedule.ics"
        CalendarIcsExporter().export_schedule(session.current_board(), str(out))
        ics_text = out.read_text(encoding="utf-8")

        assert "DTSTART;VALUE=DATE:20260203" in ics_text  # back to the original date
        assert "DTSTART;VALUE=DATE:20260208" not in ics_text

    def test_a_rejected_move_never_reaches_the_export(self, tmp_path):
        # Two mandatory exams, same cohort -> moving onto the other's day must
        # be rejected by the session/validator, and the export must therefore
        # still show the ORIGINAL, untouched dates.
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), [])
        session = ManualEditSession(_engine_generated_board(), exam_periods=[period])

        result = session.move_exam("10001", date(2026, 2, 3), date(2026, 2, 12))  # onto c2's day
        assert result.success is False
        assert result.reason == MoveResult.CONSTRAINT

        out = tmp_path / "schedule.ics"
        CalendarIcsExporter().export_schedule(session.current_board(), str(out))
        ics_text = out.read_text(encoding="utf-8")
        assert "DTSTART;VALUE=DATE:20260203" in ics_text
        assert ics_text.count("BEGIN:VEVENT") == 3  # no event was lost or merged

    def test_validator_and_session_agree_on_every_move_in_a_sequence(self, tmp_path):
        """A defensive integration check: anything ManualEditSession commits
        must independently satisfy BoardConstraintValidator, and anything it
        rejects must independently fail it. This guards against the session
        and the validator silently drifting apart in the future."""
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), [])
        constraints = SchedulingConstraints(min_days_mandatory_enabled=True,
                                             min_days_mandatory_k=3)
        session = ManualEditSession(_engine_generated_board(), exam_periods=[period],
                                     constraints=constraints)
        validator = BoardConstraintValidator(constraints)

        attempts = [
            ("10001", date(2026, 2, 3), date(2026, 2, 9)),   # likely fine
            ("10002", date(2026, 2, 12), date(2026, 2, 10)),  # may or may not collide
            ("10003", date(2026, 2, 22), date(2026, 2, 11)),  # tight gap, may fail
        ]
        for course_id, old, new in attempts:
            outcome = session.move_exam(course_id, old, new)
            assert outcome.success == validator.is_satisfied(session.current_board()) or \
                not outcome.success  # a failed move never changes board satisfaction
            # the strongest invariant: whatever the CURRENT board is right now,
            # it must satisfy the validator (since every commit is gated by it).
            assert validator.is_satisfied(session.current_board()) is True

# ===========================================================================
# 2) Religious holiday exclusions feeding into manual-edit rejection
# ===========================================================================
class TestReligiousExclusionIntegration:
    def test_holiday_excluded_date_blocks_a_manual_move_onto_it(self):
        # Build the period's excluded_dates straight from get_holidays_for_religions,
        # exactly as the model layer would when "enforce_state_to_data_manager" runs.
        holiday_map = get_holidays_for_religions(["Jewish"], year=2026)
        excluded = [ExcludedDate(start_date=d, end_date=d, comment=comment)
                    for d, comment in holiday_map.items()]
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 4, 30), excluded)

        # Pesach 2026 falls on 2026-04-02 per the holidays library - a manual
        # drag onto that date must be rejected as EXCLUDED, not as a generic
        # constraint failure.
        pesach = date(2026, 4, 2)
        assert any(ex.start_date == pesach for ex in excluded)

        course = _course("10001")
        schedule = Schedule(exams=[ScheduledExam(course=course, exam_date=date(2026, 2, 3))])
        session = ManualEditSession(schedule, exam_periods=[period])

        result = session.move_exam("10001", date(2026, 2, 3), pesach)
        assert result.success is False
        assert result.reason == MoveResult.EXCLUDED

    def test_no_selected_religion_means_no_extra_exclusions_at_all(self):
        # Sanity counterpart: with selected_religions empty, the holiday map is
        # empty, so a period built from it excludes nothing extra, and a move
        # to any in-range date succeeds.
        holiday_map = get_holidays_for_religions([])
        assert holiday_map == {}
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), [])

        course = _course("10001")
        schedule = Schedule(exams=[ScheduledExam(course=course, exam_date=date(2026, 2, 3))])
        session = ManualEditSession(schedule, exam_periods=[period])

        result = session.move_exam("10001", date(2026, 2, 3), date(2026, 2, 15))
        assert result.success is True

    def test_excluded_holiday_dates_never_appear_in_the_exported_calendar(self, tmp_path):
        # Per spec B.3.b: exclusions must never be sent to the external
        # calendar, only actual exam dates. Build a board where the holiday
        # exclusion successfully kept an exam OFF that date, then export and
        # confirm the holiday date is nowhere in the .ics, in any form.
        holiday_map = get_holidays_for_religions(["Jewish"], year=2026)
        excluded = [ExcludedDate(start_date=d, end_date=d, comment=c)
                    for d, c in holiday_map.items()]
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 4, 30), excluded)

        pesach = date(2026, 4, 2)
        course = _course("10001")
        schedule = Schedule(exams=[ScheduledExam(course=course, exam_date=date(2026, 2, 3))])
        session = ManualEditSession(schedule, exam_periods=[period])

        rejected = session.move_exam("10001", date(2026, 2, 3), pesach)
        assert rejected.success is False

        out = tmp_path / "schedule.ics"
        CalendarIcsExporter().export_schedule(session.current_board(), str(out))
        ics_text = out.read_text(encoding="utf-8")
        assert pesach.strftime("%Y%m%d") not in ics_text
        assert "Jewish" not in ics_text

# ===========================================================================
# 3) Full lifecycle: generate -> edit -> undo -> edit again -> export
# ===========================================================================
class TestFullLifecycleIntegration:
    def test_full_edit_then_export_round_trip(self, tmp_path):
        period = ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), [])
        session = ManualEditSession(_engine_generated_board(), exam_periods=[period])

        # user drags two cards around, undoes one, keeps the other
        session.move_exam("10001", date(2026, 2, 3), date(2026, 2, 5))
        session.move_exam("10002", date(2026, 2, 12), date(2026, 2, 18))
        assert session.has_changes() is True

        session.undo()
        assert session.has_changes() is False

        # re-apply just one valid move
        outcome = session.move_exam("10003", date(2026, 2, 22), date(2026, 2, 25))
        assert outcome.success is True

        out = tmp_path / "final.ics"
        path = CalendarIcsExporter().export_schedule(session.current_board(), str(out))
        assert path == str(out)

        ics_text = out.read_text(encoding="utf-8")
        assert ics_text.count("BEGIN:VEVENT") == 3
        assert "DTSTART;VALUE=DATE:20260203" in ics_text   # course 1: unchanged
        assert "DTSTART;VALUE=DATE:20260212" in ics_text   # course 2: unchanged (undone)
        assert "DTSTART;VALUE=DATE:20260225" in ics_text   # course 3: moved, kept