from datetime import date

import pytest

from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import (
    DEFAULT_WINDOW_SIZE,
    ScheduleCollectionManager,
)
from src.metrics.metrics_calculator import METRIC_KEYS
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser

_MIN_GAP_POS = METRIC_KEYS.index("min_gap_mandatory")


class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []


def _course(cid):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo("83108", 1, "FALL", "Obligatory")])


def _manager_with_gaps(tmp_path, gaps):
    c1, c2 = _course("10001"), _course("10002")
    schedules = [
        Schedule(exams=[
            ScheduledExam(c1, date(2026, 2, 1)),
            ScheduledExam(c2, date(2026, 2, 1 + g)),
        ])
        for g in gaps
    ]
    out = tmp_path / "out" / "schedules.txt"
    FileOutputWriter().write_schedules({("FALL", "Aleph"): iter(schedules)}, str(out))
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c1.course_id: c1, c2.course_id: c2}
    return ScheduleCollectionManager(str(out), dm)


def _first_gap(schedule):
    # min_gap of a 2-exam schedule == the day delta between its two exams.
    days = sorted(e.exam_date for e in schedule.exams)
    return (days[-1] - days[0]).days


# --- PLAN-499: configurable window size -------------------------------------
def test_default_window_size():
    assert DEFAULT_WINDOW_SIZE == 10


def test_window_size_limits_materialized_count(tmp_path):
    manager = _manager_with_gaps(tmp_path, list(range(2, 14)))  # 12 schedules
    manager.set_window_size(5)
    assert manager.get_window_size() == 5

    window = manager.materialize_window(start_index=0)
    assert len(window) == 5
    assert all(isinstance(s, Schedule) for s in window)


def test_window_smaller_than_size_returns_all(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5])
    manager.set_window_size(10)
    assert len(manager.materialize_window(0)) == 3


def test_set_window_size_validation(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3])
    with pytest.raises(ValueError):
        manager.set_window_size(0)
    with pytest.raises(ValueError):
        manager.set_window_size(-2)
    with pytest.raises(TypeError):
        manager.set_window_size(3.5)
    with pytest.raises(TypeError):
        manager.set_window_size(True)


# --- window reflects the sorted order (top-N) -------------------------------
def test_window_returns_top_n_of_sorted_index(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5, 1, 7])
    manager.set_window_size(3)
    manager.sort_collection(["min_gap_mandatory"])  # descending

    window = manager.materialize_window()
    gaps = [_first_gap(s) for s in window]
    assert gaps == [9, 7, 5]  # top 3 by min_gap descending


# --- PLAN-500: seek by offset, no full-file scan ----------------------------
def test_materialization_seeks_by_offset_without_full_scan(tmp_path, monkeypatch):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5, 1, 7])
    manager.set_window_size(2)

    # Spy on file.seek to prove we jump straight to the window's offsets.
    seek_targets = []
    import builtins
    orig_open = builtins.open

    class _SpyFile:
        def __init__(self, fh):
            self._fh = fh

        def seek(self, *args, **kwargs):
            if args:
                seek_targets.append(args[0])
            return self._fh.seek(*args, **kwargs)

        def __getattr__(self, name):
            return getattr(self._fh, name)

        def __enter__(self):
            self._fh.__enter__()
            return self

        def __exit__(self, *a):
            return self._fh.__exit__(*a)

    def spy_open(*args, **kwargs):
        return _SpyFile(orig_open(*args, **kwargs))

    # Build index first (uses its own scan), then watch only the materialization.
    manager.materialize_window(0)  # warm the index
    expected_offsets = [manager._offsets[0][0], manager._offsets[1][0]]

    seek_targets.clear()
    monkeypatch.setattr(builtins, "open", spy_open)
    manager.materialize_window(0)
    monkeypatch.undo()

    # The reads seek directly to each window block's byte offset.
    for off in expected_offsets:
        assert off in seek_targets


# --- PLAN-501: switching sort refreshes the materialized window -------------
def test_switching_sort_refreshes_window(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5, 1, 7])
    manager.set_window_size(2)

    manager.sort_collection(["min_gap_mandatory"], ascending=False)
    desc_window = [_first_gap(s) for s in manager.materialize_window()]
    assert desc_window == [9, 7]

    manager.sort_collection(["min_gap_mandatory"], ascending=True)
    asc_window = [_first_gap(s) for s in manager.materialize_window()]
    assert asc_window == [1, 3]
    # Window start was reset to the new top on sort change.
    assert manager.get_window_start() == 0


# --- windowing past the start (groundwork for refresh-feed PLAN-415) --------
def test_window_at_arbitrary_start(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5, 1, 7])
    manager.set_window_size(2)
    manager.sort_collection(["min_gap_mandatory"])  # 9,7,5,3,1

    second_page = [_first_gap(s) for s in manager.materialize_window(start_index=2)]
    assert second_page == [5, 3]
    assert manager.get_window_start() == 2
