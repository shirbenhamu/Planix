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
from src.engine.scheduling_constraints import SchedulingConstraints

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
            constraints=SchedulingConstraints(),            
            get_program_course_hierarchy=lambda prog_id=None: {},
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

# ---------------------------------------------------------------------------
# Stress tests (multi-subsystem, high volume, still fully headless)
#
# A single flow drives the file writer, the collection manager (parse / sort /
# window / total / current-index), the presenter (navigation, sort, refresh)
# and the fake view (render) together at scale.
# ---------------------------------------------------------------------------
from src.metrics.metrics_calculator import METRIC_KEYS


def _gap(schedule):
    """Span in days between the first and last exam of a schedule."""
    days = sorted(e.exam_date for e in schedule.exams)
    return (days[-1] - days[0]).days


def _gaps_cycle(n, lo=1, hi=27):
    """`n` deterministic gap values cycling through [lo, hi]. Kept <= 27 so the
    second exam (Feb 1 + gap) always lands on a valid February date."""
    span = hi - lo + 1
    return [lo + (i % span) for i in range(n)]


def _is_monotonic(values, ascending):
    if ascending:
        return all(values[i] <= values[i + 1] for i in range(len(values) - 1))
    return all(values[i] >= values[i + 1] for i in range(len(values) - 1))


class TestGuiStress:
    """High-volume GUI stress: parse -> sort -> navigate -> window ->
    incremental refresh -> render, with the presenter and a headless view."""

    N = 1200  # schedule blocks

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def _presenter(self, courses, manager):
        model = SimpleNamespace(
            data_manager=SimpleNamespace(get_courses=lambda: courses),
            get_exam_periods=lambda: [],
            get_user_excluded_dates=lambda: [],
            get_selected_programs=lambda: ["83101"],
            constraints=SchedulingConstraints(),
            get_program_course_hierarchy=lambda prog_id=None: {},
        )
        view = _FakeView()
        presenter = CalendarPresenter(view=view, model=model, collection_manager=manager)
        presenter.controller = MagicMock()
        presenter.controller.engine_adapter.is_generation_active.return_value = False
        return presenter, view

    def test_large_collection_sort_window_and_navigation(self, tmp_path):
        """Sort a large collection, verify the whole-collection window is
        best-first, then hammer the presenter with hundreds of navigation
        steps without ever leaving the valid index range."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "big.txt"
        _write(out, c1, c2, _gaps_cycle(self.N))

        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        assert manager.get_total_count() == self.N

        manager.set_window_size(self.N)
        window = manager.materialize_window(start_index=0)
        assert len(window) == self.N
        assert _is_monotonic([_gap(s) for s in window], ascending=False)

        presenter, view = self._presenter([c1, c2], manager)
        for _ in range(150):
            presenter._handle_next_schedule()
            assert 0 <= manager.get_current_index() < self.N
        for _ in range(150):
            presenter._handle_prev_schedule()
            assert 0 <= manager.get_current_index() < self.N
        assert view.render_count >= 1

        # Flip the sort through the presenter; ordering must invert.
        presenter._handle_sort_changed(["min_gap_mandatory"], ascending=True)
        manager.set_window_size(self.N)
        window_asc = manager.materialize_window(start_index=0)
        assert manager.get_total_count() == self.N
        assert _is_monotonic([_gap(s) for s in window_asc], ascending=True)

    def test_incremental_refresh_appends_many_batches(self, tmp_path):
        """While 'generation' is active, several batches of new schedules land
        on disk; each auto-refresh must absorb them and grow the total."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "feed.txt"

        first = 600
        _write(out, c1, c2, _gaps_cycle(first))
        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"])
        presenter, _ = self._presenter([c1, c2], manager)
        presenter.controller.engine_adapter.is_generation_active.return_value = True
        assert manager.get_total_count() == first

        total = first
        for extra in (200, 200, 200):
            new_total = total + extra
            # full cumulative list, skip the already-written prefix, append tail
            _write(out, c1, c2, _gaps_cycle(new_total), skip_count=total, append=True)
            assert presenter.auto_refresh_feed() is True
            assert manager.get_total_count() == new_total
            total = new_total
        assert total == 1200

    def test_repeated_resort_is_consistent_and_leak_free(self, tmp_path):
        """Sorting by every metric, many times over, must keep the total and
        the window length stable and must never spawn lingering processes."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "resort.txt"
        size = 800
        _write(out, c1, c2, _gaps_cycle(size))
        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.set_window_size(size)

        before = len(multiprocessing.active_children())
        for _ in range(12):
            for key in METRIC_KEYS:
                manager.sort_collection([key], ascending=False)
                window = manager.materialize_window(start_index=0)
                assert len(window) == size
                assert manager.get_total_count() == size
        time.sleep(0.2)
        after = len(multiprocessing.active_children())
        assert after <= before, "repeated sorting must not leak subprocesses"

# ---------------------------------------------------------------------------
# Additional headless GUI stress coverage
#
# More punishing variants of the existing GUI stress flow: full-collection
# window pagination through the manager, a long mixed navigation walk with
# mid-walk sort flips, fine-grained incremental refresh (many tiny batches),
# and idempotent re-sorting. All remain fully headless and leak-checked, and
# only use APIs already exercised above (CalendarPresenter, the manager and the
# _FakeView stub).
# ---------------------------------------------------------------------------


class TestGuiStressExtra:
    """Higher-volume, longer-running headless GUI stress."""

    N = 1500  # schedule blocks

    @pytest.fixture(autouse=True)
    def _reset_singleton(self):
        DataManager._instance = None
        yield
        DataManager._instance = None

    def _presenter(self, courses, manager):
        model = SimpleNamespace(
            data_manager=SimpleNamespace(get_courses=lambda: courses),
            get_exam_periods=lambda: [],
            get_user_excluded_dates=lambda: [],
            get_selected_programs=lambda: ["83101"],
            constraints=SchedulingConstraints(),
            get_program_course_hierarchy=lambda prog_id=None: {},
        )
        view = _FakeView()
        presenter = CalendarPresenter(view=view, model=model, collection_manager=manager)
        presenter.controller = MagicMock()
        presenter.controller.engine_adapter.is_generation_active.return_value = False
        return presenter, view

    def test_full_collection_window_pagination_is_complete_and_ordered(self, tmp_path):
        """Walk the entire sorted collection window by window; the pages must
        tile the full best-first ranking with no gaps, overlaps or reordering,
        including a partial final page (128 does not divide 1500)."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "gui_pages.txt"
        _write(out, c1, c2, _gaps_cycle(self.N))

        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        assert manager.get_total_count() == self.N

        manager.set_window_size(self.N)
        full = [_gap(s) for s in manager.materialize_window(start_index=0)]
        assert _is_monotonic(full, ascending=False)

        page = 128
        manager.set_window_size(page)
        seen = []
        start = 0
        while start < self.N:
            chunk = manager.materialize_window(start_index=start)
            assert 0 < len(chunk) <= page
            seen.extend(_gap(s) for s in chunk)
            start += page
        assert seen == full   # full coverage, exact order

    def test_long_mixed_navigation_walk_with_sort_flips(self, tmp_path):
        """A long, deterministic walk mixing next/prev bursts with periodic
        sort flips through the presenter; the current index must always stay in
        range and the total must never drift, no matter how the walk reorders
        the collection mid-flight."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "gui_walk.txt"
        _write(out, c1, c2, _gaps_cycle(self.N))

        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"], ascending=False)
        presenter, view = self._presenter([c1, c2], manager)

        ascending = False
        for step in range(1200):
            if step % 7 < 4:
                presenter._handle_next_schedule()
            else:
                presenter._handle_prev_schedule()
            if step % 200 == 199:                       # flip the sort periodically
                ascending = not ascending
                presenter._handle_sort_changed(["min_gap_mandatory"], ascending=ascending)
            idx = manager.get_current_index()
            assert 0 <= idx < self.N
            assert manager.get_total_count() == self.N
        assert view.render_count >= 1

    def test_many_tiny_incremental_refresh_batches(self, tmp_path):
        """Forty tiny batches of 25 land while 'generation' is active; each
        auto-refresh must absorb exactly one batch and grow the total by 25,
        stressing the incremental parse/append path far harder than the coarse
        batches in the baseline suite."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "gui_feed.txt"

        first = 100
        _write(out, c1, c2, _gaps_cycle(first))
        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.sort_collection(["min_gap_mandatory"])
        presenter, _ = self._presenter([c1, c2], manager)
        presenter.controller.engine_adapter.is_generation_active.return_value = True
        assert manager.get_total_count() == first

        total = first
        for _ in range(40):
            new_total = total + 25
            _write(out, c1, c2, _gaps_cycle(new_total), skip_count=total, append=True)
            assert presenter.auto_refresh_feed() is True
            assert manager.get_total_count() == new_total
            total = new_total
        assert total == first + 40 * 25

    def test_idempotent_resort_same_key_keeps_window_stable(self, tmp_path):
        """Sorting by the same key many times must be idempotent: identical
        window contents every time, a stable total, and no leaked processes."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "gui_idem.txt"
        size = 700
        _write(out, c1, c2, _gaps_cycle(size))
        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.set_window_size(size)

        before = len(multiprocessing.active_children())
        reference = None
        for _ in range(15):
            manager.sort_collection(["min_gap_mandatory"], ascending=False)
            gaps = [_gap(s) for s in manager.materialize_window(start_index=0)]
            assert len(gaps) == size
            assert manager.get_total_count() == size
            if reference is None:
                reference = gaps
            else:
                assert gaps == reference            # idempotent ordering
        time.sleep(0.2)
        after = len(multiprocessing.active_children())
        assert after <= before, "idempotent resorting must not leak subprocesses"

    def test_resort_every_metric_with_navigation_stays_bounded(self, tmp_path):
        """Cycle through every metric as a sort key, toggling direction, and
        navigate between resorts; the window length and total stay fixed and the
        current index never escapes the valid range."""
        c1, c2 = _course("10001"), _course("10002")
        out = tmp_path / "gui_metrics.txt"
        size = 600
        _write(out, c1, c2, _gaps_cycle(size))
        manager = ScheduleCollectionManager(str(out), _dm(c1, c2))
        manager.set_window_size(size)
        presenter, view = self._presenter([c1, c2], manager)

        ascending = False
        for _ in range(6):
            for key in METRIC_KEYS:
                presenter._handle_sort_changed([key], ascending=ascending)
                window = manager.materialize_window(start_index=0)
                assert len(window) == size
                assert manager.get_total_count() == size
                for _ in range(20):
                    presenter._handle_next_schedule()
                    assert 0 <= manager.get_current_index() < size
                ascending = not ascending
        assert view.render_count >= 1