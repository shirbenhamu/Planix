import pytest

from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.metrics.metrics_calculator import METRIC_KEYS
from src.parsers.base_parser import BaseParser


class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []


def _course(cid):
    return Course(cid, "C", "T", "Exam",
                  [ProgramCourseInfo("83108", 1, "FALL", "Obligatory")])


def _manager_with_metrics(tmp_path, metric_tuples):
    """Build a manager whose sparse index is seeded with given metric tuples.

    metric_tuples: list of 5-float tuples or None. We seed _offsets directly so
    the test targets sort_collection in isolation (no engine, no file content).
    """
    out = tmp_path / "schedules.txt"
    out.write_text("placeholder\n", encoding="utf-8")
    dm = DataManager(parser=_DummyParser())
    dm.courses = {"10001": _course("10001")}
    manager = ScheduleCollectionManager(str(out), dm)
    # Seed the index directly: offsets are arbitrary but distinct so we can track
    # ordering by offset value.
    manager._offsets = [(i * 100, mt) for i, mt in enumerate(metric_tuples)]
    manager.total_schedules = len(manager._offsets)
    return manager


def _offsets_order(manager):
    return [offset for offset, _ in manager._offsets]


# --- PLAN-492: ordered list of metric keys, priority order ------------------
def test_single_key_descending_by_default(tmp_path):
    # min_gap_mandatory is position 0; sort descending => largest first.
    manager = _manager_with_metrics(tmp_path, [
        (3.0, 0, 0, 0, 0),   # offset 0
        (9.0, 0, 0, 0, 0),   # offset 100
        (5.0, 0, 0, 0, 0),   # offset 200
    ])
    manager.sort_collection(["min_gap_mandatory"])
    assert _offsets_order(manager) == [100, 200, 0]  # 9, 5, 3


def test_multi_key_priority_primary_then_secondary(tmp_path):
    # Primary: max_exams_per_day (pos 4) desc; tie-break: avg_gap_all (pos 1) desc.
    manager = _manager_with_metrics(tmp_path, [
        (0, 2.0, 0, 0, 3.0),   # offset 0:   day=3, avg=2
        (0, 8.0, 0, 0, 3.0),   # offset 100: day=3, avg=8
        (0, 5.0, 0, 0, 5.0),   # offset 200: day=5, avg=5
    ])
    manager.sort_collection(["max_exams_per_day", "avg_gap_all"])
    # day desc: 5 first (offset 200), then the two day=3 broken by avg desc: 8 then 2
    assert _offsets_order(manager) == [200, 100, 0]


# --- PLAN-493: descending default + per-key ascending -----------------------
def test_ascending_bool_applies_to_all(tmp_path):
    manager = _manager_with_metrics(tmp_path, [
        (3.0, 0, 0, 0, 0),
        (9.0, 0, 0, 0, 0),
        (5.0, 0, 0, 0, 0),
    ])
    manager.sort_collection(["min_gap_mandatory"], ascending=True)
    assert _offsets_order(manager) == [0, 200, 100]  # 3, 5, 9


def test_ascending_per_key_list(tmp_path):
    # Primary max_exams_per_day ASCENDING, tie-break avg_gap_all DESCENDING.
    manager = _manager_with_metrics(tmp_path, [
        (0, 2.0, 0, 0, 5.0),   # offset 0:   day=5, avg=2
        (0, 8.0, 0, 0, 3.0),   # offset 100: day=3, avg=8
        (0, 5.0, 0, 0, 3.0),   # offset 200: day=3, avg=5
    ])
    manager.sort_collection(["max_exams_per_day", "avg_gap_all"], ascending=[True, False])
    # day asc: 3 first (two of them, avg desc -> 8 then 5), then day=5
    assert _offsets_order(manager) == [100, 200, 0]


def test_ascending_dict(tmp_path):
    manager = _manager_with_metrics(tmp_path, [
        (3.0, 0, 0, 0, 0),
        (9.0, 0, 0, 0, 0),
        (5.0, 0, 0, 0, 0),
    ])
    manager.sort_collection(["min_gap_mandatory"], ascending={"min_gap_mandatory": True})
    assert _offsets_order(manager) == [0, 200, 100]


# --- inf / None handling ----------------------------------------------------
def test_infinity_sorts_first_descending(tmp_path):
    manager = _manager_with_metrics(tmp_path, [
        (5.0, 0, 0, 0, 0),
        (float("inf"), 0, 0, 0, 0),
        (9.0, 0, 0, 0, 0),
    ])
    manager.sort_collection(["min_gap_mandatory"])
    assert _offsets_order(manager) == [100, 200, 0]  # inf, 9, 5


def test_none_metrics_sink_to_bottom_regardless_of_direction(tmp_path):
    manager = _manager_with_metrics(tmp_path, [
        (5.0, 0, 0, 0, 0),
        None,                  # legacy block, offset 100
        (9.0, 0, 0, 0, 0),
    ])
    manager.sort_collection(["min_gap_mandatory"])
    assert _offsets_order(manager)[-1] == 100  # None last (descending)

    manager.sort_collection(["min_gap_mandatory"], ascending=True)
    assert _offsets_order(manager)[-1] == 100  # None still last (ascending)


def test_sort_resets_current_index_to_top(tmp_path):
    manager = _manager_with_metrics(tmp_path, [
        (3.0, 0, 0, 0, 0),
        (9.0, 0, 0, 0, 0),
    ])
    manager._current_index = 1
    manager.sort_collection(["min_gap_mandatory"])
    assert manager.get_current_index() == 0


# --- PLAN-494: no file I/O, operates only on _offsets -----------------------
def test_sort_does_no_file_io(tmp_path, monkeypatch):
    manager = _manager_with_metrics(tmp_path, [
        (3.0, 0, 0, 0, 0),
        (9.0, 0, 0, 0, 0),
    ])

    def _boom(*args, **kwargs):
        raise AssertionError("sort_collection must not open the output file.")

    monkeypatch.setattr("builtins.open", _boom)
    manager.sort_collection(["min_gap_mandatory"])  # must not touch the file
    assert _offsets_order(manager) == [100, 0]


# --- validation -------------------------------------------------------------
def test_rejects_empty_keys(tmp_path):
    manager = _manager_with_metrics(tmp_path, [(1.0, 0, 0, 0, 0)])
    with pytest.raises(ValueError):
        manager.sort_collection([])


def test_rejects_unknown_key(tmp_path):
    manager = _manager_with_metrics(tmp_path, [(1.0, 0, 0, 0, 0)])
    with pytest.raises(ValueError):
        manager.sort_collection(["not_a_metric"])


def test_rejects_single_string(tmp_path):
    manager = _manager_with_metrics(tmp_path, [(1.0, 0, 0, 0, 0)])
    with pytest.raises(TypeError):
        manager.sort_collection("min_gap_mandatory")


def test_rejects_mismatched_ascending_length(tmp_path):
    manager = _manager_with_metrics(tmp_path, [(1.0, 0, 0, 0, 0)])
    with pytest.raises(ValueError):
        manager.sort_collection(["min_gap_mandatory", "avg_gap_all"], ascending=[True])


def test_all_metric_keys_are_sortable(tmp_path):
    # Every published metric key must be accepted as a sort key.
    manager = _manager_with_metrics(tmp_path, [
        (1.0, 2.0, 3.0, 4.0, 5.0),
        (5.0, 4.0, 3.0, 2.0, 1.0),
    ])
    manager.sort_collection(list(METRIC_KEYS))
    assert manager._sort_spec is not None
    assert len(manager._sort_spec) == len(METRIC_KEYS)
