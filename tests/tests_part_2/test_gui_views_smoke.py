from unittest.mock import MagicMock, patch

import pytest

from src.MVP.views import theme
from src.MVP.views.ui_utils import TRANSLATIONS, format_text
from src.MVP.views.calendar_view import CalendarGridView
from src.MVP.views.monthly_view import MonthlyGridView
from src.MVP.app_window import AppWindow


class FakeCell:
    def __init__(self):
        self.configure = MagicMock()
        self.winfo_children = MagicMock(return_value=[])


def test_format_text_returns_english_text_without_rtl_marks():
    result = format_text("load_more", "en")

    assert result == "Load More"


def test_format_text_wraps_hebrew_text_with_rtl_marks():
    result = format_text("load_more", "he")

    assert result == "\u200fטען עוד\u200f"


def test_format_text_returns_key_when_translation_is_missing():
    result = format_text("missing_key", "en")

    assert result == "missing_key"


def test_translations_include_load_more_for_hebrew_and_english():
    assert TRANSLATIONS["load_more"]["he"] == "טען עוד"
    assert TRANSLATIONS["load_more"]["en"] == "Load More"


def test_theme_core_values_are_defined():
    assert theme.BG_MAIN
    assert theme.BG_CARD
    assert theme.BORDER_ACTIVE
    assert theme.TEXT_MAIN
    assert theme.RADIUS_CARD == 16
    assert theme.RADIUS_BUTTON == 8
    assert theme.FONT_FAMILY == "Rubik"


def test_calendar_semester_colors_are_selected_by_month_group():
    view = object.__new__(CalendarGridView)

    fall_color = view._get_semester_color(10)
    spring_color = view._get_semester_color(3)
    summer_color = view._get_semester_color(7)

    assert fall_color == theme.SUCCESS
    assert spring_color == theme.TEXT_ACCENT
    assert summer_color == ("#e67e22", "#f39c12")


def test_calendar_set_monthly_view_stores_reference():
    calendar_view = object.__new__(CalendarGridView)
    monthly_view = MagicMock()

    calendar_view.set_monthly_view(monthly_view)

    assert calendar_view.monthly_view is monthly_view


def test_calendar_update_pagination_updates_toolbar_and_monthly_view():
    calendar_view = object.__new__(CalendarGridView)
    calendar_view.toolbar = MagicMock()
    calendar_view.monthly_view = MagicMock()

    calendar_view.update_pagination(3, 10)

    assert calendar_view._current_page == 3
    assert calendar_view._total_pages == 10
    calendar_view.toolbar.set_pagination.assert_called_once_with(3, 10)
    calendar_view.monthly_view.update_pagination.assert_called_once_with(3, 10)


def test_calendar_update_pagination_works_without_monthly_view():
    calendar_view = object.__new__(CalendarGridView)
    calendar_view.toolbar = MagicMock()

    calendar_view.update_pagination(1, 5)

    assert calendar_view._current_page == 1
    assert calendar_view._total_pages == 5
    calendar_view.toolbar.set_pagination.assert_called_once_with(1, 5)


def test_calendar_cell_click_ignores_invalid_calendar_cell():
    calendar_view = object.__new__(CalendarGridView)
    calendar_view._cell_day_number = {"1-0": 1}
    calendar_view.selected_cell_key = None
    calendar_view.grid_cells = {"1-0": FakeCell()}
    calendar_view.monthly_view = MagicMock()
    calendar_view.on_date_selected = MagicMock()

    calendar_view._handle_cell_click("1-40")

    calendar_view.monthly_view.highlight_cell.assert_not_called()
    calendar_view.on_date_selected.assert_not_called()
    assert calendar_view.selected_cell_key is None


def test_calendar_cell_click_selects_valid_cell_and_notifies_callbacks():
    calendar_view = object.__new__(CalendarGridView)

    old_cell = FakeCell()
    new_cell = FakeCell()

    calendar_view._cell_day_number = {
        "1-0": 1,
        "1-1": 2,
    }
    calendar_view.selected_cell_key = "1-0"
    calendar_view.grid_cells = {
        "1-0": old_cell,
        "1-1": new_cell,
    }
    calendar_view.monthly_view = MagicMock()
    calendar_view.on_date_selected = MagicMock()

    calendar_view._handle_cell_click("1-1")

    old_cell.configure.assert_called_once_with(
        border_color=theme.BORDER_DEFAULT,
        border_width=1,
    )
    new_cell.configure.assert_called_once_with(
        border_color=theme.BORDER_ACTIVE,
        border_width=2,
    )
    calendar_view.monthly_view.highlight_cell.assert_called_once_with("1-1")
    calendar_view.on_date_selected.assert_called_once_with("1-1")
    assert calendar_view.selected_cell_key == "1-1"


def test_calendar_toggle_cell_exclusion_visual_updates_cell_and_monthly_view():
    calendar_view = object.__new__(CalendarGridView)

    cell = FakeCell()
    calendar_view.grid_cells = {"1-0": cell}
    calendar_view._cell_day_number = {"1-0": 1}
    calendar_view._last_grid_data = {"1-0": {"old": "data"}}
    calendar_view.monthly_view = MagicMock()

    calendar_view.toggle_cell_exclusion_visual("1-0", True)

    cell.configure.assert_called_once_with(fg_color=("#ffcccc", "#4a1c1c"))
    assert "1-0" not in calendar_view._last_grid_data
    calendar_view.monthly_view.toggle_cell_exclusion_visual.assert_called_once_with("1-0", True)


def test_calendar_fire_sync_calls_callback_when_defined():
    calendar_view = object.__new__(CalendarGridView)
    calendar_view.on_sync_clicked = MagicMock()

    calendar_view._fire_sync()

    calendar_view.on_sync_clicked.assert_called_once()


def test_monthly_update_pagination_updates_toolbar():
    monthly_view = object.__new__(MonthlyGridView)
    monthly_view.toolbar = MagicMock()

    monthly_view.update_pagination(2, 7)

    assert monthly_view._current_page == 2
    assert monthly_view._total_pages == 7
    monthly_view.toolbar.set_pagination.assert_called_once_with(2, 7)


def test_monthly_receive_data_does_nothing_when_data_is_unchanged():
    monthly_view = object.__new__(MonthlyGridView)
    monthly_view.full_grid_data = {"1-0": {"exams": []}}
    monthly_view.active_months = [1]
    monthly_view.render_current_month = MagicMock()

    monthly_view.receive_data({"1-0": {"exams": []}}, [1])

    monthly_view.render_current_month.assert_not_called()


def test_monthly_receive_data_resets_invalid_month_index_and_renders():
    monthly_view = object.__new__(MonthlyGridView)
    monthly_view.full_grid_data = {}
    monthly_view.active_months = []
    monthly_view.current_month_index = 5
    monthly_view.render_current_month = MagicMock()

    monthly_view.receive_data({"1-0": {"exams": []}}, [1, 2])

    assert monthly_view.full_grid_data == {"1-0": {"exams": []}}
    assert monthly_view.active_months == [1, 2]
    assert monthly_view.current_month_index == 0
    monthly_view.render_current_month.assert_called_once()


def test_monthly_prev_and_next_month_respect_bounds():
    monthly_view = object.__new__(MonthlyGridView)
    monthly_view.active_months = [1, 2, 3]
    monthly_view.current_month_index = 1
    monthly_view.render_current_month = MagicMock()

    monthly_view._next_month()
    assert monthly_view.current_month_index == 2

    monthly_view._next_month()
    assert monthly_view.current_month_index == 2

    monthly_view._prev_month()
    assert monthly_view.current_month_index == 1

    monthly_view._prev_month()
    assert monthly_view.current_month_index == 0

    monthly_view._prev_month()
    assert monthly_view.current_month_index == 0

    assert monthly_view.render_current_month.call_count == 3


def test_monthly_cell_click_notifies_callback():
    monthly_view = object.__new__(MonthlyGridView)
    monthly_view.on_cell_clicked = MagicMock()

    monthly_view._handle_cell_click("2-3")

    monthly_view.on_cell_clicked.assert_called_once_with("2-3")


def test_monthly_toggle_cell_exclusion_visual_updates_visible_target_cell():
    monthly_view = object.__new__(MonthlyGridView)

    cell = FakeCell()
    monthly_view.original_to_target_map = {"1-0": "2-3"}
    monthly_view.grid_cells = {"2-3": cell}
    monthly_view._last_cell_content = {"2-3": {"old": "data"}}

    monthly_view.toggle_cell_exclusion_visual("1-0", False)

    cell.configure.assert_called_once_with(fg_color=theme.BG_CARD)
    assert "2-3" not in monthly_view._last_cell_content


def test_app_window_switch_view_routes_calendar_to_monthly_when_run_mode_is_enabled():
    app = object.__new__(AppWindow)

    app._show_monthly_on_run = True
    app.input_view = MagicMock()
    app.monthly_view = MagicMock()
    app.calendar_view = MagicMock()
    app.sidebar = MagicMock()
    app.after = MagicMock()
    app._lift_floating_controls = MagicMock()

    app.switch_view("calendar")

    app.monthly_view.tkraise.assert_called_once()
    app.calendar_view.tkraise.assert_not_called()
    app.sidebar.update_active_btn.assert_called_once_with("monthly")
    app.after.assert_called_once()


def test_app_window_switch_view_routes_calendar_to_annual_when_run_mode_is_disabled():
    app = object.__new__(AppWindow)

    app._show_monthly_on_run = False
    app.input_view = MagicMock()
    app.monthly_view = MagicMock()
    app.calendar_view = MagicMock()
    app.sidebar = MagicMock()
    app.after = MagicMock()
    app._lift_floating_controls = MagicMock()

    app.switch_view("calendar")

    app.calendar_view.tkraise.assert_called_once()
    app.monthly_view.tkraise.assert_not_called()
    app.sidebar.update_active_btn.assert_called_once_with("annual")
    app.after.assert_called_once()


def test_app_window_toggle_language_updates_all_views():
    app = object.__new__(AppWindow)

    app.sidebar = MagicMock()
    app.input_view = MagicMock()
    app.calendar_view = MagicMock()
    app.monthly_view = MagicMock()
    app.after = MagicMock()
    app._lift_floating_controls = MagicMock()

    app._toggle_language("en")

    assert app.current_lang == "en"
    app.sidebar.update_language.assert_called_once_with("en")
    app.input_view.update_language.assert_called_once_with("en")
    app.calendar_view.update_language.assert_called_once_with("en")
    app.monthly_view.update_language.assert_called_once_with("en")
    app.after.assert_called_once()


def test_app_window_run_indicator_sets_computing_speech_and_safety_timer():
    app = object.__new__(AppWindow)

    app.current_lang = "en"
    app.monthly_view = MagicMock()
    app.monthly_view.empty_robot = MagicMock()
    app._run_safety = None
    app.after = MagicMock(return_value="timer-id")

    app._begin_run_indicator()

    app.monthly_view.empty_robot.set_speech.assert_called_once_with(format_text("computing", "en"))
    app.monthly_view.show_empty_state.assert_called_once()
    assert app._run_active is True
    assert app._run_safety == "timer-id"


def test_app_window_end_run_indicator_cancels_timer_and_resets_speech():
    app = object.__new__(AppWindow)

    app.current_lang = "en"
    app.monthly_view = MagicMock()
    app.monthly_view.empty_robot = MagicMock()
    app._run_safety = "timer-id"
    app.after_cancel = MagicMock()

    app._end_run_indicator()

    app.after_cancel.assert_called_once_with("timer-id")
    app.monthly_view.empty_robot.set_speech.assert_called_once_with(format_text("empty_state", "en"))
    assert app._run_active is False
    assert app._run_safety is None