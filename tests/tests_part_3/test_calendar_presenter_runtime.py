from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock
from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.MVP.presenters.calendar_presenter import CalendarPresenter
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal stand-in for the calendar view that records the calls the presenter makes.
class _FakeView:
    """Minimal calendar view — superset of the two originals: records refresh
    activity, exposes the sort/refresh/load-more callbacks, and supports the
    no-more-results signal."""

    def __init__(self):
        self.on_sort_changed = None       
        self.on_refresh_clicked = None
        self.on_load_more_clicked = None
        self.render_count = 0
        self.no_more_shown = 0
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

# Parser stub returning nothing, so a DataManager can be built without files.
class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []

# Minimal course helper for the test schedules.
def _course(cid):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo("83108", 1, "FALL", "Obligatory")])

# Build a stand-in model wrapping the given courses.
def _fake_model(courses):
    return SimpleNamespace(
        data_manager=SimpleNamespace(get_courses=lambda: courses),
        get_exam_periods=lambda: [],
        get_user_excluded_dates=lambda: [],
        get_selected_programs=lambda: [],
    )

# Return the day gap between the first and last exam of a schedule.
def _gap(schedule):
    days = sorted(e.exam_date for e in schedule.exams)
    return (days[-1] - days[0]).days

# Build one 2-exam schedule per requested gap.
def _schedules_for_gaps(c1, c2, gaps):
    return [
        Schedule(exams=[ScheduledExam(c1, date(2026, 2, 1)),
                        ScheduledExam(c2, date(2026, 2, 1 + g))])
        for g in gaps
    ]

# Write schedules to a results file.
def _write(out, c1, c2, gaps, skip_count=0, append=False):
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(_schedules_for_gaps(c1, c2, gaps))},
        str(out), skip_count=skip_count, append=append,
    )

# Write the gaps and return a ScheduleCollectionManager over them.
def _manager(tmp_path, gaps):
    c1, c2 = _course("10001"), _course("10002")
    out = tmp_path / "out" / "schedules.txt"
    _write(out, c1, c2, gaps)
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c1.course_id: c1, c2.course_id: c2}
    return ScheduleCollectionManager(str(out), dm), out, c1, c2

# Write three fixed schedules for the pagination/refresh tests.
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

# Build a CalendarPresenter wired to fakes, with the engine optionally reported active.
def _presenter(tmp_path, gaps, engine_active=True):
    work_dir = tmp_path / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    output_file = work_dir / "schedules.txt"

    c1, c2 = _course("10001"), _course("10002")
    dm = DataManager(parser=_DummyParser())
    dm.courses = {c1.course_id: c1, c2.course_id: c2}
    manager = ScheduleCollectionManager(str(output_file), dm)

    # Seed initial schedules first.
    FileOutputWriter().write_schedules(
        {("FALL", "Aleph"): iter(_schedules_for_gaps(c1, c2, gaps))},
        str(output_file),
    )

    view = _FakeView()
    model = _fake_model([c1, c2])
    presenter = CalendarPresenter(view=view, model=model, collection_manager=manager)

    # Engine state lives on the controller's adapter; tie it to the param.
    controller = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = engine_active
    presenter.controller = controller
    manager.engine_active = engine_active

    return presenter, view, manager

# Convenience presenter builder for the simpler tests.
def _make_presenter(tmp_path):
    out, dm, courses = _write_three_schedules(tmp_path)
    manager = ScheduleCollectionManager(str(out), dm)
    view = _FakeView()
    model = _fake_model(courses)
    presenter = CalendarPresenter(view=view, model=model, collection_manager=manager)
    return presenter, view, manager


# ===========================================================================
# Runtime re-sort
# ===========================================================================

# The presenter wires the view's sort callback on setup.
def test_presenter_wires_sort_callback(tmp_path):
    presenter, view, _ = _make_presenter(tmp_path)
    assert callable(view.on_sort_changed)
    assert view.on_sort_changed == presenter._handle_sort_changed

# Sorting reorders the collection and refreshes the visible window.
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

# Sorting never triggers the engine.
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

# Sorting leaves the constraints and the cache untouched.
def test_sort_does_not_invalidate_constraints_or_cache(tmp_path):
    presenter, view, manager = _make_presenter(tmp_path)
    manager.clear_cache = MagicMock(side_effect=AssertionError("must not clear cache on sort"))
    total_before = manager.get_total_count()
    presenter._handle_sort_changed(["min_gap_mandatory"])
    # Sorting must not drop/regenerate the index — the same valid schedules
    # remain; only their order changes.
    assert manager.get_total_count() == total_before == 3

# An invalid sort request is ignored without raising.
def test_invalid_sort_request_is_ignored_gracefully(tmp_path):
    presenter, view, manager = _make_presenter(tmp_path)
    # Should not raise — the handler swallows invalid specs.
    presenter._handle_sort_changed(["not_a_metric"])
    presenter._handle_sort_changed([])

# The active sort is preserved as the snapshot grows.
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


# The page number stays at 1 while generation is in progress.
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


# ===========================================================================
# Refresh-feed / window advancing
# ===========================================================================

# Applying sort+refresh ranks newly arrived blocks into the top.
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
    assert manager._user_sorted is True

# Sort + refresh materializes lazily.
def test_apply_sort_and_refresh_is_lazy(tmp_path):
    # Only the window batch is materialized; the rest stay as light offsets.
    manager, out, c1, c2 = _manager(tmp_path, list(range(2, 20)))  # 18 schedules
    manager.set_window_size(5)
    manager.sort_collection(["min_gap_mandatory"])

    window = manager.apply_sort_and_refresh()
    assert len(window) == 5
    assert manager.get_total_count() == 18

# 'Has more' is reported correctly after filling a window and advancing.
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
    assert manager.advance_window() is False

# The auto-refresh feed never invokes the engine.
def test_auto_refresh_feed_does_not_invoke_engine(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5, 9])
    presenter.auto_refresh_feed()
    presenter.controller.regenerate_schedules_snapshot.assert_not_called()
    presenter.controller.engine_adapter.generate_from_model.assert_not_called()

# Advancing past the window refreshes while the engine is active.
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

# At the boundary with the engine idle, the end-of-results state is shown.
def test_next_at_boundary_engine_idle_shows_end_of_results(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5], engine_active=False)
    manager.jump_to_schedule(manager.get_total_count() - 1)

    presenter._handle_next_schedule()
    assert view.no_more_shown == 1

# The auto-refresh feed keeps polling, then stops when generation ends.
def test_auto_refresh_feed_continues_then_terminates(tmp_path):
    presenter, view, manager = _presenter(tmp_path, [3, 5, 9], engine_active=True)
    # While the worker is alive, the feed keeps polling.
    assert presenter.auto_refresh_feed() is True
    # Worker signals completion -> the feed stops after a final render.
    presenter.controller.engine_adapter.is_generation_active.return_value = False
    view.render_count = 0
    assert presenter.auto_refresh_feed() is False
    assert view.render_count >= 1