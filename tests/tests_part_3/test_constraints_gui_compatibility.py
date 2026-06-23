from unittest.mock import MagicMock, patch

import pytest

# Import the controller that connects the UI views to the model/presenter layer.
from src.MVP.presenters.app_controller import AppController

# Import the constraints modal utilities and constants added for PLAN-418.
from src.MVP.views.components.constraints_modal import (
    CONSTRAINT_FIELDS,
    ConstraintsSettingsModal,
    _is_non_negative_int_candidate,
    default_constraints_data,
    normalize_constraints_data,
)

# Import the three views where the Constraints button must exist and function.
from src.MVP.views.input_view import InputConfigurationView
from src.MVP.views.calendar_view import CalendarGridView
from src.MVP.views.monthly_view import MonthlyGridView

# Import the core scheduling constraints model.
from src.engine.scheduling_constraints import SchedulingConstraints


class FakeVar:
    """
    Minimal fake replacement for Tkinter UI variable wrappers.
    During automated tests, we prevent real UI windows from opening, so this stub
    provides only the vital get() and set() state management.
    """
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeLabel:
    """
    Minimal fake replacement for a Tkinter Label widget.
    The modal invokes error_label.configure(...) to display or clear runtime validation errors.
    We utilize MagicMock to verify that visual error alerts are triggered correctly.
    """
    def __init__(self):
        self.configure = MagicMock()


@pytest.fixture
def valid_constraints_payload():
    """
    Generates a valid dictionary payload simulating incoming data from the GUI modal form.
    Notice that k values are strings here because UI Entry fields usually return
    text, even when the user typed a number.
    """
    return {
        "min_days_mandatory_enabled": True,
        "min_days_mandatory_k": "4",
        "min_days_any_enabled": True,
        "min_days_any_k": "2",
        "max_elective_conflicts_enabled": False,
        "max_elective_conflicts_k": "0",
        "span_mandatory_enabled": True,
        "span_mandatory_k": "14",
        "max_exams_per_day_enabled": True,
        "max_exams_per_day_k": "2",
    }


def test_default_constraints_data_contains_all_five_constraint_pairs():
    """
    Verifies that the default constraints state contains all five constraints.
    For every constraint we expect two fields:
    1. enabled field - whether the constraint is active.
    2. k field - the numeric value configured by the user.
    """
    data = default_constraints_data()
    
    assert len(CONSTRAINT_FIELDS) == 5

    for field in CONSTRAINT_FIELDS:
        assert field["enabled"] in data
        assert field["k"] in data
        assert data[field["enabled"]] is field["default_enabled"]
        assert data[field["k"]] == field["default_k"]


def test_normalize_constraints_data_coerces_values_and_keeps_defaults_for_missing_keys():
    """
    Verifies that normalize_constraints_data() safely converts raw UI data.
    
    This test checks three important behaviors:
    1. Boolean-like values are converted to real booleans.
    2. Numeric strings are converted to integers.
    3. Missing or invalid values fall back to safe default values.
    """
    raw_data = {
        "min_days_mandatory_enabled": "yes",
        "min_days_mandatory_k": "5",
        "min_days_any_enabled": False,
        "min_days_any_k": "bad-value",  
        "span_mandatory_enabled": True,
        "span_mandatory_k": "-7",      
    }

    normalized = normalize_constraints_data(raw_data)

    assert normalized["min_days_mandatory_enabled"] is True
    assert normalized["min_days_mandatory_k"] == 5

    assert normalized["min_days_any_enabled"] is False
    assert normalized["min_days_any_k"] == 0

    assert normalized["span_mandatory_enabled"] is True
    assert normalized["span_mandatory_k"] == 0

    # These keys were missing in raw_data, so they should receive default values.
    assert normalized["max_exams_per_day_enabled"] is False
    assert normalized["max_exams_per_day_k"] == 1


def test_non_negative_integer_candidate_validation_accepts_only_digits_or_empty_value():
    """
    Verifies the input-level validation for k fields.

    Empty string is allowed at typing time because the user may temporarily clear
    the field before typing a new value. Final save validation handles whether
    an empty value is allowed or not.
    """
    assert _is_non_negative_int_candidate("") is True
    assert _is_non_negative_int_candidate("0") is True
    assert _is_non_negative_int_candidate("12") is True

    assert _is_non_negative_int_candidate("-1") is False
    assert _is_non_negative_int_candidate("abc") is False
    assert _is_non_negative_int_candidate("1.5") is False


def _modal_stub_with_vars(enabled_value=True, k_value="3"):
    """
    Creates a fake ConstraintsSettingsModal object without opening the real UI.

    object.__new__(ConstraintsSettingsModal) creates the object without calling
    the real __init__, which prevents Tkinter windows from being created during
    unit tests.

    The test then injects fake variables into modal._vars, so internal modal
    methods can be tested directly.
    """
    modal = object.__new__(ConstraintsSettingsModal)
    modal.current_lang = "en"
    modal.error_label = FakeLabel()
    modal._vars = {}

    for field in CONSTRAINT_FIELDS:
        modal._vars[field["enabled"]] = FakeVar(enabled_value)
        modal._vars[field["k"]] = FakeVar(k_value)

    return modal


def test_constraints_modal_validation_rejects_empty_k_for_enabled_constraint():
    """
    Verifies that saving is blocked when a constraint is enabled but k is empty.

    Active constraints must have a valid numeric k value.
    """
    modal = _modal_stub_with_vars(enabled_value=True, k_value="")

    assert ConstraintsSettingsModal._validate_before_save(modal) is False
    modal.error_label.configure.assert_called_once()


def test_constraints_modal_validation_allows_empty_k_when_constraint_is_disabled():
    """
    Verifies that an empty k is allowed when the constraint itself is disabled.

    If the toggle is OFF, the k value is not used by the engine.
    """
    modal = _modal_stub_with_vars(enabled_value=False, k_value="")

    assert ConstraintsSettingsModal._validate_before_save(modal) is True
    modal.error_label.configure.assert_called_with(text="")


def test_constraints_modal_validation_rejects_non_numeric_k_even_when_disabled():
    """
    Verifies that invalid text is rejected even when the constraint is disabled.

    This keeps the stored modal state clean and prevents invalid data from being
    passed further into the Presenter/Model.
    """
    modal = _modal_stub_with_vars(enabled_value=False, k_value="abc")

    assert ConstraintsSettingsModal._validate_before_save(modal) is False
    modal.error_label.configure.assert_called_once()


def test_constraints_modal_collect_data_returns_boolean_flags_and_integer_k_values():
    """
    Verifies that the modal converts UI values into the final saved data format.

    The enabled values should be real booleans.
    The k values should be real integers, not strings.
    """
    modal = _modal_stub_with_vars(enabled_value=True, k_value="7")

    data = ConstraintsSettingsModal._collect_data(modal)

    for field in CONSTRAINT_FIELDS:
        assert data[field["enabled"]] is True
        assert data[field["k"]] == 7


def test_input_view_constraints_save_persists_normalized_state_and_notifies_presenter(valid_constraints_payload):
    """
    Verifies the Input View behavior when the user saves constraints.

    Expected behavior:
    1. The view normalizes the raw modal data.
    2. The normalized data is stored as the current constraints state.
    3. The Presenter callback is called with the saved state.
    4. The mascot displays a confirmation message.
    """
    view = object.__new__(InputConfigurationView)
    view.current_lang = "en"
    view.on_save_constraints = MagicMock()
    view.mascot = MagicMock()

    view._handle_constraints_save(valid_constraints_payload)

    saved_state = view.get_constraints_data()

    assert saved_state["min_days_mandatory_enabled"] is True
    assert saved_state["min_days_mandatory_k"] == 4
    assert saved_state["max_exams_per_day_k"] == 2

    view.on_save_constraints.assert_called_once_with(saved_state)
    view.mascot.show_speech.assert_called_once()


@pytest.mark.parametrize(
    "view_cls, patch_path",
    [
        (InputConfigurationView, "src.MVP.views.input_view.show_constraints_popup"),
        (CalendarGridView, "src.MVP.views.calendar_view.show_constraints_popup"),
        (MonthlyGridView, "src.MVP.views.monthly_view.show_constraints_popup"),
    ],
)

def test_constraints_button_opens_popup_with_current_state_and_callbacks(
    view_cls,
    patch_path,
    valid_constraints_payload,
):
    """
    Verifies that each relevant view opens the Constraints popup correctly.

    This test runs once for each view:
    1. Input view.
    2. Calendar yearly/grid view.
    3. Monthly view.

    It checks that the popup receives:
    - the parent view,
    - the current language,
    - the current constraints state,
    - the save callback,
    - the close callback,
    - and whether saving is currently enabled.
    """
    view = object.__new__(view_cls)
    view.current_lang = "en"
    view._constraints_state = normalize_constraints_data(valid_constraints_payload)
    view._constraints_save_enabled = True

    with patch(patch_path) as popup_mock:
        view._open_constraints_modal()

    popup_mock.assert_called_once_with(
        parent=view,
        current_lang="en",
        constraints_data=view._constraints_state,
        on_save_callback=view._handle_constraints_save,
        on_close_callback=view._persist_constraints_state,
        save_enabled=True,
    )


class FakeConstraintsView:
    """
    Fake view used for AppController tests.

    The real AppController connects three different views to the same constraints
    save handler. For controller unit tests, we only need the methods that the
    controller calls.
    """
    def __init__(self):
        self.on_save_constraints = None
        self.set_constraints_data = MagicMock()
        self.set_save_button_state = MagicMock()


class FakeModel:
    """
    Fake model containing initial SchedulingConstraints.

    This allows AppController tests to verify that constraints are read from the
    model and pushed into all relevant views.
    """
    def __init__(self):
        self.constraints = SchedulingConstraints(
            min_days_mandatory_enabled=True,
            min_days_mandatory_k=3,
            min_days_any_enabled=True,
            min_days_any_k=2,
            max_elective_conflicts_enabled=True,
            max_elective_conflicts_k=1,
            span_mandatory_enabled=True,
            span_mandatory_k=15,
            max_exams_per_day_enabled=True,
            max_exams_per_day_k=2,
        )


def _controller_stub():
    """
    Builds a minimal AppController test double.

    The real AppController __init__ may create or wire many objects.
    For these tests we only need:
    - model
    - engine_adapter
    - input_presenter
    - app_window with input/calendar/monthly views
    """
    controller = object.__new__(AppController)

    controller.model = FakeModel()
    controller.engine_adapter = MagicMock()
    controller.input_presenter = MagicMock()

    controller.app_window = MagicMock()
    controller.app_window.input_view = FakeConstraintsView()
    controller.app_window.calendar_view = FakeConstraintsView()
    controller.app_window.monthly_view = FakeConstraintsView()

    return controller


def _all_controller_views(controller):
    """
    helper that returns all views that support constraints settings.
    """
    return [
        controller.app_window.input_view,
        controller.app_window.calendar_view,
        controller.app_window.monthly_view,
    ]


def test_app_controller_wires_all_constraints_views_to_single_save_handler():
    """
    Verifies that AppController wires all constraints views to one save handler.

    Expected behavior:
    1. Every view receives controller._handle_constraints_settings_save as callback.
    2. Every view receives the current constraints data from the model.
    3. Every view enables the Save button when generation is not active.
    """
    controller = _controller_stub()

    controller._wire_constraints_settings_callbacks()

    for view in _all_controller_views(controller):
        assert view.on_save_constraints == controller._handle_constraints_settings_save
        view.set_constraints_data.assert_called_once()
        view.set_save_button_state.assert_called_once_with(True)


def test_app_controller_saves_constraints_when_generation_is_not_active(valid_constraints_payload):
    """
    Verifies successful constraints saving through AppController.

    When the engine is not generating schedules:
    1. The controller updates all views with the new constraints data.
    2. The controller forwards the saved constraints to InputPresenter.
    """
    controller = _controller_stub()
    controller.engine_adapter.is_generation_active.return_value = False

    controller._handle_constraints_settings_save(valid_constraints_payload)

    for view in _all_controller_views(controller):
        view.set_constraints_data.assert_called_once_with(valid_constraints_payload)

    controller.input_presenter._handle_save_constraints.assert_called_once_with(valid_constraints_payload)


def test_app_controller_blocks_constraints_save_when_generation_is_active(valid_constraints_payload):
    """
    Verifies that constraints cannot be changed while schedule generation is active.

    This protects the engine from receiving changing constraints in the middle
    of a calculation run.
    """
    controller = _controller_stub()
    controller.engine_adapter.is_generation_active.return_value = True

    controller._handle_constraints_settings_save(valid_constraints_payload)

    for view in _all_controller_views(controller):
        view.set_save_button_state.assert_called_once_with(False)
        view.set_constraints_data.assert_not_called()

    controller.input_presenter._handle_save_constraints.assert_not_called()