import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from src.MVP.presenters.calendar_presenter import CalendarPresenter
from src.MVP.models.schedule import Schedule, ScheduledExam


class TestCalendarPresenter:
    @pytest.fixture
    def mock_view(self):
        """Creates a mock instance of the CalendarGridView."""
        view = MagicMock()
        view.active_month_indices = []
        return view

    @pytest.fixture
    def mock_model(self):
        """Creates a mock instance of the PlanixModel."""
        model = MagicMock()
        model.get_user_excluded_dates.return_value = []
        model.get_exam_periods.return_value = []
        model.get_selected_programs.return_value = []
        model.data_manager.get_courses.return_value = []
        return model

    @pytest.fixture
    def mock_collection_manager(self):
        """Creates a mock instance of the ScheduleCollectionManager."""
        manager = MagicMock()
        manager.get_total_count.return_value = 0
        manager.get_current_index.return_value = 0
        return manager

    @pytest.fixture
    def presenter(self, mock_view, mock_model, mock_collection_manager):
        """Initializes the CalendarPresenter with mocked dependencies."""
        return CalendarPresenter(mock_view, mock_model, mock_collection_manager)

    # ======= 1. Initialization & Binding Tests (PLAN-258 / PLAN-261) =======

    def test_presenter_initialization_binds_ui_events(self, mock_view, mock_model, mock_collection_manager):
        """Verify that the Presenter correctly binds all UI navigation and interaction events."""
        presenter = CalendarPresenter(mock_view, mock_model, mock_collection_manager)

        assert mock_view.on_next_clicked == presenter._handle_next_schedule
        assert mock_view.on_prev_clicked == presenter._handle_prev_schedule
        assert mock_view.on_page_jump == presenter._handle_page_jump
        assert mock_view.on_exclude_clicked == presenter._handle_date_exclusion
        assert mock_view.on_export_clicked == presenter._handle_export
        assert mock_view.on_filter_clicked == presenter._handle_filter_click

    # ======= 2. Grid Setup & Data Transformation Tests (PLAN-258) =======

    def test_refresh_presenter_state_shows_empty_state_when_no_schedules(
        self,
        mock_view,
        mock_collection_manager,
        presenter
    ):
        """Ensure that the View displays an empty state if the collection manager has 0 schedules."""
        mock_collection_manager.get_total_count.return_value = 0

        # Act
        presenter.refresh_presenter_state()

        # Assert - Verify it was called gracefully.
        mock_view.show_empty_state.assert_called()
        # PLAN-594: once generation has finished, a stale schedule count from a
        # previous run must be reset to 0 rather than left on screen.
        mock_view.update_pagination.assert_called_with(current_page=0, total_pages=0)

    def test_refresh_presenter_state_keeps_count_while_generation_active(
        self,
        mock_view,
        mock_collection_manager,
        presenter
    ):
        """PLAN-594 follow-up: the counter must NOT be zeroed mid-generation.

        While the engine is still producing schedules the count is briefly 0
        before the first board lands; zeroing it then looks like a freeze.
        """
        mock_collection_manager.get_total_count.return_value = 0
        controller = MagicMock()
        controller.engine_adapter.is_generation_active.return_value = True
        controller.input_presenter = None
        presenter.controller = controller
        mock_view.update_pagination.reset_mock()

        # Act
        presenter.refresh_presenter_state()

        # Assert - empty state shown, but the count was left untouched.
        mock_view.show_empty_state.assert_called()
        mock_view.update_pagination.assert_not_called()

    def test_render_active_schedule_transforms_data_to_grid_coordinates(
        self,
        mock_view,
        mock_model,
        mock_collection_manager,
        presenter
    ):
        """Verify that a raw Schedule object is correctly transformed into grid matrix coordinates."""
        mock_collection_manager.get_total_count.return_value = 1
        mock_collection_manager.get_current_index.return_value = 0

        # Create a mock scheduled exam on February 15th.
        mock_course = MagicMock()
        mock_course.course_id = "83108"
        mock_course.course_name = "Software Eng"
        mock_course.is_mandatory = True

        mock_exam = ScheduledExam(course=mock_course, exam_date=date(2026, 2, 15))
        mock_schedule = Schedule(exams=[mock_exam])
        mock_collection_manager.get_current_schedule.return_value = mock_schedule

        # Act
        presenter.refresh_presenter_state()

        # Assert
        # February should be the only unique month extracted.
        assert presenter.active_months == [1]
        mock_view.init_grid.assert_called_with([1])

        # Month index 1 is at index 0 of active_months, so row_idx = 1.
        # Day 15 maps to col_idx = 14.
        expected_cell_key = "1-14"
        mock_view.render_calendar_data.assert_called_once()

        rendered_grid_data = mock_view.render_calendar_data.call_args[0][0]
        assert rendered_grid_data[expected_cell_key]["day_text"] == "15"
        assert rendered_grid_data[expected_cell_key]["is_excluded"] is False
        assert rendered_grid_data[expected_cell_key]["exams"][0]["course_id"] == "83108"
        assert rendered_grid_data[expected_cell_key]["exams"][0]["type"] == "ח"

    # ======= 3. Multi-Schedule Traversal Tests (PLAN-260) =======

    def test_handle_next_schedule_navigates_and_refreshes(self, mock_collection_manager, presenter):
        """Ensure that clicking 'Next' advances the collection index and refreshes the layout."""
        # Arrange
        mock_collection_manager.get_total_count.return_value = 2
        mock_collection_manager.next_schedule.return_value = True

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act
            presenter._handle_next_schedule()

            # Assert
            mock_collection_manager.next_schedule.assert_called_once()
            mock_refresh.assert_called_once()

    def test_handle_page_jump_valid_bounds(self, mock_collection_manager, presenter):
        """Ensure that jumping to a valid page translates correctly to a 0-indexed manager position."""
        mock_collection_manager.jump_to_schedule.return_value = True

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act - Jump to page 3, which translates to index 2.
            presenter._handle_page_jump(3)

            # Assert
            mock_collection_manager.jump_to_schedule.assert_called_with(2)
            mock_refresh.assert_called_once()

    # ======= 4. Interactive Constraints Modification Tests (PLAN-259 / PLAN-261) =======

    def test_handle_date_exclusion_triggers_model_transaction(
        self,
        mock_model,
        mock_collection_manager,
        presenter
    ):
        """Verify that triggering an exclusion click delegates transaction logic directly to the Model layer."""
        test_cell_key = "1-14"
        test_date = date(2026, 2, 15)

        # Inject context mapping manually into the presenter tracker.
        presenter.cell_to_date_mapping[test_cell_key] = test_date
        mock_collection_manager.get_current_schedule.return_value = Schedule(exams=[])

        # Act
        presenter._handle_date_exclusion(test_cell_key)

        # Assert
        mock_model.toggle_date_exclusion.assert_called_with(test_date)
        mock_collection_manager.get_current_schedule.assert_called_once()

    # ======= 5. Data Exporting Tests (PLAN-262) =======

    def test_handle_export_writes_structured_text_file(self, mock_collection_manager, presenter):
        """Ensure that the export system dumps visualized schedule parameters onto localized files."""
        mock_course = MagicMock()
        mock_course.course_id = "83110"
        mock_course.course_name = "Logic"

        mock_exam = ScheduledExam(course=mock_course, exam_date=date(2026, 1, 20))
        mock_collection_manager.get_current_schedule.return_value = Schedule(exams=[mock_exam])

        # Act & Assert using standard builtins.open patch.
        with patch("builtins.open", MagicMock()) as mock_open:
            presenter._handle_export("fake_output.txt")

            # Assert file system open commands were invoked correctly.
            mock_open.assert_called_with("fake_output.txt", "w", encoding="utf-8")
            
    # ======= 6. Presenter-To-View Pagination Update Verification =======

    def test_refresh_presenter_state_updates_pagination_before_rendering(
        self,
        mock_view,
        mock_model,
        mock_collection_manager,
        presenter
    ):
        """Verify that refreshing an active schedule updates the View pagination state before rendering."""
        # Arrange
        mock_collection_manager.get_total_count.return_value = 4
        mock_collection_manager.get_current_index.return_value = 2

        mock_course = MagicMock()
        mock_course.course_id = "83108"
        mock_course.course_name = "Software Engineering"
        mock_course.is_mandatory = True

        mock_exam = ScheduledExam(course=mock_course, exam_date=date(2026, 3, 10))
        mock_collection_manager.get_current_schedule.return_value = Schedule(exams=[mock_exam])

        # Act
        presenter.refresh_presenter_state()

        # Assert
        mock_view.update_pagination.assert_called_with(
            current_page=3,
            total_pages=4
        )
        mock_view.render_calendar_data.assert_called_once()


    # ======= 7. Presenter-To-View Render Failure Fallback Verification =======

    def test_refresh_presenter_state_falls_back_to_empty_state_when_schedule_loading_fails(
        self,
        mock_view,
        mock_collection_manager,
        presenter
    ):
        """Verify that the View shows an empty state when the active schedule cannot be loaded."""
        # Arrange
        mock_collection_manager.get_total_count.return_value = 1
        mock_collection_manager.get_current_index.return_value = 0
        mock_collection_manager.get_current_schedule.side_effect = RuntimeError(
            "Failed to load schedule"
        )

        # Act
        presenter.refresh_presenter_state()

        # Assert
        mock_view.show_empty_state.assert_called()
        mock_view.render_calendar_data.assert_not_called()
        
    