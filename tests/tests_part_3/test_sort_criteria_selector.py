from unittest.mock import MagicMock, patch

import pytest

from src.MVP.views.components.ranking_bar import RankingBar
from src.MVP.views.components.sort_criteria_modal import (
    DEFAULT_SORT_CRITERIA,
    SORT_CRITERIA_ORDER,
    SortCriteriaSelectorModal,
    move_key_in_order,
    normalize_full_metric_order,
    normalize_selected_sort_keys,
    place_key_at_index,
)
from src.MVP.views.ui_utils import TRANSLATIONS
from src.metrics.metrics_calculator import METRIC_KEYS


class FakeBoolVar:
    def __init__(self, value):
        self.value = bool(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)


def _modal_stub(order=None, enabled_keys=None):
    modal = object.__new__(SortCriteriaSelectorModal)
    modal.current_lang = "en"
    modal._ordered_keys = list(order or SORT_CRITERIA_ORDER)
    enabled_keys = set(enabled_keys or [])
    modal._enabled_vars = {
        key: FakeBoolVar(key in enabled_keys)
        for key in SORT_CRITERIA_ORDER
    }
    modal.error_label = MagicMock()
    return modal


def _ranking_bar_stub(lang="he"):
    bar = object.__new__(RankingBar)
    bar.current_lang = lang
    bar.on_sort_changed = None
    bar._sort_keys = ["avg_gap_all"]
    bar._primary_key = "avg_gap_all"
    bar._secondary_key = None
    bar._ascending = False
    bar.sort_selector_btn = MagicMock()
    return bar


def test_normalize_selected_sort_keys_removes_invalid_duplicates_and_preserves_priority():
    result = normalize_selected_sort_keys([
        "max_exams_per_day",
        "not_a_metric",
        "avg_gap_all",
        "max_exams_per_day",
        "min_gap_mandatory",
    ])

    assert result == ["max_exams_per_day", "avg_gap_all", "min_gap_mandatory"]


def test_normalize_selected_sort_keys_falls_back_to_default_when_empty():
    assert normalize_selected_sort_keys([]) == DEFAULT_SORT_CRITERIA
    assert normalize_selected_sort_keys(["invalid"]) == DEFAULT_SORT_CRITERIA
    assert normalize_selected_sort_keys(None) == DEFAULT_SORT_CRITERIA


def test_normalize_full_metric_order_keeps_selected_first_then_adds_remaining_metrics():
    order = normalize_full_metric_order(["mandatory_span", "avg_gap_all"])

    assert order[:2] == ["mandatory_span", "avg_gap_all"]
    assert set(order) == set(METRIC_KEYS)
    assert len(order) == 5


def test_move_key_in_order_moves_metric_up_and_down_inside_bounds():
    order = ["avg_gap_all", "min_gap_mandatory", "elective_conflicts"]

    assert move_key_in_order(order, "elective_conflicts", -1) == [
        "avg_gap_all",
        "elective_conflicts",
        "min_gap_mandatory",
    ]
    assert move_key_in_order(order, "avg_gap_all", -1) == order
    assert move_key_in_order(order, "missing", 1) == order


def test_place_key_at_index_supports_drag_drop_reordering():
    order = ["avg_gap_all", "min_gap_mandatory", "elective_conflicts"]

    assert place_key_at_index(order, "elective_conflicts", 0) == [
        "elective_conflicts",
        "avg_gap_all",
        "min_gap_mandatory",
    ]
    assert place_key_at_index(order, "avg_gap_all", 99) == [
        "min_gap_mandatory",
        "elective_conflicts",
        "avg_gap_all",
    ]


def test_modal_collect_sort_keys_returns_enabled_metrics_in_visual_order():
    modal = _modal_stub(
        order=["mandatory_span", "avg_gap_all", "max_exams_per_day"],
        enabled_keys={"avg_gap_all", "max_exams_per_day"},
    )

    assert SortCriteriaSelectorModal._collect_sort_keys(modal) == [
        "avg_gap_all",
        "max_exams_per_day",
    ]


def test_modal_validation_rejects_saving_when_no_metric_is_selected():
    modal = _modal_stub(enabled_keys=set())

    assert SortCriteriaSelectorModal._validate_before_save(modal) is False
    modal.error_label.configure.assert_called_once()


def test_modal_validation_accepts_at_least_one_selected_metric():
    modal = _modal_stub(enabled_keys={"avg_gap_all"})

    assert SortCriteriaSelectorModal._validate_before_save(modal) is True
    modal.error_label.configure.assert_called_with(text="")


def test_ranking_bar_set_sort_keys_updates_visual_order_and_legacy_fields():
    bar = _ranking_bar_stub(lang="en")

    RankingBar.set_sort_keys(bar, ["mandatory_span", "avg_gap_all"])

    assert bar.get_sort_keys() == ["mandatory_span", "avg_gap_all"]
    assert bar._primary_key == "mandatory_span"
    assert bar._secondary_key == "avg_gap_all"
    assert "Span(mand)" in bar.sort_selector_btn.configure.call_args.kwargs["text"]


def test_ranking_bar_saving_popup_selection_triggers_presenter_callback():
    bar = _ranking_bar_stub(lang="en")
    bar.on_sort_changed = MagicMock()

    RankingBar._handle_sort_selection(bar, ["max_exams_per_day", "avg_gap_all"])

    assert bar.get_sort_keys() == ["max_exams_per_day", "avg_gap_all"]
    bar.on_sort_changed.assert_called_once_with(
        ["max_exams_per_day", "avg_gap_all"],
        False,
    )


def test_ranking_bar_open_sort_selector_passes_current_order_and_save_callback():
    bar = _ranking_bar_stub(lang="he")
    bar._sort_keys = ["max_exams_per_day", "avg_gap_all"]

    with patch("src.MVP.views.components.ranking_bar.show_sort_criteria_popup") as popup_mock:
        RankingBar._open_sort_selector(bar)

    popup_mock.assert_called_once_with(
        parent=bar,
        current_lang="he",
        sort_keys=["max_exams_per_day", "avg_gap_all"],
        on_save_callback=bar._handle_sort_selection,
    )


@pytest.mark.parametrize("key", [
    "sort_selector_tooltip",
    "sort_selector_title",
    "sort_selector_hint",
    "sort_selector_empty_error",
])
@pytest.mark.parametrize("lang", ["he", "en"])
def test_sort_selector_translations_exist(key, lang):
    assert TRANSLATIONS[key][lang]
