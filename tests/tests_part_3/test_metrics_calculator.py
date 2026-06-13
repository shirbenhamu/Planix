from datetime import date

import pytest

from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.metrics.metrics_calculator import (
    METRIC_KEYS,
    MetricsCalculator,
    ScheduleMetrics,
)


# --- helpers ----------------------------------------------------------------
def make_course(course_id, program_info):
    # program_info: list of (program_id, year, semester, requirement)
    return Course(
        course_id=course_id,
        course_name=f"Course {course_id}",
        instructor="Dr. Test",
        evaluation_method="Exam",
        program_info=[
            ProgramCourseInfo(program_id=p, year=y, semester=s, requirement=r)
            for (p, y, s, r) in program_info
        ],
    )


def exam(course, d):
    return ScheduledExam(course=course, exam_date=d)


def schedule(*exams):
    return Schedule(exams=list(exams))


@pytest.fixture
def calc():
    return MetricsCalculator()


# --- entry point shape (PLAN-484) -------------------------------------------
def test_calculate_yields_five_values_in_order(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    values = list(calc.calculate(s))
    assert len(values) == len(METRIC_KEYS) == 5
    assert all(isinstance(v, float) for v in values)


def test_compute_returns_named_metrics(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    metrics = calc.compute(s)
    assert isinstance(metrics, ScheduleMetrics)
    assert metrics.as_dict().keys() == set(METRIC_KEYS)
    assert metrics.as_tuple() == tuple(calc.calculate(s))


def test_from_iterable_rejects_wrong_length():
    with pytest.raises(ValueError):
        ScheduleMetrics.from_iterable(iter([1.0, 2.0, 3.0]))


def test_calculate_rejects_non_schedule(calc):
    with pytest.raises(TypeError):
        list(calc.calculate(object()))


# --- 3.1 min gap between mandatory exams ------------------------------------
def test_min_gap_mandatory_takes_global_minimum(calc):
    c1 = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    c2 = make_course("22222", [("P1", 1, "FALL", "Obligatory")])
    c3 = make_course("33333", [("P1", 1, "FALL", "Obligatory")])
    # gaps within P1/year1: 1->5 = 4, 5->8 = 3, 1->8 = 7  => min 3
    s = schedule(
        exam(c1, date(2026, 1, 1)),
        exam(c2, date(2026, 1, 5)),
        exam(c3, date(2026, 1, 8)),
    )
    assert calc.compute(s).min_gap_mandatory == 3.0


def test_min_gap_ignores_electives(calc):
    mand = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    elec = make_course("22222", [("P1", 1, "FALL", "Elective")])
    # only one mandatory exam -> no mandatory pair -> +inf
    s = schedule(exam(mand, date(2026, 1, 1)), exam(elec, date(2026, 1, 2)))
    assert calc.compute(s).min_gap_mandatory == float("inf")


def test_min_gap_separate_program_years_do_not_pair(calc):
    # same program, different years -> not a pair
    a = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    b = make_course("22222", [("P1", 2, "FALL", "Obligatory")])
    s = schedule(exam(a, date(2026, 1, 1)), exam(b, date(2026, 1, 2)))
    assert calc.compute(s).min_gap_mandatory == float("inf")


# --- 3.2 average gap (mandatory or elective) --------------------------------
def test_avg_gap_pools_all_pairs(calc):
    c1 = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    c2 = make_course("22222", [("P1", 1, "FALL", "Elective")])
    c3 = make_course("33333", [("P1", 1, "FALL", "Obligatory")])
    # pairs: (1,3)=2, (1,7)=6, (3,7)=4 => mean = 12/3 = 4
    s = schedule(
        exam(c1, date(2026, 1, 1)),
        exam(c2, date(2026, 1, 3)),
        exam(c3, date(2026, 1, 7)),
    )
    assert calc.compute(s).avg_gap_all == pytest.approx(4.0)


def test_avg_gap_zero_when_no_pairs(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    assert calc.compute(s).avg_gap_all == 0.0


# --- 3.3 elective collisions ------------------------------------------------
def test_elective_conflicts_same_day_same_program(calc):
    e1 = make_course("11111", [("P1", 1, "FALL", "Elective")])
    e2 = make_course("22222", [("P1", 1, "FALL", "Elective")])
    e3 = make_course("33333", [("P1", 1, "FALL", "Elective")])
    # three electives on the same day in P1 -> C(3,2) = 3 collisions
    d = date(2026, 1, 1)
    s = schedule(exam(e1, d), exam(e2, d), exam(e3, d))
    assert calc.compute(s).elective_conflicts == 3.0


def test_elective_conflicts_ignore_mandatory_and_other_days(calc):
    e1 = make_course("11111", [("P1", 1, "FALL", "Elective")])
    e2 = make_course("22222", [("P1", 1, "FALL", "Elective")])
    mand = make_course("33333", [("P1", 1, "FALL", "Obligatory")])
    s = schedule(
        exam(e1, date(2026, 1, 1)),
        exam(e2, date(2026, 1, 2)),   # different day -> no collision
        exam(mand, date(2026, 1, 1)),  # mandatory -> not counted
    )
    assert calc.compute(s).elective_conflicts == 0.0


def test_elective_conflicts_different_programs_do_not_collide(calc):
    e1 = make_course("11111", [("P1", 1, "FALL", "Elective")])
    e2 = make_course("22222", [("P2", 1, "FALL", "Elective")])
    d = date(2026, 1, 1)
    s = schedule(exam(e1, d), exam(e2, d))
    assert calc.compute(s).elective_conflicts == 0.0


# --- 3.4 mandatory span -----------------------------------------------------
def test_mandatory_span_first_to_last(calc):
    c1 = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    c2 = make_course("22222", [("P1", 1, "FALL", "Obligatory")])
    c3 = make_course("33333", [("P1", 1, "FALL", "Obligatory")])
    s = schedule(
        exam(c1, date(2026, 1, 1)),
        exam(c2, date(2026, 1, 10)),
        exam(c3, date(2026, 1, 4)),
    )
    assert calc.compute(s).mandatory_span == 9.0  # 10 - 1


def test_mandatory_span_min_across_groups(calc):
    # P1/y1 span = 9 ; P2/y1 span = 2 -> min = 2
    a = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    b = make_course("22222", [("P1", 1, "FALL", "Obligatory")])
    c = make_course("33333", [("P2", 1, "FALL", "Obligatory")])
    d = make_course("44444", [("P2", 1, "FALL", "Obligatory")])
    s = schedule(
        exam(a, date(2026, 1, 1)),
        exam(b, date(2026, 1, 10)),
        exam(c, date(2026, 1, 1)),
        exam(d, date(2026, 1, 3)),
    )
    assert calc.compute(s).mandatory_span == 2.0


def test_mandatory_span_inf_when_no_group_has_two(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    assert calc.compute(s).mandatory_span == float("inf")


# --- 3.5 max exams per day --------------------------------------------------
def test_max_exams_per_day(calc):
    d1 = date(2026, 1, 1)
    d2 = date(2026, 1, 2)
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), d1),
        exam(make_course("22222", [("P2", 1, "FALL", "Elective")]), d1),
        exam(make_course("33333", [("P1", 1, "FALL", "Obligatory")]), d1),
        exam(make_course("44444", [("P1", 1, "FALL", "Obligatory")]), d2),
    )
    assert calc.compute(s).max_exams_per_day == 3.0


def test_empty_schedule_defaults(calc):
    m = calc.compute(schedule())
    assert m.min_gap_mandatory == float("inf")
    assert m.avg_gap_all == 0.0
    assert m.elective_conflicts == 0.0
    assert m.mandatory_span == float("inf")
    assert m.max_exams_per_day == 0.0


# --- PLAN-485: no scheduler-internal dependency -----------------------------
def test_no_engine_import_in_module():
    # Parse the module's actual import statements (not comments/strings) and
    # assert none of them reach into the scheduler internals (src.engine).
    import ast
    import inspect
    import src.metrics.metrics_calculator as mod

    tree = ast.parse(inspect.getsource(mod))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")

    assert imported, "expected the module to import something"
    assert not any(name.startswith("src.engine") for name in imported)
