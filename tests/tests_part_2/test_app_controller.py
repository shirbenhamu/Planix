import pytest
from unittest.mock import MagicMock, patch
from src.MVP.presenters.app_controller import AppController

class TestAppController:
    @pytest.fixture
    def mock_window(self):
        """Creates a mock instance of the main AppWindow container."""
        window = MagicMock()
        window.input_view = MagicMock()
        window.calendar_view = MagicMock()
        return window

    @pytest.fixture
    def mock_data_manager(self):
        """Creates a mock instance of the system DataManager."""
        manager = MagicMock()
        manager.get_courses.return_value = []
        return manager

    # We patch the models and child presenters to isolate the central AppController logic.
    @pytest.fixture
    def controller(self, mock_window, mock_data_manager):
        """Initializes AppController while patching external component tree layers."""
        with patch("src.MVP.presenters.app_controller.PlanixModel") as mock_model_cls, \
             patch("src.MVP.presenters.app_controller.ScheduleCollectionManager") as mock_manager_cls, \
             patch("src.MVP.presenters.app_controller.InputPresenter") as mock_input_pres_cls, \
             patch("src.MVP.presenters.app_controller.CalendarPresenter") as mock_cal_pres_cls:

            # Setup mock instances returned by the constructors.
            mock_model_cls.return_value = MagicMock()
            mock_manager_cls.return_value = MagicMock()
            mock_input_pres_cls.return_value = MagicMock()
            mock_cal_pres_cls.return_value = MagicMock()

            controller_instance = AppController(mock_window, mock_data_manager)

            # Replace the real engine adapter with a mock.
            # This keeps the test isolated from the real scheduling engine.
            controller_instance.engine_adapter = MagicMock()
            controller_instance.engine_adapter.is_generation_active.return_value = False
            controller_instance.model.get_selected_programs.return_value = ["83108"]

            # Attach mocked presenter instance to the controller context for test access.
            controller_instance._mock_cal_presenter = mock_cal_pres_cls.return_value

            return controller_instance

    # ======= 1. Core Framework Setup & Wiring Tests (PLAN-265) =======

    def test_controller_initialization_wires_up_presenters_and_navigation(self, mock_window, controller):
        """Verify that the master controller hooks into the window's navigation callbacks upon boot."""
        assert mock_window.on_navigation_requested == controller._handle_navigation

    def test_controller_defaults_to_input_view_on_startup(self, mock_window, controller):
        """Ensure that the application automatically initializes its screen state configuration onto the input frame."""
        mock_window.switch_view.assert_called_with("input")

    # ======= 2. Shared Global State Context Verification (PLAN-267) =======

    def test_controller_maintains_single_persistent_state_context(self, mock_window, mock_data_manager):
        """Verify that a single unified Model instance is instantiated and injected across all presenters."""
        with patch("src.MVP.presenters.app_controller.PlanixModel") as mock_model_cls, \
             patch("src.MVP.presenters.app_controller.ScheduleCollectionManager"), \
             patch("src.MVP.presenters.app_controller.InputPresenter") as mock_input_pres_cls, \
             patch("src.MVP.presenters.app_controller.CalendarPresenter") as mock_cal_pres_cls:

            shared_model_mock = MagicMock()
            mock_model_cls.return_value = shared_model_mock

            # Act - Instantiate the core orchestrator.
            AppController(mock_window, mock_data_manager)

            # Assert - Ensure the exact same shared model context was injected into both child presenters.
            mock_input_pres_cls.assert_called_once_with(
                view=mock_window.input_view,
                model=shared_model_mock
            )
            mock_cal_pres_cls.assert_called_once()
            assert mock_cal_pres_cls.call_args[1]["model"] == shared_model_mock

    # ======= 3. Structural Routing & View Switching Logic (PLAN-266) =======

    def test_navigation_to_input_view_toggles_layout_visibility(self, mock_window, controller):
        """Ensure that requesting navigation to input triggers layout manipulation on the AppWindow frame."""
        # Act
        controller._handle_navigation("input")

        # Assert
        mock_window.switch_view.assert_called_with("input")
        controller._mock_cal_presenter.refresh_presenter_state.assert_not_called()
        controller.engine_adapter.generate_from_model.assert_not_called()

    def test_navigation_to_calendar_view_refreshes_state_before_switching(self, mock_window, controller):
        """Verify that switching to the calendar panel refreshes generated schedule state before presentation."""
        # Act
        controller._handle_navigation("calendar")

        # Assert
        controller.engine_adapter.generate_from_model.assert_called_once_with(
            model=controller.model,
            output_path=controller.output_path
        )
        mock_window.switch_view.assert_called_with("calendar")
        mock_window.after.assert_called_once()