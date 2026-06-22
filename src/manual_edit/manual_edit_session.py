from __future__ import annotations

# ManualEditSession (PLAN-558)
#
# Holds the two in-memory copies the manual drag & drop feature needs:
#   * the ORIGINAL board, exactly as produced by the engine, and
#   * the CURRENT board, reflecting the user's manual moves.
#
# A move is committed only when it passes, in order (PLAN-561):
#   1. it stays inside the exam's ORIGINAL semester (the period holding it),
#   2. the target date is not excluded, and
#   3. the resulting board still satisfies the active k-constraints (PLAN-559).
# Otherwise the move is rejected so the view can snap the card back, with no
# error dialog. `undo()` restores the current board to the original (PLAN-563).

from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from src.engine.scheduling_constraints import SchedulingConstraints
from src.manual_edit.board_validator import BoardConstraintValidator
from src.MVP.models.schedule import Schedule, ScheduledExam


@dataclass(frozen=True)
class MoveResult:
    """Outcome of a drag & drop. On failure `reason` says why (for tests/logging);
    the view treats every failure the same way — a silent snap-back."""
    success: bool
    reason: str = ""

    OUT_OF_SEMESTER = "out_of_semester"
    EXCLUDED = "excluded_date"
    OCCUPIED = "date_occupied"           # constraint/critical-conflict at the target
    NOT_FOUND = "exam_not_found"
    CONSTRAINT = "constraint_violation"


class ManualEditSession:
    def __init__(
        self,
        schedule: Schedule,
        exam_periods=None,
        constraints: Optional[SchedulingConstraints] = None,
    ):
        self._original = self._copy(schedule)
        self._current = self._copy(schedule)
        self._periods = list(exam_periods or [])
        self._validator = BoardConstraintValidator(constraints)

    # --- public API ---------------------------------------------------------
    def current_board(self) -> Schedule:
        return self._current

    def original_board(self) -> Schedule:
        return self._original

    def has_changes(self) -> bool:
        return self._signature(self._current) != self._signature(self._original)

    # Attempts to move the exam of `course_id` currently on `old_date` to
    # `new_date`. Returns a MoveResult; the current board is only mutated on
    # success.
    def move_exam(self, course_id: str, old_date: date, new_date: date) -> MoveResult:
        result, candidate = self._evaluate_move(course_id, old_date, new_date)
        if result.success and candidate is not None:
            self._current = candidate
        return result

    # Validates a move WITHOUT committing it — used for live drag feedback so the
    # view can colour a target cell green/red before the user releases.
    def can_move(self, course_id: str, old_date: date, new_date: date) -> MoveResult:
        return self._evaluate_move(course_id, old_date, new_date)[0]

    def _evaluate_move(self, course_id: str, old_date: date, new_date: date):
        if new_date == old_date:
            return MoveResult(True), None  # no-op drop back onto the same cell

        index = self._find_exam_index(course_id, old_date)
        if index is None:
            return MoveResult(False, MoveResult.NOT_FOUND), None

        # 1. Must stay within the exam's original semester (its period).
        period = self._period_containing(old_date)
        if period is None or not (period.start_date <= new_date <= period.end_date):
            return MoveResult(False, MoveResult.OUT_OF_SEMESTER), None

        # 2. Target date must not be excluded.
        if new_date not in set(period.get_available_dates()):
            return MoveResult(False, MoveResult.EXCLUDED), None

        # 3. The resulting board must still be valid (base rule + active k-checks).
        candidate = self._copy(self._current)
        candidate.exams[index].exam_date = new_date
        if not self._validator.is_satisfied(candidate):
            return MoveResult(False, MoveResult.CONSTRAINT), None

        return MoveResult(True), candidate

    # Reverts every manual change, restoring the original engine board (PLAN-563).
    def undo(self) -> Schedule:
        self._current = self._copy(self._original)
        return self._current

    # --- helpers ------------------------------------------------------------
    def _find_exam_index(self, course_id: str, on_date: date) -> Optional[int]:
        for index, exam in enumerate(self._current.exams):
            if exam.course.course_id == course_id and exam.exam_date == on_date:
                return index
        return None

    def _period_containing(self, day: date):
        for period in self._periods:
            if period.start_date <= day <= period.end_date:
                return period
        return None

    @staticmethod
    def _copy(schedule: Schedule) -> Schedule:
        # Shallow-copy the exams (new ScheduledExam wrappers, shared immutable
        # Course objects) so edits never leak between the original and current.
        return Schedule(
            exams=[
                ScheduledExam(course=exam.course, exam_date=exam.exam_date)
                for exam in (getattr(schedule, "exams", []) or [])
            ]
        )

    @staticmethod
    def _signature(schedule: Schedule) -> List[tuple]:
        return sorted(
            (exam.course.course_id, exam.exam_date) for exam in schedule.exams
        )
