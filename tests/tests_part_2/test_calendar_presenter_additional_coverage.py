from datetime import date
from unittest.mock import MagicMock, patch

from src.MVP.models.exam_period import ExamPeriod
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.presenters.calendar_presenter import CalendarPresenter


def build_presenter():
    view = MagicMock()
    view.active_month_indices = []
    view.on_load_more_clicked = None

    model = MagicMock()
    model.get_exam_periods.return_value = []
    model.get_user_excluded_dates.return_value = []
    model.get_selected_programs.return_value = []
    model.data_manager.get_courses.return_value = []

    collection_manager = MagicMock()
    collection_manager.get_total_count.return_value = 0
    collection_manager.get_current_index.return_value = 0

    controller = MagicMock()

    presenter = CalendarPresenter(
        view=view,
        model=model,
        collection_manager=collection_manager,
        controller=controller,
    )

    view.reset_mock()
    model.reset_mock()
    collection_manager.reset_mock()
    controller.reset_mock()

    return presenter, view, model, collection_manager, controller


def make_exam(course_id="10001", course_name="Algorithms", exam_date=date(2026, 2, 15)):
    course = MagicMock()
    course.course_id = course_id
    course.course_name = course_name
    course.is_mandatory = True

    return ScheduledExam(course=course, exam_date=exam_date)


def test_setup_calendar_grid_uses_full_exam_period_range_across_months():
    presenter, view, model, collection_manager, controller = build_presenter()

    model.get_exam_periods.return_value = [
        ExamPeriod(
            semester="FALL",
            moed="Aleph",
            start_date=date(2026, 1, 20),
            end_date=date(2026, 3, 5),
            excluded_dates=[],
        )
    ]

    schedule = Schedule(exams=[make_exam(exam_date=date(2026, 2, 15))])

    presenter._setup_calendar_grid_dimensions(schedule)

    assert presenter.active_months == [0, 1, 2]
    view.init_grid.assert_called_once_with([0, 1, 2])


def test_setup_calendar_grid_falls_back_to_schedule_months_when_no_exam_periods():
    presenter, view, model, collection_manager, controller = build_presenter()

    model.get_exam_periods.return_value = []

    schedule = Schedule(
        exams=[
            make_exam("10001", "Algorithms", date(2026, 2, 15)),
            make_exam("10002", "Databases", date(2026, 4, 10)),
        ]
    )

    presenter._setup_calendar_grid_dimensions(schedule)

    assert presenter.active_months == [1, 3]
    view.init_grid.assert_called_once_with([1, 3])


def test_setup_calendar_grid_does_not_reinitialize_when_months_are_unchanged():
    presenter, view, model, collection_manager, controller = build_presenter()

    presenter.active_months = [1]
    model.get_exam_periods.return_value = []

    schedule = Schedule(exams=[make_exam(exam_date=date(2026, 2, 15))])

    presenter._setup_calendar_grid_dimensions(schedule)

    view.init_grid.assert_not_called()


def test_setup_calendar_grid_handles_model_exception_without_crashing():
    presenter, view, model, collection_manager, controller = build_presenter()

    presenter.active_months = [1]
    model.get_exam_periods.side_effect = RuntimeError("broken periods")

    schedule = Schedule(exams=[make_exam(exam_date=date(2026, 2, 15))])

    presenter._setup_calendar_grid_dimensions(schedule)

    assert presenter.active_months == [1]
    view.init_grid.assert_not_called()


def test_render_active_schedule_marks_excluded_date_and_skips_exam_outside_active_months():
    presenter, view, model, collection_manager, controller = build_presenter()

    feb_exam = make_exam("10001", "Algorithms", date(2026, 2, 15))
    apr_exam = make_exam("10002", "Databases", date(2026, 4, 10))

    model.get_user_excluded_dates.return_value = [date(2026, 2, 15)]
    model.data_manager.get_courses.return_value = [feb_exam.course, apr_exam.course]

    presenter.active_months = [1]
    presenter._render_active_schedule(Schedule(exams=[feb_exam, apr_exam]))

    grid_data = view.render_calendar_data.call_args[0][0]

    assert grid_data["1-14"]["is_excluded"] is True
    assert len(grid_data["1-14"]["exams"]) == 1
    assert grid_data["1-14"]["exams"][0]["course_id"] == "10001"

    assert all(
        exam["course_id"] != "10002"
        for cell in grid_data.values()
        for exam in cell["exams"]
    )


def test_render_active_schedule_uses_elective_marker_when_course_is_not_mandatory():
    presenter, view, model, collection_manager, controller = build_presenter()

    exam = make_exam("10001", "Elective Course", date(2026, 2, 15))
    real_course = MagicMock()
    real_course.course_id = "10001"
    real_course.is_mandatory = False

    model.data_manager.get_courses.return_value = [real_course]
    presenter.active_months = [1]

    presenter._render_active_schedule(Schedule(exams=[exam]))

    grid_data = view.render_calendar_data.call_args[0][0]

    assert grid_data["1-14"]["exams"][0]["type"] == "ב"


def test_build_course_to_program_map_collects_program_names_without_duplicates():
    presenter, view, model, collection_manager, controller = build_presenter()

    model.get_selected_programs.return_value = ["83108", "83109"]
    model.get_program_course_hierarchy.side_effect = [
        {
            "program_name": "Software Engineering",
            "courses_by_year_and_semester": {
                1: {
                    "FALL": [
                        {"course_id": "10001"},
                        {"course_id": "10001"},
                        {"course_id": None},
                    ]
                }
            },
        },
        {
            "program_name": "Computer Science",
            "courses_by_year_and_semester": {
                1: {
                    "FALL": [
                        {"course_id": "10001"},
                        {"course_id": "10002"},
                    ]
                }
            },
        },
    ]

    result = presenter._build_course_to_program_map()

    assert result["10001"] == ["Software Engineering", "Computer Science"]
    assert result["10002"] == ["Computer Science"]


def test_build_course_to_program_map_returns_empty_dict_on_model_error():
    presenter, view, model, collection_manager, controller = build_presenter()

    model.get_selected_programs.side_effect = RuntimeError("program loading failed")

    result = presenter._build_course_to_program_map()

    assert result == {}


def test_date_exclusion_unknown_cell_does_not_touch_model_or_collection_manager():
    presenter, view, model, collection_manager, controller = build_presenter()

    presenter._handle_date_exclusion("missing-cell")

    model.toggle_date_exclusion.assert_not_called()
    collection_manager.get_current_schedule.assert_not_called()


def test_date_exclusion_rerender_errors_are_handled_gracefully():
    presenter, view, model, collection_manager, controller = build_presenter()

    presenter.cell_to_date_mapping["1-14"] = date(2026, 2, 15)
    collection_manager.get_current_schedule.side_effect = RuntimeError("schedule unavailable")

    presenter._handle_date_exclusion("1-14")

    model.toggle_date_exclusion.assert_called_once_with(date(2026, 2, 15))


def test_range_update_returns_when_no_exam_periods_exist():
    presenter, view, model, collection_manager, controller = build_presenter()

    model.get_exam_periods.return_value = []

    presenter._handle_range_update([("01-02-2026", "10-02-2026")])

    model.update_all_exam_periods.assert_not_called()
    collection_manager.clear_cache.assert_not_called()


def test_range_update_updates_period_ranges_and_exclusion_dates():
    presenter, view, model, collection_manager, controller = build_presenter()

    model.get_exam_periods.return_value = [
        ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 10), []),
        ExamPeriod("FALL", "Bet", date(2026, 3, 1), date(2026, 3, 10), []),
    ]

    presenter._handle_range_update(
        [
            ("02-02-2026", "12-02-2026"),
            ("05-03-2026", "05-03-2026"),
        ]
    )

    model.update_all_exam_periods.assert_called_once_with(
        [(date(2026, 2, 2), date(2026, 2, 12))]
    )
    model.exclude_date.assert_called_once_with(date(2026, 3, 5))
    collection_manager.clear_cache.assert_called_once()


def test_range_update_uses_legacy_single_range_update_when_bulk_method_missing():
    presenter, view, model, collection_manager, controller = build_presenter()

    model.get_exam_periods.return_value = [
        ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 10), [])
    ]

    del model.update_all_exam_periods
    model.update_custom_exam_period = MagicMock()

    presenter._handle_range_update([("02-02-2026", "12-02-2026")])

    model.update_custom_exam_period.assert_called_once_with(
        date(2026, 2, 2),
        date(2026, 2, 12),
    )
    collection_manager.clear_cache.assert_called_once()


def test_filter_click_cleans_program_ids_and_regenerates_snapshot():
    presenter, view, model, collection_manager, controller = build_presenter()

    view.get_selected_programs.return_value = [
        "Software Engineering (83108)",
        "Computer Science (83200)",
    ]

    presenter._handle_filter_click()

    model.update_selected_programs.assert_called_once_with(["83108", "83200"])
    controller.regenerate_schedules_snapshot.assert_called_once()


def test_filter_click_preserves_model_when_view_selection_is_empty():
    presenter, view, model, collection_manager, controller = build_presenter()

    view.get_selected_programs.return_value = []

    presenter._handle_filter_click()

    model.update_selected_programs.assert_not_called()
    controller.regenerate_schedules_snapshot.assert_called_once()


def test_sync_action_clears_cache_and_regenerates_when_controller_exists():
    presenter, view, model, collection_manager, controller = build_presenter()

    presenter._handle_sync_action()

    collection_manager.clear_cache.assert_called_once()
    controller.regenerate_schedules_snapshot.assert_called_once()