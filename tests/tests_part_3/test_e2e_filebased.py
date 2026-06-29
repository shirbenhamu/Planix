import pytest
from datetime import date
from src import cli
from src.data_manager import DataManager
from src.metrics.metrics_calculator import METRIC_KEYS, METRICS_LINE_PREFIX
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _DummyParser(BaseParser):
    """Stub parser for providing empty data during tests."""
    def parse_courses(self, file_path): return []
    def parse_exam_periods(self, file_path): return []
    def parse_selected_programs(self, file_path): return []

def _course(cid, req="Obligatory", program="83101"):
    """Helper to create a mock Course object."""
    return Course(
        course_id=cid,
        course_name=f"Course {cid}",
        instructor="Dr. Test",
        evaluation_method="Exam",
        program_info=[ProgramCourseInfo(program, 1, "FALL", req)],
    )

def _dm(*courses):
    """Initializes a DataManager with provided courses."""
    DataManager._instance = None
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c.course_id: c for c in courses}
    return dm

def _gap(schedule):
    """Calculates the gap (in days) between the first and last exam."""
    days = sorted(e.exam_date for e in schedule.exams)
    return (days[-1] - days[0]).days

def _write(out, c1, c2, gaps, skip_count=0, append=False):
    """Writes scheduling data to file."""
    schedules = [
        Schedule(exams=[
            ScheduledExam(c1, date(2026, 2, 1)),
            ScheduledExam(c2, date(2026, 2, 1 + g)),
        ])
        for g in gaps
    ]
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(schedules)},
        str(out), skip_count=skip_count, append=append,
    )


# ---------------------------------------------------------------------------
# File-based (CLI) E2E with constraints + sort priority
# ---------------------------------------------------------------------------

class TestFileBased:
    """
    Run the CLI pipeline end-to-end with constraints and
    sort criteria supplied through resolve_options, verifying output
    structure and ordering.
    """

    class _FakeScheduler:
        def __init__(self, schedules):
            self._schedules = schedules

        def generate_schedules(self, courses, exam_periods, selected_programs):
            return {("FALL", "Aleph"): iter(self._schedules)}

    def _build_schedules(self, c1, c2, gaps):
        return [
            Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                            ScheduledExam(c2, date(2026, 2, 1 + g))])
            for g in gaps
        ]

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def test_cli_produces_well_formed_output_with_metrics(self, tmp_path, monkeypatch):
        """Validates output structure and metrics inclusion."""
        c1, c2 = _course("10001"), _course("10002")
        gaps = [3, 9, 5, 1, 7]
        schedules = self._build_schedules(c1, c2, gaps)

        monkeypatch.setattr(cli, "_load_data_manager", lambda opts: (_dm(c1, c2), ["83101"]))
        monkeypatch.setattr(cli, "ExamScheduler", lambda: self._FakeScheduler(schedules))
        output = tmp_path / "top.txt"
        work = tmp_path / "work.txt"

        rc = cli.main([
            "--programs", "83101",
            "--sort", "min_gap_mandatory",
            "--window", "3",
            "--output", str(output),
            "--work-file", str(work),
        ])

        assert rc == 0
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "RANK 1" in content
        assert "RANK 3" in content
        assert "RANK 4" not in content          
        work_content = work.read_text(encoding="utf-8")
        assert work_content.count(METRICS_LINE_PREFIX + "|") == len(gaps)

    def test_cli_output_is_sorted_by_configured_criteria(self, tmp_path, monkeypatch):
        """Validates correct ranking order based on sort configuration."""
        c1, c2 = _course("10001"), _course("10002")
        gaps = [3, 9, 5, 1, 7]   # file order
        schedules = self._build_schedules(c1, c2, gaps)

        monkeypatch.setattr(cli, "_load_data_manager", lambda opts: (_dm(c1, c2), ["83101"]))
        monkeypatch.setattr(cli, "ExamScheduler", lambda: self._FakeScheduler(schedules))

        output = tmp_path / "top.txt"
        work = tmp_path / "work.txt"

        cli.main([
            "--programs", "83101",
            "--sort", "min_gap_mandatory",
            "--window", "3",
            "--output", str(output),
            "--work-file", str(work),
        ])

        # Extract rank order from the output text.
        text = output.read_text(encoding="utf-8")
        rank1_pos = text.index("RANK 1")
        rank2_pos = text.index("RANK 2")
        rank3_pos = text.index("RANK 3")
        assert rank1_pos < rank2_pos < rank3_pos

        # The top-3 by min_gap descending are gaps [9, 7, 5].
        # Verify that the date corresponding to gap 9 appears before gap 7.
        # gap 9 -> exam on 2026-02-10 (Feb 1 + 9)
        # gap 7 -> exam on 2026-02-08 (Feb 1 + 7)
        date_9 = "10-02-2026"   # dd-mm-yyyy
        date_7 = "08-02-2026"
        assert text.index(date_9) < text.index(date_7), (
            "schedule with gap=9 must appear before schedule with gap=7 in the output"
        )

    def test_cli_all_five_metrics_usable_as_sort_key(self, tmp_path, monkeypatch):
        """Verifies every defined metric is accepted as a CLI sort key."""
        c1, c2 = _course("10001"), _course("10002")
        schedules = self._build_schedules(c1, c2, [3, 7])

        monkeypatch.setattr(cli, "_load_data_manager", lambda opts: (_dm(c1, c2), ["83101"]))
        monkeypatch.setattr(cli, "ExamScheduler", lambda: self._FakeScheduler(schedules))

        for key in METRIC_KEYS:
            output = tmp_path / f"out_{key}.txt"
            work = tmp_path / f"work_{key}.txt"
            rc = cli.main([
                "--programs", "83101",
                "--sort", key,
                "--window", "2",
                "--output", str(output),
                "--work-file", str(work),
            ])
            assert rc == 0, f"--sort {key} returned non-zero exit code"


# ---------------------------------------------------------------------------
# GUI and CLI produce equivalent top-N for identical inputs
# ---------------------------------------------------------------------------

class TestGuiCliEquivalence:
    """Verifies consistency between the GUI and CLI ranking logic."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def test_gui_and_cli_agree_on_top_n(self, tmp_path):
        """Validates that both paths return the same results for identical inputs."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "schedules.txt"
        gaps = [3, 9, 5, 1, 7]
        _write(out, c1, c2, gaps)

        dm = _dm(c1, c2)

        # CLI Path
        cli_window, cli_metrics, cli_total = cli.rank_and_slice(
            dm, str(out),
            sort_keys=["min_gap_mandatory"],
            ascending=False,
            window_size=3,
        )

        # GUI path
        DataManager._instance = None
        dm2 = _dm(c1, c2)
        manager = ScheduleCollectionManager(str(out), dm2)
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        manager.set_window_size(3)
        gui_window = manager.materialize_window(start_index=0)

        assert len(cli_window) == len(gui_window) == 3

        for rank, (cli_s, gui_s) in enumerate(zip(cli_window, gui_window)):
            cli_gap = _gap(cli_s)
            gui_gap = _gap(gui_s)
            assert cli_gap == gui_gap, (
                f"Rank {rank + 1}: CLI gap={cli_gap} but GUI gap={gui_gap}; "
                "the two modes must produce the same ordering for identical inputs"
            )

    def test_gui_and_cli_agree_on_total_count(self, tmp_path):
        """Validates that both paths agree on the total number of schedules found."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "schedules.txt"
        _write(out, c1, c2, [3, 9, 5])

        dm = _dm(c1, c2)
        _, _, cli_total = cli.rank_and_slice(
            dm, str(out), ["avg_gap_all"], ascending=False, window_size=10
        )

        DataManager._instance = None
        dm2 = _dm(c1, c2)
        manager = ScheduleCollectionManager(str(out), dm2)
        gui_total = manager.get_total_count()

        assert cli_total == gui_total, (
            f"CLI reports {cli_total} schedules but GUI reports {gui_total}"
        )

# ---------------------------------------------------------------------------
# Stress tests (file-based / CLI pipeline under volume + GUI<->CLI equivalence
# at scale). One flow ties together: scheduler -> file writer ->
# rank_and_slice / collection manager -> metrics -> sort.
# ---------------------------------------------------------------------------

def _gaps_cycle(n, lo=1, hi=27):
    """`n` deterministic gaps cycling through [lo, hi] (<=27 keeps Feb dates
    valid). Produces lots of intentional ties to stress the tie-breaker."""
    span = hi - lo + 1
    return [lo + (i % span) for i in range(n)]


def _monotonic(values, ascending):
    if ascending:
        return all(values[i] <= values[i + 1] for i in range(len(values) - 1))
    return all(values[i] >= values[i + 1] for i in range(len(values) - 1))


class _BulkFakeScheduler:
    """Returns a large precomputed batch of schedules for a single period."""

    def __init__(self, schedules):
        self._schedules = schedules

    def generate_schedules(self, courses, exam_periods, selected_programs):
        return {("FALL", "Aleph"): iter(self._schedules)}


def _bulk_schedules(c1, c2, gaps):
    return [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                        ScheduledExam(c2, date(2026, 2, 1 + g))])
        for g in gaps
    ]


class TestFileBasedStress:
    """The CLI ranking path under heavy volume and at the window edges."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def test_rank_and_slice_orders_large_volume(self, tmp_path):
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "bulk.txt"
        N = 2000
        _write(out, c1, c2, _gaps_cycle(N))

        window, _metrics, total = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["min_gap_mandatory"], ascending=False, window_size=N)
        assert total == N
        assert len(window) == N
        assert _monotonic([_gap(s) for s in window], ascending=False)

        DataManager._instance = None
        window_asc, _m, _t = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["min_gap_mandatory"], ascending=True, window_size=N)
        assert _monotonic([_gap(s) for s in window_asc], ascending=True)

    def test_window_slicing_edge_conditions_at_scale(self, tmp_path):
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "edges.txt"
        N = 500
        _write(out, c1, c2, _gaps_cycle(N))

        w_all, _m, total = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["avg_gap_all"], ascending=False, window_size=10 ** 6)
        assert total == N and len(w_all) == N  # window larger than total -> all

        DataManager._instance = None
        w_one, _m, _t = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["avg_gap_all"], ascending=False, window_size=1)
        assert len(w_one) == 1
        # the single best must equal the head of the full ranking
        assert _gap(w_one[0]) == _gap(w_all[0])

    def test_all_metrics_sortable_under_volume(self, tmp_path, monkeypatch):
        c1, c2 = _course("10001"), _course("10002")
        schedules = _bulk_schedules(c1, c2, _gaps_cycle(400))
        monkeypatch.setattr(cli, "_load_data_manager", lambda opts: (_dm(c1, c2), ["83101"]))
        monkeypatch.setattr(cli, "ExamScheduler", lambda: _BulkFakeScheduler(schedules))

        for key in METRIC_KEYS:
            output = tmp_path / f"bulk_{key}.txt"
            work = tmp_path / f"bulk_work_{key}.txt"
            rc = cli.main([
                "--programs", "83101",
                "--sort", key,
                "--window", "50",
                "--output", str(output),
                "--work-file", str(work),
            ])
            assert rc == 0, f"--sort {key} failed under volume"
            text = output.read_text(encoding="utf-8")
            assert "RANK 1" in text and "RANK 50" in text


class TestGuiCliEquivalenceStress:
    """GUI and CLI must produce the identical ranking for a large, tie-heavy
    input, not just for a handful of distinct schedules."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def test_gui_and_cli_agree_on_full_ranking_at_scale(self, tmp_path):
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "equiv.txt"
        N = 1200
        _write(out, c1, c2, _gaps_cycle(N))

        # CLI path
        cli_window, _m, cli_total = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["min_gap_mandatory"], ascending=False, window_size=N)

        # GUI path
        DataManager._instance = None
        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        manager.set_window_size(N)
        gui_window = manager.materialize_window(start_index=0)
        gui_total = manager.get_total_count()

        assert cli_total == gui_total == N
        assert len(cli_window) == len(gui_window) == N
        # Tie-break agnostic but strict: the per-rank metric sequence is identical.
        assert [_gap(s) for s in cli_window] == [_gap(s) for s in gui_window]


class TestCliPipelineStress:
    """Heavy, repeated runs of the real CLI entry point and rank_and_slice."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def test_cli_main_repeated_invocations_stay_well_formed(self, tmp_path, monkeypatch):
        """Forty back-to-back CLI runs over a large batch must each exit 0 and
        emit a correctly truncated, metric-bearing output + work file. Guards
        against state leaking between runs (stale singletons, half-written
        files, exhausted generators)."""
        c1, c2 = _course("10001"), _course("10002")
        N = 600
        schedules = _bulk_schedules(c1, c2, _gaps_cycle(N))
        monkeypatch.setattr(cli, "_load_data_manager", lambda opts: (_dm(c1, c2), ["83101"]))
        monkeypatch.setattr(cli, "ExamScheduler", lambda: _BulkFakeScheduler(schedules))

        window = 20
        for i in range(40):
            output = tmp_path / f"run_{i}.txt"
            work = tmp_path / f"work_{i}.txt"
            rc = cli.main([
                "--programs", "83101",
                "--sort", "min_gap_mandatory",
                "--window", str(window),
                "--output", str(output),
                "--work-file", str(work),
            ])
            assert rc == 0, f"run {i} exited non-zero"
            text = output.read_text(encoding="utf-8")
            assert "RANK 1" in text and f"RANK {window}" in text
            assert f"RANK {window + 1}" not in text  # window strictly truncates
            # every generated schedule carries exactly one metrics line on disk
            assert work.read_text(encoding="utf-8").count(METRICS_LINE_PREFIX + "|") == N

    def test_rank_and_slice_is_deterministic_across_repeats(self, tmp_path):
        """Re-ranking the very same file repeatedly yields an identical metric
        ordering every time and never mutates the source file (ranking is a
        pure read)."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "det.txt"
        N = 1000
        _write(out, c1, c2, _gaps_cycle(N))
        original_bytes = out.read_bytes()

        reference = None
        for _ in range(8):
            DataManager._instance = None
            window, _m, total = cli.rank_and_slice(
                _dm(c1, c2), str(out), ["min_gap_mandatory"],
                ascending=False, window_size=N)
            gaps = [_gap(s) for s in window]
            assert total == N and len(gaps) == N
            assert _monotonic(gaps, ascending=False)
            if reference is None:
                reference = gaps
            else:
                assert gaps == reference            # fully deterministic
        assert out.read_bytes() == original_bytes   # source untouched

    def test_full_collection_pagination_reconstructs_global_order(self, tmp_path):
        """Page through the entire ranked collection in fixed windows; the
        concatenation of every page must reproduce the single full-window
        ranking exactly — every schedule present once, order preserved, with a
        partial final page."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "pages.txt"
        N = 950
        _write(out, c1, c2, _gaps_cycle(N))

        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        assert manager.get_total_count() == N

        # full ranking in one shot (reference)
        manager.set_window_size(N)
        full = [_gap(s) for s in manager.materialize_window(start_index=0)]
        assert len(full) == N and _monotonic(full, ascending=False)

        # the same ranking, walked page by page (100 does not divide 950)
        page = 100
        manager.set_window_size(page)
        paged = []
        start = 0
        while start < N:
            chunk = manager.materialize_window(start_index=start)
            assert 0 < len(chunk) <= page
            paged.extend(_gap(s) for s in chunk)
            start += page
        assert paged == full   # identical sequence: full coverage, no dupes/gaps

    def test_ascending_and_descending_are_multiset_equivalent_under_ties(self, tmp_path):
        """A tie-saturated input ranked both ways: each direction is monotonic
        and both hold exactly the same multiset of schedules (the sort direction
        never drops or invents a schedule)."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "ties.txt"
        N = 1500
        _write(out, c1, c2, _gaps_cycle(N, lo=1, hi=5))  # only 5 distinct gaps

        desc, _m1, t1 = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["min_gap_mandatory"], ascending=False, window_size=N)
        DataManager._instance = None
        asc, _m2, t2 = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["min_gap_mandatory"], ascending=True, window_size=N)

        dgaps = [_gap(s) for s in desc]
        agaps = [_gap(s) for s in asc]
        assert t1 == t2 == N
        assert _monotonic(dgaps, ascending=False)
        assert _monotonic(agaps, ascending=True)
        assert sorted(dgaps) == sorted(agaps)   # same multiset both directions


class TestFileWriterIncrementalStress:
    """The writer's skip_count/append contract feeding the ranker at scale."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def test_many_appended_batches_rank_as_one_collection(self, tmp_path):
        """Build a 1000-schedule file as 20 appended batches of 50 (each batch
        skips the already-written prefix), then rank the whole thing: the total
        and the ordering must match a single monolithic write of the same data."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "incr.txt"

        N, batch = 1000, 50
        written = 0
        while written < N:
            nxt = written + batch
            _write(out, c1, c2, _gaps_cycle(nxt),
                   skip_count=written, append=(written > 0))
            written = nxt

        window, _m, total = cli.rank_and_slice(
            _dm(c1, c2), str(out), ["min_gap_mandatory"], ascending=False, window_size=N)
        assert total == N
        assert _monotonic([_gap(s) for s in window], ascending=False)

        # equivalence to a single-shot write of the identical gaps
        DataManager._instance = None
        out2 = tmp_path / "single.txt"
        _write(out2, c1, c2, _gaps_cycle(N))
        w2, _m2, total2 = cli.rank_and_slice(
            _dm(c1, c2), str(out2), ["min_gap_mandatory"], ascending=False, window_size=N)
        assert total2 == total
        assert [_gap(s) for s in window] == [_gap(s) for s in w2]