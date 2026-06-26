import multiprocessing
import os
import time
import pytest
import psutil
import time
from datetime import date, timedelta
from src.engine.scheduling_constraints import SchedulingConstraints
from src.metrics.metrics_calculator import METRIC_KEYS, METRICS_LINE_PREFIX, is_metrics_line, parse_metrics_line
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.data_manager import DataManager
from src.parsers.base_parser import BaseParser
from src.MVP.models.exam_period import ExamPeriod

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _StubModel:
    """A minimal mock satisfying the contract for generate_from_model."""
    def __init__(self, data_manager, selected_programs, constraints):
        self.data_manager = data_manager
        self._selected_programs = list(selected_programs)
        self.constraints = constraints
        self.is_generating = False

    def get_selected_programs(self):
        return self._selected_programs

class _DummyParser(BaseParser):
    """Minimal parser to inject static test data into the DataManager."""
    def __init__(self, courses, periods, programs):
        self._courses = courses
        self._periods = periods
        self._programs = programs

    def parse_courses(self, file_path): return self._courses
    def parse_exam_periods(self, file_path): return self._periods
    def parse_selected_programs(self, file_path): return self._programs


def _make_course(cid, req="Obligatory", program="83101"):
    """Helper to generate a Course object for testing."""
    return Course(
        course_id=cid,
        course_name=f"Course {cid}",
        instructor="Dr. Test",
        evaluation_method="Exam",
        program_info=[ProgramCourseInfo(program, 1, "FALL", req)],
    )

def _small_dataset():
    """A tiny dataset: 3 courses in one program, one FALL exam period, for rapid integration testing."""
    c1 = _make_course("10001", "Obligatory")
    c2 = _make_course("10002", "Obligatory")
    c3 = _make_course("10003", "Elective")

    # One 14-day FALL/A exam period. semester must match the courses' "FALL"
    # so the scheduler can pair courses with available dates.
    exam_periods = [
        ExamPeriod(
            semester="FALL",
            moed="A",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 14),
            excluded_dates=[],
        )
    ]

    courses = [c1, c2, c3]
    programs = ["83101"]
    return courses, exam_periods, programs


def _run_adapter(output_path, constraints, timeout=60):
    """
    Invokes the PlanixEngineAdapter and waits for the worker to finish.
    Raises TimeoutError if generation exceeds the specified timeout.
    """
    try:
        from src.engine.engine_adapter import PlanixEngineAdapter
    except ImportError:
        pytest.skip("PlanixEngineAdapter not available in this build")

    courses, exam_periods, programs = _small_dataset()

    # Initialize DataManager with mock data
    DataManager._instance = None
    dm = DataManager(parser=_DummyParser(courses, exam_periods, programs))
    dm.courses = {c.course_id: c for c in courses}
    dm.exam_periods = exam_periods
    dm.selected_programs = list(programs)

    model = _StubModel(dm, programs, constraints)

    adapter = PlanixEngineAdapter()
    adapter.generate_from_model(model=model, output_path=str(output_path))

    # Wait for the background worker to complete.
    deadline = time.monotonic() + timeout
    while adapter.is_generation_active():
        if time.monotonic() > deadline:
            raise TimeoutError("Worker did not finish within the timeout period.")
        time.sleep(0.2)

    proc = getattr(adapter, "_worker_process", None)
    proc = getattr(adapter, "_worker_process", None)
    if proc is not None:
        proc.join(timeout=5)   # Ensure cleanup
    return proc


# ---------------------------------------------------------------------------
# Output file structure with constraints
# ---------------------------------------------------------------------------

class TestAdapterOutputStructure:

    def test_output_contains_schedule_blocks_with_metrics(self, tmp_path):
        """Verifies that every schedule block is followed by a valid METRICS line."""
        output = tmp_path / "schedules.txt"
        constraints = SchedulingConstraints(
            min_days_mandatory_enabled=True, min_days_mandatory_k=2,
            max_exams_per_day_enabled=True, max_exams_per_day_k=2,
        )
        _run_adapter(output, constraints)

        assert output.exists(), "adapter must create the output file"
        content = output.read_text(encoding="utf-8")

        header_count = content.count("--- FULL SYSTEM OPTION")
        metrics_count = content.count(METRICS_LINE_PREFIX + "|")

        assert header_count > 0, "output must contain at least one schedule block"
        assert metrics_count == header_count, (
            "every schedule block must be followed by exactly one METRICS| line; "
            f"found {header_count} blocks but {metrics_count} METRICS lines"
        )

    def test_metrics_lines_are_parseable_and_sane(self, tmp_path):
        """Verifies metrics lines are correctly formatted and contain valid numerical values."""
        output = tmp_path / "schedules.txt"
        constraints = SchedulingConstraints(
            min_days_mandatory_enabled=True, min_days_mandatory_k=1,
        )
        _run_adapter(output, constraints)

        for line in output.read_text(encoding="utf-8").splitlines():
            if not is_metrics_line(line):
                continue
            parsed = parse_metrics_line(line)
            assert len(parsed.as_tuple()) == len(METRIC_KEYS)
            for val in parsed.as_tuple():
                assert val >= 0.0 or val == float("inf"), (
                    f"metric value {val!r} should be non-negative or +inf"
                )

    def test_constraints_actually_filter_schedules(self, tmp_path):
        """Verifies that applying constraints reduces or maintains the number of generated schedules."""
        output_unconstrained = tmp_path / "unconstrained.txt"
        output_constrained = tmp_path / "constrained.txt"

        _run_adapter(output_unconstrained, SchedulingConstraints())
        _run_adapter(
            output_constrained,
            SchedulingConstraints(
                min_days_mandatory_enabled=True,
                min_days_mandatory_k=5,   # aggressive: >=5 days between mandatory exams
            ),
        )
        
        def _count_blocks(path):
            return path.read_text(encoding="utf-8").count("--- FULL SYSTEM OPTION")
        unconstrained_count = _count_blocks(output_unconstrained)
        constrained_count = _count_blocks(output_constrained)

        # Tighter constraints should produce ≤ schedules than no constraints.
        assert constrained_count <= unconstrained_count, (
            "adding a constraint must not increase the number of valid schedules"
        )

    def test_output_is_readable_by_collection_manager(self, tmp_path):
        """Verifies that the generated output can be successfully ingested by ScheduleCollectionManager."""
        output = tmp_path / "schedules.txt"
        _run_adapter(output, SchedulingConstraints())

        courses, _, _ = _small_dataset()

        class _P(BaseParser):
            def parse_courses(self, f): return []
            def parse_exam_periods(self, f): return []
            def parse_selected_programs(self, f): return []

        dm = DataManager(parser=_P())
        dm.courses = {c.course_id: c for c in courses}

        manager = ScheduleCollectionManager(str(output), dm)
        total = manager.get_total_count()
        assert total > 0, "ScheduleCollectionManager must find at least one schedule"

        # Verify at least the first schedule materializes without error.
        first = manager.get_current_schedule()
        assert first is not None
        assert len(first.exams) > 0


# ---------------------------------------------------------------------------
# Worker terminates cleanly with no orphan processes
# ---------------------------------------------------------------------------

class TestWorkerCleanTermination:

    def test_worker_pid_not_alive_after_generation(self, tmp_path):
        """Verifies the worker process terminates upon completion."""
        output = tmp_path / "schedules.txt"
        proc = _run_adapter(output, SchedulingConstraints())

        if proc is None:
            pytest.skip("adapter did not expose its worker process")

        assert not proc.is_alive(), (
            f"Worker (pid={proc.pid}) is still alive after generation completed"
        )
        assert proc.exitcode is not None, "worker did not terminate with an exit code"

    def test_no_new_processes_linger_after_generation(self, tmp_path):
        """Verifies that no subprocesses are leaked after the operation."""
        output = tmp_path / "schedules.txt"

        before = len(multiprocessing.active_children())
        _run_adapter(output, SchedulingConstraints())
        time.sleep(1.0)   # let the OS clean up
        after = len(multiprocessing.active_children())

        assert after <= before, (
            f"Found {after - before} more active child process(es) after generation "
            "than before — possible subprocess leak."
        )