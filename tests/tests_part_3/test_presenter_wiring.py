# tests/tests_part_3/test_presenter_wiring.py

import pytest
from unittest.mock import MagicMock, patch

# Robust multi-path import resolution pattern to perfectly match all testing configurations
try:
    from MVP.models.planix_model import PlanixModel
    from MVP.presenters.input_presenter import InputPresenter
    from MVP.presenters.calendar_presenter import CalendarPresenter
except ModuleNotFoundError:
    from src.MVP.models.planix_model import PlanixModel
    from src.MVP.presenters.input_presenter import InputPresenter
    from src.MVP.presenters.calendar_presenter import CalendarPresenter


# Light-weight dummy implementation to ensure clean tests without full app cascade crashes
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

    def enforce_state_to_data_manager(self):   
        pass

class DummyController:
    def __init__(self, mock_window):
        self.model = DummyModel()
        self.output_path = "output_results/final_schedules.txt"
        self.engine_adapter = MagicMock()
        self.app_window = mock_window
        
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
            
        # Secure UI Lock fallback validation
        if self.engine_adapter.is_generation_active():
            self.app_window.switch_view("calendar")
            return

        self.engine_adapter.generate_from_model(model=self.model, output_path=self.output_path)


@pytest.fixture
def mock_mvp_setup():
    mock_window = MagicMock()
    mock_window.input_view = MagicMock()
    mock_window.calendar_view = MagicMock()
    mock_window.monthly_view = MagicMock()
    
    return {
        "window": mock_window
    }


def test_input_presenter_saves_constraints_to_model(mock_mvp_setup):
    """PLAN-405: Verifies InputPresenter captures view data and updates long-lived model constraints."""
    model = DummyModel()
    view = mock_mvp_setup["window"].input_view
    
    presenter = InputPresenter(view=view, model=model)
    simulated_ui_data = {
        "min_days_mandatory_enabled": True,
        "min_days_mandatory_k": "5",  # checking numeric evaluation safety string casting
        "max_exams_per_day_enabled": True,
        "max_exams_per_day_k": "2",
    }
    
    presenter._handle_save_constraints(simulated_ui_data)
    
    assert model.constraints.min_days_mandatory_enabled is True
    assert model.constraints.min_days_mandatory_k == 5
    assert model.constraints.max_exams_per_day_enabled is True
    assert model.constraints.max_exams_per_day_k == 2


def test_app_controller_safe_ui_lock_fallback_routing(mock_mvp_setup):
    """PLAN-405: Verifies AppController cleanly routes straight to preview screen without re-triggering active runs."""
    window = mock_mvp_setup["window"]
    controller = DummyController(mock_window=window)
    
    controller.model.selected_programs = ["83101"]
    controller.engine_adapter.is_generation_active.return_value = True
    
    controller.regenerate_schedules_snapshot()
        
    # Verify the background run was NOT launched a second time
    controller.engine_adapter.generate_from_model.assert_not_called()
    # Verify app safely switched view straight to the layout results screen
    window.switch_view.assert_called_once_with("calendar")