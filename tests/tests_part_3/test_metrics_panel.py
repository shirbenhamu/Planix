import pytest
import inspect
from unittest.mock import MagicMock
from src.MVP.views.calendar_view import CalendarGridView
from src.MVP.views.monthly_view import MonthlyGridView
from src.MVP.views.components.metrics_panel import METRICS_PANEL_FIELDS, MetricsPanel
from src.MVP.views.ui_utils import TRANSLATIONS
from src.metrics.metrics_calculator import METRIC_KEYS

class FakeLabel:
    """Small stand-in for CTkLabel that records configure(...) calls."""

    def __init__(self):
        self.configure = MagicMock()

def _panel_stub(lang="en"):
    """Build a MetricsPanel without creating real CustomTkinter widgets."""
    panel = object.__new__(MetricsPanel)
    panel.current_lang = lang
    panel._last_metrics = None
    panel.title_label = FakeLabel()
    panel.status_label = FakeLabel()
    panel._name_labels = {key: FakeLabel() for key in METRICS_PANEL_FIELDS}
    panel._value_labels = {key: FakeLabel() for key in METRICS_PANEL_FIELDS}
    return panel

# Panel fields equal the five metric keys, in engine order.
def test_metrics_panel_fields_cover_all_five_metric_keys_in_engine_order():
    assert tuple(METRICS_PANEL_FIELDS) == tuple(METRIC_KEYS)
    assert len(METRICS_PANEL_FIELDS) == 5

# The panel title is translated in each language.
@pytest.mark.parametrize("lang", ["he", "en"])
def test_metrics_panel_has_title_translation(lang):
    assert TRANSLATIONS["metrics_panel_title"][lang]

# Each of the five values renders next to its correct label (including the infinity symbol).
def test_metrics_panel_renders_all_five_labeled_values():
    panel = _panel_stub(lang="en")
    panel.update_metrics((5.0, 3.5, 0.0, float("inf"), 2.0))
    rendered_values = {
        key: panel._value_labels[key].configure.call_args.kwargs["text"]
        for key in METRICS_PANEL_FIELDS
    }
    assert rendered_values["min_gap_mandatory"] == "5"
    assert rendered_values["avg_gap_all"] == "3.5"
    assert rendered_values["elective_conflicts"] == "0"
    assert rendered_values["mandatory_span"] == "∞"
    assert rendered_values["max_exams_per_day"] == "2"
    for key in METRICS_PANEL_FIELDS:
        panel._value_labels[key].configure.assert_called()

# The panel accepts a dict payload, not only a tuple.
def test_metrics_panel_accepts_metric_dictionary_payload():
    panel = _panel_stub(lang="en")
    panel.update_metrics({
        "min_gap_mandatory": 4.0,
        "avg_gap_all": 2.5,
        "elective_conflicts": 1.0,
        "mandatory_span": 12.0,
        "max_exams_per_day": 3.0,
    })

    assert panel._value_labels["min_gap_mandatory"].configure.call_args.kwargs["text"] == "4"
    assert panel._value_labels["avg_gap_all"].configure.call_args.kwargs["text"] == "2.5"
    assert panel._value_labels["max_exams_per_day"].configure.call_args.kwargs["text"] == "3"

# Passing None clears every value to a dash.
def test_metrics_panel_clears_to_dash_when_metrics_are_missing():
    panel = _panel_stub(lang="en")
    panel.update_metrics(None)
    for key in METRICS_PANEL_FIELDS:
        assert panel._value_labels[key].configure.call_args.kwargs["text"] == "—"

# A language switch refreshes the title and the full metric labels.
def test_metrics_panel_language_update_uses_full_metric_labels():
    panel = _panel_stub(lang="he")

    panel.set_language("he")

    title_text = panel.title_label.configure.call_args.kwargs["text"]
    assert TRANSLATIONS["metrics_panel_title"]["he"] in title_text

    for key in METRICS_PANEL_FIELDS:
        label_text = panel._name_labels[key].configure.call_args.kwargs["text"]
        assert TRANSLATIONS[f"metric_{key}"]["he"] in label_text

# show_no_more_results sets the localized status text.
def test_metrics_panel_show_no_more_results_sets_localized_status():
    panel = _panel_stub(lang="en")

    panel.show_no_more_results()

    assert panel.status_label.configure.call_args.kwargs["text"] == "End of results"

# The panel source uses theme constants for layout, colors and fonts (no hard-coded styling).
def test_metrics_panel_source_uses_theme_constants_for_layout_colors_and_fonts():
    source = inspect.getsource(MetricsPanel)

    assert "theme.BG_CARD" in source
    assert "theme.BG_CARD_HOVER" in source
    assert "theme.BORDER_DEFAULT" in source
    assert "theme.TEXT_MAIN" in source
    assert "theme.TEXT_MUTED" in source
    assert "theme.TEXT_ACCENT" in source
    assert "theme.FONT_FAMILY" in source
    assert "theme.RADIUS_CARD" in source
    assert "theme.SPACING_SMALL" in source
    assert "theme.SPACING_REGULAR" in source

# The calendar view forwards metrics to both the ranking bar and the monthly view.
def test_calendar_view_updates_compact_ranking_bar_and_monthly_view():
    view = object.__new__(CalendarGridView)
    view.ranking_bar = MagicMock()
    view.monthly_view = MagicMock()

    metrics = (5.0, 3.5, 0.0, 9.0, 2.0)
    view.update_metrics_display(metrics)

    view.ranking_bar.update_metrics.assert_called_once_with(metrics)
    view.monthly_view.update_metrics_display.assert_called_once_with(metrics)

# The monthly view forwards metrics only to its ranking bar.
def test_monthly_view_updates_compact_metric_display_only():
    view = object.__new__(MonthlyGridView)
    view.ranking_bar = MagicMock()

    metrics = (5.0, 3.5, 0.0, 9.0, 2.0)
    view.update_metrics_display(metrics)

    view.ranking_bar.update_metrics.assert_called_once_with(metrics)

# A language switch refreshes the ranking bar in both calendar and monthly views.
def test_calendar_and_monthly_language_update_refreshes_compact_ranking_bar():
    calendar_view = object.__new__(CalendarGridView)
    calendar_view.current_lang = "en"
    calendar_view.toolbar = MagicMock()
    calendar_view.ranking_bar = MagicMock()
    calendar_view.empty_robot = MagicMock()
    calendar_view._current_page = 1
    calendar_view._total_pages = 1
    calendar_view.day_headers = []
    calendar_view.month_labels = []
    calendar_view.grid_cells = {}
    calendar_view._cell_day_number = {}
    calendar_view.update_pagination = MagicMock()
    calendar_view.update_language("he")
    calendar_view.ranking_bar.set_language.assert_called_once_with("he")
    monthly_view = object.__new__(MonthlyGridView)
    monthly_view.current_lang = "en"
    monthly_view.toolbar = MagicMock()
    monthly_view.ranking_bar = MagicMock()
    monthly_view.empty_robot = MagicMock()
    monthly_view._current_page = 1
    monthly_view._total_pages = 1
    monthly_view.day_headers = []
    monthly_view.active_months = []
    monthly_view.update_pagination = MagicMock()
    monthly_view.update_language("he")
    monthly_view.ranking_bar.set_language.assert_called_once_with("he")

# _metrics_by_key maps each value to the key at its position.
def test_metrics_panel_mapping_logic():
    panel = _panel_stub()
    # Distinct test values so a wrong key-to-value pairing is easy to spot
    test_values = (10.0, 20.0, 30.0, 40.0, 50.0)
    panel.update_metrics(test_values)
    mapped_data = panel._metrics_by_key()
    
    # Ensure every key is present
    assert len(mapped_data) == len(METRICS_PANEL_FIELDS)

    # Ensure each key received the value matching its position in METRICS_PANEL_FIELDS
    for i, key in enumerate(METRICS_PANEL_FIELDS):
        assert mapped_data[key] == test_values[i]
        
# Update_metrics writes each formatted value into its label.
def test_metrics_panel_rendering_updates_labels():
    panel = _panel_stub(lang="en")
    test_metrics = {"avg_gap_all": 2.5, "min_gap_mandatory": 1.0, "elective_conflicts": 0, "mandatory_span": 5, "max_exams_per_day": 2}
    
    panel.update_metrics(test_metrics)
    
    for key, value in test_metrics.items():
        panel._value_labels[key].configure.assert_called()
        args, kwargs = panel._value_labels[key].configure.call_args
        
        # Stringify the value like the code does (drop the trailing .0 for whole numbers)
        expected_text = str(int(value)) if value == int(value) else str(value)
        # When the value is 0 it may be "0" or "0.0" - ensure this matches the metrics_panel.py implementation
        if value == 0:
            expected_text = "0"
            
        assert kwargs["text"] == expected_text
        
# set_language updates the language and re-renders.
def test_metrics_panel_set_language_calls_render():
    panel = _panel_stub(lang="en")
    panel._render_metrics = MagicMock()
    
    panel.set_language("he")
    
    assert panel.current_lang == "he"
    panel._render_metrics.assert_called_once()