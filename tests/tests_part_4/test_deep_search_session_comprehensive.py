import itertools
import pytest
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from multiprocessing import Queue, Value
from src.engine.exam_scheduler import ExamScheduler
from src.engine.engine_adapter import PlanixEngineAdapter
from src.engine.scheduling_constraints import SchedulingConstraints
from src.metrics.metrics_calculator import MetricsCalculator
from src.output.file_output_writer import FileOutputWriter
from src.data_manager import DataManager
from src.parsers.base_parser import BaseParser
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.MVP.presenters.app_controller import AppController
from src.MVP.presenters.calendar_presenter import CalendarPresenter
from src.MVP.views.components.top_toolbar import TopToolbar
from src.MVP.views.components.ui_components import ICON_SEARCH
from src.MVP.views.ui_utils import TRANSLATIONS

PROGRAM = "83108"

# ===========================================================================
# Shared builders
# ===========================================================================

def make_course(course_id, requirement="Obligatory", name=None):
    info = [ProgramCourseInfo(program_id=PROGRAM, year=1, semester="FALL", requirement=requirement)]
    return Course(course_id, name or f"C{course_id}", "Teacher", "Exam", info)


def make_period(num_days=6):
    return ExamPeriod(
        semester="FALL", moed="Aleph",
        start_date=date(2026, 1, 1), end_date=date(2026, 1, num_days),
        excluded_dates=[],
    )


class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []


def make_data_manager(courses):
    DataManager._instance = None
    dm = DataManager(_DummyParser())
    dm.courses = {c.course_id: c for c in courses}
    return dm


SCHEDULE_BLOCK = (
    "=== Complete Academic Year Schedules ===\n\n"
    "--- FULL SYSTEM OPTION 1 ---\n"
    "Date: 01-02-2026 | Course: 10001 - Intro | Instructor: Teacher A\n"
    "Date: 05-02-2026 | Course: 10002 - Logic | Instructor: Teacher B\n"
    "METRICS|4.0|4.0|0|4|1\n"
    "------------------------------------------------------------\n"
)


# ===========================================================================
# 1. Engine: count + deep search
# ===========================================================================
class TestEngineCountAndDeepSearch:
    def _courses_periods(self):
        return [make_course("10001"), make_course("10002")], [make_period(6)]

    def test_count_total_equals_product_of_per_period_counts(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        gens = scheduler.generate_schedules(courses, periods, [PROGRAM])
        brute = sum(1 for _ in itertools.product(*[list(g) for g in gens.values()]))

        assert scheduler.count_total_schedules(courses, periods, [PROGRAM]) == brute

    def test_count_total_respects_per_period_cap(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        assert scheduler.count_total_schedules(courses, periods, [PROGRAM], max_per_period=3) == 3

    def test_count_total_zero_path_raises_for_no_matching_program(self):
        # The engine raises; the count worker (tested below) turns this into 0.
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        with pytest.raises(ValueError):
            scheduler.count_total_schedules(courses, periods, ["NO_SUCH"])

    def test_find_best_returns_top_n_in_best_first_order(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        sort_spec = [(1, False)]  # avg_gap_all descending
        calc = MetricsCalculator()
        all_keys = sorted(
            scheduler._deep_search_sort_key(
                calc.compute(Schedule(exams=[e for sub in combo for e in sub.exams])).as_tuple(),
                sort_spec)
            for combo in itertools.product(
                *[list(g) for g in scheduler.generate_schedules(courses, periods, [PROGRAM]).values()])
        )

        best, scanned = scheduler.find_best_schedules(
            courses, periods, [PROGRAM], sort_spec, top_n=3, max_scan=10 ** 9)
        got = [scheduler._deep_search_sort_key(m, sort_spec) for _s, m in best]

        assert len(best) == 3
        assert got == all_keys[:3]
        assert got == sorted(got)
        assert scanned == len(all_keys)

    def test_find_best_multi_criteria_with_ascending(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        spec = [(4, True), (1, False)]  # max_exams_per_day asc, then avg_gap desc
        calc = MetricsCalculator()
        all_keys = sorted(
            scheduler._deep_search_sort_key(
                calc.compute(Schedule(exams=[e for sub in combo for e in sub.exams])).as_tuple(), spec)
            for combo in itertools.product(
                *[list(g) for g in scheduler.generate_schedules(courses, periods, [PROGRAM]).values()])
        )
        best, _ = scheduler.find_best_schedules(courses, periods, [PROGRAM], spec, top_n=5, max_scan=10 ** 9)
        got = [scheduler._deep_search_sort_key(m, spec) for _s, m in best]
        assert got == all_keys[:5]

    def test_find_best_top_n_larger_than_total_keeps_all(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        total = scheduler.count_total_schedules(courses, periods, [PROGRAM])
        best, scanned = scheduler.find_best_schedules(
            courses, periods, [PROGRAM], [(1, False)], top_n=10 ** 9, max_scan=10 ** 9)
        assert len(best) == total
        assert scanned == total

    def test_find_best_respects_max_scan(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        best, scanned = scheduler.find_best_schedules(
            courses, periods, [PROGRAM], [(1, False)], top_n=100, max_scan=2)
        assert scanned == 2 and len(best) == 2

    def test_find_best_respects_zero_time_budget(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        _best, scanned = scheduler.find_best_schedules(
            courses, periods, [PROGRAM], [(1, False)], top_n=100,
            max_seconds=0, progress_every=1)
        assert scanned == 1

    def test_find_best_respects_cancel_callback(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        best, scanned = scheduler.find_best_schedules(
            courses, periods, [PROGRAM], [(1, False)], top_n=100,
            max_scan=10 ** 9, progress_every=1, cancel_callback=lambda: True)
        assert scanned == 1 and len(best) == 1

    def test_find_best_reports_progress(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        seen = []
        scheduler.find_best_schedules(
            courses, periods, [PROGRAM], [(1, False)], top_n=2,
            max_scan=10 ** 9, progress_callback=seen.append, progress_every=1)
        assert seen and seen[-1] == scheduler.count_total_schedules(courses, periods, [PROGRAM])

    def test_partial_metrics_match_full_compute(self):
        """The scan-time optimization must produce the SAME values as the full
        calculator for every metric index."""
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        calc = MetricsCalculator()
        gens = scheduler.generate_schedules(courses, periods, [PROGRAM])
        for combo in itertools.product(*[list(g) for g in gens.values()]):
            sched = Schedule(exams=[e for sub in combo for e in sub.exams])
            full = calc.compute(sched).as_tuple()
            for index in range(5):
                assert calc.calculate_indices(sched, [index])[index] == full[index]


# ===========================================================================
# 2. FileOutputWriter
# ===========================================================================
class TestFileOutputWriter:
    def _count(self, path):
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read().count("--- FULL SYSTEM OPTION")

    def test_uncapped_untimed_writes_everything(self, tmp_path):
        scheduler = ExamScheduler()
        courses, periods = [make_course("10001"), make_course("10002")], [make_period(5)]
        total = scheduler.count_total_schedules(courses, periods, [PROGRAM])
        out = tmp_path / "all.txt"
        FileOutputWriter(max_time_seconds=None, max_per_period=None).write_schedules(
            scheduler.generate_schedules(courses, periods, [PROGRAM]), str(out))
        assert self._count(out) == total

    def test_explicit_per_period_cap(self, tmp_path):
        scheduler = ExamScheduler()
        courses, periods = [make_course("10001"), make_course("10002")], [make_period(5)]
        out = tmp_path / "capped.txt"
        FileOutputWriter(max_time_seconds=None, max_per_period=2).write_schedules(
            scheduler.generate_schedules(courses, periods, [PROGRAM]), str(out))
        assert self._count(out) == 2

    def test_write_schedule_list_uses_precomputed_metrics(self, tmp_path):
        scheduler = ExamScheduler()
        courses, periods = [make_course("10001"), make_course("10002")], [make_period(6)]
        best, _ = scheduler.find_best_schedules(courses, periods, [PROGRAM], [(1, False)], top_n=3, max_scan=10 ** 9)
        out = tmp_path / "best.txt"
        FileOutputWriter().write_schedule_list(best, str(out))
        text = open(out, encoding="utf-8").read()
        assert self._count(out) == 3
        assert text.count("METRICS|") == 3  # metrics carried through, not dropped

    def test_write_schedule_list_empty_writes_no_combinations(self, tmp_path):
        out = tmp_path / "empty.txt"
        FileOutputWriter().write_schedule_list([], str(out))
        assert "No valid full-year combinations" in open(out, encoding="utf-8").read()


# ===========================================================================
# 3. Adapter background workers + in-memory IPC (no temp files)
# ===========================================================================
class TestAdapterIPC:
    def _courses_periods(self):
        return [make_course("10001"), make_course("10002")], [make_period(6)]

    def test_count_worker_puts_total_on_queue(self):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        expected = scheduler.count_total_schedules(courses, periods, [PROGRAM])
        q = Queue()
        PlanixEngineAdapter._count_worker(courses, periods, [PROGRAM], SchedulingConstraints(), q)
        assert q.get(timeout=2) == expected

    def test_count_worker_reports_zero_on_bad_input(self):
        courses, periods = self._courses_periods()
        q = Queue()
        PlanixEngineAdapter._count_worker(courses, periods, ["NO_SUCH"], SchedulingConstraints(), q)
        assert q.get(timeout=2) == 0

    def test_read_total_count_drains_queue_then_caches(self):
        adapter = PlanixEngineAdapter()
        adapter._count_queue = Queue()
        adapter._count_queue.put(63_446_479_018_203_067_093_536_768_000_000)  # huge int survives
        assert adapter.read_total_count() == 63_446_479_018_203_067_093_536_768_000_000
        assert adapter.read_total_count() == 63_446_479_018_203_067_093_536_768_000_000

    def test_read_total_count_none_when_not_started(self):
        assert PlanixEngineAdapter().read_total_count() is None

    def test_deep_search_worker_writes_top_n_and_publishes_scanned(self, tmp_path):
        scheduler = ExamScheduler()
        courses, periods = self._courses_periods()
        total = scheduler.count_total_schedules(courses, periods, [PROGRAM])
        out = tmp_path / "best.txt"
        scanned_value = Value("q", 0)
        PlanixEngineAdapter._deep_search_worker(
            courses, periods, [PROGRAM], SchedulingConstraints(),
            [(1, False)], 3, 10 ** 9, None, str(out), scanned_value)
        with open(out, encoding="utf-8") as fh:
            assert fh.read().count("--- FULL SYSTEM OPTION") == min(3, total)
        assert scanned_value.value == total

    def test_read_deep_search_scanned(self):
        adapter = PlanixEngineAdapter()
        assert adapter.read_deep_search_scanned() == 0
        adapter._deep_scanned = Value("q", 4242)
        assert adapter.read_deep_search_scanned() == 4242

    def test_cancel_active_worker_terminates_running_process(self):
        adapter = PlanixEngineAdapter()
        proc = MagicMock()
        proc.is_alive.return_value = True
        adapter._worker_process = proc
        assert adapter.cancel_active_worker() is True
        proc.terminate.assert_called_once()
        assert adapter._worker_process is None

    def test_cancel_active_worker_no_process(self):
        assert PlanixEngineAdapter().cancel_active_worker() is False

    def test_is_count_active_reflects_process_state(self):
        adapter = PlanixEngineAdapter()
        assert adapter.is_count_active() is False
        proc = MagicMock()
        proc.is_alive.return_value = True
        adapter._count_process = proc
        assert adapter.is_count_active() is True
        proc.is_alive.return_value = False
        assert adapter.is_count_active() is False
        assert adapter._count_process is None  # cleared once done


# ===========================================================================
# 4. ScheduleCollectionManager
# ===========================================================================
class TestCollectionManager:
    def test_get_active_sort_spec_defaults_then_follows_user(self, tmp_path):
        dm = make_data_manager([make_course("10001"), make_course("10002")])
        out = tmp_path / "s.txt"
        out.write_text(SCHEDULE_BLOCK, encoding="utf-8")
        cm = ScheduleCollectionManager(str(out), dm)

        default = cm.get_active_sort_spec()
        assert isinstance(default, list) and default  # documented default present

        cm.sort_collection(["max_exams_per_day"], ascending=True)
        assert cm.get_active_sort_spec() == [(4, True)]

    def test_unknown_course_is_synthesized_not_fatal(self, tmp_path):
        # data manager has NO courses -> the block's course must be synthesized
        dm = make_data_manager([])
        out = tmp_path / "s.txt"
        out.write_text(SCHEDULE_BLOCK, encoding="utf-8")
        cm = ScheduleCollectionManager(str(out), dm)

        schedule = cm.get_current_schedule()  # must NOT raise
        ids = {e.course.course_id for e in schedule.exams}
        names = {e.course.course_name for e in schedule.exams}
        assert ids == {"10001", "10002"}
        assert "Intro" in names and "Logic" in names  # name carried from the block

    def test_clear_cache_resets_state(self, tmp_path):
        dm = make_data_manager([make_course("10001"), make_course("10002")])
        out = tmp_path / "s.txt"
        out.write_text(SCHEDULE_BLOCK, encoding="utf-8")
        cm = ScheduleCollectionManager(str(out), dm)
        assert cm.get_total_count() == 1
        cm.clear_cache()
        # Offsets dropped + scan position reset (re-scan on next access).
        assert cm._offsets == [] and cm._scan_position == 0 and cm._current_index == 0


# ===========================================================================
# 5. CalendarPresenter: counter reset, defensive constraints, drag & drop
# ===========================================================================
class TestCalendarPresenter:
    @pytest.fixture
    def view(self):
        v = MagicMock()
        v.active_month_indices = []
        return v

    @pytest.fixture
    def model(self):
        m = MagicMock()
        m.get_user_excluded_dates.return_value = []
        m.get_exam_periods.return_value = []
        m.get_selected_programs.return_value = []
        m.data_manager.get_courses.return_value = []
        return m

    @pytest.fixture
    def collection(self):
        c = MagicMock()
        c.get_total_count.return_value = 0
        c.get_current_index.return_value = 0
        return c

    def test_counter_resets_to_zero_when_idle_and_empty(self, view, model, collection):
        collection.get_total_count.return_value = 0
        presenter = CalendarPresenter(view, model, collection)  # controller=None -> not generating
        view.update_pagination.reset_mock()
        view.show_empty_state.reset_mock()

        presenter.refresh_presenter_state()

        view.show_empty_state.assert_called()
        view.update_pagination.assert_called_with(current_page=0, total_pages=0)

    def test_counter_not_reset_while_generation_active(self, view, model, collection):
        collection.get_total_count.return_value = 0
        presenter = CalendarPresenter(view, model, collection)
        controller = MagicMock()
        controller.engine_adapter.is_generation_active.return_value = True
        controller.input_presenter = None
        presenter.controller = controller
        view.update_pagination.reset_mock()

        presenter.refresh_presenter_state()

        view.show_empty_state.assert_called()
        view.update_pagination.assert_not_called()   # left alone mid-generation

    def test_pagination_only_leaves_counter_untouched_when_empty(self, view, model, collection):
        # The reset-to-0 lives in refresh_presenter_state (the terminal render),
        # NOT in the lightweight pagination poll, which returns early on 0.
        collection.get_total_count.return_value = 0
        presenter = CalendarPresenter(view, model, collection)
        view.update_pagination.reset_mock()
        presenter.refresh_pagination_only()
        view.update_pagination.assert_not_called()

    def test_render_survives_constraints_without_selected_religions(self, view, model, collection):
        """Render must not blank the board when constraints lack the religion
        field (the getattr fix); it should reach render_calendar_data."""
        model.constraints = SchedulingConstraints()  # real object, no selected_religions
        model.data_manager.get_courses.return_value = [make_course("10001")]
        presenter = CalendarPresenter(view, model, collection)

        exam = ScheduledExam(course=make_course("10001"), exam_date=date(2026, 2, 15))
        schedule = Schedule(exams=[exam])
        presenter._setup_calendar_grid_dimensions(schedule)
        presenter._render_active_schedule(schedule)  # would AttributeError before the fix

        view.render_calendar_data.assert_called_once()

    def test_drag_move_applies_and_refreshes(self, view, model, collection):
        presenter = CalendarPresenter(view, model, collection)
        presenter.cell_to_date_mapping = {"1-0": date(2026, 2, 1), "1-4": date(2026, 2, 5)}
        presenter._edit_session = MagicMock()
        presenter._edit_session.move_exam.return_value = SimpleNamespace(success=True, reason="")
        with patch.object(presenter, "_active_board"), patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_exam_dropped("10001", "1-0", "1-4")
        presenter._edit_session.move_exam.assert_called_once_with("10001", date(2026, 2, 1), date(2026, 2, 5))
        refresh.assert_called_once()

    def test_drag_to_unknown_cell_snaps_back(self, view, model, collection):
        presenter = CalendarPresenter(view, model, collection)
        presenter.cell_to_date_mapping = {"1-0": date(2026, 2, 1)}  # target unmapped
        presenter._edit_session = MagicMock()
        with patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_exam_dropped("10001", "1-0", "9-9")
        presenter._edit_session.move_exam.assert_not_called()
        refresh.assert_called_once()  # redraw -> snap back

    def test_validate_drop_uses_can_move(self, view, model, collection):
        presenter = CalendarPresenter(view, model, collection)
        presenter.cell_to_date_mapping = {"1-0": date(2026, 2, 1), "1-4": date(2026, 2, 5)}
        presenter._edit_session = MagicMock()
        presenter._edit_session.can_move.return_value = SimpleNamespace(success=True)
        with patch.object(presenter, "_active_board"):
            assert presenter._validate_drop("10001", "1-0", "1-4") is True
        presenter._edit_session.can_move.assert_called_once()

    def test_validate_drop_false_for_unmapped_cells(self, view, model, collection):
        presenter = CalendarPresenter(view, model, collection)
        presenter.cell_to_date_mapping = {}
        assert presenter._validate_drop("10001", "x", "y") is False

    def test_undo_reverts_and_refreshes(self, view, model, collection):
        presenter = CalendarPresenter(view, model, collection)
        presenter._edit_session = MagicMock()
        with patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_undo()
        presenter._edit_session.undo.assert_called_once()
        refresh.assert_called_once()


# ===========================================================================
# 6. AppController orchestration
# ===========================================================================
def _make_controller():
    c = object.__new__(AppController)
    c.output_path = "fake_output.txt"
    c.load_all_output_path = "fake_all.txt"
    c._total_count = None
    c._all_loaded = False
    c._deep_search_active = False
    c._deep_search_started = None
    c.model = MagicMock()
    c.model.get_selected_programs.return_value = ["P1"]
    c.engine_adapter = MagicMock()
    c.engine_adapter.read_total_count.return_value = 0
    c.engine_adapter.read_deep_search_scanned.return_value = 0
    c.collection_manager = MagicMock()
    c.collection_manager.get_active_sort_spec.return_value = [(1, False)]
    c.app_window = MagicMock()
    c.calendar_presenter = MagicMock()
    c._set_constraints_save_state = MagicMock()
    c._lock_engine_triggers = MagicMock()
    return c


class TestControllerDeepSearch:
    def test_start_launches_deep_search_and_locks_engine(self):
        c = _make_controller()
        c.engine_adapter.is_generation_active.return_value = False
        c.load_all_schedules()

        _, kwargs = c.engine_adapter.deep_search_from_model.call_args
        assert kwargs["output_path"] == c.load_all_output_path
        assert kwargs["sort_spec"] == [(1, False)]
        assert kwargs["top_n"] == AppController.DEEP_SEARCH_TOP_N
        assert kwargs["max_seconds"] == AppController.DEEP_SEARCH_MAX_SECONDS
        assert c._deep_search_active is True
        c.calendar_presenter.view.set_load_more_enabled.assert_called_once_with(False)
        c.calendar_presenter.view.set_load_all_running.assert_called_once_with(True)
        c._lock_engine_triggers.assert_called_once_with(True)
        c.app_window.after.assert_called_once()

    def test_start_denied_while_generation_active(self):
        c = _make_controller()
        c.engine_adapter.is_generation_active.return_value = True
        c.load_all_schedules()
        c.engine_adapter.deep_search_from_model.assert_not_called()

    def test_second_click_cancels(self):
        c = _make_controller()
        c._deep_search_active = True
        c.load_all_schedules()
        c.engine_adapter.cancel_active_worker.assert_called_once()
        c.engine_adapter.deep_search_from_model.assert_not_called()
        assert c._deep_search_active is False
        c.calendar_presenter.view.set_load_all_running.assert_called_with(False)
        c.calendar_presenter.view.set_load_more_enabled.assert_called_with(True)
        c._lock_engine_triggers.assert_called_with(False)

    def test_percent_is_time_based(self):
        import time
        c = _make_controller()
        c._deep_search_started = time.time() - (AppController.DEEP_SEARCH_MAX_SECONDS / 2)
        assert 45.0 <= c._deep_search_percent() <= 55.0

    def test_monitor_finalizes_swaps_file_and_blocks_further_search(self, monkeypatch):
        c = _make_controller()
        c._deep_search_active = True
        c.engine_adapter.is_generation_active.return_value = False
        c.engine_adapter.read_deep_search_scanned.return_value = 8_150_000
        c.collection_manager.get_total_count.return_value = 100_000
        replaced = {}
        monkeypatch.setattr("os.replace", lambda s, d: replaced.update(s=s, d=d))

        c._monitor_load_all_progress()

        assert replaced == {"s": c.load_all_output_path, "d": c.output_path}
        assert c._deep_search_active is False
        assert c._all_loaded is True
        c.collection_manager.clear_cache.assert_called_once()
        c.calendar_presenter.view.set_load_more_enabled.assert_called_with(False)
        c.calendar_presenter.view.set_load_all_enabled.assert_called_with(False)
        c.calendar_presenter.view.set_deep_search_done.assert_called_once_with(8_150_000, 100_000)
        c._lock_engine_triggers.assert_called_with(False)

    def test_monitor_reports_progress_without_touching_collection(self):
        import time
        c = _make_controller()
        c._deep_search_active = True
        c._deep_search_started = time.time()
        c.engine_adapter.is_generation_active.return_value = True
        c._monitor_load_all_progress()
        c.app_window.after.assert_called_once()
        c.calendar_presenter.view.set_load_all_progress.assert_called_once()
        c.collection_manager.build_snapshot_index.assert_not_called()

    def test_monitor_stops_silently_after_cancel(self):
        c = _make_controller()
        c._deep_search_active = False
        c._monitor_load_all_progress()
        c.app_window.after.assert_not_called()
        c.calendar_presenter.view.set_load_all_progress.assert_not_called()

    def test_lock_engine_triggers_disables_run_and_sync(self):
        c = _make_controller()
        del c._lock_engine_triggers  # use the REAL method
        AppController._lock_engine_triggers(c, True)
        c.app_window.input_view.btn_run.configure.assert_called_with(state="disabled")
        c.app_window.calendar_view.toolbar.set_sync_enabled.assert_called_with(False)
        c.app_window.monthly_view.toolbar.set_sync_enabled.assert_called_with(False)

        AppController._lock_engine_triggers(c, False)
        c.app_window.input_view.btn_run.configure.assert_called_with(state="normal")
        c.app_window.calendar_view.toolbar.set_sync_enabled.assert_called_with(True)


class TestControllerIndicators:
    def test_remaining_is_total_minus_loaded(self):
        c = _make_controller()
        c._total_count = 2_000_000
        c.collection_manager.get_total_count.return_value = 200_000
        c._update_remaining_indicator()
        c.calendar_presenter.view.update_remaining_indicator.assert_called_once_with(
            remaining=1_800_000, total=2_000_000, loaded=200_000, all_loaded=False)

    def test_remaining_clamps_and_marks_all_loaded(self):
        c = _make_controller()
        c._total_count = 500
        c.collection_manager.get_total_count.return_value = 500
        c._update_remaining_indicator()
        _, kwargs = c.calendar_presenter.view.update_remaining_indicator.call_args
        assert kwargs["remaining"] == 0 and kwargs["all_loaded"] is True

    def test_remaining_noop_until_total_known(self):
        c = _make_controller()
        c._total_count = None
        c._update_remaining_indicator()
        c.calendar_presenter.view.update_remaining_indicator.assert_not_called()

    def test_poll_total_count_reads_and_updates_when_done(self):
        c = _make_controller()
        c.engine_adapter.is_count_active.return_value = False
        c.engine_adapter.read_total_count.return_value = 12345
        c.collection_manager.get_total_count.return_value = 100
        c._poll_total_count()
        assert c._total_count == 12345
        c.app_window.after.assert_not_called()
        c.calendar_presenter.view.update_remaining_indicator.assert_called_once()

    def test_poll_total_count_reschedules_while_active(self):
        c = _make_controller()
        c.engine_adapter.is_count_active.return_value = True
        c._poll_total_count()
        c.app_window.after.assert_called_once()
        assert c._total_count is None

    def test_start_total_count_skipped_once_all_loaded(self):
        c = _make_controller()
        c._all_loaded = True
        c.start_total_count()
        c.engine_adapter.count_total_from_model.assert_not_called()

    def test_start_total_count_shows_calculating(self):
        c = _make_controller()
        c.engine_adapter.is_count_active.return_value = False
        c.start_total_count()
        c.engine_adapter.count_total_from_model.assert_called_once_with(c.model)
        c.calendar_presenter.view.set_load_more_calculating.assert_called_once()
        c.app_window.after.assert_called_once()


# ===========================================================================
# 7. Toolbar + view UI (display-independent via stubs)
# ===========================================================================
def _toolbar_stub():
    tb = object.__new__(TopToolbar)
    tb.current_lang = "he"
    tb._f_icon = MagicMock()
    tb._f_btn = MagicMock()
    tb.load_all_btn = MagicMock()
    tb.load_more_btn = MagicMock()
    tb.tip_load_all = SimpleNamespace(text="")
    tb.tip_load_more = SimpleNamespace(text="")
    tb.remaining_lbl = MagicMock()
    tb._load_all_running = False
    tb._load_more_remaining = None
    return tb


class TestToolbarUI:
    def test_deep_search_button_toggles_search_and_x(self):
        tb = _toolbar_stub()
        tb.set_load_all_running(True)
        assert tb.load_all_btn.configure.call_args.kwargs["text"] == "✕"
        assert tb.tip_load_all.text == TRANSLATIONS["load_all_cancel"]["he"]

        tb.set_load_all_running(False)
        assert tb.load_all_btn.configure.call_args.kwargs["text"] == ICON_SEARCH
        assert tb.tip_load_all.text == TRANSLATIONS["load_all_tooltip"]["he"]

    def test_deep_search_button_enable_disable(self):
        tb = _toolbar_stub()
        tb.set_load_all_enabled(False)
        tb.load_all_btn.configure.assert_called_with(state="disabled")
        tb.set_load_all_enabled(True)
        tb.load_all_btn.configure.assert_called_with(state="normal")

    def test_load_more_remaining_tooltip(self):
        tb = _toolbar_stub()
        tb.set_load_more_remaining(300_000_000)
        assert "300,000,000" in tb.tip_load_more.text
        tb.set_load_more_remaining(0)
        assert tb.tip_load_more.text == TRANSLATIONS["load_more_stock_none"]["he"]

    def test_load_more_calculating_tooltip(self):
        tb = _toolbar_stub()
        tb.set_load_more_calculating()
        assert tb.tip_load_more.text == TRANSLATIONS["load_more_calc"]["he"]

    def test_side_meter_text(self):
        tb = _toolbar_stub()
        tb.set_remaining_text("מחפש… 12.50%")
        tb.remaining_lbl.configure.assert_called_with(text="מחפש… 12.50%")


def _page_toolbar_stub():
    tb = object.__new__(TopToolbar)
    tb._box_text = "1"
    entry = MagicMock()
    entry.get.side_effect = lambda: tb._box_text

    def _insert(_i, value):
        tb._box_text = str(value)
    entry.insert.side_effect = _insert
    entry.delete.side_effect = lambda *a, **k: None
    tb.page_entry = entry
    tb.out_of_lbl = MagicMock()
    tb._page_entry_dirty = False
    tb._page_current = 1
    tb._page_total = 1
    return tb


class TestPageJumpBox:
    def test_browsing_keeps_counter_in_sync(self):
        tb = _page_toolbar_stub()
        tb.set_pagination(2, 99)
        assert tb._box_text == "2"
        tb.set_pagination(3, 99)
        assert tb._box_text == "3"

    def test_typed_jump_survives_background_refresh(self):
        tb = _page_toolbar_stub()
        tb._box_text = "5000"
        tb._on_page_entry_key(SimpleNamespace(keysym="5"))  # user typed -> dirty
        tb.set_pagination(3, 76040)                          # background poll
        assert tb._box_text == "5000"                        # not clobbered
        tb.out_of_lbl.configure.assert_called_with(text=" / 76040")

    def test_focus_out_restores_real_page(self):
        tb = _page_toolbar_stub()
        tb.set_pagination(7, 100)
        tb._box_text = "999"
        tb._on_page_entry_key(SimpleNamespace(keysym="9"))
        tb._on_page_entry_focus_out()
        assert tb._page_entry_dirty is False
        assert tb._box_text == "7"

    def test_return_submits_jump(self):
        tb = _page_toolbar_stub()
        tb.on_page_jump = MagicMock()
        tb._box_text = "42"
        tb._on_page_entry_return()
        tb.on_page_jump.assert_called_once_with(42)

    def test_return_invalid_restores_current(self):
        tb = _page_toolbar_stub()
        tb.on_page_jump = MagicMock()
        tb.set_pagination(4, 50)
        tb._box_text = ""
        tb._on_page_entry_return()
        tb.on_page_jump.assert_not_called()
        assert tb._box_text == "4"


def _view_stub():
    from src.MVP.views.calendar_view import CalendarGridView
    v = object.__new__(CalendarGridView)
    v.current_lang = "he"
    v.toolbar = MagicMock()
    v.monthly_view = None
    v._deep_search_running = False
    v.on_load_all_clicked = None
    return v


class TestViewIndicatorMessages:
    def test_done_message_includes_scanned_and_kept(self):
        v = _view_stub()
        v.set_deep_search_done(8_150_000, 100_000)
        text = v.toolbar.set_remaining_text.call_args.args[0]
        assert "8,150,000" in text and "100,000" in text

    def test_progress_message(self):
        v = _view_stub()
        v.set_load_all_progress(12.5)
        text = v.toolbar.set_remaining_text.call_args.args[0]
        assert "12.50" in text

    def test_saving_message(self):
        v = _view_stub()
        v.set_load_all_saving()
        text = v.toolbar.set_remaining_text.call_args.args[0]
        assert TRANSLATIONS["load_all_saving"]["he"] in text

    def test_all_loaded_disables_load_more_only(self):
        v = _view_stub()
        v.update_remaining_indicator(remaining=0, total=5, loaded=5, all_loaded=True)
        v.toolbar.set_load_more_enabled.assert_called_with(False)
        # the deep-search button is NOT disabled here (entry point / cancel toggle)
        v.toolbar.set_load_all_enabled.assert_not_called()

    def test_not_all_loaded_reenables_load_more(self):
        v = _view_stub()
        v.update_remaining_indicator(remaining=10, total=20, loaded=10, all_loaded=False)
        v.toolbar.set_load_more_enabled.assert_called_with(True)

    def test_clear_indicators_wipes_meter_and_tooltip(self):
        v = _view_stub()
        v.clear_load_indicators()
        v.toolbar.set_remaining_text.assert_called_with("")
        v.toolbar.set_load_more_remaining.assert_called_with(None)

    def test_confirm_load_all_cancels_immediately_while_running(self):
        v = _view_stub()
        v._deep_search_running = True
        v.on_load_all_clicked = MagicMock()
        v._confirm_load_all()  # must NOT open a modal; just cancel
        v.on_load_all_clicked.assert_called_once()


# ===========================================================================
# 8. Modal focus hygiene (sort + constraints): grab released, focus returned
# ===========================================================================
class TestModalDismiss:
    def _check_dismiss(self, modal_cls):
        m = object.__new__(modal_cls)
        m.parent = MagicMock()
        m.grab_release = MagicMock()
        m.destroy = MagicMock()
        m._dismiss()
        m.grab_release.assert_called_once()
        m.destroy.assert_called_once()
        m.parent.winfo_toplevel.return_value.focus_force.assert_called_once()

    def test_sort_modal_dismiss_releases_grab_and_returns_focus(self):
        from src.MVP.views.components.sort_criteria_modal import SortCriteriaSelectorModal
        self._check_dismiss(SortCriteriaSelectorModal)

    def test_constraints_modal_dismiss_releases_grab_and_returns_focus(self):
        from src.MVP.views.components.constraints_modal import ConstraintsSettingsModal
        self._check_dismiss(ConstraintsSettingsModal)

    def test_sort_modal_save_runs_callback_then_dismisses(self):
        from src.MVP.views.components.sort_criteria_modal import SortCriteriaSelectorModal
        m = object.__new__(SortCriteriaSelectorModal)
        m.on_save_callback = MagicMock()
        m._validate_before_save = MagicMock(return_value=True)
        m._collect_sort_keys = MagicMock(return_value=["avg_gap_all"])
        m._dismiss = MagicMock()
        m._save_and_close()
        m.on_save_callback.assert_called_once_with(["avg_gap_all"])
        m._dismiss.assert_called_once()


# ===========================================================================
# 9. Translations completeness
# ===========================================================================
class TestTranslations:
    NEW_KEYS = [
        "load_all_title", "load_all_warning", "load_all_confirm", "load_all_btn",
        "load_all_cancel", "load_all_tooltip", "load_all_progress", "load_all_saving",
        "deep_search_done", "all_loaded",
        "load_more_stock", "load_more_stock_none", "load_more_tooltip", "load_more_calc",
    ]

    def test_every_new_key_has_both_languages(self):
        for key in self.NEW_KEYS:
            assert key in TRANSLATIONS, f"missing translation key: {key}"
            assert "he" in TRANSLATIONS[key] and "en" in TRANSLATIONS[key], f"key {key} missing a language"
            assert TRANSLATIONS[key]["he"] and TRANSLATIONS[key]["en"]

    def test_formatted_keys_accept_their_placeholders(self):
        assert "5" in TRANSLATIONS["load_more_stock"]["en"].format(n=5)
        assert "9" in TRANSLATIONS["load_all_progress"]["he"].format(p=9)
        out = TRANSLATIONS["deep_search_done"]["he"].format(scanned=1, kept=2)
        assert "1" in out and "2" in out