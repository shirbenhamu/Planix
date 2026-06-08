from unittest.mock import MagicMock, patch, mock_open

from src.MVP.presenters.calendar_presenter import CalendarPresenter
from src.MVP.presenters.app_controller import AppController


class TestLoadMoreSchedules:
    def _build_calendar_presenter_with_controller(self, tmp_path):
        view = MagicMock()
        view.active_month_indices = []

        model = MagicMock()
        model.get_exam_periods.return_value = []
        model.get_user_excluded_dates.return_value = []
        model.get_selected_programs.return_value = []
        model.data_manager.get_courses.return_value = []

        collection_manager = MagicMock()
        collection_manager.get_total_count.return_value = 0
        collection_manager.get_current_index.return_value = 0

        controller = MagicMock()
        controller.output_path = str(tmp_path / "final_schedules.txt")

        presenter = CalendarPresenter(
            view=view,
            model=model,
            collection_manager=collection_manager,
            controller=controller,
        )
        view.reset_mock()
        return presenter, view, controller

    def test_calendar_presenter_binds_load_more_callback_when_view_supports_it(self):
        """Verify that the presenter wires the Load More button to its handler."""
        view = MagicMock()
        view.active_month_indices = []
        view.on_load_more_clicked = None

        model = MagicMock()
        model.get_exam_periods.return_value = []
        model.get_user_excluded_dates.return_value = []
        model.get_selected_programs.return_value = []
        model.data_manager.get_courses.return_value = []

        collection_manager = MagicMock()
        collection_manager.get_total_count.return_value = 0
        collection_manager.get_current_index.return_value = 0

        presenter = CalendarPresenter(view, model, collection_manager)

        assert view.on_load_more_clicked == presenter._handle_load_more

    def test_load_more_counts_existing_options_and_delegates_skip_count(self, tmp_path):
        """Verify that Load More counts existing schedule options and sends the count to the controller."""
        presenter, view, controller = self._build_calendar_presenter_with_controller(tmp_path)
        output_path = tmp_path / "final_schedules.txt"
        output_path.write_text(
            "--- FULL SYSTEM OPTION 1 ---\n"
            "Date: 01-02-2026 | Course: 10001 - Intro | Instructor: A\n"
            "------------------------------------------------------------\n"
            "--- FULL SYSTEM OPTION 2 ---\n"
            "Date: 02-02-2026 | Course: 10002 - Data | Instructor: B\n"
            "------------------------------------------------------------\n",
            encoding="utf-8",
        )

        presenter._handle_load_more()

        controller.load_more_schedules.assert_called_once_with(skip_count=2)

    def test_load_more_uses_zero_skip_count_when_output_file_does_not_exist(self, tmp_path):
        """Verify that Load More starts from zero when no schedule output file exists yet."""
        presenter, view, controller = self._build_calendar_presenter_with_controller(tmp_path)

        presenter._handle_load_more()

        controller.load_more_schedules.assert_called_once_with(skip_count=0)

    def test_app_controller_load_more_rejects_request_while_generation_is_active(self):
        """Verify that AppController does not start a second Load More run while generation is active."""
        controller = object.__new__(AppController)
        controller.engine_adapter = MagicMock()
        controller.engine_adapter.is_generation_active.return_value = True
        controller.collection_manager = MagicMock()
        controller.model = MagicMock()
        controller.app_window = MagicMock()
        controller.calendar_presenter = MagicMock()
        controller.output_path = "output_results/final_schedules.txt"

        controller.load_more_schedules(skip_count=3)

        controller.engine_adapter.generate_from_model.assert_not_called()
        controller.app_window.after.assert_not_called()

    def test_app_controller_load_more_starts_generation_with_skip_count_and_snapshot_mode(self):
        """Verify that AppController starts the background Load More pipeline with append-style skip count."""
        controller = object.__new__(AppController)
        controller.engine_adapter = MagicMock()
        controller.engine_adapter.is_generation_active.return_value = False
        controller.collection_manager = MagicMock()
        controller.model = MagicMock()
        controller.model.is_generating = False
        controller.app_window = MagicMock()
        controller.calendar_presenter = MagicMock()
        controller.output_path = "output_results/final_schedules.txt"

        controller.load_more_schedules(skip_count=5)

        assert controller.model.is_generating is True
        assert controller.collection_manager.snapshot_mode is True
        controller.engine_adapter.generate_from_model.assert_called_once_with(
            model=controller.model,
            output_path=controller.output_path,
            skip_count=5,
        )
        controller.app_window.after.assert_called_once()

    def test_monitor_load_more_shows_no_more_results_when_count_does_not_increase(self):
        """Verify that the monitor notifies the view when no additional schedules were produced."""
        controller = object.__new__(AppController)
        controller.engine_adapter = MagicMock()
        controller.engine_adapter.is_generation_active.return_value = False
        controller.collection_manager = MagicMock()
        controller.model = MagicMock()
        controller.model.is_generating = True
        controller.app_window = MagicMock()
        controller.app_window.after.side_effect = lambda delay, callback: callback()
        controller.calendar_presenter = MagicMock()
        controller.calendar_presenter.view.show_no_more_results = MagicMock()
        controller.output_path = "output_results/final_schedules.txt"

        file_text = (
            "--- FULL SYSTEM OPTION 1 ---\n"
            "------------------------------------------------------------\n"
            "--- FULL SYSTEM OPTION 2 ---\n"
            "------------------------------------------------------------\n"
        )

        with patch("threading.Thread") as thread_cls, patch("builtins.open", mock_open(read_data=file_text)):
            thread_cls.side_effect = lambda target, daemon=True: MagicMock(start=target)
            controller._monitor_load_more_progress(previous_count=2)

        controller.collection_manager.build_snapshot_index.assert_called_once()
        controller.calendar_presenter.refresh_presenter_state.assert_called_once()
        assert controller.collection_manager.snapshot_mode is False
        assert controller.model.is_generating is False
        controller.engine_adapter.clear_finished_worker.assert_called_once()
        controller.calendar_presenter.view.show_no_more_results.assert_called_once()
