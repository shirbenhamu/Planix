"""Controller orchestration for the Load All feature and the remaining-to-load
indicator. The AppController is built with object.__new__ and hand-wired mocks,
matching the existing controller tests, so no GUI/process is spawned.
"""

import time
from unittest.mock import MagicMock

from src.MVP.presenters.app_controller import AppController


def _controller():
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
    return c


# ===== remaining indicator ===============================================

def test_update_remaining_indicator_reports_total_minus_loaded():
    c = _controller()
    c._total_count = 2_000_000
    c.collection_manager.get_total_count.return_value = 200_000

    c._update_remaining_indicator()

    c.calendar_presenter.view.update_remaining_indicator.assert_called_once_with(
        remaining=1_800_000, total=2_000_000, loaded=200_000, all_loaded=False,
    )


def test_update_remaining_indicator_clamps_at_zero_and_marks_all_loaded():
    c = _controller()
    c._total_count = 500
    c.collection_manager.get_total_count.return_value = 500

    c._update_remaining_indicator()

    _, kwargs = c.calendar_presenter.view.update_remaining_indicator.call_args
    assert kwargs["remaining"] == 0
    assert kwargs["all_loaded"] is True


def test_update_remaining_indicator_noop_until_total_known():
    c = _controller()
    c._total_count = None

    c._update_remaining_indicator()

    c.calendar_presenter.view.update_remaining_indicator.assert_not_called()


def test_poll_total_count_reads_total_when_worker_done():
    c = _controller()
    c.engine_adapter.is_count_active.return_value = False
    c.engine_adapter.read_total_count.return_value = 12345
    c.collection_manager.get_total_count.return_value = 100

    c._poll_total_count()

    assert c._total_count == 12345
    c.app_window.after.assert_not_called()  # not re-scheduled once done
    c.calendar_presenter.view.update_remaining_indicator.assert_called_once()


def test_poll_total_count_reschedules_while_worker_active():
    c = _controller()
    c.engine_adapter.is_count_active.return_value = True

    c._poll_total_count()

    c.app_window.after.assert_called_once()
    assert c._total_count is None


def test_start_total_count_skipped_once_all_loaded():
    c = _controller()
    c._all_loaded = True

    c.start_total_count()

    c.engine_adapter.count_total_from_model.assert_not_called()


# ===== Load All ==========================================================

def test_load_all_denied_while_generation_active():
    c = _controller()
    c.engine_adapter.is_generation_active.return_value = True

    c.load_all_schedules()

    c.engine_adapter.deep_search_from_model.assert_not_called()


def test_load_all_launches_deep_search_and_toggles_button():
    c = _controller()
    c.engine_adapter.is_generation_active.return_value = False
    c._deep_search_active = False
    c._set_constraints_save_state = MagicMock()
    c._lock_engine_triggers = MagicMock()

    c.load_all_schedules()

    # Deep search into the SEPARATE file, using the active sort, top-N + time budget.
    _, kwargs = c.engine_adapter.deep_search_from_model.call_args
    assert kwargs["output_path"] == c.load_all_output_path
    assert kwargs["sort_spec"] == [(1, False)]
    assert kwargs["top_n"] == AppController.DEEP_SEARCH_TOP_N
    assert kwargs["max_seconds"] == AppController.DEEP_SEARCH_MAX_SECONDS
    assert c._deep_search_active is True
    # Load More retired, button toggled to 'Cancel deep search', engine locked.
    c.calendar_presenter.view.set_load_more_enabled.assert_called_once_with(False)
    c.calendar_presenter.view.set_load_all_running.assert_called_once_with(True)
    c._lock_engine_triggers.assert_called_once_with(True)
    c.app_window.after.assert_called_once()  # monitor scheduled


def test_second_click_cancels_the_deep_search():
    c = _controller()
    c._deep_search_active = True  # already running
    c._set_constraints_save_state = MagicMock()

    c.load_all_schedules()  # second click

    c.engine_adapter.cancel_active_worker.assert_called_once()
    c.engine_adapter.deep_search_from_model.assert_not_called()
    assert c._deep_search_active is False
    # Button restored and Load More re-enabled.
    c.calendar_presenter.view.set_load_all_running.assert_called_with(False)
    c.calendar_presenter.view.set_load_more_enabled.assert_called_with(True)


def test_deep_search_percent_is_time_based():
    c = _controller()
    c._deep_search_started = time.time() - (AppController.DEEP_SEARCH_MAX_SECONDS / 2)

    percent = c._deep_search_percent()

    assert 45.0 <= percent <= 55.0  # ~halfway through the time budget


def test_monitor_load_all_finalizes_swaps_file_and_shows_all(monkeypatch):
    c = _controller()
    c._deep_search_active = True
    c.engine_adapter.is_generation_active.return_value = False
    c.collection_manager.get_total_count.return_value = 8_000_000
    c._set_constraints_save_state = MagicMock()

    replaced = {}
    monkeypatch.setattr("os.replace", lambda src, dst: replaced.update(src=src, dst=dst))

    c._monitor_load_all_progress()

    assert replaced == {"src": c.load_all_output_path, "dst": c.output_path}
    assert c._deep_search_active is False
    assert c._all_loaded is True
    assert c._total_count == 8_000_000
    c.collection_manager.clear_cache.assert_called_once()
    c.calendar_presenter.view.set_load_all_running.assert_called_with(False)
    c.calendar_presenter.refresh_presenter_state.assert_called()


def test_monitor_load_all_reports_progress_without_touching_collection():
    c = _controller()
    c._deep_search_active = True
    c._deep_search_started = time.time()
    c.engine_adapter.is_generation_active.return_value = True

    c._monitor_load_all_progress()

    c.app_window.after.assert_called_once()  # keeps polling
    c.calendar_presenter.view.set_load_all_progress.assert_called_once()
    c.collection_manager.build_snapshot_index.assert_not_called()


def test_monitor_stops_silently_after_cancel():
    c = _controller()
    c._deep_search_active = False  # cancelled

    c._monitor_load_all_progress()

    c.app_window.after.assert_not_called()
    c.calendar_presenter.view.set_load_all_progress.assert_not_called()
