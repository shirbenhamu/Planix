import pytest
from datetime import date
from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import (
    DEFAULT_SORT_ASCENDING,
    DEFAULT_SORT_KEYS,
    ScheduleCollectionManager,
)
from src.metrics.metrics_calculator import METRIC_KEYS
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser

_AVG_GAP_POS = METRIC_KEYS.index("avg_gap_all")
_MIN_GAP_POS = METRIC_KEYS.index("min_gap_mandatory")

# Parser stub returning nothing, so a DataManager can be built without real files.
class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []

# Obligatory course in program 83108, year 1, FALL.
def _course(cid):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo("83108", 1, "FALL", "Obligatory")])


# Write one 2-exam schedule per gap and return a manager over them.
def _manager_with_gaps(tmp_path, gaps):
    """Write one 2-exam schedule per gap (avg_gap_all == min_gap == the gap)."""
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

# The agreed default sort is avg_gap_all, descending.
def test_default_sort_is_avg_gap_descending():
    assert DEFAULT_SORT_KEYS == ("avg_gap_all",)
    assert DEFAULT_SORT_ASCENDING is False
    assert "avg_gap_all" in METRIC_KEYS

# The default sort is applied automatically on the first load.
def test_default_applied_on_first_load(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5])  # avg gaps 3, 9, 5

    # Default = avg_gap_all descending -> ordering becomes 9, 5, 3.
    assert [mt[_AVG_GAP_POS] for _, mt in manager._offsets] == [9.0, 5.0, 3.0]
    # First window shows the best (highest avg gap).
    assert manager.get_current_index() == 0
    assert manager.get_current_metrics()[_AVG_GAP_POS] == 9.0

# No sort is applied to an empty collection.
def test_default_not_applied_to_empty_collection(tmp_path):
    out = tmp_path / "empty.txt"
    out.write_text("=== header ===\n", encoding="utf-8")
    dm = DataManager(parser=_DummyParser())
    dm.courses = {"10001": _course("10001")}
    manager = ScheduleCollectionManager(str(out), dm)
    assert manager.get_total_count() == 0
    assert manager._sort_spec is None  # nothing to rank yet
    assert manager._user_sorted is False

# Legacy (metric-less) blocks keep file order, untouched by the default.
def test_default_does_not_reorder_legacy_blocks(tmp_path):
    # Old-format blocks (no METRICS) carry None metrics -> stable, file order kept.
    block = (
        "--- FULL SYSTEM OPTION {n} ---\n"
        "Date: 0{n}-02-2026 | Course: 10001 - C | Instructor: T\n"
        "------------------------------------------------------------\n\n"
    )
    out = tmp_path / "legacy.txt"
    out.write_text(block.format(n=1) + block.format(n=2), encoding="utf-8")
    dm = DataManager(parser=_DummyParser())
    dm.courses = {"10001": _course("10001")}
    manager = ScheduleCollectionManager(str(out), dm)

    assert manager.get_total_count() == 2
    # File order preserved (first block first).
    assert manager._offsets[0][0] < manager._offsets[1][0]

# A user sort replaces the default for the rest of the session.
def test_user_sort_overrides_default(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5])
    assert manager._user_sorted is False  # default in effect

    manager.sort_collection(["min_gap_mandatory"], ascending=True)
    assert manager._user_sorted is True
    assert [mt[_MIN_GAP_POS] for _, mt in manager._offsets] == [3.0, 5.0, 9.0]

# After a regeneration the user's sort is re-applied, not the default.
def test_user_sort_persists_across_regeneration(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5])
    manager.sort_collection(["min_gap_mandatory"], ascending=True)

    # Simulate a fresh generation cycle: cache cleared, same file re-scanned.
    manager.clear_cache()
    manager.get_total_count()  # forces a rebuild of the index

    # The user's sort is reapplied (ascending min_gap), NOT the default.
    assert manager._user_sorted is True
    assert [mt[_MIN_GAP_POS] for _, mt in manager._offsets] == [3.0, 5.0, 9.0]

# Clearing a sort leaves it cleared; it does not silently restore the default.
def test_clear_sort_does_not_revert_to_default(tmp_path):
    manager = _manager_with_gaps(tmp_path, [3, 9, 5])
    manager.sort_collection(["min_gap_mandatory"], ascending=True)

    manager.clear_sort()
    assert manager._sort_spec is None
    assert manager._user_sorted is True

    # Re-scan must not re-apply the default sort.
    manager.clear_cache()
    manager.get_total_count()
    assert manager._sort_spec is None