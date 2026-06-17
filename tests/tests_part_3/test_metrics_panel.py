from unittest.mock import MagicMock
import inspect

import pytest

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


def test_metrics_panel_fields_cover_all_five_metric_keys_in_engine_order():
    assert tuple(METRICS_PANEL_FIELDS) == tuple(METRIC_KEYS)
    assert len(METRICS_PANEL_FIELDS) == 5


@pytest.mark.parametrize("lang", ["he", "en"])
def test_metrics_panel_has_title_translation(lang):
    assert TRANSLATIONS["metrics_panel_title"][lang]


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


def test_metrics_panel_clears_to_dash_when_metrics_are_missing():
    panel = _panel_stub(lang="en")

    panel.update_metrics(None)

    for key in METRICS_PANEL_FIELDS:
        assert panel._value_labels[key].configure.call_args.kwargs["text"] == "—"


def test_metrics_panel_language_update_uses_full_metric_labels():
    panel = _panel_stub(lang="he")

    panel.set_language("he")

    title_text = panel.title_label.configure.call_args.kwargs["text"]
    assert TRANSLATIONS["metrics_panel_title"]["he"] in title_text

    for key in METRICS_PANEL_FIELDS:
        label_text = panel._name_labels[key].configure.call_args.kwargs["text"]
        assert TRANSLATIONS[f"metric_{key}"]["he"] in label_text


def test_metrics_panel_show_no_more_results_sets_localized_status():
    panel = _panel_stub(lang="en")

    panel.show_no_more_results()

    assert panel.status_label.configure.call_args.kwargs["text"] == "End of results"


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


def test_calendar_view_updates_ranking_bar_metrics_panel_and_monthly_view():
    view = object.__new__(CalendarGridView)
    view.ranking_bar = MagicMock()
    view.metrics_panel = MagicMock()
    view.monthly_view = MagicMock()

    metrics = (5.0, 3.5, 0.0, 9.0, 2.0)
    view.update_metrics_display(metrics)

    view.ranking_bar.update_metrics.assert_called_once_with(metrics)
    view.metrics_panel.update_metrics.assert_called_once_with(metrics)
    view.monthly_view.update_metrics_display.assert_called_once_with(metrics)


def test_monthly_view_updates_both_compact_and_panel_metric_displays():
    view = object.__new__(MonthlyGridView)
    view.ranking_bar = MagicMock()
    view.metrics_panel = MagicMock()

    metrics = (5.0, 3.5, 0.0, 9.0, 2.0)
    view.update_metrics_display(metrics)

    view.ranking_bar.update_metrics.assert_called_once_with(metrics)
    view.metrics_panel.update_metrics.assert_called_once_with(metrics)


def test_calendar_and_monthly_language_update_refreshes_metrics_panel():
    calendar_view = object.__new__(CalendarGridView)
    calendar_view.current_lang = "en"
    calendar_view.toolbar = MagicMock()
    calendar_view.ranking_bar = MagicMock()
    calendar_view.metrics_panel = MagicMock()
    calendar_view.empty_robot = MagicMock()
    calendar_view._current_page = 1
    calendar_view._total_pages = 1
    calendar_view.day_headers = []
    calendar_view.month_labels = []
    calendar_view.grid_cells = {}
    calendar_view._cell_day_number = {}

    calendar_view.update_pagination = MagicMock()
    calendar_view.update_language("he")

    calendar_view.metrics_panel.set_language.assert_called_once_with("he")

    monthly_view = object.__new__(MonthlyGridView)
    monthly_view.current_lang = "en"
    monthly_view.toolbar = MagicMock()
    monthly_view.ranking_bar = MagicMock()
    monthly_view.metrics_panel = MagicMock()
    monthly_view.empty_robot = MagicMock()
    monthly_view._current_page = 1
    monthly_view._total_pages = 1
    monthly_view.day_headers = []
    monthly_view.active_months = []

    monthly_view.update_pagination = MagicMock()
    monthly_view.update_language("he")

    monthly_view.metrics_panel.set_language.assert_called_once_with("he")
