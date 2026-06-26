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