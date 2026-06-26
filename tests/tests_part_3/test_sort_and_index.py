import pytest
import builtins
import tracemalloc
from datetime import date
from src.data_manager import DataManager
from src.metrics.metrics_calculator import METRIC_KEYS
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser

# ===========================================================================
# Shared fixtures / helpers
# ===========================================================================

# Parser that returns nothing, so a DataManager can be built without touching real files.
class _DummyParser(BaseParser):
    def parse_courses(self, file_path): return []
    def parse_exam_periods(self, file_path): return []
    def parse_selected_programs(self, file_path): return []

# Autouse fixture: clear the DataManager singleton before and after each test so state never leaks.
@pytest.fixture(autouse=True)
def _reset_singleton():
    """Keep DataManager's singleton from leaking state across tests."""
    DataManager._instance = None
    yield
    DataManager._instance = None

# Build an obligatory course in program 83108, year 1, FALL.
def _course(cid, req="Obligatory"):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo("83108", 1, "FALL", req)])

# Wrap the given courses in a fresh DataManager keyed by course id.
def _dm(*courses):
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c.course_id: c for c in courses}
    return dm

# Write one 2-exam schedule per requested gap.
def _write_gaps(path, c1, c2, gaps):
    """Write one 2-exam schedule per gap value via the real FileOutputWriter.
    For a 2-exam schedule whose courses are both Obligatory in the same
    program/year, min_gap_mandatory == avg_gap_all == mandatory_span == the gap.
    """
    schedules = [
        Schedule(exams=[
            ScheduledExam(c1, date(2026, 2, 1)),
            ScheduledExam(c2, date(2026, 2, 1 + g)),
        ])
        for g in gaps
    ]
    FileOutputWriter().write_schedules({("FALL", "Aleph"): iter(schedules)}, str(path))


# Write the gaps to disk and return a ScheduleCollectionManager over them.
def _manager_from_gaps(tmp_path, gaps):
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "out" / "schedules.txt"
    _write_gaps(out, c1, c2, gaps)
    return ScheduleCollectionManager(str(out), _dm(c1, c2)), c1, c2, out

# Seed the sparse index directly from metric tuples, bypassing file generation.
def _seed_manager(tmp_path, metric_tuples):
    """Seed _offsets directly so the test targets sort_collection in isolation
    (no engine, no real file content). Offsets are distinct so ordering can be
    tracked by offset value alone.
    """
    out = tmp_path / "schedules.txt"
    out.write_text("placeholder\n", encoding="utf-8")
    manager = ScheduleCollectionManager(str(out), _dm(_course("10001")))
    manager._offsets = [(i * 100, mt) for i, mt in enumerate(metric_tuples)]
    manager.total_schedules = len(manager._offsets)
    return manager

# Return the index's current ordering as a list, for asserting sort results.
def _offsets_order(manager):
    return [offset for offset, _ in manager._offsets]


# ===========================================================================
# Sparse-index structure
# ===========================================================================

# The sparse index holds (file offset, metric tuple) entries and reads metrics without parsing bodies.
class TestSparseIndexStructure:
    """Parsed _offsets must agree with what FileOutputWriter wrote."""

    # One index entry per written schedule.
    def test_offset_count_matches_written_schedules(self, tmp_path):
        manager, *_ = _manager_from_gaps(tmp_path, [3, 7, 12])
        assert manager.get_total_count() == 3

    # Each entry is an (offset, metric_tuple) pair.
    def test_index_entries_are_offset_metric_tuple(self, tmp_path):
        manager, *_ = _manager_from_gaps(tmp_path, [5, 9])
        manager.get_total_count()
        for offset, mt in manager._offsets:
            assert isinstance(offset, int), "offset must be an int (byte position)"
            assert isinstance(mt, tuple), "metric_tuple must be a tuple"
            assert len(mt) == len(METRIC_KEYS)
            assert all(isinstance(v, float) for v in mt)

    # File offsets are unique, positive integers.
    def test_offsets_are_distinct_positive_ints(self, tmp_path):
        # The manager applies its default sort on load (avg_gap descending), so
        # _offsets is NOT in raw file order. The meaningful invariant is that the
        # byte offsets are distinct, non-negative ints — one per schedule block.
        manager, *_ = _manager_from_gaps(tmp_path, [2, 5, 8])
        manager.get_total_count()
        offsets = [off for off, _ in manager._offsets]
        assert len(offsets) == 3
        assert len(set(offsets)) == len(offsets), "byte offsets must be distinct"
        assert all(isinstance(o, int) and o >= 0 for o in offsets)

    # Indexed metric values equal the gaps that were written.
    def test_metric_values_match_written_gaps(self, tmp_path):
        gaps = [3, 7, 11]
        manager, *_ = _manager_from_gaps(tmp_path, gaps)
        manager.get_total_count()
        idx = METRIC_KEYS.index("min_gap_mandatory")
        # Default sort reorders _offsets, so compare as a set of values, not in order.
        stored = sorted(mt[idx] for _, mt in manager._offsets)
        assert stored == sorted(float(g) for g in gaps)

    # Metric accessors serve values straight from the index, never reading the schedule body.
    def test_metric_accessors_read_from_index_without_body(self, tmp_path):
        manager, *_ = _manager_from_gaps(tmp_path, [4, 9])
        current = manager.get_current_metrics()
        assert current == manager.get_metrics(0)
        assert len(current) == len(METRIC_KEYS)
        manager.jump_to_schedule(1)
        assert manager.get_current_metrics() == manager.get_metrics(1)

    # Legacy blocks with no METRICS line yield None metrics.
    def test_old_format_blocks_produce_none_metrics(self, tmp_path):
        block = (
            "--- FULL SYSTEM OPTION {n} ---\n"
            "Date: 0{n}-02-2026 | Course: 10001 - C10001 | Instructor: T\n"
            "------------------------------------------------------------\n\n"
        )
        out = tmp_path / "legacy.txt"
        out.write_text(block.format(n=1) + block.format(n=2), encoding="utf-8")
        manager = ScheduleCollectionManager(str(out), _dm(_course("10001")))
        assert manager.get_total_count() == 2
        assert all(mt is None for _, mt in manager._offsets)
        assert manager.get_metrics(0) is None and manager.get_metrics(1) is None

# ===========================================================================
# Single-key DESCENDING sort for each of the five metrics
# ===========================================================================

# descending sort on each of the five metrics individually.
class TestSingleKeyDescendingAllMetrics:
    """Each of the five METRIC_KEYS must work as a standalone sort key."""

    # Fixture: a manager seeded with one distinct value per metric for ordering checks.
    @pytest.fixture
    def seeded_manager(self, tmp_path):
        # columns map to METRIC_KEYS order:
        # (min_gap_mandatory, avg_gap_all, elective_conflicts, mandatory_span, max_exams_per_day)
        manager = _seed_manager(tmp_path, [
            (3.0, 3.0, 1.0, 8.0, 1.0),   # offset 0
            (7.0, 7.0, 3.0, 4.0, 2.0),   # offset 100
            (9.0, 9.0, 5.0, 2.0, 4.0),   # offset 200
        ])
        return manager

    @pytest.mark.parametrize("key,expected_order", [
        ("min_gap_mandatory", [200, 100, 0]),   # 9 > 7 > 3
        ("avg_gap_all",       [200, 100, 0]),   # 9 > 7 > 3
        ("elective_conflicts",[200, 100, 0]),   # 5 > 3 > 1
        ("mandatory_span",    [0,   100, 200]), # 8 > 4 > 2
        ("max_exams_per_day", [200, 100, 0]),   # 4 > 2 > 1
    ])
    
    # Each metric, sorted alone, orders highest-to-lowest.
    def test_single_key_descending(self, seeded_manager, key, expected_order):
        seeded_manager.sort_collection([key], ascending=False)
        assert _offsets_order(seeded_manager) == expected_order, (
            f"descending sort on '{key}' produced wrong offset order"
        )

    # Omitting the direction defaults to descending.
    def test_single_key_descending_is_default_direction(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (3.0, 0, 0, 0, 0), (9.0, 0, 0, 0, 0), (5.0, 0, 0, 0, 0),
        ])
        manager.sort_collection(["min_gap_mandatory"])  # no ascending -> desc default
        assert _offsets_order(manager) == [100, 200, 0]  # 9, 5, 3


# ===========================================================================
# Multi-key priority sort
# ===========================================================================

# Multi-key sort where earlier keys take priority over later ones.
class TestMultiKeyPrioritySort:
    """Secondary/tertiary keys must break ties in the higher-priority key."""

    # The secondary key breaks ties on the primary key.
    def test_primary_then_secondary_descending(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (5.0, 2.0, 0.0, 0.0, 0.0),   # offset 0
            (5.0, 8.0, 0.0, 0.0, 0.0),   # offset 100  same primary, higher secondary
            (9.0, 4.0, 0.0, 0.0, 0.0),   # offset 200  highest primary
        ])
        manager.sort_collection(["min_gap_mandatory", "avg_gap_all"], ascending=False)
        assert _offsets_order(manager) == [200, 100, 0]

    # Primary and secondary may target different metrics.
    def test_primary_uses_different_metric_than_secondary(self, tmp_path):
        # Primary max_exams_per_day desc; tie-break avg_gap_all desc.
        manager = _seed_manager(tmp_path, [
            (0, 2.0, 0, 0, 3.0),   # offset 0
            (0, 8.0, 0, 0, 3.0),   # offset 100
            (0, 5.0, 0, 0, 5.0),   # offset 200
        ])
        manager.sort_collection(["max_exams_per_day", "avg_gap_all"])
        assert _offsets_order(manager) == [200, 100, 0]

    # Per-key direction: ascending primary, descending secondary.
    def test_primary_ascending_secondary_descending(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (7.0, 2.0, 0.0, 0.0, 0.0),   # offset 0
            (3.0, 5.0, 0.0, 0.0, 0.0),   # offset 100
            (3.0, 9.0, 0.0, 0.0, 0.0),   # offset 200
        ])
        manager.sort_collection(["min_gap_mandatory", "avg_gap_all"], ascending=[True, False])
        assert _offsets_order(manager) == [200, 100, 0]

    # Three-level tie-breaking cascade.
    def test_three_key_cascade(self, tmp_path):
        # All share min=5 and avg=3; elective (ascending) breaks the tie.
        manager = _seed_manager(tmp_path, [
            (5.0, 3.0, 4.0, 0.0, 0.0),   # offset 0   elective 4 -> last
            (5.0, 3.0, 1.0, 0.0, 0.0),   # offset 100 elective 1 -> first
            (5.0, 3.0, 2.0, 0.0, 0.0),   # offset 200 elective 2 -> second
        ])
        manager.sort_collection(
            ["min_gap_mandatory", "avg_gap_all", "elective_conflicts"],
            ascending=[False, False, True],
        )
        assert _offsets_order(manager) == [100, 200, 0]


# ===========================================================================
# Ascending variants
# ===========================================================================

# 'ascending' can be a bool, a per-key list, or a dict.
class TestAscendingVariants:

    # A single bool sets the direction for every key.
    def test_ascending_bool_applies_to_all(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (3.0, 0, 0, 0, 0), (9.0, 0, 0, 0, 0), (5.0, 0, 0, 0, 0),
        ])
        manager.sort_collection(["min_gap_mandatory"], ascending=True)
        assert _offsets_order(manager) == [0, 200, 100]  # 3, 5, 9

    # A list sets the direction per key, positionally.
    def test_ascending_per_key_list(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (0, 2.0, 0, 0, 5.0),   # offset 0:   day=5, avg=2
            (0, 8.0, 0, 0, 3.0),   # offset 100: day=3, avg=8
            (0, 5.0, 0, 0, 3.0),   # offset 200: day=3, avg=5
        ])
        manager.sort_collection(["max_exams_per_day", "avg_gap_all"], ascending=[True, False])
        assert _offsets_order(manager) == [100, 200, 0]

    # A dict sets the direction per key, by name.
    def test_ascending_dict(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (3.0, 0, 0, 0, 0), (9.0, 0, 0, 0, 0), (5.0, 0, 0, 0, 0),
        ])
        manager.sort_collection(["min_gap_mandatory"], ascending={"min_gap_mandatory": True})
        assert _offsets_order(manager) == [0, 200, 100]


# ===========================================================================
# inf / None handling
# ===========================================================================

# How +inf and missing (None) metrics are ordered.
class TestInfinityAndNone:

    # inf ranks first when sorting descending.
    def test_infinity_sorts_first_descending(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (5.0, 0, 0, 0, 0), (float("inf"), 0, 0, 0, 0), (9.0, 0, 0, 0, 0),
        ])
        manager.sort_collection(["min_gap_mandatory"])
        assert _offsets_order(manager) == [100, 200, 0]  # inf, 9, 5

    # None metrics always sink to the bottom, in either direction.
    def test_none_metrics_sink_to_bottom_regardless_of_direction(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (5.0, 0, 0, 0, 0), None, (9.0, 0, 0, 0, 0),
        ])
        manager.sort_collection(["min_gap_mandatory"])
        assert _offsets_order(manager)[-1] == 100  # None last (descending)
        manager.sort_collection(["min_gap_mandatory"], ascending=True)
        assert _offsets_order(manager)[-1] == 100  # None still last (ascending)


# ===========================================================================
# Re-sort on the SAME index without re-reading the file
# ===========================================================================

# Re-sorting reuses the in-memory index with no further file reads.
class TestResortWithoutFileIO:

    # A second sort triggers zero file opens.
    def test_resort_does_no_file_io_on_seeded_index(self, tmp_path, monkeypatch):
        manager = _seed_manager(tmp_path, [(3.0, 0, 0, 0, 0), (9.0, 0, 0, 0, 0)])

        def _boom(*args, **kwargs):
            raise AssertionError("sort_collection must not open the output file.")

        monkeypatch.setattr("builtins.open", _boom)
        manager.sort_collection(["min_gap_mandatory"])
        assert _offsets_order(manager) == [100, 0]

    # Re-sorting by a new key yields the new correct order.
    def test_resort_produces_different_correct_order(self, tmp_path, monkeypatch):
        manager, *_ = _manager_from_gaps(tmp_path, [3, 7, 11])
        manager.get_total_count()  # builds index by reading the file once
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        idx = METRIC_KEYS.index("min_gap_mandatory")
        assert [mt[idx] for _, mt in manager._offsets] == [11.0, 7.0, 3.0]
        orig_open = builtins.open
        def _no_open(*args, **kwargs):
            raise AssertionError(
                "sort_collection must NOT open the file on a re-sort; "
                "it should operate only on the in-memory _offsets."
            )
        monkeypatch.setattr(builtins, "open", _no_open)
        try:
            manager.sort_collection(["min_gap_mandatory"], ascending=True)
        finally:
            monkeypatch.setattr(builtins, "open", orig_open)
        assert [mt[idx] for _, mt in manager._offsets] == [3.0, 7.0, 11.0]

    # Re-sorting moves the cursor back to the top.
    def test_resort_resets_current_index_to_zero(self, tmp_path):
        manager, *_ = _manager_from_gaps(tmp_path, [3, 7])
        manager.get_total_count()
        manager.jump_to_schedule(1)
        assert manager.get_current_index() == 1
        manager.sort_collection(["min_gap_mandatory"])
        assert manager.get_current_index() == 0

    # Re-sorting never changes how many schedules exist.
    def test_resort_preserves_total_count(self, tmp_path):
        manager, *_ = _manager_from_gaps(tmp_path, [3, 7, 11, 5])
        n = manager.get_total_count()
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        manager.sort_collection(["avg_gap_all"], ascending=True)
        manager.sort_collection(["max_exams_per_day"], ascending=False)
        assert manager.get_total_count() == n


# ===========================================================================
# Validation / edge cases
# ===========================================================================

# Invalid sort requests are rejected.
class TestSortValidation:

    # An empty key list is rejected.
    def test_rejects_empty_keys(self, tmp_path):
        manager = _seed_manager(tmp_path, [(1.0, 0, 0, 0, 0)])
        with pytest.raises(ValueError):
            manager.sort_collection([])

    # An unknown metric name is rejected.
    def test_rejects_unknown_key(self, tmp_path):
        manager = _seed_manager(tmp_path, [(1.0, 0, 0, 0, 0)])
        with pytest.raises(ValueError):
            manager.sort_collection(["not_a_metric"])

    # A bare string (not a list) is rejected.
    def test_rejects_single_string(self, tmp_path):
        manager = _seed_manager(tmp_path, [(1.0, 0, 0, 0, 0)])
        with pytest.raises(TypeError):
            manager.sort_collection("min_gap_mandatory")

    # A per-key direction list of the wrong length is rejected.
    def test_rejects_mismatched_ascending_length(self, tmp_path):
        manager = _seed_manager(tmp_path, [(1.0, 0, 0, 0, 0)])
        with pytest.raises(ValueError):
            manager.sort_collection(["min_gap_mandatory", "avg_gap_all"], ascending=[True])
            
    # Every metric key is accepted as a sort key.
    def test_all_metric_keys_are_sortable(self, tmp_path):
        manager = _seed_manager(tmp_path, [
            (1.0, 2.0, 3.0, 4.0, 5.0), (5.0, 4.0, 3.0, 2.0, 1.0),
        ])
        manager.sort_collection(list(METRIC_KEYS))
        assert manager._sort_spec is not None
        assert len(manager._sort_spec) == len(METRIC_KEYS)


# ===========================================================================
# On-demand materialization / snapshot scan / memory bound
# ===========================================================================

# On-demand body materialization, snapshot scanning, pagination and memory bound.
class TestMaterializationAndSnapshot:

    # A snapshot scan parses METRICS lines into the index.
    def test_snapshot_index_parses_metrics(self, tmp_path):
        manager, *_ = _manager_from_gaps(tmp_path, [3, 5, 7, 9])
        manager.build_snapshot_index()
        assert manager.total_schedules == 4
        assert all(mt is not None and len(mt) == 5 for _, mt in manager._offsets)

    # Re-scanning picks up schedules appended after the first scan.
    def test_incremental_snapshot_picks_up_metrics_as_file_grows(self, tmp_path):
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "out" / "schedules.txt"
        _write_gaps(out, c1, c2, [3])

        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.build_snapshot_index()
        assert manager.total_schedules == 1
        assert manager._offsets[0][1] is not None

        # "Load More": engine regenerates ALL and skip_count skips already-written.
        FileOutputWriter().write_schedules(
            {("FALL", "Aleph"): iter([
                Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 4))]),
                Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 9))]),
            ])},
            str(out), skip_count=1, append=True,
        )
        manager.build_snapshot_index()
        assert manager.total_schedules == 2
        assert all(mt is not None for _, mt in manager._offsets)

    # Re-scanning picks up schedules appended after the first scan.
    def test_pagination_and_body_materialization(self, tmp_path):
        manager, c1, c2, _ = _manager_from_gaps(tmp_path, [3, 5, 7])
        assert manager.get_total_count() == 3
        assert manager.get_current_index() == 0

        s0 = manager.get_current_schedule()
        assert isinstance(s0, Schedule)
        assert {e.course.course_id for e in s0.exams} == {"10001", "10002"}

        assert manager.next_schedule() is True
        assert manager.get_current_index() == 1
        assert isinstance(manager.get_current_schedule(), Schedule)

        assert manager.jump_to_schedule(2) is True
        assert isinstance(manager.get_current_schedule(), Schedule)

    # Legacy blocks still materialize when their body is requested.
    def test_old_format_blocks_materialize_on_demand(self, tmp_path):
        block = (
            "--- FULL SYSTEM OPTION {n} ---\n"
            "Date: 0{n}-02-2026 | Course: 10001 - C | Instructor: T\n"
            "------------------------------------------------------------\n\n"
        )
        out = tmp_path / "legacy.txt"
        out.write_text(block.format(n=1) + block.format(n=2), encoding="utf-8")
        manager = ScheduleCollectionManager(str(out), _dm(_course("10001")))
        assert manager.get_total_count() == 2
        assert isinstance(manager.get_current_schedule(), Schedule)

    # Index memory stays bounded even for a large result set.
    def test_index_memory_bounded_for_large_result_set(self, tmp_path):
        # The index holds only offsets + 5-float tuples, so peak memory scales
        # with entry count, not body size.
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "out" / "schedules.txt"
        schedules = [
            Schedule(exams=[
                ScheduledExam(c1, date(2026, 2, 1)),
                ScheduledExam(c2, date(2026, 2, 1 + (i % 20) + 1)),
            ])
            for i in range(1500)
        ]
        FileOutputWriter().write_schedules({("FALL", "Aleph"): iter(schedules)}, str(out))
        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))

        tracemalloc.start()
        manager.get_total_count()
        _, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        assert manager.total_schedules >= 1000
        assert peak < 4_000_000  
        for _offset, metric_tuple in manager._offsets:
            assert metric_tuple is None or isinstance(metric_tuple, tuple)