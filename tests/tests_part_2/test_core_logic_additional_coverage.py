from datetime import date
from unittest.mock import MagicMock, patch, mock_open

import pytest

from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExcludedDate, ExamPeriod
from src.MVP.models.planix_model import PlanixModel
from src.MVP.presenters.app_controller import AppController
from src.MVP.presenters.input_presenter import InputPresenter


def make_course(
    course_id="10001",
    course_name="Algorithms",
    program_id="83108",
    year=1,
    semester="FALL",
    requirement="Obligatory",
):
    info = ProgramCourseInfo(
        program_id=program_id,
        year=year,
        semester=semester,
        requirement=requirement,
    )

    return Course(
        course_id=course_id,
        course_name=course_name,
        instructor="Teacher",
        evaluation_method="Exam",
        program_info=[info],
    )


def make_period(
    start=date(2026, 2, 1),
    end=date(2026, 2, 10),
    exclusions=None,
):
    return ExamPeriod(
        semester="FALL",
        moed="Aleph",
        start_date=start,
        end_date=end,
        excluded_dates=exclusions or [],
    )


def make_model(courses=None, periods=None):
    data_manager = MagicMock()
    data_manager.get_courses.return_value = courses if courses is not None else []
    data_manager.get_exam_periods.return_value = periods if periods is not None else []
    data_manager.exam_periods = periods if periods is not None else []

    return PlanixModel(data_manager=data_manager), data_manager


def test_is_generating_getter_and_setter_are_thread_safe_state_wrappers():
    model, _ = make_model()

    assert model.is_generating is False

    model.is_generating = True
    assert model.is_generating is True

    model.is_generating = False
    assert model.is_generating is False


def test_is_generating_rejects_non_boolean_value():
    model, _ = make_model()

    with pytest.raises(TypeError, match="is_generating must be a boolean"):
        model.is_generating = "yes"


def test_set_data_paths_and_getters_store_paths():
    model, _ = make_model()

    model.set_data_paths(
        courses_path="data/courses.txt",
        exam_periods_path="data/exam_periods.txt",
        selected_programs_path="data/selected_programs.txt",
    )

    assert model.get_courses_path() == "data/courses.txt"
    assert model.get_exam_periods_path() == "data/exam_periods.txt"
    assert model.get_selected_programs_path() == "data/selected_programs.txt"


def test_selected_program_validation_rejects_non_string_program_id():
    model, _ = make_model()

    with pytest.raises(TypeError, match="program_id must be a string"):
        model.add_selected_program(83108)


def test_selected_program_validation_rejects_empty_program_id():
    model, _ = make_model()

    with pytest.raises(ValueError, match="program_id cannot be empty"):
        model.add_selected_program("   ")


def test_set_selected_programs_rejects_more_than_max_after_normalization():
    model, _ = make_model()

    with pytest.raises(ValueError, match="Cannot select more than 5 programs"):
        model.set_selected_programs(["1", "2", "3", "4", "5", "6"])


def test_update_custom_exam_period_stores_range_and_enforces_state():
    period = make_period()
    model, _ = make_model(periods=[period])

    with patch.object(model, "enforce_state_to_data_manager") as enforce_mock:
        model.update_custom_exam_period(date(2026, 2, 2), date(2026, 2, 8))

    assert model._current_start_date == date(2026, 2, 2)
    assert model._current_end_date == date(2026, 2, 8)
    enforce_mock.assert_called_once()


def test_update_custom_exam_period_rejects_invalid_date_type():
    model, _ = make_model()

    with pytest.raises(TypeError, match="Expected a datetime.date value"):
        model.update_custom_exam_period("2026-02-01", date(2026, 2, 8))


def test_update_custom_exam_period_rejects_reversed_range():
    model, _ = make_model()

    with pytest.raises(ValueError, match="start_date cannot be after end_date"):
        model.update_custom_exam_period(date(2026, 2, 8), date(2026, 2, 1))


def test_update_all_exam_periods_returns_when_model_has_no_data_manager():
    model = PlanixModel(data_manager=None)

    model.update_all_exam_periods([(date(2026, 2, 1), date(2026, 2, 10))])

    assert model.data_manager is None


def test_update_all_exam_periods_returns_when_no_periods_exist():
    model, data_manager = make_model(periods=[])

    model.update_all_exam_periods([])

    data_manager.get_exam_periods.assert_called_once()


def test_update_all_exam_periods_rejects_range_count_mismatch():
    period = make_period()
    model, _ = make_model(periods=[period])

    with pytest.raises(ValueError, match="updated_ranges length must match"):
        model.update_all_exam_periods([])


def test_update_all_exam_periods_rejects_invalid_date_value():
    period = make_period()
    model, _ = make_model(periods=[period])

    with pytest.raises(TypeError, match="Expected a datetime.date value"):
        model.update_all_exam_periods([("2026-02-01", date(2026, 2, 10))])


def test_update_all_exam_periods_rejects_reversed_period_range():
    period = make_period()
    model, _ = make_model(periods=[period])

    with pytest.raises(ValueError, match="start_date cannot be after end_date"):
        model.update_all_exam_periods([(date(2026, 2, 10), date(2026, 2, 1))])


def test_update_all_exam_periods_preserves_original_exclusions_and_adds_user_exclusions():
    original_exclusion = ExcludedDate(
        start_date=date(2026, 2, 3),
        end_date=date(2026, 2, 3),
        comment="Weekend",
    )
    old_user_exclusion = ExcludedDate(
        start_date=date(2026, 2, 4),
        end_date=date(2026, 2, 4),
        comment="User Excluded",
    )

    period = make_period(exclusions=[original_exclusion, old_user_exclusion])
    model, data_manager = make_model(periods=[period])
    model._user_excluded_dates.add(date(2026, 2, 5))

    model.update_all_exam_periods([(date(2026, 2, 1), date(2026, 2, 10))])

    updated_period = data_manager.exam_periods[0]

    assert updated_period.start_date == date(2026, 2, 1)
    assert updated_period.end_date == date(2026, 2, 10)

    assert original_exclusion in updated_period.excluded_dates
    assert old_user_exclusion in updated_period.excluded_dates
    assert any(
        exclusion.start_date == date(2026, 2, 5)
        and exclusion.comment == "User Excluded"
        for exclusion in updated_period.excluded_dates
    )


def test_include_date_removes_user_exclusion_and_syncs_to_periods():
    period = make_period()
    model, _ = make_model(periods=[period])

    model.exclude_date(date(2026, 2, 5))
    assert model.get_user_excluded_dates() == [date(2026, 2, 5)]

    model.include_date(date(2026, 2, 5))

    assert model.get_user_excluded_dates() == []
    assert all(
        getattr(exclusion, "comment", "") != "User Excluded"
        for exclusion in period.excluded_dates
    )


def test_date_exclusion_rejects_invalid_type():
    model, _ = make_model()

    with pytest.raises(TypeError, match="Expected a datetime.date value"):
        model.exclude_date("2026-02-05")

    with pytest.raises(TypeError, match="Expected a datetime.date value"):
        model.include_date("2026-02-05")

    with pytest.raises(TypeError, match="Expected a datetime.date value"):
        model.toggle_date_exclusion("2026-02-05")


def test_sync_excluded_dates_returns_when_data_manager_is_missing():
    model = PlanixModel(data_manager=None)
    model._user_excluded_dates.add(date(2026, 2, 5))

    model._sync_excluded_dates_to_data_manager()

    assert model.get_user_excluded_dates() == [date(2026, 2, 5)]


def test_sync_excluded_dates_handles_data_manager_exception_gracefully():
    model, data_manager = make_model()
    data_manager.get_exam_periods.side_effect = RuntimeError("broken data manager")

    with patch("builtins.print") as print_mock:
        model.exclude_date(date(2026, 2, 5))

    assert print_mock.called


def test_validate_constraints_rejects_missing_data_manager():
    model = PlanixModel(data_manager=None)

    with pytest.raises(ValueError, match="Data manager is not configured"):
        model.validate_scheduling_constraints()


def test_validate_constraints_rejects_missing_courses():
    model, _ = make_model(courses=[], periods=[make_period()])
    model.selected_programs = ["83108"]

    with pytest.raises(ValueError, match="No courses have been loaded"):
        model.validate_scheduling_constraints()


def test_validate_constraints_rejects_missing_exam_periods():
    model, _ = make_model(courses=[make_course()], periods=[])
    model.selected_programs = ["83108"]

    with pytest.raises(ValueError, match="No exam periods have been loaded"):
        model.validate_scheduling_constraints()


def test_validate_constraints_rejects_missing_selected_programs():
    model, _ = make_model(courses=[make_course()], periods=[make_period()])

    with pytest.raises(ValueError, match="No selected programs are configured"):
        model.validate_scheduling_constraints()


def test_validate_constraints_rejects_more_than_max_selected_programs():
    model, _ = make_model(courses=[make_course()], periods=[make_period()])
    model.selected_programs = ["1", "2", "3", "4", "5", "6"]

    with pytest.raises(ValueError, match="Cannot select more than 5 programs"):
        model.validate_scheduling_constraints()


def test_validate_constraints_builds_available_programs_when_missing():
    course = make_course(program_id="83108")
    model, _ = make_model(courses=[course], periods=[make_period()])
    model.selected_programs = ["83108"]
    model.available_programs = {}

    model.validate_scheduling_constraints()

    assert model.available_programs == {"83108": "Software Engineering"}


def test_validate_constraints_rejects_invalid_excluded_date_value():
    course = make_course(program_id="83108")
    model, _ = make_model(courses=[course], periods=[make_period()])
    model.selected_programs = ["83108"]
    model.available_programs = {"83108": "Software Engineering"}
    model._user_excluded_dates.add("not-a-date")

    with pytest.raises(TypeError, match="Expected a datetime.date value"):
        model.validate_scheduling_constraints()


def test_get_program_course_hierarchy_groups_courses_and_skips_invalid_matches():
    valid_course = make_course(
        course_id="10001",
        course_name="Algorithms",
        program_id="83108",
        year=1,
        semester="FALL",
        requirement="Obligatory",
    )
    other_program_course = make_course(
        course_id="10002",
        course_name="Physics",
        program_id="83101",
        year=1,
        semester="FALL",
        requirement="Obligatory",
    )
    missing_year_course = make_course(
        course_id="10003",
        course_name="Invalid",
        program_id="83108",
        year=None,
        semester="FALL",
        requirement="Elective",
    )

    model, _ = make_model(
        courses=[valid_course, other_program_course, missing_year_course],
        periods=[make_period()],
    )

    hierarchy = model.get_program_course_hierarchy("83108")

    assert hierarchy["program_id"] == "83108"
    assert hierarchy["program_name"] == "Software Engineering"
    assert list(hierarchy["courses_by_year_and_semester"].keys()) == [1]

    fall_courses = hierarchy["courses_by_year_and_semester"][1]["FALL"]
    assert fall_courses == [
        {
            "course_id": "10001",
            "course_name": "Algorithms",
            "requirement": "Obligatory",
            "evaluation_method": "Exam",
        }
    ]


def test_get_program_course_hierarchy_uses_unknown_program_id_as_name():
    model, _ = make_model(courses=[], periods=[])

    hierarchy = model.get_program_course_hierarchy("99999")

    assert hierarchy["program_id"] == "99999"
    assert hierarchy["program_name"] == "99999"
    assert hierarchy["courses_by_year_and_semester"] == {}


def test_get_program_course_hierarchy_rejects_empty_program_id():
    model, _ = make_model()

    with pytest.raises(ValueError, match="program_id cannot be empty"):
        model.get_program_course_hierarchy("   ")


def test_get_exam_periods_returns_empty_list_without_data_manager():
    model = PlanixModel(data_manager=None)

    assert model.get_exam_periods() == []


def test_enforce_state_returns_when_data_manager_is_missing():
    model = PlanixModel(data_manager=None)

    model.enforce_state_to_data_manager()

    assert model.data_manager is None


def test_enforce_state_returns_when_no_periods_exist():
    model, data_manager = make_model(periods=[])

    model.enforce_state_to_data_manager()

    data_manager.get_exam_periods.assert_called_once()


def test_enforce_state_preserves_original_exclusions_and_adds_user_exclusions():
    original_exclusion = ExcludedDate(
        start_date=date(2026, 2, 2),
        end_date=date(2026, 2, 2),
        comment="Weekend",
    )
    old_user_exclusion = ExcludedDate(
        start_date=date(2026, 2, 5),
        end_date=date(2026, 2, 5),
        comment="User Excluded",
    )

    period = make_period(exclusions=[original_exclusion, old_user_exclusion])
    model, _ = make_model(periods=[period])
    model._user_excluded_dates.add(date(2026, 2, 6))

    model.enforce_state_to_data_manager()

    assert original_exclusion in period.excluded_dates
    assert old_user_exclusion in period.excluded_dates
    assert any(
        exclusion.start_date == date(2026, 2, 6)
        and exclusion.comment == "User Excluded"
        for exclusion in period.excluded_dates
    )


def test_exam_period_available_dates_excludes_blocked_ranges():
    period = ExamPeriod(
        semester="FALL",
        moed="Aleph",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 5),
        excluded_dates=[
            ExcludedDate(date(2026, 2, 2), date(2026, 2, 3), "Blocked")
        ],
    )

    assert period.get_available_dates() == [
        date(2026, 2, 1),
        date(2026, 2, 4),
        date(2026, 2, 5),
    ]


def test_input_presenter_validated_mode_maps_append_and_update_to_append():
    view = MagicMock()
    view.load_mode_var.get.return_value = "append"
    model = MagicMock()

    presenter = InputPresenter(view, model)
    assert presenter._get_validated_mode() == "append"

    view.load_mode_var.get.return_value = "update"
    assert presenter._get_validated_mode() == "append"


def test_input_presenter_validated_mode_maps_unknown_mode_to_replace():
    view = MagicMock()
    view.load_mode_var.get.return_value = "unexpected"
    model = MagicMock()

    presenter = InputPresenter(view, model)

    assert presenter._get_validated_mode() == "replace"


def test_input_presenter_program_details_are_read_only():
    view = MagicMock()
    model = MagicMock()
    model.get_program_course_hierarchy.return_value = {"program_id": "83108"}

    presenter = InputPresenter(view, model)
    presenter._handle_program_details("83108")

    model.get_program_course_hierarchy.assert_called_once_with("83108")
    view.display_program_courses.assert_called_once_with({"program_id": "83108"})
    model.add_selected_program.assert_not_called()
    model.remove_selected_program.assert_not_called()


def test_input_presenter_update_summary_clears_view_when_nothing_selected():
    view = MagicMock()
    model = MagicMock()
    model.get_selected_programs.return_value = []

    presenter = InputPresenter(view, model)
    presenter._update_view_summary()

    view.display_program_courses.assert_called_with({})


def test_input_presenter_selection_limit_warning_refreshes_view_and_does_not_update_summary():
    view = MagicMock()
    view.checkboxes = []
    view.show_warning_dialog = MagicMock()

    model = MagicMock()
    model.get_selected_programs.return_value = []
    model.add_selected_program.side_effect = ValueError("too many programs")
    model.get_available_programs.return_value = {}

    presenter = InputPresenter(view, model)
    presenter._handle_program_selection("83109")

    view.show_warning_dialog.assert_called_once_with("too many programs")
    view.display_programs_list.assert_called_once_with({})
    view.display_program_courses.assert_not_called()


def test_app_controller_navigation_calendar_triggers_regeneration():
    controller = object.__new__(AppController)
    controller.app_window = MagicMock()
    controller.regenerate_schedules_snapshot = MagicMock()

    controller._handle_navigation("calendar")

    controller.regenerate_schedules_snapshot.assert_called_once()
    controller.app_window.switch_view.assert_not_called()


def test_app_controller_navigation_non_calendar_switches_view():
    controller = object.__new__(AppController)
    controller.app_window = MagicMock()
    controller.regenerate_schedules_snapshot = MagicMock()

    controller._handle_navigation("input")

    controller.app_window.switch_view.assert_called_once_with("input")
    controller.regenerate_schedules_snapshot.assert_not_called()


def test_app_controller_regenerate_clears_cache_when_no_programs_selected():
    controller = object.__new__(AppController)
    controller.model = MagicMock()
    controller.model.get_selected_programs.return_value = []
    controller.collection_manager = MagicMock()
    controller.app_window = MagicMock()
    controller.engine_adapter = MagicMock()

    controller.regenerate_schedules_snapshot()

    controller.collection_manager.clear_cache.assert_called_once()
    controller.app_window.switch_view.assert_not_called()
    controller.engine_adapter.generate_from_model.assert_not_called()


def test_app_controller_regenerate_reuses_active_generation_snapshot_flow():
    controller = object.__new__(AppController)
    controller.model = MagicMock()
    controller.model.get_selected_programs.return_value = ["83108"]
    controller.model.is_generating = False
    controller.collection_manager = MagicMock()
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = True
    controller.app_window = MagicMock()
    controller._load_snapshot_schedules = MagicMock()

    controller.regenerate_schedules_snapshot()

    assert controller.collection_manager.clear_cache.call_count == 1
    controller.app_window.switch_view.assert_any_call("annual")
    controller.app_window.switch_view.assert_any_call("calendar")
    controller.engine_adapter.generate_from_model.assert_not_called()
    controller.app_window.after.assert_called_once_with(
        100,
        controller._load_snapshot_schedules,
    )


def test_app_controller_regenerate_starts_engine_when_idle():
    controller = object.__new__(AppController)
    controller.output_path = "output_results/final_schedules.txt"
    controller.model = MagicMock()
    controller.model.get_selected_programs.return_value = ["83108"]
    controller.model.is_generating = True
    controller.collection_manager = MagicMock()
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False
    controller.app_window = MagicMock()
    controller._load_snapshot_schedules = MagicMock()

    controller.regenerate_schedules_snapshot()

    assert controller.model.is_generating is False
    assert controller.collection_manager.snapshot_mode is False
    controller.engine_adapter.generate_from_model.assert_called_once_with(
        model=controller.model,
        output_path=controller.output_path,
    )
    controller.app_window.switch_view.assert_any_call("annual")
    controller.app_window.switch_view.assert_any_call("calendar")
    controller.app_window.after.assert_called_once_with(
        100,
        controller._load_snapshot_schedules,
    )


def test_app_controller_load_more_rejects_when_generation_is_active():
    controller = object.__new__(AppController)
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = True
    controller.collection_manager = MagicMock()
    controller.model = MagicMock()
    controller.app_window = MagicMock()

    controller.load_more_schedules(5)

    controller.engine_adapter.generate_from_model.assert_not_called()
    controller.app_window.after.assert_not_called()


def test_app_controller_load_more_starts_generation_and_monitoring():
    controller = object.__new__(AppController)
    controller.output_path = "output_results/final_schedules.txt"
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False
    controller.collection_manager = MagicMock()
    controller.model = MagicMock()
    controller.model.is_generating = False
    controller.app_window = MagicMock()

    controller.load_more_schedules(7)

    assert controller.model.is_generating is True
    assert controller.collection_manager.snapshot_mode is True
    controller.engine_adapter.generate_from_model.assert_called_once_with(
        model=controller.model,
        output_path=controller.output_path,
        skip_count=7,
    )
    assert controller.app_window.after.call_count == 1


def test_app_controller_monitor_load_more_finishes_and_notifies_when_no_new_results():
    controller = object.__new__(AppController)
    controller.output_path = "fake_output.txt"
    controller.collection_manager = MagicMock()
    controller.model = MagicMock()
    controller.model.is_generating = True
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False
    controller.calendar_presenter = MagicMock()
    controller.calendar_presenter.view.show_no_more_results = MagicMock()
    controller.app_window = MagicMock()

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    file_content = "--- FULL SYSTEM OPTION 1 ---\n"

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        with patch("builtins.open", mock_open(read_data=file_content)):
            controller._monitor_load_more_progress(previous_count=1)

    controller.collection_manager.build_snapshot_index.assert_called_once()
    assert controller.collection_manager.snapshot_mode is False
    assert controller.model.is_generating is False
    controller.engine_adapter.clear_finished_worker.assert_called_once()
    controller.app_window.after.assert_any_call(
        0,
        controller.calendar_presenter.refresh_presenter_state,
    )
    controller.app_window.after.assert_any_call(
        0,
        controller.calendar_presenter.view.show_no_more_results,
    )


def test_app_controller_monitor_load_more_continues_when_worker_is_active():
    controller = object.__new__(AppController)
    controller.collection_manager = MagicMock()
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = True
    controller.calendar_presenter = MagicMock()
    controller.app_window = MagicMock()

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        controller._monitor_load_more_progress(previous_count=4)

    controller.collection_manager.build_snapshot_index.assert_called_once()
    controller.app_window.after.assert_any_call(
        0,
        controller.calendar_presenter.refresh_presenter_state,
    )
    assert controller.app_window.after.call_count == 2
    
def test_app_controller_load_snapshot_schedules_continues_when_engine_is_active():
    controller = object.__new__(AppController)
    controller.collection_manager = MagicMock()
    controller.app_window = MagicMock()
    controller.calendar_presenter = MagicMock()
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = True
    controller.model = MagicMock()
    controller.model.is_generating = True

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        controller._load_snapshot_schedules()

    controller.collection_manager.build_snapshot_index.assert_called_once()
    controller.app_window.after.assert_any_call(
        0,
        controller.calendar_presenter.refresh_presenter_state,
    )
    controller.app_window.after.assert_any_call(
        1000,
        controller._load_snapshot_schedules,
    )
    controller.engine_adapter.clear_finished_worker.assert_not_called()
    assert controller.model.is_generating is True


def test_app_controller_load_snapshot_schedules_finishes_when_engine_is_idle():
    controller = object.__new__(AppController)
    controller.collection_manager = MagicMock()
    controller.collection_manager.snapshot_mode = True
    controller.app_window = MagicMock()
    controller.calendar_presenter = MagicMock()
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False
    controller.model = MagicMock()
    controller.model.is_generating = True

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        controller._load_snapshot_schedules()

    controller.collection_manager.build_snapshot_index.assert_called_once()
    controller.app_window.after.assert_called_once_with(
        0,
        controller.calendar_presenter.refresh_presenter_state,
    )
    assert controller.collection_manager.snapshot_mode is False
    assert controller.model.is_generating is False
    controller.engine_adapter.clear_finished_worker.assert_called_once()


def test_app_controller_load_snapshot_schedules_finishes_without_is_generating_attribute():
    controller = object.__new__(AppController)
    controller.collection_manager = MagicMock()
    controller.collection_manager.snapshot_mode = True
    controller.app_window = MagicMock()
    controller.calendar_presenter = MagicMock()
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False

    class ModelWithoutGenerating:
        pass

    controller.model = ModelWithoutGenerating()

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        controller._load_snapshot_schedules()

    controller.collection_manager.build_snapshot_index.assert_called_once()
    assert controller.collection_manager.snapshot_mode is False
    controller.engine_adapter.clear_finished_worker.assert_called_once()


def test_app_controller_monitor_load_more_handles_final_count_read_error():
    controller = object.__new__(AppController)
    controller.output_path = "missing_or_locked_output.txt"
    controller.collection_manager = MagicMock()
    controller.collection_manager.snapshot_mode = True
    controller.model = MagicMock()
    controller.model.is_generating = True
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False
    controller.calendar_presenter = MagicMock()
    controller.calendar_presenter.view.show_no_more_results = MagicMock()
    controller.app_window = MagicMock()

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        with patch("builtins.open", side_effect=OSError("file is locked")):
            with patch("builtins.print") as print_mock:
                controller._monitor_load_more_progress(previous_count=3)

    controller.collection_manager.build_snapshot_index.assert_called_once()
    assert controller.collection_manager.snapshot_mode is False
    assert controller.model.is_generating is False
    controller.engine_adapter.clear_finished_worker.assert_called_once()
    controller.app_window.after.assert_called_once_with(
        0,
        controller.calendar_presenter.refresh_presenter_state,
    )
    controller.calendar_presenter.view.show_no_more_results.assert_not_called()
    assert any(
        "Error evaluating post-run final counts" in str(call.args[0])
        for call in print_mock.call_args_list
    )


def test_app_controller_monitor_load_more_does_not_notify_when_new_results_exist():
    controller = object.__new__(AppController)
    controller.output_path = "fake_output.txt"
    controller.collection_manager = MagicMock()
    controller.collection_manager.snapshot_mode = True
    controller.model = MagicMock()
    controller.model.is_generating = True
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False
    controller.calendar_presenter = MagicMock()
    controller.calendar_presenter.view.show_no_more_results = MagicMock()
    controller.app_window = MagicMock()

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    file_content = (
        "--- FULL SYSTEM OPTION 1 ---\n"
        "--- FULL SYSTEM OPTION 2 ---\n"
    )

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        with patch("builtins.open", mock_open(read_data=file_content)):
            controller._monitor_load_more_progress(previous_count=1)

    controller.collection_manager.build_snapshot_index.assert_called_once()
    assert controller.collection_manager.snapshot_mode is False
    assert controller.model.is_generating is False
    controller.engine_adapter.clear_finished_worker.assert_called_once()
    controller.app_window.after.assert_called_once_with(
        0,
        controller.calendar_presenter.refresh_presenter_state,
    )
    controller.calendar_presenter.view.show_no_more_results.assert_not_called()


def test_app_controller_monitor_load_more_no_more_results_without_view_notification_method():
    controller = object.__new__(AppController)
    controller.output_path = "fake_output.txt"
    controller.collection_manager = MagicMock()
    controller.collection_manager.snapshot_mode = True
    controller.model = MagicMock()
    controller.model.is_generating = True
    controller.engine_adapter = MagicMock()
    controller.engine_adapter.is_generation_active.return_value = False
    controller.calendar_presenter = MagicMock()

    class ViewWithoutNoMoreResults:
        pass

    controller.calendar_presenter.view = ViewWithoutNoMoreResults()
    controller.app_window = MagicMock()

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    file_content = "--- FULL SYSTEM OPTION 1 ---\n"

    with patch("src.MVP.presenters.app_controller.threading.Thread", ImmediateThread):
        with patch("builtins.open", mock_open(read_data=file_content)):
            controller._monitor_load_more_progress(previous_count=1)

    controller.collection_manager.build_snapshot_index.assert_called_once()
    assert controller.collection_manager.snapshot_mode is False
    assert controller.model.is_generating is False
    controller.engine_adapter.clear_finished_worker.assert_called_once()
    controller.app_window.after.assert_called_once_with(
        0,
        controller.calendar_presenter.refresh_presenter_state,
    )   

def test_input_presenter_trigger_data_loading_handles_data_manager_exception(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    view = MagicMock()
    view.load_mode_var.get.return_value = "replace"
    view.checkboxes = []

    model = MagicMock()
    model.data_manager.load_data.side_effect = RuntimeError("load failed")

    presenter = InputPresenter(view, model)
    presenter._courses_path = "courses.txt"
    presenter._exam_periods_path = "periods.txt"

    with patch("builtins.print") as print_mock:
        presenter._trigger_data_loading()

    model.set_data_paths.assert_called_once()
    model.data_manager.load_data.assert_called_once()
    model.build_available_programs.assert_not_called()

    assert any(
        "Error during data loading flow execution" in str(call.args[0])
        for call in print_mock.call_args_list
    )


def test_input_presenter_handle_load_dates_saves_path_and_triggers_loading():
    view = MagicMock()
    model = MagicMock()

    presenter = InputPresenter(view, model)
    presenter._trigger_data_loading = MagicMock()

    presenter._handle_load_dates("data/exam_periods.txt")

    assert presenter._exam_periods_path == "data/exam_periods.txt"
    presenter._trigger_data_loading.assert_called_once()


def test_input_presenter_refresh_programs_list_selects_and_deselects_checkboxes():
    selected_checkbox = MagicMock()
    selected_checkbox.cget.return_value = "Software Engineering (83108)"

    unselected_checkbox = MagicMock()
    unselected_checkbox.cget.return_value = "Computer Science (83200)"

    view = MagicMock()
    view.checkboxes = [selected_checkbox, unselected_checkbox]

    model = MagicMock()
    model.get_available_programs.return_value = {
        "83108": "Software Engineering",
        "83200": "Computer Science",
    }
    model.get_selected_programs.return_value = ["83108"]

    presenter = InputPresenter(view, model)

    presenter._refresh_programs_list()

    view.display_programs_list.assert_called_once_with(
        {
            "83108": "Software Engineering",
            "83200": "Computer Science",
        }
    )

    selected_checkbox.select.assert_called_once()
    selected_checkbox.deselect.assert_not_called()

    unselected_checkbox.deselect.assert_called_once()
    unselected_checkbox.select.assert_not_called()