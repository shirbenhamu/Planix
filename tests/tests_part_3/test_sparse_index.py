import tracemalloc
from datetime import date

import pytest

from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.metrics.metrics_calculator import METRIC_KEYS
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser


class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []


def _course(cid, name="C", req="Obligatory"):
    return Course(
        course_id=cid,
        course_name=name,
        instructor="Teacher",
        evaluation_method="Exam",
        program_info=[ProgramCourseInfo("83108", 1, "FALL", req)],
    )


def _dm(*courses):
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c.course_id: c for c in courses}
    return dm


def _write_new_format(tmp_path, n_blocks):
    """Generate `n_blocks` real schedule blocks (with METRICS lines) via the writer."""
    c1, c2 = _course("10001"), _course("10002")
    schedules = [
        Schedule(exams=[
            ScheduledExam(c1, date(2026, 2, 1)),
            ScheduledExam(c2, date(2026, 2, 1 + (i % 20) + 1)),
        ])
        for i in range(n_blocks)
    ]
    out = tmp_path / "out" / "schedules.txt"
    FileOutputWriter().write_schedules({("FALL", "Aleph"): iter(schedules)}, str(out))
    return out, c1, c2


# --- PLAN-489: entries are (offset, metric_tuple) and nothing more ----------
def test_index_entries_are_offset_metric_tuple(tmp_path):
    out, c1, c2 = _write_new_format(tmp_path, 3)
    manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
    manager.get_total_count()

    entries = manager._offsets
    assert len(entries) == 3
    for offset, metric_tuple in entries:
        assert isinstance(offset, int)
        assert isinstance(metric_tuple, tuple)
        assert len(metric_tuple) == len(METRIC_KEYS)
        assert all(isinstance(v, float) for v in metric_tuple)


def test_metric_accessors_read_from_index_without_body(tmp_path):
    out, c1, c2 = _write_new_format(tmp_path, 2)
    manager = ScheduleCollectionManager(str(out), _dm(c1, c2))

    current = manager.get_current_metrics()
    assert current == manager.get_metrics(0)
    assert len(current) == len(METRIC_KEYS)

    manager.jump_to_schedule(1)
    assert manager.get_current_metrics() == manager.get_metrics(1)


# --- PLAN-490: snapshot scan parses METRICS lines ---------------------------
def test_snapshot_index_parses_metrics(tmp_path):
    out, c1, c2 = _write_new_format(tmp_path, 4)
    manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
    manager.build_snapshot_index()

    assert manager.total_schedules == 4
    assert all(mt is not None and len(mt) == 5 for _, mt in manager._offsets)


def test_incremental_snapshot_picks_up_metrics_as_file_grows(tmp_path):
    # Simulate the engine writing blocks in two flushes, polled in snapshot mode.
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "out" / "schedules.txt"

    s1 = [Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 4))])]
    FileOutputWriter().write_schedules({("FALL", "Aleph"): iter(s1)}, str(out))

    manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
    manager.build_snapshot_index()
    assert manager.total_schedules == 1
    assert manager._offsets[0][1] is not None

    # Append a second block. As in the real "Load More" flow, the engine
    # regenerates ALL schedules and skip_count skips the already-written ones.
    s2 = [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 4))]),
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 9))]),
    ]
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(s2)}, str(out), skip_count=1, append=True
    )

    manager.build_snapshot_index()
    assert manager.total_schedules == 2
    assert all(mt is not None for _, mt in manager._offsets)


# --- PLAN-491: on-demand full-schedule materialization still works ----------
def test_pagination_and_body_materialization(tmp_path):
    out, c1, c2 = _write_new_format(tmp_path, 3)
    manager = ScheduleCollectionManager(str(out), _dm(c1, c2))

    assert manager.get_total_count() == 3
    assert manager.get_current_index() == 0

    schedule0 = manager.get_current_schedule()
    assert isinstance(schedule0, Schedule)
    assert {e.course.course_id for e in schedule0.exams} == {"10001", "10002"}

    assert manager.next_schedule() is True
    assert manager.get_current_index() == 1
    assert isinstance(manager.get_current_schedule(), Schedule)

    assert manager.jump_to_schedule(2) is True
    assert isinstance(manager.get_current_schedule(), Schedule)


# --- backward compatibility: old-format blocks (no METRICS line) ------------
def test_old_format_blocks_indexed_with_none_metrics(tmp_path):
    block = (
        "--- FULL SYSTEM OPTION {n} ---\n"
        "Date: 0{n}-02-2026 | Course: 10001 - C | Instructor: Teacher\n"
        "------------------------------------------------------------\n\n"
    )
    out = tmp_path / "legacy.txt"
    out.write_text(block.format(n=1) + block.format(n=2), encoding="utf-8")

    manager = ScheduleCollectionManager(str(out), _dm(_course("10001")))
    assert manager.get_total_count() == 2
    assert manager.get_metrics(0) is None
    assert manager.get_metrics(1) is None
    # body still materializes on demand
    assert isinstance(manager.get_current_schedule(), Schedule)


# --- memory stays bounded regardless of result-set size ---------------------
def test_index_memory_bounded_for_large_result_set(tmp_path):
    # A large file should not load schedule bodies into RAM: the index holds only
    # offsets + 5-float tuples, so peak memory scales with entry count, not body size.
    out, c1, c2 = _write_new_format(tmp_path, 1500)
    manager = ScheduleCollectionManager(str(out), _dm(c1, c2))

    tracemalloc.start()
    manager.get_total_count()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    n = manager.total_schedules
    assert n >= 1000
    # No schedule body text is retained; entries are tiny. Generous ceiling.
    assert peak < 4_000_000  # < 4 MB for 1500+ entries
    # Spot-check that bodies are NOT held anywhere in the index.
    for _offset, metric_tuple in manager._offsets:
        assert metric_tuple is None or isinstance(metric_tuple, tuple)
