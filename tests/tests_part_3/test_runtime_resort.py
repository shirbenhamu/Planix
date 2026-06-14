from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.MVP.presenters.calendar_presenter import CalendarPresenter
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser


# --- shared fakes -----------------------------------------------------------
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


class _FakeView:
    """Minimal calendar view: records refresh activity, exposes sort callback."""

    def __init__(self):
        self.on_sort_changed = None        # presence => presenter wires it
        self.on_load_more_clicked = None
        self.render_count = 0
        self.pagination = None

    def update_pagination(self, current_page, total_pages):
        self.pagination = (current_page, total_pages)

    def init_grid(self, months):
        pass

    def render_calendar_data(self, grid_data):
        self.render_count += 1

    def show_empty_state(self):
        pass


def _fake_model(courses):
    return SimpleNamespace(
        data_manager=SimpleNamespace(get_courses=lambda: courses),
        get_exam_periods=lambda: [],
        get_user_excluded_dates=lambda: [],
        get_selected_programs=lambda: [],
    )


def _write_three_schedules(tmp_path):
    """Three schedules whose min_gap_mandatory is 3, 9, 5 days (in that order)."""
    c1, c2 = _course("10001"), _course("10002")
    schedules = [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 4))]),   # gap 3
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 10))]),  # gap 9
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 6))]),   # gap 5
    ]
    out = tmp_path / "out" / "schedules.txt"
    FileOutputWriter().write_schedules({("FALL", "Aleph"): iter(schedules)}, str(out))

    dm = DataManager(parser=_DummyParser())
    dm.courses = {c1.course_id: c1, c2.course_id: c2}
    return out, dm, [c1, c2]


def _make_presenter(tmp_path):
    out, dm, courses = _write_three_schedules(tmp_path)
    manager = ScheduleCollectionManager(str(out), dm)
    view = _FakeView()
    model = _fake_model(courses)
    presenter = CalendarPresenter(view=view, model=model, collection_manager=manager)
    return presenter, view, manager


# --- the sort callback is wired on the presenter ----------------------------
def test_presenter_wires_sort_callback(tmp_path):
    presenter, view, _ = _make_presenter(tmp_path)
    assert callable(view.on_sort_changed)
    assert view.on_sort_changed == presenter._handle_sort_changed


# --- window updates to the new top schedule (in-memory) ---------------------
def test_sort_reorders_and_refreshes_window(tmp_path):
    presenter, view, manager = _make_presenter(tmp_path)
    view.render_count = 0

    presenter._handle_sort_changed(["min_gap_mandatory"])  # descending default

    # Top schedule is now the one with the largest min_gap (9 days).
    assert manager.get_current_index() == 0
    assert manager.get_current_metrics()[0] == 9.0
    # The window was redrawn to reflect the new ordering.
    assert view.render_count >= 1
    assert view.pagination == (1, 3)


# --- AC: changing sort triggers NO engine activity --------------------------
def test_sort_does_not_invoke_engine(tmp_path):
    presenter, view, manager = _make_presenter(tmp_path)

    controller = MagicMock()
    controller.engine_adapter = MagicMock()
    presenter.controller = controller

    # Multiple sort changes across the session.
    presenter._handle_sort_changed(["min_gap_mandatory"])
    presenter._handle_sort_changed(["max_exams_per_day"], ascending=True)
    presenter._handle_sort_changed(["avg_gap_all", "min_gap_mandatory"])

    # The engine is never re-run by sorting (no recompute, no snapshot regen).
    controller.regenerate_schedules_snapshot.assert_not_called()
    controller.load_more_schedules.assert_not_called()
    controller.engine_adapter.generate_from_model.assert_not_called()


# --- AC (PLAN-495): active k-constraints / index state unaffected -----------
def test_sort_does_not_invalidate_constraints_or_cache(tmp_path):
    presenter, view, manager = _make_presenter(tmp_path)

    manager.clear_cache = MagicMock(side_effect=AssertionError("must not clear cache on sort"))
    total_before = manager.get_total_count()

    presenter._handle_sort_changed(["min_gap_mandatory"])

    # Sorting must not drop/regenerate the index — the same valid schedules
    # remain; only their order changes.
    assert manager.get_total_count() == total_before == 3


def test_invalid_sort_request_is_ignored_gracefully(tmp_path):
    presenter, view, manager = _make_presenter(tmp_path)
    # Should not raise — the handler swallows invalid specs.
    presenter._handle_sort_changed(["not_a_metric"])
    presenter._handle_sort_changed([])


# --- AC: re-sort works "on snapshots" as new blocks stream in ---------------
def test_active_sort_maintained_as_snapshot_grows(tmp_path):
    out, dm, courses = _write_three_schedules(tmp_path)
    c1, c2 = courses
    manager = ScheduleCollectionManager(str(out), dm)

    # User sorts by min_gap descending: order becomes 9, 5, 3.
    manager.sort_collection(["min_gap_mandatory"])
    assert [mt[0] for _, mt in manager._offsets] == [9.0, 5.0, 3.0]

    # User is browsing the middle schedule (gap 5).
    manager.jump_to_schedule(1)
    assert manager.get_current_metrics()[0] == 5.0

    # Engine streams in a 4th schedule with a bigger gap (12 days). The real
    # load-more flow regenerates all and skips the already-written ones.
    streamed = [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 4))]),
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 10))]),
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 6))]),
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)), ScheduledExam(c2, date(2026, 2, 13))]),  # gap 12
    ]
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(streamed)}, str(out), skip_count=3, append=True
    )

    manager.build_snapshot_index()

    # New block is inserted in sorted position: 12, 9, 5, 3.
    assert [mt[0] for _, mt in manager._offsets] == [12.0, 9.0, 5.0, 3.0]
    # The page number stays put (still index 1) — it only moves when the USER
    # navigates. The content at page 1 now reflects the updated ranking (gap 9).
    assert manager.get_current_index() == 1
    assert manager.get_current_metrics()[0] == 9.0


def test_page_number_stays_at_one_during_generation(tmp_path):
    # Regression: when the user runs generation and does NOT navigate, the page
    # counter must stay at 1 as better schedules stream in — not grow on its own.
    out, dm, courses = _write_three_schedules(tmp_path)  # gaps 3,9,5
    c1, c2 = courses
    manager = ScheduleCollectionManager(str(out), dm)  # default sort -> index 0
    assert manager.get_current_index() == 0

    # Engine streams progressively better schedules (regenerate-all + skip done).
    for extra_gap in (12, 20):
        gaps = [3, 9, 5] + [g for g in (12, 20) if g <= extra_gap]
        schedules = [
            Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                            ScheduledExam(c2, date(2026, 2, 1 + g))])
            for g in gaps
        ]
        FileOutputWriter().write_schedules(
            {("FALL", "Aleph"): iter(schedules)}, str(out),
            skip_count=3, append=True,
        )
        manager.build_snapshot_index()
        # Never navigated -> still page 1 (index 0).
        assert manager.get_current_index() == 0
