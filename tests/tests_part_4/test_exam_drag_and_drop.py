import pytest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.manual_edit_session import ManualEditSession, MoveResult
from src.manual_edit.board_validator import BoardConstraintValidator
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod, ExcludedDate
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.presenters.calendar_presenter import CalendarPresenter

PROGRAM = "83108"

# ===========================================================================
# Builders
# ===========================================================================
def course(cid, requirement="Obligatory", year=1):
    info = [ProgramCourseInfo(program_id=PROGRAM, year=year, semester="FALL", requirement=requirement)]
    return Course(cid, f"C{cid}", "Teacher", "Exam", info)

def exam(cid, day, requirement="Obligatory", year=1):
    return ScheduledExam(course=course(cid, requirement, year), exam_date=date(2026, 1, day))

def period(excluded=None):
    return ExamPeriod(
        semester="FALL", moed="Aleph",
        start_date=date(2026, 1, 1), end_date=date(2026, 1, 31),
        excluded_dates=excluded or [],
    )

def constraints(**kw):
    return SchedulingConstraints(**kw)

# ===========================================================================
# 1. ManualEditSession — successful move
# ===========================================================================
class TestManualEditMoveSuccess:
    def _session(self):
        schedule = Schedule(exams=[exam("10001", 1), exam("10002", 10)])
        return ManualEditSession(schedule, [period()], constraints())

    def test_valid_move_updates_current_board(self):
        s = self._session()
        result = s.move_exam("10001", date(2026, 1, 1), date(2026, 1, 5))
        assert result.success
        dates = {(e.course.course_id, e.exam_date) for e in s.current_board().exams}
        assert ("10001", date(2026, 1, 5)) in dates
        assert s.has_changes() is True

    def test_original_board_is_not_mutated_by_a_move(self):
        s = self._session()
        s.move_exam("10001", date(2026, 1, 1), date(2026, 1, 5))
        original = {(e.course.course_id, e.exam_date) for e in s.original_board().exams}
        assert ("10001", date(2026, 1, 1)) in original  # original keeps the old date

    def test_no_op_drop_onto_same_date(self):
        s = self._session()
        result = s.move_exam("10001", date(2026, 1, 1), date(2026, 1, 1))
        assert result.success and result.reason == ""
        assert s.has_changes() is False

    def test_can_move_does_not_commit(self):
        s = self._session()
        assert s.can_move("10001", date(2026, 1, 1), date(2026, 1, 5)).success
        assert s.has_changes() is False  # validation only, board untouched

# ===========================================================================
# 2. ManualEditSession — rejections (each yields a silent snap-back)
# ===========================================================================
class TestManualEditRejections:
    def _session(self, excluded=None, cons=None):
        schedule = Schedule(exams=[exam("10001", 1), exam("10002", 10)])
        return ManualEditSession(schedule, [period(excluded)], cons or constraints())

    def test_exam_not_found(self):
        s = self._session()
        r = s.move_exam("NOPE", date(2026, 1, 1), date(2026, 1, 5))
        assert not r.success and r.reason == MoveResult.NOT_FOUND

    def test_out_of_semester(self):
        s = self._session()
        r = s.move_exam("10001", date(2026, 1, 1), date(2026, 2, 15))  # outside the period
        assert not r.success and r.reason == MoveResult.OUT_OF_SEMESTER

    def test_excluded_target_date(self):
        excl = ExcludedDate(start_date=date(2026, 1, 5), end_date=date(2026, 1, 5), comment="holiday")
        s = self._session(excluded=[excl])
        r = s.move_exam("10001", date(2026, 1, 1), date(2026, 1, 5))
        assert not r.success and r.reason == MoveResult.EXCLUDED

    def test_constraint_violation_critical_conflict(self):
        # Two mandatory exams, same program & year -> may not share a day.
        s = self._session()
        r = s.move_exam("10001", date(2026, 1, 1), date(2026, 1, 10))  # onto 10002's day
        assert not r.success and r.reason == MoveResult.CONSTRAINT
        # board unchanged after a rejected move
        assert ("10001", date(2026, 1, 1)) in {(e.course.course_id, e.exam_date) for e in s.current_board().exams}

    def test_constraint_violation_min_days(self):
        s = self._session(cons=constraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5))
        # Moving 10001 to Jan 7 leaves only 3 days before 10002 (Jan 10) -> < k.
        r = s.move_exam("10001", date(2026, 1, 1), date(2026, 1, 7))
        assert not r.success and r.reason == MoveResult.CONSTRAINT

    def test_rejected_move_keeps_has_changes_false(self):
        s = self._session()
        s.move_exam("10001", date(2026, 1, 1), date(2026, 2, 15))  # rejected
        assert s.has_changes() is False

# ===========================================================================
# 3. ManualEditSession — undo
# ===========================================================================
class TestManualEditUndo:
    def test_undo_restores_original_board(self):
        schedule = Schedule(exams=[exam("10001", 1), exam("10002", 10)])
        s = ManualEditSession(schedule, [period()], constraints())
        s.move_exam("10001", date(2026, 1, 1), date(2026, 1, 5))
        assert s.has_changes() is True

        s.undo()

        assert s.has_changes() is False
        dates = {(e.course.course_id, e.exam_date) for e in s.current_board().exams}
        assert ("10001", date(2026, 1, 1)) in dates  # back to the engine board

# ===========================================================================
# 4. BoardConstraintValidator — whole-board checks
# ===========================================================================
class TestBoardValidator:
    def test_empty_constraints_satisfied(self):
        board = Schedule(exams=[exam("10001", 1), exam("10002", 10)])
        assert BoardConstraintValidator(constraints()).is_satisfied(board)

    def test_two_mandatory_same_day_is_critical_conflict(self):
        board = Schedule(exams=[exam("10001", 5), exam("10002", 5)])  # same cohort, same day
        assert "critical_conflict" in BoardConstraintValidator(constraints()).violations(board)

    def test_two_electives_same_day_allowed(self):
        board = Schedule(exams=[exam("10001", 5, "Elective"), exam("10002", 5, "Elective")])
        assert BoardConstraintValidator(constraints()).violations(board) == []

    def test_min_days_mandatory_violation(self):
        board = Schedule(exams=[exam("10001", 1), exam("10002", 3)])  # 2 days apart
        v = BoardConstraintValidator(constraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5))
        assert "min_days_mandatory" in v.violations(board)

    def test_min_days_any_violation(self):
        board = Schedule(exams=[exam("10001", 1, "Elective"), exam("10002", 3, "Elective")])
        v = BoardConstraintValidator(constraints(min_days_any_enabled=True, min_days_any_k=5))
        assert "min_days_any" in v.violations(board)

    def test_span_mandatory_violation(self):
        board = Schedule(exams=[exam("10001", 1), exam("10002", 25)])  # span 25 days
        v = BoardConstraintValidator(constraints(span_mandatory_enabled=True, span_mandatory_k=10))
        assert "span_mandatory" in v.violations(board)

    def test_max_exams_per_day_violation(self):
        # 3 electives on the same day (allowed by critical-conflict, but > k=2 total/day)
        board = Schedule(exams=[exam("1", 5, "Elective"), exam("2", 5, "Elective"), exam("3", 5, "Elective")])
        v = BoardConstraintValidator(constraints(max_exams_per_day_enabled=True, max_exams_per_day_k=2))
        assert "max_exams_per_day" in v.violations(board)

    def test_max_elective_conflicts_violation(self):
        board = Schedule(exams=[exam("1", 5, "Elective"), exam("2", 5, "Elective")])  # 1 pair same day
        v = BoardConstraintValidator(constraints(max_elective_conflicts_enabled=True, max_elective_conflicts_k=0))
        assert "max_elective_conflicts" in v.violations(board)

    def test_disabled_constraints_are_skipped(self):
        board = Schedule(exams=[exam("10001", 1), exam("10002", 3)])  # close, but checks disabled
        assert BoardConstraintValidator(constraints()).is_satisfied(board)

# ===========================================================================
# 5. CalendarPresenter drag handlers
# ===========================================================================
class TestPresenterDragHandlers:
    def _presenter(self):
        view = MagicMock()
        view.active_month_indices = []
        model = MagicMock()
        model.get_user_excluded_dates.return_value = []
        model.get_exam_periods.return_value = []
        model.get_selected_programs.return_value = []
        model.data_manager.get_courses.return_value = []
        collection = MagicMock()
        collection.get_total_count.return_value = 0
        collection.get_current_index.return_value = 0
        return CalendarPresenter(view, model, collection), view

    def test_drag_callbacks_are_wired_on_init(self):
        presenter, view = self._presenter()
        # The presenter binds the view's drag hooks to its own handlers.
        assert view.on_exam_dropped == presenter._handle_exam_dropped
        assert view.on_drag_validate == presenter._validate_drop
        assert view.on_undo_clicked == presenter._handle_undo

    def test_valid_drop_commits_and_refreshes(self):
        presenter, _ = self._presenter()
        presenter.cell_to_date_mapping = {"1-0": date(2026, 1, 1), "1-4": date(2026, 1, 5)}
        presenter._edit_session = MagicMock()
        presenter._edit_session.move_exam.return_value = SimpleNamespace(success=True, reason="")
        with patch.object(presenter, "_active_board"), patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_exam_dropped("10001", "1-0", "1-4")
        presenter._edit_session.move_exam.assert_called_once_with("10001", date(2026, 1, 1), date(2026, 1, 5))
        refresh.assert_called_once()

    def test_rejected_drop_still_refreshes_to_snap_back(self):
        presenter, _ = self._presenter()
        presenter.cell_to_date_mapping = {"1-0": date(2026, 1, 1), "1-4": date(2026, 1, 5)}
        presenter._edit_session = MagicMock()
        presenter._edit_session.move_exam.return_value = SimpleNamespace(
            success=False, reason=MoveResult.CONSTRAINT)
        with patch.object(presenter, "_active_board"), patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_exam_dropped("10001", "1-0", "1-4")
        refresh.assert_called_once()  # redraw -> card snaps back, no error dialog

    def test_drop_with_unmapped_cell_snaps_back_without_moving(self):
        presenter, _ = self._presenter()
        presenter.cell_to_date_mapping = {"1-0": date(2026, 1, 1)}  # target not mapped
        presenter._edit_session = MagicMock()
        with patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_exam_dropped("10001", "1-0", "9-9")
        presenter._edit_session.move_exam.assert_not_called()
        refresh.assert_called_once()

    def test_validate_drop_returns_can_move_result(self):
        presenter, _ = self._presenter()
        presenter.cell_to_date_mapping = {"1-0": date(2026, 1, 1), "1-4": date(2026, 1, 5)}
        presenter._edit_session = MagicMock()
        presenter._edit_session.can_move.return_value = SimpleNamespace(success=True)
        with patch.object(presenter, "_active_board"):
            assert presenter._validate_drop("10001", "1-0", "1-4") is True
        presenter._edit_session.can_move.return_value = SimpleNamespace(success=False)
        with patch.object(presenter, "_active_board"):
            assert presenter._validate_drop("10001", "1-0", "1-4") is False

    def test_validate_drop_false_for_unmapped_cells(self):
        presenter, _ = self._presenter()
        presenter.cell_to_date_mapping = {}
        assert presenter._validate_drop("10001", "x", "y") is False

    def test_undo_reverts_session_and_refreshes(self):
        presenter, _ = self._presenter()
        presenter._edit_session = MagicMock()
        with patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_undo()
        presenter._edit_session.undo.assert_called_once()
        refresh.assert_called_once()

    def test_undo_with_no_session_is_safe(self):
        presenter, _ = self._presenter()
        presenter._edit_session = None
        with patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_undo()  # must not raise
        refresh.assert_called_once()

    def test_sync_undo_state_enables_button_only_with_changes(self):
        presenter, view = self._presenter()
        presenter._edit_session = MagicMock()
        presenter._edit_session.has_changes.return_value = True
        presenter._sync_undo_state()
        view.set_undo_enabled.assert_called_with(True)

        presenter._edit_session.has_changes.return_value = False
        presenter._sync_undo_state()
        view.set_undo_enabled.assert_called_with(False)

    def test_sync_undo_state_disabled_without_session(self):
        presenter, view = self._presenter()
        presenter._edit_session = None
        presenter._sync_undo_state()
        view.set_undo_enabled.assert_called_with(False)