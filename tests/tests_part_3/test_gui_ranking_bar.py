import pytest
from unittest.mock import MagicMock
from src.MVP.views.components.ranking_bar import (
    METRIC_DISPLAY_ORDER,
    RankingBar,
    format_metric_value,
)
from src.MVP.views.ui_utils import TRANSLATIONS
from src.metrics.metrics_calculator import METRIC_KEYS


def _bar(lang="he", primary="avg_gap_all", secondary=None, ascending=False):
    """Build a RankingBar without the heavy CTk __init__ (no display in CI),
    seeding just the state + label maps that the logic methods touch."""
    bar = object.__new__(RankingBar)
    bar.current_lang = lang
    bar.on_sort_changed = None
    bar._primary_key = primary
    bar._secondary_key = secondary
    bar._ascending = ascending
    bar._last_metrics = None
    bar.metrics_label = MagicMock()
    # Label maps the real set_language() would have built.
    bar._primary_label_to_key = {bar._metric_label(k): k for k in METRIC_DISPLAY_ORDER}
    bar._secondary_label_to_key = {bar._t("sort_none"): None}
    bar._secondary_label_to_key.update(
        {bar._metric_label(k): k for k in METRIC_DISPLAY_ORDER}
    )
    bar._dir_desc = f"{bar._t('sort_dir_desc')} ▼"
    bar._dir_asc = f"{bar._t('sort_dir_asc')} ▲"
    return bar


# _fire with one key reports it, descending by default.
def test_fire_single_key_descending_default():
    bar = _bar()
    bar.on_sort_changed = MagicMock()
    bar._fire()
    bar.on_sort_changed.assert_called_once_with(["avg_gap_all"], False)

# _fire reports primary+secondary in priority order, ascending.
def test_fire_multi_key_priority_ascending():
    bar = _bar(primary="max_exams_per_day", secondary="min_gap_mandatory", ascending=True)
    bar.on_sort_changed = MagicMock()
    bar._fire()
    bar.on_sort_changed.assert_called_once_with(
        ["max_exams_per_day", "min_gap_mandatory"], True
    )

# A secondary equal to the primary is dropped.
def test_fire_dedupes_secondary_equal_primary():
    bar = _bar(primary="avg_gap_all", secondary="avg_gap_all")
    bar.on_sort_changed = MagicMock()
    bar._fire()
    bar.on_sort_changed.assert_called_once_with(["avg_gap_all"], False)

# _fire is a no-op (no error) when no handler is wired.
def test_fire_noop_without_handler():
    bar = _bar()
    bar.on_sort_changed = None
    bar._fire()  # must not raise


# Choosing a primary metric updates state and fires the callback.
def test_on_primary_updates_key_and_fires():
    bar = _bar()
    bar.on_sort_changed = MagicMock()
    bar._on_primary(bar._metric_label("min_gap_mandatory"))
    assert bar._primary_key == "min_gap_mandatory"
    bar.on_sort_changed.assert_called_once_with(["min_gap_mandatory"], False)

# Choosing the 'none' secondary clears the secondary key.
def test_on_secondary_none_clears_key():
    bar = _bar(secondary="min_gap_mandatory")
    bar.on_sort_changed = MagicMock()
    bar._on_secondary(bar._t("sort_none"))
    assert bar._secondary_key is None
    bar.on_sort_changed.assert_called_once_with(["avg_gap_all"], False)

# Selecting the ascending label flips direction and fires.
def test_on_direction_toggles_ascending():
    bar = _bar()
    bar.on_sort_changed = MagicMock()
    bar._on_direction(bar._dir_asc)
    assert bar._ascending is True
    bar.on_sort_changed.assert_called_once_with(["avg_gap_all"], True)

# The info button invokes its handler when one is present.
def test_on_info_click_calls_handler():
    bar = _bar()
    bar.on_info = MagicMock()
    bar._on_info_click()
    bar.on_info.assert_called_once()

# The info button does nothing (no error) without a handler.
def test_on_info_click_noop_without_handler():
    bar = _bar()
    bar.on_info = None
    bar.on_metrics_details = None
    bar._on_info_click()  # must not raise

# Hebrew readout uses localized short labels, including the infinity symbol.
def test_render_metrics_hebrew():
    bar = _bar(lang="he")
    bar.update_metrics((5.0, 3.5, 0.0, float("inf"), 2.0))
    text = bar.metrics_label.configure.call_args.kwargs["text"]
    assert TRANSLATIONS["metric_short_min_gap_mandatory"]["he"] + ": 5" in text
    assert TRANSLATIONS["metric_short_mandatory_span"]["he"] + ": ∞" in text

# English readout uses localized short labels and formats values.
def test_render_metrics_english():
    bar = _bar(lang="en")
    bar.update_metrics((5.0, 3.5, 0.0, 9.0, 2.0))
    text = bar.metrics_label.configure.call_args.kwargs["text"]
    assert "Avg: 3.5" in text
    assert "Max/day: 2" in text

# Passing None blanks the metrics readout.
def test_update_metrics_none_clears():
    bar = _bar()
    bar.update_metrics(None)
    assert bar.metrics_label.configure.call_args.kwargs["text"] == ""

# The end-of-results message is localized per language.
def test_show_no_more_results_localized():
    bar_he = _bar(lang="he")
    bar_he.show_no_more_results()
    assert "סוף" in bar_he.metrics_label.configure.call_args.kwargs["text"]

    bar_en = _bar(lang="en")
    bar_en.show_no_more_results()
    assert "End of results" in bar_en.metrics_label.configure.call_args.kwargs["text"]


# --- value formatting + metric coverage ---

@pytest.mark.parametrize("value,expected", [
    (None, "—"),
    (float("inf"), "∞"),
    (2.0, "2"),
    (3.5, "3.5"),
    (0.0, "0"),
])

# Value formatter: dash for None, infinity symbol for inf, integers without a trailing .0.
def test_format_metric_value(value, expected):
    assert format_metric_value(value) == expected

# The display order covers every metric, with the default metric first.
def test_display_order_covers_all_metrics_default_first():
    assert set(METRIC_DISPLAY_ORDER) == set(METRIC_KEYS)
    assert METRIC_DISPLAY_ORDER[0] == "avg_gap_all"


# Every metric has both long and short labels in each language.
@pytest.mark.parametrize("key", METRIC_KEYS)
@pytest.mark.parametrize("lang", ["he", "en"])
def test_translations_exist_for_every_metric(key, lang):
    assert TRANSLATIONS[f"metric_{key}"][lang]
    assert TRANSLATIONS[f"metric_short_{key}"][lang]


# Every info/help string is translated in each language.
@pytest.mark.parametrize("lang", ["he", "en"])
def test_info_help_translations_exist(lang):
    for key in (
        "info_btn_tooltip", "metrics_values_button", "metrics_values_tooltip",
        "metrics_values_empty", "info_title", "info_sort_title", "info_sort_desc",
        "info_metrics_title", "info_pref_higher", "info_pref_lower",
    ):
        assert TRANSLATIONS[key][lang], f"missing {key}/{lang}"

# Every metric has an info-panel description in each language.
@pytest.mark.parametrize("key", METRIC_KEYS)
@pytest.mark.parametrize("lang", ["he", "en"])
def test_info_metric_descriptions_exist(key, lang):
    assert TRANSLATIONS[f"info_metric_{key}"][lang], f"missing info_metric_{key}/{lang}"
    
# Spot-check of the value formatter's main edge cases.
def test_format_metric_value_edge_cases():
    """
    Ensures the formatter correctly handles special data types to prevent 
    displaying raw technical values to the end user.
    """
    from src.MVP.views.components.ranking_bar import format_metric_value
    # Verify that missing data is represented by a clean placeholder.
    assert format_metric_value(None) == "—"
    # Verify that mathematical infinity is converted to a readable symbol.
    assert format_metric_value(float('inf')) == "∞"
    # Verify that zero is preserved as a numeric string.
    assert format_metric_value(0) == "0"
    
# _render_metrics writes the formatted value into the readout label.
def test_ranking_bar_render_metrics_formatting():
    """
    Verifies that the Ranking Bar UI component correctly processes a list of 
    raw metrics and updates the display label with formatted text.
    """
    bar = _bar(lang="en")
    # Simulate a set of raw metrics (e.g., scores or counts).
    bar._last_metrics = [1.5, 0, 2, 3, 1] 
    # Trigger the rendering process that updates the UI label.
    bar._render_metrics()
    # Verify that the UI 'configure' method was triggered (updating the text).
    assert bar.metrics_label.configure.called
    # Extract the arguments passed to the configuration method to check the final output.
    args, kwargs = bar.metrics_label.configure.call_args
    # Confirm that the UI text contains the expected label ('Avg') and the processed value ('1.5').
    assert "Avg" in kwargs["text"]
    assert "1.5" in kwargs["text"]