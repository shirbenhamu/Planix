import pytest
from datetime import date
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.metrics.metrics_calculator import (
    METRIC_KEYS,
    MetricsCalculator,
    ScheduleMetrics,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Build a course with the given id and program memberships.
def make_course(course_id, program_info):
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

# Build a ScheduledExam for a course on a given date.
def exam(course, d):
    return ScheduledExam(course=course, exam_date=d)

# Build a Schedule from the given exams.
def schedule(*exams):
    return Schedule(exams=list(exams))

# Fixture: a fresh MetricsCalculator.
@pytest.fixture
def calc():
    return MetricsCalculator()

# calculate() returns the five metric values in engine order.
def test_calculate_yields_five_values_in_order(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    values = list(calc.calculate(s))
    assert len(values) == len(METRIC_KEYS) == 5
    assert all(isinstance(v, float) for v in values)

# compute() returns a named ScheduleMetrics object.
def test_compute_returns_named_metrics(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    metrics = calc.compute(s)
    assert isinstance(metrics, ScheduleMetrics)
    assert metrics.as_dict().keys() == set(METRIC_KEYS)
    assert metrics.as_tuple() == tuple(calc.calculate(s))

# Building metrics from an iterable rejects the wrong number of values.
def test_from_iterable_rejects_wrong_length():
    with pytest.raises(ValueError):
        ScheduleMetrics.from_iterable(iter([1.0, 2.0, 3.0]))

# calculate() rejects input that is not a Schedule.
def test_calculate_rejects_non_schedule(calc):
    with pytest.raises(TypeError):
        list(calc.calculate(object()))


# min_gap_mandatory is the global minimum gap across all mandatory pairs.
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

# min_gap_mandatory ignores elective exams.
def test_min_gap_ignores_electives(calc):
    mand = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    elec = make_course("22222", [("P1", 1, "FALL", "Elective")])
    # only one mandatory exam -> no mandatory pair -> +inf
    s = schedule(exam(mand, date(2026, 1, 1)), exam(elec, date(2026, 1, 2)))
    assert calc.compute(s).min_gap_mandatory == float("inf")

# Exams from different program-years are never paired for the gap.
def test_min_gap_separate_program_years_do_not_pair(calc):
    # same program, different years -> not a pair
    a = make_course("11111", [("P1", 1, "FALL", "Obligatory")])
    b = make_course("22222", [("P1", 2, "FALL", "Obligatory")])
    s = schedule(exam(a, date(2026, 1, 1)), exam(b, date(2026, 1, 2)))
    assert calc.compute(s).min_gap_mandatory == float("inf")

# avg_gap_all averages the gaps over all valid pairs.
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

# avg_gap_all is zero when there are no pairs.
def test_avg_gap_zero_when_no_pairs(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    assert calc.compute(s).avg_gap_all == 0.0

# Two electives on the same day in the same program count as a conflict.
def test_elective_conflicts_same_day_same_program(calc):
    e1 = make_course("11111", [("P1", 1, "FALL", "Elective")])
    e2 = make_course("22222", [("P1", 1, "FALL", "Elective")])
    e3 = make_course("33333", [("P1", 1, "FALL", "Elective")])
    # three electives on the same day in P1 -> C(3,2) = 3 collisions
    d = date(2026, 1, 1)
    s = schedule(exam(e1, d), exam(e2, d), exam(e3, d))
    assert calc.compute(s).elective_conflicts == 3.0

# Mandatory exams and different days are not elective conflicts.
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

# Electives in different programs do not collide.
def test_elective_conflicts_different_programs_do_not_collide(calc):
    e1 = make_course("11111", [("P1", 1, "FALL", "Elective")])
    e2 = make_course("22222", [("P2", 1, "FALL", "Elective")])
    d = date(2026, 1, 1)
    s = schedule(exam(e1, d), exam(e2, d))
    assert calc.compute(s).elective_conflicts == 0.0


# mandatory_span is the span from the first to the last mandatory exam.
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

# mandatory_span takes the minimum span across program-year groups.
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

# mandatory_span is +inf when no group has at least two mandatory exams.
def test_mandatory_span_inf_when_no_group_has_two(calc):
    s = schedule(
        exam(make_course("11111", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1)),
    )
    assert calc.compute(s).mandatory_span == float("inf")

# max_exams_per_day is the busiest single day's exam count.
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

# An empty schedule yields the documented default metric values.
def test_empty_schedule_defaults(calc):
    m = calc.compute(schedule())
    assert m.min_gap_mandatory == float("inf")
    assert m.avg_gap_all == 0.0
    assert m.elective_conflicts == 0.0
    assert m.mandatory_span == float("inf")
    assert m.max_exams_per_day == 0.0

# The metrics module must not import the engine (keeps the layers separate).
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

# An exam belonging to two mandatory groups is counted in both.
def test_single_exam_with_two_mandatory_memberships_counts_in_both_groups(calc):
    """A course mandatory in two different (program, year) pairs must
    contribute its exam date to both groups."""
    shared = make_course(
        "95000",
        [("P1", 1, "FALL", "Obligatory"), ("P2", 2, "FALL", "Obligatory")],
    )
    partner_p1 = make_course("95001", [("P1", 1, "FALL", "Obligatory")])
    partner_p2 = make_course("95002", [("P2", 2, "FALL", "Obligatory")])

    s = schedule(
        exam(shared, date(2026, 1, 1)),
        exam(partner_p1, date(2026, 1, 6)),   # P1/1 gap -> 5
        exam(partner_p2, date(2026, 1, 10)),  # P2/2 gap -> 9
    )
    metrics = calc.compute(s)
    assert metrics.min_gap_mandatory == 5.0   # min(5, 9)
    assert metrics.mandatory_span == 5.0      # min(span 5, span 9)

# A course with no program info only affects the max-exams-per-day count.
def test_course_with_empty_program_info_only_affects_max_per_day(calc):
    orphan = make_course("90000", [])  # no program/year/requirement at all
    s = schedule(exam(orphan, date(2026, 1, 1)))
    metrics = calc.compute(s)
    assert metrics.min_gap_mandatory == float("inf")
    assert metrics.avg_gap_all == 0.0
    assert metrics.elective_conflicts == 0.0
    assert metrics.mandatory_span == float("inf")
    assert metrics.max_exams_per_day == 1.0

# All five metrics computed together on one schedule match expected values.
def test_combined_schedule_all_five_metrics_together(calc):
    shared = lambda cid: make_course(
        cid, [("P1", 1, "FALL", "Obligatory"), ("P2", 2, "FALL", "Obligatory")]
    )
    s = schedule(
        exam(shared("M1"), date(2026, 1, 1)),
        exam(shared("M2"), date(2026, 1, 7)),
        exam(make_course("M3", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 11)),
        exam(make_course("E1", [("P1", 1, "FALL", "Elective")]), date(2026, 1, 7)),
        exam(make_course("E2", [("P1", 1, "FALL", "Elective")]), date(2026, 1, 7)),
        exam(make_course("E3", [("P1", 1, "FALL", "Elective")]), date(2026, 1, 21)),
        exam(make_course("N1", []), date(2026, 4, 11)),
    )
    metrics = calc.compute(s)
    assert metrics.min_gap_mandatory == pytest.approx(4.0)
    assert metrics.avg_gap_all == pytest.approx(7.375)
    assert metrics.elective_conflicts == pytest.approx(1.0)
    assert metrics.mandatory_span == pytest.approx(6.0)
    assert metrics.max_exams_per_day == pytest.approx(3.0)
    # calculate() (yield-based entry point) must agree with compute().
    assert tuple(calc.calculate(s)) == metrics.as_tuple()

# calculate() rejects every kind of non-Schedule input.
@pytest.mark.parametrize("bad_schedule", [None, "schedule", 42, 3.14, [], {}, object()])
def test_calculate_rejects_every_kind_of_non_schedule_input(calc, bad_schedule):
    with pytest.raises(TypeError):
        list(calc.calculate(bad_schedule))
    with pytest.raises(TypeError):
        calc.compute(bad_schedule)

# Building metrics from an iterable rejects too many values.
def test_from_iterable_rejects_too_many_values():
    with pytest.raises(ValueError):
        ScheduleMetrics.from_iterable(iter([1.0, 2.0, 3.0, 4.0, 5.0, 6.0]))
        
# Fixture: a hand-built schedule exercising several metrics at once.
@pytest.fixture
def schedule_rich():
    m1 = make_course("S1M1", [("P1", 1, "FALL", "Obligatory")])
    m2 = make_course("S1M2", [("P1", 1, "FALL", "Obligatory")])
    m3 = make_course("S1M3", [("P1", 1, "FALL", "Obligatory")])
    e1 = make_course("S1E1", [("P1", 1, "FALL", "Elective")])
    e2 = make_course("S1E2", [("P1", 1, "FALL", "Elective")])
    e3 = make_course("S1E3", [("P1", 1, "FALL", "Elective")])
    return schedule(
        exam(m1, date(2026, 1, 1)),
        exam(m2, date(2026, 1, 5)),
        exam(m3, date(2026, 1, 12)),
        exam(e1, date(2026, 1, 8)),
        exam(e2, date(2026, 1, 8)),
        exam(e3, date(2026, 1, 19)),
    )

# Fixture: a schedule spanning two program-year groups.
@pytest.fixture
def schedule_two_groups():
    p1a = make_course("S2P1A", [("P1", 1, "FALL", "Obligatory")])
    p1b = make_course("S2P1B", [("P1", 1, "FALL", "Obligatory")])
    p2a = make_course("S2P2A", [("P2", 2, "FALL", "Obligatory")])
    p2b = make_course("S2P2B", [("P2", 2, "FALL", "Obligatory")])
    p2c = make_course("S2P2C", [("P2", 2, "FALL", "Obligatory")])
    return schedule(
        exam(p1a, date(2026, 1, 1)),
        exam(p1b, date(2026, 1, 11)),
        exam(p2a, date(2026, 1, 1)),
        exam(p2b, date(2026, 1, 4)),
        exam(p2c, date(2026, 1, 6)),
    )
    
# Fixture: a schedule where all exams fall on the same day.
@pytest.fixture
def schedule_all_same_day():
    d = date(2026, 1, 1)
    m1 = make_course("S3M1", [("P1", 1, "FALL", "Obligatory")])
    m2 = make_course("S3M2", [("P1", 1, "FALL", "Obligatory")])
    e1 = make_course("S3E1", [("P1", 1, "FALL", "Elective")])
    e2 = make_course("S3E2", [("P1", 1, "FALL", "Elective")])
    e3 = make_course("S3E3", [("P1", 1, "FALL", "Elective")])
    return schedule(exam(m1, d), exam(m2, d), exam(e1, d), exam(e2, d), exam(e3, d))

# Fixture: a schedule containing a single exam.
@pytest.fixture
def schedule_single_exam():
    """S4 (edge case: a single exam) — no pair exists anywhere."""
    return schedule(
        exam(make_course("S4M1", [("P1", 1, "FALL", "Obligatory")]), date(2026, 1, 1))
    )

# Fixture: an empty schedule.
@pytest.fixture
def schedule_empty():
    """S5 (edge case: an empty schedule) — no exams at all."""
    return schedule()

# Metric 3.1: min_gap_mandatory checked against hand-built schedules with known values.
def test_metric_3_1_min_gap_mandatory_across_hand_built_schedules(
    calc, schedule_rich, schedule_two_groups, schedule_all_same_day,
    schedule_single_exam, schedule_empty,
):
    """3.1 - minimum days between two mandatory exams (same program & year)."""
    assert calc.compute(schedule_rich).min_gap_mandatory == 4.0
    assert calc.compute(schedule_two_groups).min_gap_mandatory == 2.0
    assert calc.compute(schedule_all_same_day).min_gap_mandatory == 0.0
    assert calc.compute(schedule_single_exam).min_gap_mandatory == float("inf")
    assert calc.compute(schedule_empty).min_gap_mandatory == float("inf")

# Metric 3.2: avg_gap_all checked against hand-built schedules with known values.
def test_metric_3_2_avg_gap_all_across_hand_built_schedules(
    calc, schedule_rich, schedule_two_groups, schedule_all_same_day,
    schedule_single_exam, schedule_empty,
):
    """3.2 - average days between exams (mandatory OR elective, same program & year)."""
    assert calc.compute(schedule_rich).avg_gap_all == pytest.approx(7.4)
    assert calc.compute(schedule_two_groups).avg_gap_all == pytest.approx(5.0)
    assert calc.compute(schedule_all_same_day).avg_gap_all == pytest.approx(0.0)
    assert calc.compute(schedule_single_exam).avg_gap_all == pytest.approx(0.0)
    assert calc.compute(schedule_empty).avg_gap_all == pytest.approx(0.0)

# Metric 3.3: elective_conflicts checked against hand-built schedules with known values.
def test_metric_3_3_elective_conflicts_across_hand_built_schedules(
    calc, schedule_rich, schedule_two_groups, schedule_all_same_day, schedule_single_exam,
):
    """3.3 - collisions between two elective courses in the same program (same day)."""
    assert calc.compute(schedule_rich).elective_conflicts == 1.0
    # empty-electives edge case: a schedule with no electives at all -> 0.
    assert calc.compute(schedule_two_groups).elective_conflicts == 0.0
    assert calc.compute(schedule_all_same_day).elective_conflicts == 3.0
    assert calc.compute(schedule_single_exam).elective_conflicts == 0.0

# Metric 3.4: mandatory_span checked against hand-built schedules with known values.
def test_metric_3_4_mandatory_span_across_hand_built_schedules(
    calc, schedule_rich, schedule_two_groups, schedule_all_same_day,
    schedule_single_exam, schedule_empty,
):
    """3.4 - span (days) between first & last mandatory exam (same program & year)."""
    assert calc.compute(schedule_rich).mandatory_span == 11.0
    assert calc.compute(schedule_two_groups).mandatory_span == 5.0
    assert calc.compute(schedule_all_same_day).mandatory_span == 0.0
    assert calc.compute(schedule_single_exam).mandatory_span == float("inf")
    assert calc.compute(schedule_empty).mandatory_span == float("inf")

# Metric 3.5: max_exams_per_day checked against hand-built schedules with known values.
def test_metric_3_5_max_exams_per_day_across_hand_built_schedules(
    calc, schedule_rich, schedule_two_groups, schedule_all_same_day,
    schedule_single_exam, schedule_empty,
):
    """3.5 - maximum number of exams scheduled on a single day."""
    assert calc.compute(schedule_rich).max_exams_per_day == 2.0
    assert calc.compute(schedule_two_groups).max_exams_per_day == 2.0
    assert calc.compute(schedule_all_same_day).max_exams_per_day == 5.0
    assert calc.compute(schedule_single_exam).max_exams_per_day == 1.0
    assert calc.compute(schedule_empty).max_exams_per_day == 0.0