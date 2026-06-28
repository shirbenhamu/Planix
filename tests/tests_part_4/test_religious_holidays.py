import pytest
from datetime import date
from unittest.mock import MagicMock, patch
from src.engine.scheduling_constraints import SchedulingConstraints
from src.engine.holiday_data import get_holidays_for_religions
from src.MVP.models.planix_model import PlanixModel
from src.MVP.models.exam_period import ExamPeriod, ExcludedDate
from src.MVP.presenters.input_presenter import InputPresenter
from src.MVP.views.components.constraints_modal import normalize_constraints_data, default_constraints_data

# =====================================================================
# 1. HOLIDAY DATA LAYER TESTS (DYNAMIC)
# =====================================================================
def test_get_holidays_for_religions_valid():
    """Validates that checking multiple religions aggregates and flattens data correctly via holidays lib."""
    selected = ["Jewish", "Muslim"]
    holiday_map = get_holidays_for_religions(selected, year=2026)
    
    # Assert specific 2026 dates exist in the dynamically generated dictionary from the library
    assert date(2026, 4, 2) in holiday_map       # Pesach
    assert date(2026, 3, 20) in holiday_map      # Eid al-Fitr
    assert "Jewish" in holiday_map[date(2026, 4, 2)]
    assert "Muslim" in holiday_map[date(2026, 3, 20)]

def test_get_holidays_for_religions_empty_and_invalid():
    """Ensures empty selections or unrecognized keys do not trigger crashes."""
    assert get_holidays_for_religions([]) == {}
    assert get_holidays_for_religions(["Buddhism", "Unknown"]) == {}

# =====================================================================
# 2. SCHEDULING CONSTRAINTS DATACLASS TESTS
# =====================================================================
def test_scheduling_constraints_initialization():
    """Verifies selected_religions field integration inside the baseline dataclass."""
    constraints = SchedulingConstraints()
    assert hasattr(constraints, "selected_religions")
    assert isinstance(constraints.selected_religions, list)
    assert len(constraints.selected_religions) == 0

# =====================================================================
# 3. PLANIX MODEL CACHE & INJECTION INTEGRATION TESTS
# =====================================================================
def test_model_religious_holidays_cache_logic():
    """Asserts model accurately reflects active constraints into its internal cache helper."""
    mock_dm = MagicMock()
    # Setup mock ExamPeriod to allow dynamic year extraction
    mock_period = ExamPeriod(
        semester="Spring", moed="A",
        start_date=date(2026, 1, 1), end_date=date(2026, 12, 31),
        excluded_dates=[]
    )
    mock_dm.get_exam_periods.return_value = [mock_period]
    model = PlanixModel(data_manager=mock_dm)
    
    model.constraints.selected_religions = ["Christian"]
    cache = model.get_religious_holidays_cache()
    
    assert date(2026, 12, 25) in cache  # Christmas Day
    assert "Christian" in cache[date(2026, 12, 25)]

def test_model_enforce_state_injects_holidays_to_data_manager():
    """Verifies that enforce_state safely builds ExcludedDate instances into the DataManager."""
    mock_dm = MagicMock()
    
    # Setup mock ExamPeriod covering April 2026
    mock_period = ExamPeriod(
        semester="Spring",
        moed="A",
        start_date=date(2026, 4, 1),
        end_date=date(2026, 4, 30),
        excluded_dates=[]
    )
    mock_dm.get_exam_periods.return_value = [mock_period]
    
    model = PlanixModel(data_manager=mock_dm)
    model.constraints.selected_religions = ["Jewish"]
    
    # Trigger injection execution pipeline
    model.enforce_state_to_data_manager()
    
    # Assertions on DataManager mutations
    assert len(mock_period.excluded_dates) > 0
    religious_exclusions = [
        ex for ex in mock_period.excluded_dates 
        if isinstance(ex, ExcludedDate) and "Jewish" in ex.comment
    ]
    assert len(religious_exclusions) >= 1

# =====================================================================
# 4. INPUT PRESENTER MULTI-SELECT PIPELINE TESTS
# =====================================================================
def test_presenter_extracts_and_saves_selected_religions_from_view():
    """Validates that the save handler fetches selected_religions map array securely."""
    mock_view = MagicMock()
    mock_model = MagicMock()
    mock_model.constraints = SchedulingConstraints()
    
    ui_payload = {
        "min_days_mandatory_enabled": True,
        "min_days_mandatory_k": 3,
        "selected_religions": ["Jewish", "Muslim"]
    }
    
    presenter = InputPresenter(view=mock_view, model=mock_model)
    presenter._handle_save_constraints(ui_payload)
    
    assert mock_model.constraints.min_days_mandatory_enabled is True
    assert mock_model.constraints.min_days_mandatory_k == 3
    assert mock_model.constraints.selected_religions == ["Jewish", "Muslim"]
    mock_model.enforce_state_to_data_manager.assert_called_once()

# =====================================================================
# 5. VIEW CONSTRAINTS MODAL DATA NORMALIZATION TESTS
# =====================================================================
def test_modal_data_normalization_handles_religions_safely():
    """Ensures that components normalization layer accurately reads/defaults arrays."""
    raw_input = {"selected_religions": ["Christian"], "min_days_any_enabled": True}
    normalized = normalize_constraints_data(raw_input)
    assert normalized["selected_religions"] == ["Christian"]
    assert normalized["min_days_any_enabled"] is True
    
    normalized_empty = normalize_constraints_data(None)
    assert normalized_empty["selected_religions"] == []