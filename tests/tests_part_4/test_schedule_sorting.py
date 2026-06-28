import pytest
from unittest.mock import MagicMock, patch
from src.data_manager import DataManager
from src.parsers.base_parser import BaseParser
from src.metrics.metrics_calculator import METRIC_KEYS
from src.MVP.models.schedule_collection_manager import (
    ScheduleCollectionManager, DEFAULT_SORT_KEYS, DEFAULT_SORT_ASCENDING,
)
from src.MVP.presenters.calendar_presenter import CalendarPresenter
from src.MVP.views.components.sort_criteria_modal import (
    normalize_selected_sort_keys,
    normalize_full_metric_order,
    move_key_in_order,
    place_key_at_index,
    DEFAULT_SORT_CRITERIA,
)

# METRIC_KEYS order: (min_gap_mandatory, avg_gap_all, elective_conflicts,
#                     mandatory_span, max_exams_per_day)
MIN_GAP, AVG_GAP, ELECTIVE, SPAN, MAX_DAY = range(5)

# ===========================================================================
# Helpers — write real schedule blocks (with METRICS lines) to disk
# ===========================================================================
class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []

def _data_manager():
    DataManager._instance = None
    dm = DataManager(_DummyParser())
    dm.courses = {}
    return dm

def _write_blocks(tmp_path, metric_tuples, include_metrics=True):
    """metric_tuples: list of 5-tuples in METRIC_KEYS order; None entry -> a block
    with NO metrics line (legacy block, must sink to the bottom)."""
    lines = ["=== Complete Academic Year Schedules ===", "", ""]
    for i, metrics in enumerate(metric_tuples, start=1):
        lines.append(f"--- FULL SYSTEM OPTION {i} ---")
        lines.append(f"Date: 0{(i % 9) + 1}-02-2026 | Course: 1000{i} - C{i} | Instructor: T")
        if metrics is not None:
            lines.append("METRICS|" + "|".join(str(x) for x in metrics))
        lines.append("-" * 60)
        lines.append("")
    path = tmp_path / "schedules.txt"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path

def _manager(tmp_path, metric_tuples):
    path = _write_blocks(tmp_path, metric_tuples)
    return ScheduleCollectionManager(str(path), _data_manager())

def _order(cm, index):
    """The metric value at position `index` for every schedule, in current order."""
    return [cm.get_metrics(i)[index] if cm.get_metrics(i) is not None else None
            for i in range(cm.get_total_count())]

# ===========================================================================
# 1. sort_collection — single criterion
# ===========================================================================
class TestSingleCriterionSort:
    def _metrics(self):
        # avg_gap values 10/30/20 so default (avg desc) is NOT already in file order
        return [
            (1.0, 10.0, 0.0, 4.0, 2.0),
            (1.0, 30.0, 0.0, 4.0, 1.0),
            (1.0, 20.0, 0.0, 4.0, 3.0),
        ]

    def test_descending_sort_puts_highest_first(self, tmp_path):
        cm = _manager(tmp_path, self._metrics())
        cm.sort_collection(["avg_gap_all"], ascending=False)
        assert _order(cm, AVG_GAP) == [30.0, 20.0, 10.0]

    def test_ascending_sort_puts_lowest_first(self, tmp_path):
        cm = _manager(tmp_path, self._metrics())
        cm.sort_collection(["avg_gap_all"], ascending=True)
        assert _order(cm, AVG_GAP) == [10.0, 20.0, 30.0]

    def test_sort_by_a_different_metric(self, tmp_path):
        cm = _manager(tmp_path, self._metrics())
        cm.sort_collection(["max_exams_per_day"], ascending=True)
        assert _order(cm, MAX_DAY) == [1.0, 2.0, 3.0]

    def test_user_sort_jumps_to_top(self, tmp_path):
        cm = _manager(tmp_path, self._metrics())
        cm.jump_to_schedule(2)
        cm.sort_collection(["avg_gap_all"], ascending=False)
        assert cm.get_current_index() == 0  # a user sort resets to the new best

# ===========================================================================
# 2. sort_collection — multi-criteria (priority + tie-breakers)
# ===========================================================================
class TestMultiCriteriaSort:
    def test_primary_then_tiebreaker(self, tmp_path):
        # Same avg_gap (primary) -> max_exams_per_day (secondary, asc) breaks ties.
        metrics = [
            (1.0, 20.0, 0.0, 4.0, 3.0),
            (1.0, 20.0, 0.0, 4.0, 1.0),
            (1.0, 20.0, 0.0, 4.0, 2.0),
            (1.0, 50.0, 0.0, 4.0, 9.0),
        ]
        cm = _manager(tmp_path, metrics)
        cm.sort_collection(["avg_gap_all", "max_exams_per_day"], ascending=[False, True])
        # 50 first (best primary), then the three 20s ordered by max_day asc.
        assert _order(cm, AVG_GAP) == [50.0, 20.0, 20.0, 20.0]
        assert _order(cm, MAX_DAY) == [9.0, 1.0, 2.0, 3.0]

# ===========================================================================
# 3. Blocks without metrics sink to the bottom
# ===========================================================================
class TestNoMetricBlocksSink:
    def test_legacy_blocks_sort_last_regardless_of_direction(self, tmp_path):
        cm = _manager(tmp_path, [(1.0, 10.0, 0.0, 4.0, 1.0), None, (1.0, 30.0, 0.0, 4.0, 1.0)])
        cm.sort_collection(["avg_gap_all"], ascending=False)
        order = _order(cm, AVG_GAP)
        assert order[:2] == [30.0, 10.0]      # scored blocks first, best-first
        assert order[2] is None               # the metric-less block sinks last

# ===========================================================================
# 4. get_active_sort_spec & the documented default
# ===========================================================================
class TestActiveSortSpecAndDefault:
    def test_default_sort_applied_on_first_load(self, tmp_path):
        # Default is avg_gap_all descending — applied without any user action.
        cm = _manager(tmp_path, [(1, 10, 0, 4, 1), (1, 30, 0, 4, 1), (1, 20, 0, 4, 1)])
        assert _order(cm, AVG_GAP) == [30.0, 20.0, 10.0]

    def test_active_spec_is_default_then_follows_user(self, tmp_path):
        cm = _manager(tmp_path, [(1, 10, 0, 4, 1), (1, 30, 0, 4, 1)])
        default_index = METRIC_KEYS.index(DEFAULT_SORT_KEYS[0])
        assert cm.get_active_sort_spec() == [(default_index, DEFAULT_SORT_ASCENDING)]

        cm.sort_collection(["max_exams_per_day", "min_gap_mandatory"], ascending=[True, False])
        assert cm.get_active_sort_spec() == [(MAX_DAY, True), (MIN_GAP, False)]

    def test_clear_sort_stops_auto_resort_without_reapplying_default(self, tmp_path):
        cm = _manager(tmp_path, [(1, 10, 0, 4, 1), (1, 30, 0, 4, 1)])
        cm.clear_sort()
        assert cm._sort_spec is None
        assert cm._user_sorted is True   # user has taken control; default won't re-apply

# ===========================================================================
# 5. _resolve_sort_spec / _resolve_ascending_flags / _build_sort_key
# ===========================================================================
class TestSortSpecResolution:
    @pytest.fixture
    def cm(self, tmp_path):
        return _manager(tmp_path, [(1, 10, 0, 4, 1)])

    def test_resolve_spec_maps_keys_to_indices(self, cm):
        spec = cm._resolve_sort_spec(["avg_gap_all", "max_exams_per_day"], None)
        assert spec == [(AVG_GAP, False), (MAX_DAY, False)]

    def test_resolve_spec_rejects_unknown_key(self, cm):
        with pytest.raises(ValueError, match="Unknown metric"):
            cm._resolve_sort_spec(["not_a_metric"], None)

    def test_resolve_spec_rejects_empty(self, cm):
        with pytest.raises(ValueError, match="at least one"):
            cm._resolve_sort_spec([], None)

    def test_resolve_spec_rejects_bare_string(self, cm):
        with pytest.raises(TypeError, match="not a single string"):
            cm._resolve_sort_spec("avg_gap_all", None)

    def test_ascending_flags_default_all_descending(self, cm):
        assert cm._resolve_ascending_flags(["a", "b"], None) == [False, False]

    def test_ascending_flags_single_bool_applies_to_all(self, cm):
        assert cm._resolve_ascending_flags(["a", "b"], True) == [True, True]

    def test_ascending_flags_per_key_dict(self, cm):
        assert cm._resolve_ascending_flags(["a", "b"], {"a": True}) == [True, False]

    def test_ascending_flags_list_must_match_length(self, cm):
        with pytest.raises(ValueError, match="length"):
            cm._resolve_ascending_flags(["a", "b"], [True])

    def test_ascending_flags_list_must_be_bools(self, cm):
        with pytest.raises(TypeError, match="booleans"):
            cm._resolve_ascending_flags(["a", "b"], [True, "no"])

    def test_build_sort_key_negates_for_descending(self, cm):
        key_fn = cm._build_sort_key([(AVG_GAP, False)])  # descending
        a = key_fn((0, (1.0, 30.0, 0.0, 4.0, 1.0)))
        b = key_fn((0, (1.0, 10.0, 0.0, 4.0, 1.0)))
        assert a < b  # higher avg_gap compares "smaller" => sorts first

    def test_build_sort_key_sinks_metric_less_entries(self, cm):
        key_fn = cm._build_sort_key([(AVG_GAP, False)])
        scored = key_fn((0, (1.0, 99.0, 0.0, 4.0, 1.0)))
        unscored = key_fn((0, None))
        assert scored < unscored  # (0, ...) < (1, ()) -> metric-less always last

# ===========================================================================
# 6. CalendarPresenter._handle_sort_changed
# ===========================================================================
class TestPresenterSortWiring:
    def _presenter(self):
        view = MagicMock()
        view.active_month_indices = []
        model = MagicMock()
        model.get_user_excluded_dates.return_value = []
        model.get_exam_periods.return_value = []
        model.get_selected_programs.return_value = []
        model.data_manager.get_courses.return_value = []
        collection = MagicMock()
        collection.get_total_count.return_value = 0
        collection.get_current_index.return_value = 0
        return CalendarPresenter(view, model, collection), collection

    def test_sort_change_sorts_then_refreshes(self):
        presenter, collection = self._presenter()
        with patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_sort_changed(["avg_gap_all"], ascending=False)
        collection.sort_collection.assert_called_once_with(["avg_gap_all"], ascending=False)
        refresh.assert_called_once()

    def test_invalid_sort_request_is_ignored(self):
        presenter, collection = self._presenter()
        collection.sort_collection.side_effect = ValueError("bad keys")
        with patch.object(presenter, "refresh_presenter_state") as refresh:
            presenter._handle_sort_changed(["nope"])
        refresh.assert_not_called()  # swallowed, no crash, no redraw

# ===========================================================================
# 7. sort_criteria_modal pure helpers
# ===========================================================================
class TestSortModalHelpers:
    def test_normalize_dedups_and_filters_invalid(self):
        assert normalize_selected_sort_keys(
            ["avg_gap_all", "avg_gap_all", "junk", "max_exams_per_day"]
        ) == ["avg_gap_all", "max_exams_per_day"]

    def test_normalize_falls_back_to_default_when_empty(self):
        assert normalize_selected_sort_keys([]) == list(DEFAULT_SORT_CRITERIA)
        assert normalize_selected_sort_keys(None) == list(DEFAULT_SORT_CRITERIA)
        assert normalize_selected_sort_keys(["junk"]) == list(DEFAULT_SORT_CRITERIA)

    def test_normalize_accepts_a_single_string(self):
        assert normalize_selected_sort_keys("max_exams_per_day") == ["max_exams_per_day"]

    def test_full_order_keeps_selected_first_then_appends_rest(self):
        order = normalize_full_metric_order(["max_exams_per_day"])
        assert order[0] == "max_exams_per_day"
        assert set(order) == set(METRIC_KEYS)
        assert len(order) == len(METRIC_KEYS)

    def test_move_key_up_and_down(self):
        order = list(METRIC_KEYS)
        moved = move_key_in_order(order, METRIC_KEYS[2], -1)
        assert moved.index(METRIC_KEYS[2]) == 1
        back = move_key_in_order(moved, METRIC_KEYS[2], +1)
        assert back == order

    def test_move_key_clamps_at_edges(self):
        order = list(METRIC_KEYS)
        assert move_key_in_order(order, METRIC_KEYS[0], -1) == order  # already first
        assert move_key_in_order(order, METRIC_KEYS[-1], +1) == order  # already last

    def test_move_unknown_key_is_noop(self):
        order = list(METRIC_KEYS)
        assert move_key_in_order(order, "junk", 1) == order

    def test_place_key_at_index(self):
        order = list(METRIC_KEYS)
        placed = place_key_at_index(order, METRIC_KEYS[4], 0)
        assert placed[0] == METRIC_KEYS[4]
        assert set(placed) == set(METRIC_KEYS)

    def test_place_key_clamps_out_of_range_index(self):
        order = list(METRIC_KEYS)
        placed = place_key_at_index(order, METRIC_KEYS[0], 999)
        assert placed[-1] == METRIC_KEYS[0]