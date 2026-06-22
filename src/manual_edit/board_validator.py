from __future__ import annotations

# BoardConstraintValidator (PLAN-559)
#
# Validates a COMPLETE schedule board against the five section-2 threshold
# (k-) constraints. Manual drag & drop edits the board in place, so unlike the
# engine (which checks constraints incrementally while generating), this checks
# a whole, already-formed board after a move.
#
# The check semantics intentionally mirror AdvancedExamScheduler so that a board
# produced by the engine under a given SchedulingConstraints always passes here:
#   2.1 min days between mandatory exams (same program & year)  >= k
#   2.2 min days between ANY two exams   (same program & year)  >= k
#   2.3 elective-elective same-day conflicts (same program & year) <= k
#   2.4 span first->last mandatory exam  (same program & year)  <= k  (inclusive)
#   2.5 max exams on a single day                                <= k
#
# It depends only on the domain models + SchedulingConstraints — no engine, no UI.

from itertools import combinations
from typing import Dict, List, Tuple

from src.engine.scheduling_constraints import SchedulingConstraints
from src.MVP.models.schedule import Schedule, ScheduledExam

_ELECTIVE = "Elective"


class BoardConstraintValidator:
    """Whole-board validator for the five enabled k-constraints."""

    def __init__(self, constraints: SchedulingConstraints = None):
        self.constraints = constraints if constraints is not None else SchedulingConstraints()

    # Returns True only if the board satisfies every ENABLED constraint. Disabled
    # constraints are skipped, exactly like the engine.
    def is_satisfied(self, schedule: Schedule) -> bool:
        return not self.violations(schedule)

    # Returns the list of violated constraint keys (empty == valid). Useful for
    # tests and for explaining a snap-back, without raising.
    def violations(self, schedule: Schedule) -> List[str]:
        exams = list(getattr(schedule, "exams", []) or [])
        c = self.constraints
        failed: List[str] = []

        # Always enforced (the V1.0 base rule, independent of the k-constraints):
        # no two conflicting exams may share a day. Two exams conflict when they
        # share a (program, year) cohort and are not both electives — so a manual
        # move can never stack a mandatory exam onto a busy day for its cohort.
        if not self._no_critical_conflict(exams):
            failed.append("critical_conflict")

        if c.min_days_mandatory_enabled and not self._min_gap_ok(
            exams, c.min_days_mandatory_k, mandatory_only=True
        ):
            failed.append("min_days_mandatory")

        if c.min_days_any_enabled and not self._min_gap_ok(
            exams, c.min_days_any_k, mandatory_only=False
        ):
            failed.append("min_days_any")

        if c.max_elective_conflicts_enabled and not self._elective_conflicts_ok(
            exams, c.max_elective_conflicts_k
        ):
            failed.append("max_elective_conflicts")

        if c.span_mandatory_enabled and not self._span_ok(exams, c.span_mandatory_k):
            failed.append("span_mandatory")

        if c.max_exams_per_day_enabled and not self._max_per_day_ok(
            exams, c.max_exams_per_day_k
        ):
            failed.append("max_exams_per_day")

        return failed

    # --- per-constraint checks (board level) --------------------------------
    # 2.1 / 2.2: every pair of exam dates within a (program, year) cohort must be
    # at least k days apart (mandatory-only for 2.1, all exams for 2.2).
    def _min_gap_ok(self, exams, k: int, mandatory_only: bool) -> bool:
        for dates in self._dates_by_program_year(exams, mandatory_only).values():
            for earlier, later in combinations(sorted(dates), 2):
                if (later - earlier).days < k:
                    return False
        return True

    # 2.3: in each (program, year) cohort, the number of elective-elective pairs
    # sharing a day must not exceed k.
    def _elective_conflicts_ok(self, exams, k: int) -> bool:
        # (program, year) -> date -> set of elective course ids
        cohorts: Dict[Tuple[str, int], Dict[object, set]] = {}
        for exam in exams:
            for info in exam.course.program_info:
                if info.requirement != _ELECTIVE:
                    continue
                cohorts.setdefault((info.program_id, info.year), {}).setdefault(
                    exam.exam_date, set()
                ).add(exam.course.course_id)

        for by_date in cohorts.values():
            conflicts = 0
            for course_ids in by_date.values():
                n = len(course_ids)
                conflicts += n * (n - 1) // 2
            if conflicts > k:
                return False
        return True

    # 2.4: the inclusive span (max - min + 1 days) of mandatory exams in each
    # (program, year) cohort must not exceed k (matches the engine's +1 span).
    def _span_ok(self, exams, k: int) -> bool:
        for dates in self._dates_by_program_year(exams, mandatory_only=True).values():
            if len(dates) < 2:
                continue
            span = (max(dates) - min(dates)).days + 1
            if span > k:
                return False
        return True

    # 2.5: no calendar day may hold more than k exams.
    def _max_per_day_ok(self, exams, k: int) -> bool:
        counts: Dict[object, int] = {}
        for exam in exams:
            counts[exam.exam_date] = counts.get(exam.exam_date, 0) + 1
            if counts[exam.exam_date] > k:
                return False
        return True

    # Base V1.0 rule: no two conflicting exams on the same day. Two exams on the
    # same date conflict if they share a (program, year) cohort in which they are
    # not both electives.
    def _no_critical_conflict(self, exams) -> bool:
        by_date: Dict[object, List[ScheduledExam]] = {}
        for exam in exams:
            by_date.setdefault(exam.exam_date, []).append(exam)

        for same_day in by_date.values():
            for first, second in combinations(same_day, 2):
                if self._exams_conflict(first, second):
                    return False
        return True

    def _exams_conflict(self, first: ScheduledExam, second: ScheduledExam) -> bool:
        for a in first.course.program_info:
            for b in second.course.program_info:
                if a.program_id == b.program_id and a.year == b.year:
                    both_elective = a.requirement == _ELECTIVE and b.requirement == _ELECTIVE
                    if not both_elective:
                        return True
        return False

    # --- shared grouping ----------------------------------------------------
    def _dates_by_program_year(
        self, exams: List[ScheduledExam], mandatory_only: bool
    ) -> Dict[Tuple[str, int], List[object]]:
        groups: Dict[Tuple[str, int], List[object]] = {}
        for exam in exams:
            for info in exam.course.program_info:
                if mandatory_only and info.requirement == _ELECTIVE:
                    continue
                groups.setdefault((info.program_id, info.year), []).append(exam.exam_date)
        return groups
