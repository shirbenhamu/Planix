from __future__ import annotations

# MetricsCalculator (PLAN-408)
#
# Computes the five scoring dimensions defined in section 3 of the V3 (3.0+4.0)
# requirements document, for a single fully-formed Schedule.
#
# Design constraints from the epic / subtasks:
#   PLAN-483: this module computes ALL five metrics.
#   PLAN-484: a single yield-based entry point (`calculate`) takes a Schedule and
#             yields its five metric values, in a fixed canonical order.
#   PLAN-485: ZERO dependencies on the scheduler internals. We import only the
#             shared domain models (Schedule / Course); we do NOT import anything
#             from src.engine, and we re-implement the elective-collision logic
#             locally so the calculator stays fully decoupled from how schedules
#             are generated.

import math
from dataclasses import dataclass
from itertools import combinations
from typing import Dict, Iterator, List, Tuple

from src.MVP.models.schedule import Schedule, ScheduledExam

# A course's program_info entry whose requirement equals this string is an
# elective; anything else is treated as mandatory (the engine uses the same
# "== Elective" test, but we keep our own copy to honour PLAN-485).
_ELECTIVE_REQUIREMENT = "Elective"

# Canonical order of the five metric values yielded by MetricsCalculator.calculate.
# Downstream code (METRICS line writer, sparse index, sorter) relies on this order.
METRIC_KEYS: Tuple[str, ...] = (
    "min_gap_mandatory",     # 3.1
    "avg_gap_all",           # 3.2
    "elective_conflicts",    # 3.3
    "mandatory_span",        # 3.4
    "max_exams_per_day",     # 3.5
)

# Human-readable labels keyed by metric key, used later by the GUI / file mode.
METRIC_LABELS: Dict[str, str] = {
    "min_gap_mandatory": "Min days between mandatory exams (same program & year)",
    "avg_gap_all": "Average days between exams (same program & year)",
    "elective_conflicts": "Elective-elective collisions (same program)",
    "mandatory_span": "Span between first & last mandatory exam (same program & year)",
    "max_exams_per_day": "Maximum exams scheduled on a single day",
}

# --- METRICS line wire format (PLAN-409) ------------------------------------
# Each schedule block in the output file is followed by a single line of the
# form "METRICS|v1|v2|v3|v4|v5", matching METRIC_KEYS order. Positions 1-3 are
# written as floats and positions 4-5 as integers (per the acceptance criteria);
# a non-finite sentinel (e.g. +inf for "no applicable pair") is written via repr
# so it round-trips through float(). This module owns the format so the writer
# (PLAN-409) and the sparse index parser (PLAN-410) share one source of truth.
METRICS_LINE_PREFIX = "METRICS"

# 0-based positions that are serialized as integers rather than floats.
_INTEGER_METRIC_POSITIONS = frozenset({3, 4})  # mandatory_span, max_exams_per_day


def format_metrics_line(metrics: "ScheduleMetrics") -> str:
    """Render a ScheduleMetrics as a single 'METRICS|...' output line (no newline)."""
    parts: List[str] = []
    for position, value in enumerate(metrics.as_tuple()):
        numeric = float(value)
        if position in _INTEGER_METRIC_POSITIONS and math.isfinite(numeric):
            parts.append(str(int(numeric)))
        else:
            parts.append(repr(numeric))
    return METRICS_LINE_PREFIX + "|" + "|".join(parts)


def is_metrics_line(line: str) -> bool:
    return line.strip().startswith(METRICS_LINE_PREFIX + "|")


def parse_metrics_line(line: str) -> "ScheduleMetrics":
    """Parse a 'METRICS|...' line back into a ScheduleMetrics (inverse of format)."""
    text = line.strip()
    if not is_metrics_line(text):
        raise ValueError(f"Not a METRICS line: {line!r}")

    payload = text[len(METRICS_LINE_PREFIX) + 1:]
    parts = payload.split("|")
    if len(parts) != len(METRIC_KEYS):
        raise ValueError(
            f"Expected {len(METRIC_KEYS)} metric values, got {len(parts)} in {line!r}."
        )
    return ScheduleMetrics.from_iterable(float(part) for part in parts)


@dataclass(frozen=True)
class ScheduleMetrics:
    """The five scoring dimensions of a single schedule (section 3)."""

    min_gap_mandatory: float      # 3.1 — higher is better (more breathing room)
    avg_gap_all: float            # 3.2 — higher is better
    elective_conflicts: float     # 3.3 — count of elective same-day collisions
    mandatory_span: float         # 3.4 — span in days between first/last mandatory exam
    max_exams_per_day: float      # 3.5 — busiest single day

    def as_tuple(self) -> Tuple[float, ...]:
        # Same order as METRIC_KEYS.
        return (
            self.min_gap_mandatory,
            self.avg_gap_all,
            self.elective_conflicts,
            self.mandatory_span,
            self.max_exams_per_day,
        )

    def as_dict(self) -> Dict[str, float]:
        return dict(zip(METRIC_KEYS, self.as_tuple()))

    @classmethod
    def from_iterable(cls, values: Iterator[float]) -> "ScheduleMetrics":
        # Build a ScheduleMetrics from any iterable producing the five values
        # in canonical (METRIC_KEYS) order, e.g. MetricsCalculator.calculate(...).
        materialized = list(values)
        if len(materialized) != len(METRIC_KEYS):
            raise ValueError(
                f"Expected {len(METRIC_KEYS)} metric values, got {len(materialized)}."
            )
        return cls(*materialized)


class MetricsCalculator:
    """
    Stateless calculator that scores a Schedule against the five section-3 metrics.

    Aggregation choices (documented because section 3 is per-(program, year[, moed])
    while sorting needs a single comparable scalar per schedule):
      * 3.1 / 3.4 reduce their per-group values with `min` — the tightest group is
        the binding case, so surfacing schedules whose worst group is still well
        spread mirrors the spirit of the section-2 threshold requirements.
      * The Schedule model carries no moed label (only course + date), so the
        per-moed dimension of 3.4 is approximated by (program, year) grouping.
    """

    # --- PLAN-484: the single, yield-based public entry point. ----------------
    def calculate(self, schedule: Schedule) -> Iterator[float]:
        """Yield the five metric values for `schedule`, in METRIC_KEYS order."""
        exams = self._validate_schedule(schedule)

        yield self._min_gap_mandatory(exams)
        yield self._avg_gap_all(exams)
        yield self._elective_conflicts(exams)
        yield self._mandatory_span(exams)
        yield self._max_exams_per_day(exams)

    # Convenience wrapper returning a named, frozen value object.
    def compute(self, schedule: Schedule) -> ScheduleMetrics:
        return ScheduleMetrics.from_iterable(self.calculate(schedule))

    # Computes ONLY the requested metric indices (0..4, METRIC_KEYS order). Used
    # by the deep search to build a sort key without paying for all five metrics
    # on every one of millions of scanned schedules.
    def calculate_indices(self, schedule: Schedule, indices) -> Dict[int, float]:
        exams = self._validate_schedule(schedule)
        funcs = (
            self._min_gap_mandatory,
            self._avg_gap_all,
            self._elective_conflicts,
            self._mandatory_span,
            self._max_exams_per_day,
        )
        return {index: funcs[index](exams) for index in indices}

    # --- Metric 3.1 -----------------------------------------------------------
    # Minimum number of days between two mandatory exams sharing the same program
    # and the same year. Returns +inf when no such pair exists (no constraint to
    # violate => best possible, sorts first in descending order).
    def _min_gap_mandatory(self, exams: List[ScheduledExam]) -> float:
        groups = self._group_dates_by_program_year(exams, mandatory_only=True)

        minimum = float("inf")
        for dates in groups.values():
            for earlier, later in combinations(sorted(dates), 2):
                gap = (later - earlier).days
                if gap < minimum:
                    minimum = gap
        return float(minimum)

    # --- Metric 3.2 -----------------------------------------------------------
    # Average number of days between two exams (mandatory OR elective) sharing the
    # same program and year, pooled over every qualifying pair. 0.0 when no pair.
    def _avg_gap_all(self, exams: List[ScheduledExam]) -> float:
        groups = self._group_dates_by_program_year(exams, mandatory_only=False)

        total_days = 0
        pair_count = 0
        for dates in groups.values():
            for earlier, later in combinations(sorted(dates), 2):
                total_days += (later - earlier).days
                pair_count += 1

        if pair_count == 0:
            return 0.0
        return total_days / pair_count

    # --- Metric 3.3 -----------------------------------------------------------
    # Number of collisions between two elective courses in the same program, i.e.
    # pairs of distinct elective courses sharing a program that land on the same day.
    def _elective_conflicts(self, exams: List[ScheduledExam]) -> float:
        # date -> {program_id -> set of elective course ids on that date}
        by_date: Dict[object, Dict[str, set]] = {}
        for exam in exams:
            for program_id in self._program_ids(exam, elective_only=True):
                by_date.setdefault(exam.exam_date, {}).setdefault(
                    program_id, set()
                ).add(exam.course.course_id)

        conflicts = 0
        for programs in by_date.values():
            for course_ids in programs.values():
                # Every unordered pair of distinct electives on the same day in
                # the same program is one collision.
                n = len(course_ids)
                conflicts += n * (n - 1) // 2
        return float(conflicts)

    # --- Metric 3.4 -----------------------------------------------------------
    # Days between the first and last mandatory exam within a (program, year)
    # group, reduced across groups with `min`. +inf when no group has >= 2
    # mandatory exams (no span defined => best, sorts first in descending order).
    def _mandatory_span(self, exams: List[ScheduledExam]) -> float:
        groups = self._group_dates_by_program_year(exams, mandatory_only=True)

        minimum_span = float("inf")
        for dates in groups.values():
            if len(dates) < 2:
                continue
            span = (max(dates) - min(dates)).days
            if span < minimum_span:
                minimum_span = span
        return float(minimum_span)

    # --- Metric 3.5 -----------------------------------------------------------
    # Maximum number of exams scheduled on any single day across the schedule.
    def _max_exams_per_day(self, exams: List[ScheduledExam]) -> float:
        counts: Dict[object, int] = {}
        for exam in exams:
            counts[exam.exam_date] = counts.get(exam.exam_date, 0) + 1
        return float(max(counts.values())) if counts else 0.0

    # --- Shared helpers -------------------------------------------------------
    # Group exam dates by (program_id, year). When mandatory_only is True only
    # mandatory program memberships contribute; the same exam can land in several
    # groups when its course belongs to multiple programs/years.
    def _group_dates_by_program_year(
        self,
        exams: List[ScheduledExam],
        mandatory_only: bool,
    ) -> Dict[Tuple[str, int], List[object]]:
        groups: Dict[Tuple[str, int], List[object]] = {}
        for exam in exams:
            for info in exam.course.program_info:
                is_elective = info.requirement == _ELECTIVE_REQUIREMENT
                if mandatory_only and is_elective:
                    continue
                groups.setdefault((info.program_id, info.year), []).append(
                    exam.exam_date
                )
        return groups

    # Yield the program ids the exam's course belongs to, optionally restricted
    # to elective memberships.
    def _program_ids(
        self, exam: ScheduledExam, elective_only: bool
    ) -> Iterator[str]:
        for info in exam.course.program_info:
            if elective_only and info.requirement != _ELECTIVE_REQUIREMENT:
                continue
            yield info.program_id

    def _validate_schedule(self, schedule: Schedule) -> List[ScheduledExam]:
        if not isinstance(schedule, Schedule):
            raise TypeError("schedule must be a Schedule instance.")
        return list(schedule.exams or [])
