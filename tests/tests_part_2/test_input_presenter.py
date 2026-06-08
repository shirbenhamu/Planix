import os
import pytest
from unittest.mock import MagicMock
from src.MVP.presenters.input_presenter import InputPresenter


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
        expected_exam_periods_path = os.path.normpath(".")
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
        # Arrange
        mock_model.get_selected_programs.return_value = []

        # Act - Select a brand new program.
        presenter._handle_program_selection("83108")

        # Assert
        mock_model.add_selected_program.assert_called_once_with("83108")
        mock_model.remove_selected_program.assert_not_called()

    # ======= 4. Program Deselection Constraint Verification =======

    def test_handle_program_selection_removes_already_selected_program(self, mock_model, presenter):
        """Verify that selecting an already-selected program removes it from the model state."""
        # Arrange
        mock_model.get_selected_programs.return_value = ["83108"]

        # Act
        presenter._handle_program_selection("83108")

        # Assert
        mock_model.remove_selected_program.assert_called_once_with("83108")
        mock_model.add_selected_program.assert_not_called()

    # ======= 5. Maximum Program Selection Constraint Verification =======

    def test_handle_program_selection_rejects_program_when_model_limit_is_reached(
        self,
        mock_view,
        mock_model,
        presenter
    ):
        """Verify that the presenter refreshes the program list when the model rejects a new selection."""
        # Arrange
        # The model already contains 5 selected programs, so adding another one should fail.
        mock_model.get_selected_programs.return_value = [
            "83101",
            "83102",
            "83104",
            "83107",
            "83108"
        ]

        mock_model.add_selected_program.side_effect = ValueError(
            "Cannot select more than 5 programs."
        )

        mock_model.get_available_programs.return_value = {
            "83101": "Computer Engineering",
            "83102": "Electrical Engineering",
            "83104": "Industrial and Information Systems Engineering",
            "83107": "Data Engineering",
            "83108": "Software Engineering",
            "83109": "Materials Engineering"
        }

        # Act
        presenter._handle_program_selection("83109")

        # Assert
        mock_model.add_selected_program.assert_called_once_with("83109")
        mock_model.remove_selected_program.assert_not_called()

        # The presenter should refresh the programs list so the UI returns to a valid state.
        mock_view.display_programs_list.assert_called_once_with(
            mock_model.get_available_programs.return_value
        )

        # Since the selection failed, the selected-program summary should not be updated.
        mock_view.display_program_courses.assert_not_called()

    # ======= 6. Selected Program Summary Update After Add Verification =======

    def test_handle_program_selection_updates_summary_after_successful_add(
        self,
        mock_view,
        mock_model,
        presenter
    ):
        """Verify that a successful program selection refreshes the selected-program summary panel."""
        # Arrange
        # First call: before selection.
        # Second call: after successful selection.
        mock_model.get_selected_programs.side_effect = [
            [],
            ["83108"]
        ]

        mock_model.get_program_course_hierarchy.return_value = {
            "courses_by_year_and_semester": {
                1: {
                    "FALL": [
                        {
                            "course_id": "10001",
                            "course_name": "Intro to Software Engineering",
                            "requirement": "Obligatory"
                        }
                    ]
                }
            }
        }

        # Act
        presenter._handle_program_selection("83108")

        # Assert
        mock_model.add_selected_program.assert_called_once_with("83108")
        mock_model.remove_selected_program.assert_not_called()

        mock_view.display_program_courses.assert_called_once_with(
            mock_model.get_program_course_hierarchy.return_value
        )

    # ======= 7. Selected Program Summary Update After Remove Verification =======

    def test_handle_program_selection_updates_summary_after_successful_remove(
        self,
        mock_view,
        mock_model,
        presenter
    ):
        """Verify that removing a selected program refreshes the summary panel to an empty state."""
        # Arrange
        # First call: before click, the program is already selected.
        # Second call: after removal, no programs are selected.
        mock_model.get_selected_programs.side_effect = [
            ["83108"],
            []
        ]

        # Act
        presenter._handle_program_selection("83108")

        # Assert
        mock_model.remove_selected_program.assert_called_once_with("83108")
        mock_model.add_selected_program.assert_not_called()

        mock_view.display_program_courses.assert_called_once_with({})
        
    # ======= 8. Presenter-To-View Program List Update Verification =======

    def test_handle_load_courses_refreshes_available_programs_view(
        self,
        mock_view,
        mock_model,
        presenter,
        tmp_path,
        monkeypatch
    ):
        """Verify that loading courses refreshes the available-programs list in the View."""
        # Arrange
        monkeypatch.chdir(tmp_path)

        mock_model.get_available_programs.return_value = {
            "83108": "Software Engineering",
            "83101": "Computer Engineering"
        }

        # Act
        presenter._handle_load_courses("fake_courses.txt")

        # Assert
        mock_view.display_programs_list.assert_called_once_with({
            "83108": "Software Engineering",
            "83101": "Computer Engineering"
        })


    # ======= 9. Presenter-To-View Empty Summary Update Verification =======

    def test_handle_load_courses_refreshes_empty_selected_program_summary(
        self,
        mock_view,
        mock_model,
        presenter,
        tmp_path,
        monkeypatch
    ):
        """Verify that loading courses clears the selected-program summary when no programs are selected."""
        # Arrange
        monkeypatch.chdir(tmp_path)
        mock_model.get_selected_programs.return_value = []

        # Act
        presenter._handle_load_courses("fake_courses.txt")

        # Assert
        mock_view.display_program_courses.assert_called_once_with({})
    