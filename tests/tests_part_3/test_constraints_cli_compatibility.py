import pytest
import argparse
from datetime import date
from src import cli
from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser
from src.engine.scheduling_constraints import SchedulingConstraints

# --- Infrastructure / Mocks ---


class _DummyParser(BaseParser):
    def parse_courses(self, file_path): return []
    def parse_exam_periods(self, file_path): return []
    def parse_selected_programs(self, file_path): return []


class _FakeScheduler:
    def __init__(self, schedules): self._schedules = schedules

    def generate_schedules(self, courses, exam_periods, selected_programs):
        return {("FALL", "Aleph"): iter(self._schedules)}


def _course(cid):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo("83108", 1, "FALL", "Obligatory")])


def _dm_with_courses(c1, c2):
    DataManager._instance = None
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c1.course_id: c1, c2.course_id: c2}
    return dm


def _write_results(out, c1, c2, gaps):
    schedules = [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                        ScheduledExam(c2, date(2026, 2, 1 + g))])
        for g in gaps
    ]
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(schedules)}, str(out))


def _gap(schedule):
    days = sorted(e.exam_date for e in schedule.exams)
    return (days[-1] - days[0]).days


@pytest.fixture(autouse=True)
def _reset_singleton():
    DataManager._instance = None
    yield
    DataManager._instance = None

# --- Core Criteria Tests ---


def test_system_accepts_all_five_criteria():
    """Validates that the system recognizes all 5 core constraints."""
    criteria = [
        "min_days_mandatory", "min_days_any",
        "max_elective_conflicts", "span_mandatory", "max_exams_per_day"
    ]
    # Check that constraints object can be instantiated for these criteria
    for c in criteria:
        assert SchedulingConstraints(**{f"{c}_enabled": True}) is not None

# --- Integration & Pipeline Tests (Original Logic) ---


def test_rank_and_slice_sorts_and_slices(tmp_path):
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "schedules.txt"
    _write_results(out, c1, c2, [3, 9, 5, 1, 7])
    dm = _dm_with_courses(c1, c2)

    window, metrics, total = cli.rank_and_slice(
        dm, str(out), ["min_gap_mandatory"], ascending=False, window_size=3
    )
    assert total == 5
    assert len(window) == 3
    assert [_gap(s) for s in window] == [9, 7, 5]


def test_rank_and_slice_ascending(tmp_path):
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "schedules.txt"
    _write_results(out, c1, c2, [3, 9, 5, 1, 7])
    dm = _dm_with_courses(c1, c2)

    window, _, _ = cli.rank_and_slice(
        dm, str(out), ["min_gap_mandatory"], ascending=True, window_size=2
    )
    assert [_gap(s) for s in window] == [1, 3]


def test_generate_ranked_window_runs_engine_and_ranks(tmp_path):
    c1, c2 = _course("10001"), _course("10002")
    dm = _dm_with_courses(c1, c2)
    schedules = [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                 ScheduledExam(c2, date(2026, 2, 1 + g))])
        for g in [4, 8, 2]
    ]
    work = tmp_path / "work" / "out.txt"
    work.parent.mkdir()

    window, metrics, total = cli.generate_ranked_window(
        dm, ["83108"], ["min_gap_mandatory"], ascending=False, window_size=2,
        work_file_path=str(work), scheduler=_FakeScheduler(schedules),
    )
    assert total == 3
    assert [_gap(s) for s in window] == [8, 4]
    assert "METRICS|" in work.read_text(encoding="utf-8")

# --- Edge Case Tests ---


def test_invalid_criteria_handling():
    parser = cli.build_arg_parser()
    args = parser.parse_args(["--sort", "invalid_metric"])
    with pytest.raises(ValueError, match="Unknown sort metric"):
        cli.resolve_options(args, {})


def test_resolve_options_defaults():
    args = cli.build_arg_parser().parse_args([])
    opts = cli.resolve_options(args, {})
    assert opts["sort"] == list(cli.DEFAULT_SORT_KEYS)
    assert opts["ascending"] is cli.DEFAULT_SORT_ASCENDING
    assert opts["window"] == cli.DEFAULT_WINDOW_SIZE


def test_resolve_options_cli_overrides_config():
    args = cli.build_arg_parser().parse_args(
        ["--sort", "max_exams_per_day,min_gap_mandatory",
            "--window", "5", "--ascending"]
    )
    config = {"sort": ["avg_gap_all"], "window": 20,
              "ascending": False, "programs": ["1"]}
    opts = cli.resolve_options(args, config)
    assert opts["sort"] == ["max_exams_per_day", "min_gap_mandatory"]
    assert opts["window"] == 5
    assert opts["ascending"] is True


def test_resolve_options_reads_config_values():
    args = cli.build_arg_parser().parse_args([])
    config = {"sort": ["mandatory_span"], "window": 7,
              "ascending": True, "programs": ["83101", "83102"]}
    opts = cli.resolve_options(args, config)
    assert opts["sort"] == ["mandatory_span"]
    assert opts["window"] == 7
    assert opts["ascending"] is True
    assert opts["programs"] == ["83101", "83102"]


def test_csv_parsing_handles_list_and_string():
    assert cli._split_csv("a, b ,c") == ["a", "b", "c"]
    assert cli._split_csv(["a", " b "]) == ["a", "b"]
    assert cli._split_csv(None) is None

# --- Presentation Tests ---


def test_format_listing_shows_top_n_and_boundary(tmp_path):
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "schedules.txt"
    _write_results(out, c1, c2, [3, 9, 5])
    dm = _dm_with_courses(c1, c2)

    window, metrics, total = cli.rank_and_slice(
        dm, str(out), ["min_gap_mandatory"], ascending=False, window_size=10
    )
    listing = cli.format_window_listing(window, metrics, total, 10, [
                                        "min_gap_mandatory"], False)

    assert "RANK 1" in listing
    assert "RANK 3" in listing
    assert "descending" in listing
    assert "End of results." in listing


def test_format_listing_truncation_note(tmp_path):
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "schedules.txt"
    _write_results(out, c1, c2, [3, 9, 5, 1, 7])
    dm = _dm_with_courses(c1, c2)

    window, metrics, total = cli.rank_and_slice(
        dm, str(out), ["min_gap_mandatory"], ascending=False, window_size=2
    )
    listing = cli.format_window_listing(window, metrics, total, 2, [
                                        "min_gap_mandatory"], False)
    assert "3 more schedule(s) not shown" in listing


def test_format_listing_empty():
    listing = cli.format_window_listing([], [], 0, 10, ["avg_gap_all"], False)
    assert "No valid schedules found" in listing

# --- Main E2E Tests ---


def test_main_writes_output_file(tmp_path, monkeypatch):
    c1, c2 = _course("10001"), _course("10002")
    schedules = [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                 ScheduledExam(c2, date(2026, 2, 1 + g))])
        for g in [3, 9, 5]
    ]

    def _fake_loader(opts):
        return _dm_with_courses(c1, c2), ["83108"]

    monkeypatch.setattr(cli, "_load_data_manager", _fake_loader)
    monkeypatch.setattr(cli, "ExamScheduler",
                        lambda: _FakeScheduler(schedules))

    output = tmp_path / "top.txt"
    work = tmp_path / "work.txt"
    rc = cli.main([
        "--programs", "83108",
        "--sort", "min_gap_mandatory",
        "--window", "2",
        "--output", str(output),
        "--work-file", str(work),
    ])

    assert rc == 0
    text = output.read_text(encoding="utf-8")
    assert "RANK 1" in text and "RANK 2" in text
    assert text.index("RANK 1") < text.index("RANK 2")