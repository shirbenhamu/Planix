from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.MVP.presenters.calendar_presenter import CalendarPresenter
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


def _schedules_for_gaps(c1, c2, gaps):
    return [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                        ScheduledExam(c2, date(2026, 2, 1 + g))])
        for g in gaps
    ]


def _write(out, c1, c2, gaps, skip_count=0, append=False):
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(_schedules_for_gaps(c1, c2, gaps))},
        str(out), skip_count=skip_count, append=append,
    )


def _manager(tmp_path, gaps):
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "out" / "schedules.txt"
    _write(out, c1, c2, gaps)
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c1.course_id: c1, c2.course_id: c2}
    return ScheduleCollectionManager(str(out), dm), out, c1, c2


def _gap(schedule):
    days = sorted(e.exam_date for e in schedule.exams)
    return (days[-1] - days[0]).days


# --- PLAN-503/505: apply_sort_and_refresh factors new blocks into the top ----
def test_apply_sort_and_refresh_ranks_new_blocks_into_top(tmp_path):
    manager, out, c1, c2 = _manager(tmp_path, [3, 5])
    manager.set_window_size(2)
    manager.sort_collection(["min_gap_mandatory"])  # desc -> [5, 3]
    assert [_gap(s) for s in manager.materialize_window()] == [5, 3]

    # Engine discovers a better schedule (gap 9). Regenerate-all + skip the 2 done.
    _write(out, c1, c2, [3, 5, 9], skip_count=2, append=True)

    refreshed = manager.apply_sort_and_refresh()
    # The new schedule is ranked into the top WITHOUT re-selecting the sort.
    assert [_gap(s) for s in refreshed] == [9, 5]
    assert manager._user_sorted is True  # active sort preserved (PLAN-505)


def test_apply_sort_and_refresh_is_lazy(tmp_path):
    # Only the window batch is materialized; the rest stay as light offsets.
    manager, out, c1, c2 = _manager(tmp_path, list(range(2, 20)))  # 18 schedules
    manager.set_window_size(5)
    manager.sort_collection(["min_gap_mandatory"])

    window = manager.apply_sort_and_refresh()
    assert len(window) == 5
    assert manager.get_total_count() == 18  # all indexed, only 5 materialized


# --- window advancing / boundary (PLAN-414/415) -----------------------------
def test_has_more_after_window_and_advance(tmp_path):
    manager, *_ = _manager(tmp_path, [2, 3, 4, 5, 6])
    manager.set_window_size(2)
    manager.sort_collection(["min_gap_mandatory"])

    assert manager.has_more_after_window() is True
    assert manager.advance_window() is True
    assert manager.get_window_start() == 2
    assert manager.advance_window() is True
    assert manager.get_window_start() == 4
    # Only one schedule left in the final window -> nothing after it.
    assert manager.has_more_after_window() is False
    assert manager.advance_window() is False  # at the end


# --- presenter wiring -------------------------------------------------------
class _FakeView:
    def __init__(self):
        self.on_sort_changed = None
        self.on_refresh_feed_clicked = None
        self.on_refresh_clicked = None
        self.no_more_shown = 0
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

    def show_no_more_results(self):
        self.no_more_shown += 1


def _fake_model(courses):
    return SimpleNamespace(
        data_manager=SimpleNamespace(get_courses=lambda: courses),
        get_exam_periods=lambda: [],
        get_user_excluded_dates=lambda: [],
        get_selected_programs=lambda: [],
    )


def _presenter(tmp_path, gaps, engine_active=False):
    manager, out, c1, c2 = _manager(tmp_path, gaps)
    view = _FakeView()
    model = _fake_model([c1, c2])
    presenter = CalendarPresenter(view=view, model=model, collection_manager=manager)

    controller = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = engine_active
    presenter.controller = controller
    return presenter, view, manager



# --- PLAN-421 Trigger Logic: toolbar refresh -> Presenter.refresh_feed --------
def test_refresh_feed_button_hook_refreshes_top_window_without_engine(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5, 9])
    manager.set_window_size(2)
    manager.sort_collection(["min_gap_mandatory"])
    manager.jump_to_schedule(1)
    view.render_count = 0

    manager.apply_sort_and_refresh = MagicMock(wraps=manager.apply_sort_and_refresh)
    view.on_refresh_feed_clicked()

    manager.apply_sort_and_refresh.assert_called_once_with(reset_to_top=True)
    assert manager.get_current_index() == 0
    assert manager.get_window_start() == 0
    assert view.render_count >= 1
    presenter.controller.regenerate_schedules_snapshot.assert_not_called()
    presenter.controller.engine_adapter.generate_from_model.assert_not_called()


def test_refresh_feed_button_hook_supports_legacy_callback_name(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5, 9])

    assert view.on_refresh_clicked.__self__ is presenter
    assert view.on_refresh_clicked.__name__ == "refresh_feed"


# --- PLAN-421 Predictive Auto-Refresh: crossing active window boundary --------
def test_next_crossing_active_window_refreshes_then_advances_to_next_batch(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [2, 3, 4, 5, 6, 7], engine_active=True)
    manager.set_window_size(5)
    manager.sort_collection(["min_gap_mandatory"])
    manager.jump_to_schedule(4)
    view.render_count = 0

    manager.apply_sort_and_refresh = MagicMock(wraps=manager.apply_sort_and_refresh)
    presenter._handle_next_schedule()

    manager.apply_sort_and_refresh.assert_called_once_with(reset_to_top=False)
    assert manager.get_window_start() == 5
    assert manager.get_current_index() == 5
    assert view.render_count >= 1


# --- PLAN-421 Completion Logic: engine idle lifts the top-N boundary ----------
def test_next_crossing_window_boundary_when_engine_idle_does_not_auto_refresh(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [2, 3, 4, 5, 6, 7], engine_active=False)
    manager.set_window_size(5)
    manager.sort_collection(["min_gap_mandatory"])
    manager.jump_to_schedule(4)

    manager.apply_sort_and_refresh = MagicMock(wraps=manager.apply_sort_and_refresh)
    presenter._handle_next_schedule()

    manager.apply_sort_and_refresh.assert_not_called()
    assert manager.get_current_index() == 5

# --- refresh-feed via auto-refresh: re-ranks without re-running the engine ---
def test_auto_refresh_feed_does_not_invoke_engine(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5, 9])
    presenter.auto_refresh_feed()
    presenter.controller.regenerate_schedules_snapshot.assert_not_called()
    presenter.controller.engine_adapter.generate_from_model.assert_not_called()


# --- PLAN-502 navigate-beyond triggers feed while engine active -------------
def test_next_beyond_window_refreshes_when_engine_active(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5], engine_active=True)
    # Park on the last known schedule.
    manager.jump_to_schedule(manager.get_total_count() - 1)

    # Engine streams a 3rd schedule (gap 7) into the same output file: the
    # real flow regenerates all and skips the 2 already written.
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(
            _schedules_for_gaps(_course("10001"), _course("10002"), [3, 5, 7]))},
        manager._output_file_path, skip_count=2, append=True,
    )

    before = manager.get_current_index()
    presenter._handle_next_schedule()
    # The feed pulled the new schedule and advanced onto it.
    assert manager.get_current_index() == before + 1
    assert view.no_more_shown == 0


# --- PLAN-502 / Boundary: engine finished and no more -> End of results ------
def test_next_at_boundary_engine_idle_shows_end_of_results(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5], engine_active=False)
    manager.jump_to_schedule(manager.get_total_count() - 1)

    presenter._handle_next_schedule()
    assert view.no_more_shown == 1


# --- PLAN-504 termination: auto-refresh stops when worker dies ---------------
def test_auto_refresh_feed_continues_then_terminates(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5, 9], engine_active=True)

    # While the worker is alive, the feed keeps polling.
    assert presenter.auto_refresh_feed() is True

    # Worker signals completion -> the feed stops after a final render.
    presenter.controller.engine_adapter.is_generation_active.return_value = False
    view.render_count = 0
    assert presenter.auto_refresh_feed() is False
    assert view.render_count >= 1  # final full render issued on termination
