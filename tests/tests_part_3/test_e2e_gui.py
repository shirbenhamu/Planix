import pytest
import multiprocessing
import time
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser
from src.MVP.presenters.calendar_presenter import CalendarPresenter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _DummyParser(BaseParser):
    """Stub parser for providing empty data during tests."""

    def parse_courses(self, file_path): return []
    def parse_exam_periods(self, file_path): return []
    def parse_selected_programs(self, file_path): return []


def _course(cid, req="Obligatory", program="83101"):
    """Creates a mock Course object."""
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


def _write(out, c1, c2, gaps, skip_count=0, append=False):
    """Writes scheduled exam data to a file for the collection manager."""
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


class _FakeView:
    """Headless view stub simulating UI behavior."""

    def __init__(self):
        self.render_count = 0
        self.pagination = None

    def update_pagination(self, current_page, total_pages): self.pagination = (
        current_page, total_pages)

    def init_grid(self, months): pass
    def render_calendar_data(self, data): self.render_count += 1
    def show_empty_state(self): pass
    def show_no_more_results(self): pass

# ---------------------------------------------------------------------------
# GUI smoke test (headless, no real window)
# ---------------------------------------------------------------------------


class TestGuiSmoke:
    """
    Headless GUI smoke tests exercising the Presenter/Controller lifecycle.
    the controller and presenter layer are exercised via thin stubs that simulate the
    interaction without opening a display."""

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def _setup_presenter(self, out, courses, manager=None):
        """Helper to bootstrap the CalendarPresenter with mock dependencies."""
        dm = manager or _dm(*courses)
        model = SimpleNamespace(
            data_manager=SimpleNamespace(get_courses=lambda: courses),
            get_exam_periods=lambda: [],
            get_user_excluded_dates=lambda: [],
            get_selected_programs=lambda: ["83101"],
        )
        controller = MagicMock()
        view = _FakeView()

        manager = manager or ScheduleCollectionManager(str(out), dm)
        presenter = CalendarPresenter(
            view=view, model=model, collection_manager=manager)
        presenter.controller = controller
        return presenter, view, manager

    def test_happy_path_no_exception(self, tmp_path):
        """Validates that navigation operations complete without errors."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "schedules.txt"
        _write(out, c1, c2, [3, 5])

        presenter, view, _ = self._setup_presenter(out, [c1, c2])
        presenter.controller.engine_adapter.is_generation_active.return_value = False

        presenter._handle_next_schedule()
        presenter._handle_prev_schedule()
        presenter._handle_sort_changed(["min_gap_mandatory"])

        assert view.render_count >= 1

    def test_refresh_feed_transitions_between_batches(self, tmp_path):
        """Validates that refreshing the feed appends new data batches correctly."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "schedules.txt"
        _write(out, c1, c2, [3, 5])

        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"])
        
        presenter, _, manager = self._setup_presenter(out, [c1, c2], manager=manager)
        presenter.controller.engine_adapter.is_generation_active.return_value = True

        _write(out, c1, c2, [3, 5, 9], skip_count=2, append=True)
        
        assert presenter.auto_refresh_feed() is True
        assert manager.get_total_count() == 3

    def test_no_subprocess_leaks_after_headless_run(self, tmp_path):
        """Ensures no orphaned processes remain post-execution."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "schedules.txt"
        _write(out, c1, c2, [3, 7])

        before = len(multiprocessing.active_children())
        presenter, _, _ = self._setup_presenter(out, [c1, c2])
        
        presenter._handle_sort_changed(["min_gap_mandatory"])
        presenter._handle_next_schedule()

        time.sleep(0.3)
        after = len(multiprocessing.active_children())

        assert after <= before, "Subprocess leak detected."