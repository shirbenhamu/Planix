"""
Stress suite for SCHEDULE SORTING at volume.

Builds hundreds of on-disk schedule blocks with randomized (and some missing)
METRICS lines, then hammers ScheduleCollectionManager.sort_collection with
random single- and multi-criteria specs. Each result is checked against the
documented CONTRACT rather than a hand-written expected list, so the checks
hold regardless of the manager's internal tie-breaking:

  * the order is monotonic under the requested (key, direction) comparator,
  * the multiset of metric tuples is preserved (nothing lost or duplicated),
  * metric-less ("legacy") blocks always sink to the very bottom,
  * repeated identical sorts are deterministic.

Display-independent: the manager runs its real parse/sort path over a temp file.

NOTE: this file mirrors the helpers/APIs already exercised in
test_schedule_sorting.py (sort_collection, get_metrics, get_total_count) so it
should drop straight into the same suite. Seeds are fixed for reproducibility.
"""
import random

import pytest

from src.data_manager import DataManager
from src.parsers.base_parser import BaseParser
from src.metrics.metrics_calculator import METRIC_KEYS
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager


# ===========================================================================
# Helpers — write real schedule blocks (with/without METRICS lines) to disk
# ===========================================================================
class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []


def _data_manager():
    DataManager._instance = None
    dm = DataManager(_DummyParser())
    dm.courses = {}
    return dm


def _write_blocks(tmp_path, metric_tuples, name="schedules.txt"):
    """metric_tuples: list of 5-tuples in METRIC_KEYS order; a None entry ->
    a block with NO metrics line (legacy block that must sink to the bottom)."""
    lines = ["=== Complete Academic Year Schedules ===", "", ""]
    for i, metrics in enumerate(metric_tuples, start=1):
        lines.append(f"--- FULL SYSTEM OPTION {i} ---")
        lines.append(f"Date: 0{(i % 9) + 1}-02-2026 | Course: 1000{i % 7} - C{i} | Instructor: T")
        if metrics is not None:
            lines.append("METRICS|" + "|".join(str(x) for x in metrics))
        lines.append("-" * 60)
        lines.append("")
    path = tmp_path / name
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _manager(tmp_path, metric_tuples):
    return ScheduleCollectionManager(str(_write_blocks(tmp_path, metric_tuples)),
                                     _data_manager())


def _ordered_tuples(cm):
    """Metric tuple (or None) for each schedule, in the current sorted order."""
    return [cm.get_metrics(i) for i in range(cm.get_total_count())]


def _as_cmp(metric_tuple):
    """A totally-orderable stand-in so None and tuples can share a sorted()."""
    return (1,) if metric_tuple is None else (0, tuple(metric_tuple))


def _key(metric_tuple, spec):
    """The contractual comparison key for one entry under `spec`
    (list of (index, ascending)). Metric-less entries sort strictly last,
    descending means a larger value compares 'smaller' (comes first)."""
    if metric_tuple is None:
        return (1,)
    parts = []
    for index, ascending in spec:
        v = metric_tuple[index]
        parts.append(v if ascending else -v)
    return (0, tuple(parts))


def _is_sorted(ordered, spec):
    keys = [_key(t, spec) for t in ordered]
    return all(keys[i] <= keys[i + 1] for i in range(len(keys) - 1))


def _assert_none_sinks(ordered):
    seen_none = False
    for t in ordered:
        if t is None:
            seen_none = True
        else:
            assert not seen_none, "a scored block appeared after a metric-less one"


def _random_metrics(n, rng, none_fraction=0.1):
    out = []
    for _ in range(n):
        if rng.random() < none_fraction:
            out.append(None)
        else:
            out.append((
                float(rng.randint(0, 9)),    # min_gap_mandatory
                float(rng.randint(0, 40)),   # avg_gap_all
                float(rng.randint(0, 5)),    # elective_conflicts
                float(rng.randint(1, 30)),   # mandatory_span
                float(rng.randint(1, 6)),    # max_exams_per_day
            ))
    return out


# ===========================================================================
# Stress tests
# ===========================================================================
class TestSortingStress:
    N = 400

    def test_random_single_key_sorts_are_monotonic_and_lossless(self, tmp_path):
        rng = random.Random(20260628)
        metrics = _random_metrics(self.N, rng)
        cm = _manager(tmp_path, metrics)
        reference_multiset = sorted(_as_cmp(t) for t in metrics)

        for index, key in enumerate(METRIC_KEYS):
            for ascending in (True, False):
                cm.sort_collection([key], ascending=ascending)
                ordered = _ordered_tuples(cm)
                assert _is_sorted(ordered, [(index, ascending)]), \
                    f"{key} ascending={ascending} not monotonic"
                # nothing gained, lost, or duplicated by the sort
                assert sorted(_as_cmp(t) for t in ordered) == reference_multiset
                _assert_none_sinks(ordered)

    def test_random_multi_key_sorts_are_monotonic(self, tmp_path):
        rng = random.Random(7)
        metrics = _random_metrics(self.N, rng, none_fraction=0.05)
        cm = _manager(tmp_path, metrics)

        for _ in range(25):
            k = rng.randint(2, len(METRIC_KEYS))
            indices = rng.sample(range(len(METRIC_KEYS)), k)
            keys = [METRIC_KEYS[i] for i in indices]
            asc = [rng.choice([True, False]) for _ in indices]
            cm.sort_collection(keys, ascending=asc)
            spec = list(zip(indices, asc))
            assert _is_sorted(_ordered_tuples(cm), spec), \
                f"multi-key sort {keys} {asc} not monotonic"

    def test_repeated_identical_sorts_are_deterministic(self, tmp_path):
        rng = random.Random(99)
        cm = _manager(tmp_path, _random_metrics(self.N, rng))
        cm.sort_collection(["avg_gap_all", "max_exams_per_day"], ascending=[False, True])
        first = _ordered_tuples(cm)
        for _ in range(10):
            cm.sort_collection(["avg_gap_all", "max_exams_per_day"], ascending=[False, True])
            assert _ordered_tuples(cm) == first

    def test_metricless_blocks_always_sink_in_every_direction(self, tmp_path):
        rng = random.Random(123)
        metrics = _random_metrics(self.N, rng, none_fraction=0.3)  # ~30% legacy
        cm = _manager(tmp_path, metrics)
        for key in METRIC_KEYS:
            for ascending in (True, False):
                cm.sort_collection([key], ascending=ascending)
                _assert_none_sinks(_ordered_tuples(cm))