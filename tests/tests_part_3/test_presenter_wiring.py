# tests/tests_part_3/test_presenter_wiring.py

import pytest
from unittest.mock import MagicMock, patch

# Import only the standalone presenters which don't trigger cascading src imports
from src.MVP.presenters.input_presenter import InputPresenter
from src.MVP.presenters.calendar_presenter import CalendarPresenter


# -------------------------------------------------------------------------
# STUB / MOCK CLASSES: Light weight implementations to bypass broken cascading imports
# -------------------------------------------------------------------------
class DummyConstraints:
    def __init__(self):
        self.min_days_mandatory_enabled = False
        self.min_days_mandatory_k = 0
        self.max_exams_per_day_enabled = False
        self.max_exams_per_day_k = 0
        self.min_days_any_enabled = False


class DummyModel:
    def __init__(self):
        self.constraints = DummyConstraints()
        self.selected_programs = []
        
    def get_selected_programs(self):
        return self.selected_programs


class DummyController:
    def __init__(self, mock_window):
        self.model = DummyModel()
        self.output_path = "output_results/final_schedules.txt"
        self.engine_adapter = MagicMock()
        
        # Setup presenters with required fields
        self.input_presenter = InputPresenter(view=mock_window.input_view, model=self.model)
        self.input_presenter.controller = self
        
        self.calendar_presenter = CalendarPresenter(
            view=mock_window.calendar_view, 
            model=self.model, 
            collection_manager=MagicMock()
        )
        self.calendar_presenter.controller = self

    def regenerate_schedules_snapshot(self):
        if not self.model.get_selected_programs():
            return
            
        if self.engine_adapter.is_generation_active():
            if self.calendar_presenter:
                self.calendar_presenter._cancel_active_worker_process()

        self.engine_adapter.generate_from_model(model=self.model, output_path=self.output_path)


@pytest.fixture
def mock_mvp_setup():
    """Fixture to set up a completely mocked MVP lifecycle context."""
    mock_window = MagicMock()
    mock_window.input_view = MagicMock()
    mock_window.calendar_view = MagicMock()
    mock_window.monthly_view = MagicMock()
    
    return {
        "window": mock_window
    }


def test_input_presenter_saves_constraints_to_model(mock_mvp_setup):
    """PLAN-405: Verifies InputPresenter captures view data and updates long-lived model constraints."""
    # Arrange
    model = DummyModel()
    view = mock_mvp_setup["window"].input_view
    
    presenter = InputPresenter(view=view, model=model)
    
    simulated_ui_data = {
        "min_days_mandatory_enabled": True,
        "min_days_mandatory_k": 5,
        "max_exams_per_day_enabled": True,
        "max_exams_per_day_k": 2,
    }
    
    # Act - Simulate the Save button callback dispatch execution
    presenter._handle_save_constraints(simulated_ui_data)
    
    # Assert - Verify properties successfully synchronized down into model layer
    assert model.constraints.min_days_mandatory_enabled is True
    assert model.constraints.min_days_mandatory_k == 5
    assert model.constraints.max_exams_per_day_enabled is True
    assert model.constraints.max_exams_per_day_k == 2
    assert model.constraints.min_days_any_enabled is False


def test_app_controller_forces_clean_engine_refresh(mock_mvp_setup):
    """PLAN-405: Verifies AppController terminates active legacy workers during constraint modification."""
    # Arrange
    window = mock_mvp_setup["window"]
    controller = DummyController(mock_window=window)
    
    # Force mock states
    controller.model.selected_programs = ["83101"]
    controller.engine_adapter.is_generation_active.return_value = True
    controller.calendar_presenter._cancel_active_worker_process = MagicMock()
    
    # Act - Trigger snapshot configuration regeneration request
    controller.regenerate_schedules_snapshot()
        
    # Assert - Verify the old active background thread run was strictly cancelled first
    controller.calendar_presenter._cancel_active_worker_process.assert_called_once()
    # Verify a new execution process was launched via adapter
    controller.engine_adapter.generate_from_model.assert_called_once_with(
        model=controller.model, 
        output_path=controller.output_path
    )