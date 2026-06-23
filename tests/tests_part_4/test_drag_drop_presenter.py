from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.engine.scheduling_constraints import SchedulingConstraints
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.presenters.calendar_presenter import CalendarPresenter


def _course(cid, program="83101", year=1, requirement="Obligatory"):
    return Course(cid, f"C{cid}", "T", "Exam",
                  [ProgramCourseInfo(program, year, "FALL", requirement)])


def _period():
    return ExamPeriod("FALL", "Aleph", date(2026, 2, 1), date(2026, 2, 28), [])


def _build_presenter(exams, constraints=None):
    c_by_id = {c.course_id: c for c, _ in exams}
    board = Schedule(exams=[ScheduledExam(course=c, exam_date=d) for c, d in exams])

    manager = MagicMock()
    manager.get_total_count.return_value = 1
    manager.get_current_index.return_value = 0
    manager.get_current_schedule.return_value = board
    manager.get_current_metrics.return_value = None

    view = SimpleNamespace()
    # the presenter assigns its handlers onto these attributes
    for attr in ("on_next_clicked", "on_prev_clicked", "on_page_jump",
                 "on_exclude_clicked", "on_range_update_clicked", "on_export_clicked",
                 "on_filter_clicked", "on_load_more_clicked", "on_sort_changed",
                 "on_exam_dropped", "on_undo_clicked", "get_exam_periods_callback",
                 "on_sync_clicked"):
        setattr(view, attr, None)
    view.update_pagination = lambda **k: None
    view.show_empty_state = lambda: None
    view.set_undo_enabled = MagicMock()

    model = SimpleNamespace(
        constraints=constraints or SchedulingConstraints(),
        get_exam_periods=lambda: [_period()],
        get_user_excluded_dates=lambda: [],
        get_selected_programs=lambda: [],
        data_manager=SimpleNamespace(get_courses=lambda: list(c_by_id.values())),
    )

    presenter = CalendarPresenter(view=view, model=model, collection_manager=manager)
    # Skip the heavy grid render; we test the edit/session wiring in isolation.
    presenter.refresh_presenter_state = MagicMock()
    return presenter, view, manager


def _current_date(presenter, course_id):
    for e in presenter._active_board().exams:
        if e.course.course_id == course_id:
            return e.exam_date
    return None


# --- the view callbacks are wired (PLAN-560 / PLAN-563) ---------------------
def test_drag_and_undo_callbacks_are_wired():
    presenter, view, _ = _build_presenter([(_course("11111"), date(2026, 2, 3))])
    assert view.on_exam_dropped == presenter._handle_exam_dropped
    assert view.on_undo_clicked == presenter._handle_undo


# --- PLAN-560: a valid drop moves the exam ----------------------------------
def test_valid_drop_moves_exam_and_redraws():
    presenter, view, _ = _build_presenter([
        (_course("11111"), date(2026, 2, 3)),
        (_course("22222"), date(2026, 2, 20)),
    ])
    presenter.cell_to_date_mapping = {"src": date(2026, 2, 3), "dst": date(2026, 2, 10)}

    presenter._handle_exam_dropped("11111", "src", "dst")

    assert _current_date(presenter, "11111") == date(2026, 2, 10)
    presenter.refresh_presenter_state.assert_called()  # redrew


# --- PLAN-561: an invalid drop snaps back (board unchanged) -----------------
def test_invalid_drop_out_of_semester_snaps_back():
    presenter, _, _ = _build_presenter([(_course("11111"), date(2026, 2, 3))])
    presenter.cell_to_date_mapping = {"src": date(2026, 2, 3), "dst": date(2026, 5, 1)}

    presenter._handle_exam_dropped("11111", "src", "dst")

    assert _current_date(presenter, "11111") == date(2026, 2, 3)  # unchanged
    presenter.refresh_presenter_state.assert_called()  # still redrew (snap back)


def test_invalid_drop_violating_constraint_snaps_back():
    constraints = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=5)
    presenter, _, _ = _build_presenter([
        (_course("11111"), date(2026, 2, 3)),
        (_course("22222"), date(2026, 2, 20)),
    ], constraints=constraints)
    presenter.cell_to_date_mapping = {"src": date(2026, 2, 3), "dst": date(2026, 2, 18)}

    presenter._handle_exam_dropped("11111", "src", "dst")
    assert _current_date(presenter, "11111") == date(2026, 2, 3)  # unchanged


# --- PLAN-563: undo reverts -------------------------------------------------
def test_undo_reverts_manual_changes():
    presenter, _, _ = _build_presenter([(_course("11111"), date(2026, 2, 3))])
    presenter.cell_to_date_mapping = {"src": date(2026, 2, 3), "dst": date(2026, 2, 10)}

    presenter._handle_exam_dropped("11111", "src", "dst")
    assert _current_date(presenter, "11111") == date(2026, 2, 10)

    presenter._handle_undo()
    assert _current_date(presenter, "11111") == date(2026, 2, 3)


# --- PLAN-562: export uses the edited board ---------------------------------
def test_export_reflects_manual_edits(tmp_path):
    presenter, _, _ = _build_presenter([(_course("11111"), date(2026, 2, 3))])
    presenter.cell_to_date_mapping = {"src": date(2026, 2, 3), "dst": date(2026, 2, 12)}
    presenter._handle_exam_dropped("11111", "src", "dst")

    out = tmp_path / "exported.txt"
    presenter._handle_export(str(out))

    text = out.read_text(encoding="utf-8")
    assert "12-02-2026" in text       # the moved date
    assert "03-02-2026" not in text   # not the original date


# --- PLAN-554: the five metrics track the edited board ----------------------
def test_metrics_recompute_after_move_and_revert_on_undo():
    # Two mandatory exams in the same cohort. Metric 3.1 (min gap mandatory) is the
    # day-distance between them; dragging them closer must shrink it live, and undo
    # must restore the precomputed on-disk metrics.
    presenter, _, manager = _build_presenter([
        (_course("11111"), date(2026, 2, 3)),
        (_course("22222"), date(2026, 2, 20)),
    ])
    manager.get_current_metrics.return_value = ("ORIGINAL",)

    # No edits yet -> reuse the precomputed on-disk metrics verbatim.
    assert presenter._current_metrics() == ("ORIGINAL",)

    presenter.cell_to_date_mapping = {"src": date(2026, 2, 3), "dst": date(2026, 2, 18)}
    presenter._handle_exam_dropped("11111", "src", "dst")  # gap 17 -> 2 days

    edited = presenter._current_metrics()
    assert edited != ("ORIGINAL",)          # recomputed from the edited board
    assert edited[0] == 2                    # min_gap_mandatory now reflects 18th vs 20th

    presenter._handle_undo()
    assert presenter._current_metrics() == ("ORIGINAL",)  # back to the on-disk metrics
