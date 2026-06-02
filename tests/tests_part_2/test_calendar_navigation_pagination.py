import time
from unittest.mock import MagicMock, patch

from MVP.presenters.calendar_presenter import CalendarPresenter


class TestSchedulingNavigationAndPagination:
    def _build_presenter(self):
        """Create an isolated CalendarPresenter with mocked view, model, and collection manager."""
        mock_view = MagicMock()
        mock_view.active_month_indices = []

        mock_model = MagicMock()
        mock_model.get_user_excluded_dates.return_value = []

        mock_collection_manager = MagicMock()
        mock_collection_manager.get_total_count.return_value = 3
        mock_collection_manager.get_current_index.return_value = 0

        presenter = CalendarPresenter(
            mock_view,
            mock_model,
            mock_collection_manager
        )

        # Clear constructor-time View calls so each test measures only the action under test.
        mock_view.reset_mock()

        return presenter, mock_view, mock_model, mock_collection_manager

    # ======= PLAN-327. Next Navigation Boundary Verification =======

    def test_next_navigation_does_not_refresh_when_already_on_last_schedule(self):
        """Verify that clicking Next at the final schedule does not refresh or move past the boundary."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.get_total_count.return_value = 3
        mock_collection_manager.next_schedule.return_value = False

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act
            presenter._handle_next_schedule()

            # Assert
            mock_collection_manager.next_schedule.assert_called_once()
            mock_refresh.assert_not_called()

    # ======= PLAN-327. Previous Navigation Boundary Verification =======

    def test_previous_navigation_does_not_refresh_when_already_on_first_schedule(self):
        """Verify that clicking Previous at the first schedule does not refresh or move before index zero."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.get_total_count.return_value = 3
        mock_collection_manager.prev_schedule.return_value = False

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act
            presenter._handle_prev_schedule()

            # Assert
            mock_collection_manager.prev_schedule.assert_called_once()
            mock_refresh.assert_not_called()

    # ======= PLAN-327. Empty Collection Navigation Boundary Verification =======

    def test_navigation_on_empty_collection_refreshes_empty_state_without_moving_index(self):
        """Verify that navigation on an empty collection refreshes the View but does not request movement."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.get_total_count.return_value = 0

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act
            presenter._handle_next_schedule()

            # Assert
            mock_collection_manager.next_schedule.assert_not_called()
            mock_collection_manager.prev_schedule.assert_not_called()
            mock_refresh.assert_called_once()

    # ======= PLAN-328. Direct Index Jump Success Verification =======

    def test_page_jump_converts_one_based_page_number_to_zero_based_index(self):
        """Verify that direct page jumps convert UI page numbers into zero-based schedule indices."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.jump_to_schedule.return_value = True

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act
            presenter._handle_page_jump(3)

            # Assert
            mock_collection_manager.jump_to_schedule.assert_called_once_with(2)
            mock_refresh.assert_called_once()
            mock_view.update_pagination.assert_not_called()

    # ======= PLAN-328. Direct Index Jump Lower Boundary Verification =======

    def test_page_jump_rejects_page_zero_and_restores_current_pagination(self):
        """Verify that jumping to page zero is rejected and the View pagination is restored."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.jump_to_schedule.return_value = False
        mock_collection_manager.get_current_index.return_value = 1
        mock_collection_manager.get_total_count.return_value = 4

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act
            presenter._handle_page_jump(0)

            # Assert
            mock_collection_manager.jump_to_schedule.assert_called_once_with(-1)
            mock_refresh.assert_not_called()
            mock_view.update_pagination.assert_called_once_with(
                current_page=2,
                total_pages=4
            )

    # ======= PLAN-328. Direct Index Jump Upper Boundary Verification =======

    def test_page_jump_rejects_out_of_range_page_and_restores_current_pagination(self):
        """Verify that jumping beyond the total schedule count restores the previous pagination display."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.jump_to_schedule.return_value = False
        mock_collection_manager.get_current_index.return_value = 2
        mock_collection_manager.get_total_count.return_value = 3

        with patch.object(presenter, "refresh_presenter_state") as mock_refresh:
            # Act
            presenter._handle_page_jump(99)

            # Assert
            mock_collection_manager.jump_to_schedule.assert_called_once_with(98)
            mock_refresh.assert_not_called()
            mock_view.update_pagination.assert_called_once_with(
                current_page=3,
                total_pages=3
            )

    # ======= PLAN-329. State Synchronization After Next Navigation Verification =======

    def test_successful_next_navigation_synchronizes_view_with_updated_collection_index(self):
        """Verify that after a successful Next action, refreshed pagination reflects the updated manager index."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.next_schedule.return_value = True
        mock_collection_manager.get_total_count.return_value = 3
        mock_collection_manager.get_current_index.return_value = 1
        mock_collection_manager.get_current_schedule.side_effect = RuntimeError(
            "Schedule content is not needed for this pagination test."
        )

        # Act
        presenter._handle_next_schedule()

        # Assert
        mock_collection_manager.next_schedule.assert_called_once()
        mock_view.update_pagination.assert_called_with(
            current_page=2,
            total_pages=3
        )
        mock_view.show_empty_state.assert_called()

    # ======= PLAN-329. State Synchronization After Previous Navigation Verification =======

    def test_successful_previous_navigation_synchronizes_view_with_updated_collection_index(self):
        """Verify that after a successful Previous action, refreshed pagination reflects the updated manager index."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.prev_schedule.return_value = True
        mock_collection_manager.get_total_count.return_value = 3
        mock_collection_manager.get_current_index.return_value = 0
        mock_collection_manager.get_current_schedule.side_effect = RuntimeError(
            "Schedule content is not needed for this pagination test."
        )

        # Act
        presenter._handle_prev_schedule()

        # Assert
        mock_collection_manager.prev_schedule.assert_called_once()
        mock_view.update_pagination.assert_called_with(
            current_page=1,
            total_pages=3
        )
        mock_view.show_empty_state.assert_called()

    # ======= PLAN-333. UI Response Time Validation For Next Navigation =======

    def test_next_navigation_handler_returns_quickly_for_responsive_ui(self):
        """Verify that the Next navigation handler completes quickly enough for a responsive UI interaction."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.next_schedule.return_value = True

        with patch.object(presenter, "refresh_presenter_state"):
            start_time = time.perf_counter()

            # Act
            presenter._handle_next_schedule()

            elapsed_time = time.perf_counter() - start_time

        # Assert
        assert elapsed_time < 0.1

    # ======= PLAN-333. UI Response Time Validation For Direct Page Jump =======

    def test_page_jump_handler_returns_quickly_for_responsive_ui(self):
        """Verify that direct page jumping completes quickly enough for a responsive UI interaction."""
        # Arrange
        presenter, mock_view, mock_model, mock_collection_manager = self._build_presenter()

        mock_collection_manager.jump_to_schedule.return_value = True

        with patch.object(presenter, "refresh_presenter_state"):
            start_time = time.perf_counter()

            # Act
            presenter._handle_page_jump(2)

            elapsed_time = time.perf_counter() - start_time

        # Assert
        assert elapsed_time < 0.1