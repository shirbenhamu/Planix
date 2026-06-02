import os
import pytest
from unittest.mock import MagicMock
from MVP.presenters.input_presenter import InputPresenter


class TestInputPresenter:
    @pytest.fixture
    def mock_view(self):
        """Creates a mock instance of the InputConfigurationView."""
        view = MagicMock()
        view.load_mode_var.get.return_value = "replace"
        return view

    @pytest.fixture
    def mock_model(self):
        """Creates a mock instance of the PlanixModel."""
        model = MagicMock()
        model.get_selected_programs.return_value = []
        model.get_available_programs.return_value = {}
        model.get_program_course_hierarchy.return_value = {
            "courses_by_year_and_semester": {}
        }
        return model

    @pytest.fixture
    def presenter(self, mock_view, mock_model):
        """Initializes the InputPresenter with mocked dependencies."""
        return InputPresenter(mock_view, mock_model)

    # ======= 1. UI Event Binding Verification =======

    def test_presenter_initialization_binds_ui_events(self, mock_view, presenter):
        """Verify that the Presenter correctly binds core layout user events without the 3rd file."""
        assert mock_view.on_load_courses == presenter._handle_load_courses
        assert mock_view.on_load_dates == presenter._handle_load_dates
        assert mock_view.on_program_selected == presenter._handle_program_selection

    # ======= 2. Dynamic Program Extraction Verification =======

    def test_handle_load_courses_triggers_model_and_builds_programs(
        self,
        mock_model,
        presenter,
        tmp_path,
        monkeypatch
    ):
        """Ensure that loading a courses text file builds academic program mapping configurations directly."""
        # Arrange
        # Keep generated dummy data files inside pytest's temporary directory.
        monkeypatch.chdir(tmp_path)

        expected_courses_path = os.path.normpath("fake_courses.txt")
        expected_exam_periods_path = os.path.normpath("data/exam_periods.txt")
        expected_selected_programs_path = os.path.normpath("data/selected_programs.txt")

        # Act
        presenter._handle_load_courses("fake_courses.txt")

        # Assert
        mock_model.set_data_paths.assert_called_once_with(
            courses_path=expected_courses_path,
            exam_periods_path=expected_exam_periods_path,
            selected_programs_path=expected_selected_programs_path
        )

        mock_model.data_manager.load_data.assert_called_once_with(
            courses_path=expected_courses_path,
            exam_periods_path=expected_exam_periods_path,
            selected_programs_path=expected_selected_programs_path,
            mode="replace"
        )

        mock_model.build_available_programs.assert_called_once()

    # ======= 3. Program Selection State Verification =======

    def test_handle_program_selection_toggles_model_state(self, mock_model, presenter):
        """Verify that selecting an academic program updates the central model's selected list parameters."""
        mock_model.get_selected_programs.return_value = []

        # Act - Select a brand new program.
        presenter._handle_program_selection("83108")

        # Assert
        mock_model.add_selected_program.assert_called_with("83108")