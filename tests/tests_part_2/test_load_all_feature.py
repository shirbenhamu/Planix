"""Foundation tests for the 'Load All' feature.

Covers the two engine/output building blocks:
  * ExamScheduler.count_total_schedules — counts the total valid full-year
    schedules as the product of per-period counts, without materializing them,
    with an optional per-period cap.
  * FileOutputWriter — its per-period cap and runtime timeout are configurable,
    and passing None for each streams every valid schedule with no limit
    (the mode 'Load All' uses).
"""

import itertools
from datetime import date
from multiprocessing import Queue, Value

from src.engine.exam_scheduler import ExamScheduler
from src.engine.engine_adapter import PlanixEngineAdapter
from src.engine.scheduling_constraints import SchedulingConstraints
from src.metrics.metrics_calculator import MetricsCalculator
from src.output.file_output_writer import FileOutputWriter
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.exam_period import ExamPeriod
from src.MVP.models.schedule import Schedule


PROGRAM = "83108"


def _course(course_id, requirement="Obligatory"):
    info = [ProgramCourseInfo(program_id=PROGRAM, year=1, semester="FALL", requirement=requirement)]
    return Course(course_id, f"C{course_id}", "Teacher", "Exam", info)


def _period(num_days=4):
    return ExamPeriod(
        semester="FALL",
        moed="Aleph",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, num_days),
        excluded_dates=[],
    )


def _brute_force_total(scheduler, courses, periods):
    """Materialize every full-year combination and count them (ground truth)."""
    generators = scheduler.generate_schedules(courses, periods, [PROGRAM])
    materialized = [list(gen) for gen in generators.values()]
    return sum(1 for _ in itertools.product(*materialized))


def test_count_total_matches_brute_force_enumeration():
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=4)]

    expected = _brute_force_total(scheduler, courses, periods)
    counted = scheduler.count_total_schedules(courses, periods, [PROGRAM])

    assert counted == expected
    assert counted > 0


def test_count_total_respects_per_period_cap():
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=6)]  # plenty of combinations

    uncapped = scheduler.count_total_schedules(courses, periods, [PROGRAM])
    capped = scheduler.count_total_schedules(courses, periods, [PROGRAM], max_per_period=3)

    assert uncapped > 3
    assert capped == 3  # single period -> total equals the per-period cap


def _count_options(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().count("--- FULL SYSTEM OPTION")


def test_writer_uncapped_writes_every_schedule(tmp_path):
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=5)]

    total = scheduler.count_total_schedules(courses, periods, [PROGRAM])
    assert total > 3  # ensure the cap below is actually meaningful

    out = tmp_path / "all.txt"
    # 'Load All' mode: no per-period cap, no timeout -> writes everything.
    writer = FileOutputWriter(max_time_seconds=None, max_per_period=None)
    writer.write_schedules(
        scheduler.generate_schedules(courses, periods, [PROGRAM]),
        str(out),
    )

    assert _count_options(out) == total


def test_writer_honours_explicit_per_period_cap(tmp_path):
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=5)]

    out = tmp_path / "capped.txt"
    writer = FileOutputWriter(max_time_seconds=None, max_per_period=2)
    writer.write_schedules(
        scheduler.generate_schedules(courses, periods, [PROGRAM]),
        str(out),
    )

    # Single period -> the full-year count equals the per-period cap.
    assert _count_options(out) == 2


# ===== Adapter background workers (in-memory IPC, no temp files) ==========

def test_deep_search_worker_writes_top_n_and_reports_scanned(tmp_path):
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=6)]
    total = scheduler.count_total_schedules(courses, periods, [PROGRAM])

    out = tmp_path / "best.txt"
    scanned_value = Value("q", 0)
    top_n = 3

    PlanixEngineAdapter._deep_search_worker(
        courses, periods, [PROGRAM], SchedulingConstraints(),
        [(1, False)], top_n, 10**9, None, str(out), scanned_value,
    )

    # Only the top-N are written to disk (disk stays bounded).
    assert _count_options(out) == min(top_n, total)
    # The scanned counter (shared memory) ends at the whole space here.
    assert scanned_value.value == total


def test_count_worker_puts_total_on_queue():
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=5)]
    expected = scheduler.count_total_schedules(courses, periods, [PROGRAM])

    q = Queue()
    PlanixEngineAdapter._count_worker(
        courses, periods, [PROGRAM], SchedulingConstraints(), q,
    )

    assert q.get(timeout=2) == expected


def test_read_total_count_drains_queue_then_caches():
    adapter = PlanixEngineAdapter()
    adapter._count_queue = Queue()
    adapter._count_queue.put(12345)

    assert adapter.read_total_count() == 12345
    assert adapter.read_total_count() == 12345  # cached, queue already drained


def test_read_total_count_none_when_no_count_started():
    assert PlanixEngineAdapter().read_total_count() is None


def _sig(schedule):
    return tuple(sorted((e.course.course_id, e.exam_date) for e in schedule.exams))


def _all_keys_sorted(scheduler, courses, periods, sort_spec):
    calc = MetricsCalculator()
    gens = scheduler.generate_schedules(courses, periods, [PROGRAM])
    pools = [list(gens[k]) for k in sorted(gens)]
    keys = []
    for combo in itertools.product(*pools):
        exams = [e for sub in combo for e in sub.exams]
        schedule = Schedule(exams=exams)
        keys.append(scheduler._deep_search_sort_key(calc.compute(schedule).as_tuple(), sort_spec))
    keys.sort()
    return keys


def test_find_best_returns_top_n_in_sorted_order():
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=6)]
    sort_spec = [(1, False)]  # avg_gap_all, descending (higher gap is better)
    top_n = 3

    expected_keys = _all_keys_sorted(scheduler, courses, periods, sort_spec)[:top_n]

    best, scanned = scheduler.find_best_schedules(
        courses, periods, [PROGRAM], sort_spec, top_n=top_n, max_scan=10**9,
    )

    # best is a list of (schedule, metrics) pairs, best-first.
    got_keys = [scheduler._deep_search_sort_key(metrics, sort_spec) for _s, metrics in best]

    assert len(best) == top_n
    assert got_keys == expected_keys          # the actual best, in best-first order
    assert got_keys == sorted(got_keys)        # ordered best-first
    assert scanned == len(_all_keys_sorted(scheduler, courses, periods, sort_spec))


def test_find_best_respects_max_scan_bound():
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=6)]

    best, scanned = scheduler.find_best_schedules(
        courses, periods, [PROGRAM], [(1, False)], top_n=100, max_scan=2,
    )

    assert scanned == 2          # stopped early


def test_find_best_respects_time_budget():
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=6)]

    # 0-second budget, checked after every scan -> stops at the first check.
    _best, scanned = scheduler.find_best_schedules(
        courses, periods, [PROGRAM], [(1, False)], top_n=100,
        max_seconds=0, progress_every=1,
    )

    assert scanned == 1


def test_find_best_respects_cancel_callback():
    scheduler = ExamScheduler()
    courses = [_course("10001"), _course("10002")]
    periods = [_period(num_days=6)]

    best, scanned = scheduler.find_best_schedules(
        courses, periods, [PROGRAM], [(1, False)], top_n=100,
        max_scan=10**9, progress_every=1, cancel_callback=lambda: True,
    )

    assert scanned == 1
    assert len(best) == 1        # kept the one (schedule, metrics) pair it scanned


def test_count_worker_reports_zero_when_no_valid_schedules():
    # No selected program match -> generation raises -> worker reports 0.
    courses = [_course("10001")]
    periods = [_period(num_days=4)]

    q = Queue()
    PlanixEngineAdapter._count_worker(
        courses, periods, ["99999"], SchedulingConstraints(), q,
    )

    assert q.get(timeout=2) == 0
