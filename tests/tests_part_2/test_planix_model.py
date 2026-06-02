import pytest
from datetime import date
from unittest.mock import MagicMock

from MVP.models.course import Course, ProgramCourseInfo
from MVP.models.planix_model import PlanixModel


class TestPlanixModel:
    @pytest.fixture
    def mock_data_manager(self):
        """Creates a mock DataManager-like object for isolated model-state tests."""
        manager = MagicMock()
        manager.get_courses.return_value = []
        manager.get_exam_periods.return_value = []
        return manager

    @pytest.fixture
    def model(self, mock_data_manager):
        """Initializes a PlanixModel with mocked data dependencies."""
        return PlanixModel(data_manager=mock_data_manager)

    # ======= 1. Selected Program Add State Consistency Verification =======

    def test_add_selected_program_normalizes_and_stores_program_id(self, model):
        """Verify that adding a program trims spaces and stores the normalized value."""
        # Act
        model.add_selected_program(" 83108 ")

        # Assert
        assert model.get_selected_programs() == ["83108"]

    # ======= 2. Duplicate Selected Program Consistency Verification =======

    def test_add_selected_program_ignores_duplicate_program_id(self, model):
        """Verify that adding the same program twice does not duplicate model state."""
        # Act
        model.add_selected_program("83108")
        model.add_selected_program("83108")

        # Assert
        assert model.get_selected_programs() == ["83108"]

    # ======= 3. Selected Program Removal State Consistency Verification =======

    def test_remove_selected_program_updates_state_consistently(self, model):
        """Verify that removing a selected program deletes only that program from state."""
        # Arrange
        model.set_selected_programs(["83101", "83108"])

        # Act
        model.remove_selected_program("83101")

        # Assert
        assert model.get_selected_programs() == ["83108"]

    # ======= 4. Missing Selected Program Removal Validation Verification =======

    def test_remove_selected_program_raises_for_unselected_program(self, model):
        """Verify that removing a program that is not selected raises a clear state error."""
        # Arrange
        model.add_selected_program("83108")

        # Act & Assert
        with pytest.raises(ValueError, match="not currently selected"):
            model.remove_selected_program("83101")

    # ======= 5. Maximum Selected Program State Constraint Verification =======

    def test_add_selected_program_rejects_more_than_five_programs(self, model):
        """Verify that the model never stores more than the configured maximum selected programs."""
        # Arrange
        model.set_selected_programs(["83101", "83102", "83104", "83107", "83108"])

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot select more than 5 programs"):
            model.add_selected_program("83109")

        assert model.get_selected_programs() == [
            "83101",
            "83102",
            "83104",
            "83107",
            "83108"
        ]

    # ======= 6. Bulk Selected Program Normalization Verification =======

    def test_set_selected_programs_normalizes_and_removes_duplicates(self, model):
        """Verify that bulk program selection normalizes IDs and removes duplicates while preserving order."""
        # Act
        model.set_selected_programs([" 83108 ", "83101", "83108", "83102"])

        # Assert
        assert model.get_selected_programs() == ["83108", "83101", "83102"]

    # ======= 7. Defensive Copy For Selected Programs Verification =======

    def test_get_selected_programs_returns_defensive_copy(self, model):
        """Verify that external mutation of returned selected-program lists cannot modify model state."""
        # Arrange
        model.set_selected_programs(["83108"])

        # Act
        returned_programs = model.get_selected_programs()
        returned_programs.append("83101")

        # Assert
        assert model.get_selected_programs() == ["83108"]

    # ======= 8. Available Programs Build State Verification =======

    def test_build_available_programs_collects_unique_programs_from_courses(self, mock_data_manager, model):
        """Verify that available-program state is built from course metadata without duplicate program IDs."""
        # Arrange
        info_1 = ProgramCourseInfo(
            program_id="83108",
            year=1,
            semester="FALL",
            requirement="Obligatory"
        )
        info_2 = ProgramCourseInfo(
            program_id="83101",
            year=1,
            semester="SPRING",
            requirement="Elective"
        )
        info_duplicate = ProgramCourseInfo(
            program_id="83108",
            year=2,
            semester="FALL",
            requirement="Elective"
        )

        course_1 = Course("10001", "Intro", "Teacher", "Exam", [info_1, info_2])
        course_2 = Course("10002", "Advanced", "Teacher", "Exam", [info_duplicate])
        mock_data_manager.get_courses.return_value = [course_1, course_2]

        # Act
        available_programs = model.build_available_programs()

        # Assert
        assert available_programs == {
            "83108": "Software Engineering",
            "83101": "Computer Engineering"
        }
        assert model.get_available_programs() == available_programs

    # ======= 9. Defensive Copy For Available Programs Verification =======

    def test_get_available_programs_returns_defensive_copy(self, model):
        """Verify that external mutation of returned available-program dictionaries cannot modify model state."""
        # Arrange
        model.available_programs = {"83108": "Software Engineering"}

        # Act
        returned_programs = model.get_available_programs()
        returned_programs["83101"] = "Computer Engineering"

        # Assert
        assert model.get_available_programs() == {"83108": "Software Engineering"}

    # ======= 10. Date Exclusion Toggle State Consistency Verification =======

    def test_toggle_date_exclusion_adds_and_removes_same_date_consistently(self, model):
        """Verify that toggling the same date twice returns the exclusion state to its original value."""
        # Arrange
        blocked_date = date(2026, 2, 15)

        # Act
        model.toggle_date_exclusion(blocked_date)
        first_state = model.get_user_excluded_dates()

        model.toggle_date_exclusion(blocked_date)
        second_state = model.get_user_excluded_dates()

        # Assert
        assert first_state == [blocked_date]
        assert second_state == []

    # ======= 11. Date Exclusion Sorting Verification =======

    def test_get_user_excluded_dates_returns_sorted_dates(self, model):
        """Verify that excluded dates are returned in chronological order regardless of insertion order."""
        # Arrange
        later_date = date(2026, 3, 10)
        earlier_date = date(2026, 2, 1)

        # Act
        model.exclude_date(later_date)
        model.exclude_date(earlier_date)

        # Assert
        assert model.get_user_excluded_dates() == [earlier_date, later_date]

    # ======= 12. Scheduling Constraint Validation Happy Path Verification =======

    def test_validate_scheduling_constraints_accepts_consistent_model_state(self, mock_data_manager, model):
        """Verify that validation passes when courses, periods, selected programs, and available programs agree."""
        # Arrange
        mock_course = MagicMock()
        mock_period = MagicMock()

        mock_data_manager.get_courses.return_value = [mock_course]
        mock_data_manager.get_exam_periods.return_value = [mock_period]

        model.available_programs = {"83108": "Software Engineering"}
        model.set_selected_programs(["83108"])

        # Act & Assert
        model.validate_scheduling_constraints()

    # ======= 13. Scheduling Constraint Validation Missing Programs Verification =======

    def test_validate_scheduling_constraints_rejects_selected_program_missing_from_available_programs(
        self,
        mock_data_manager,
        model
    ):
        """Verify that validation rejects selected programs that are absent from loaded course metadata."""
        # Arrange
        mock_course = MagicMock()
        mock_period = MagicMock()

        mock_data_manager.get_courses.return_value = [mock_course]
        mock_data_manager.get_exam_periods.return_value = [mock_period]

        model.available_programs = {"83101": "Computer Engineering"}
        model.set_selected_programs(["83108"])

        # Act & Assert
        with pytest.raises(ValueError, match="Selected programs are not available"):
            model.validate_scheduling_constraints()