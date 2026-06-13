import math
from datetime import date

import pytest

from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule, ScheduledExam
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.metrics.metrics_calculator import (
    METRIC_KEYS,
    METRICS_LINE_PREFIX,
    MetricsCalculator,
    ScheduleMetrics,
    format_metrics_line,
    is_metrics_line,
    parse_metrics_line,
)
from src.output.file_output_writer import FileOutputWriter
from src.parsers.base_parser import BaseParser


# --- wire-format round trip (PLAN-487) --------------------------------------
def test_format_line_shape_floats_then_ints():
    m = ScheduleMetrics(5.0, 3.3333333333333335, 2.0, 9.0, 3.0)
    line = format_metrics_line(m)
    assert line.startswith(METRICS_LINE_PREFIX + "|")
    parts = line.split("|")[1:]
    assert len(parts) == 5
    # positions 1-3 are floats, positions 4-5 are ints
    assert parts == ["5.0", "3.3333333333333335", "2.0", "9", "3"]


def test_format_parse_round_trip_exact():
    m = ScheduleMetrics(5.0, 3.3333333333333335, 2.0, 9.0, 3.0)
    assert parse_metrics_line(format_metrics_line(m)).as_tuple() == m.as_tuple()


def test_round_trip_handles_infinity():
    m = ScheduleMetrics(float("inf"), 0.0, 0.0, float("inf"), 0.0)
    line = format_metrics_line(m)
    parsed = parse_metrics_line(line)
    assert math.isinf(parsed.min_gap_mandatory)
    assert math.isinf(parsed.mandatory_span)


def test_parse_rejects_non_metrics_line():
    assert not is_metrics_line("--- FULL SYSTEM OPTION 1 ---")
    with pytest.raises(ValueError):
        parse_metrics_line("Date: 01-01-2026 | Course: x")


def test_parse_rejects_wrong_field_count():
    with pytest.raises(ValueError):
        parse_metrics_line("METRICS|1.0|2.0|3.0")


# --- writer integration (PLAN-486 / PLAN-488) -------------------------------
@pytest.fixture
def sample_courses():
    info = [ProgramCourseInfo(program_id="83108", year=1, semester="FALL", requirement="Obligatory")]
    c1 = Course("83102", "Physics 1", "Prof. O. Some", "Exam", info)
    c2 = Course("83112", "Calculus 1", "Prof. Erez Scheiner", "Exam", info)
    return c1, c2


def test_every_block_followed_by_exactly_one_metrics_line(tmp_path, sample_courses):
    c1, c2 = sample_courses
    writer = FileOutputWriter()
    output_file = tmp_path / "out" / "schedules.txt"

    fall = Schedule(exams=[
        ScheduledExam(course=c1, exam_date=date(2026, 2, 1)),
        ScheduledExam(course=c2, exam_date=date(2026, 2, 6)),
    ])
    writer.write_schedules({("FALL", "Aleph"): iter([fall])}, str(output_file))

    content = output_file.read_text(encoding="utf-8")
    header_count = content.count("--- FULL SYSTEM OPTION")
    metrics_count = content.count(METRICS_LINE_PREFIX + "|")
    assert header_count == 1
    # exactly one METRICS line per block
    assert metrics_count == header_count


def test_metrics_line_values_match_calculator(tmp_path, sample_courses):
    c1, c2 = sample_courses
    writer = FileOutputWriter()
    output_file = tmp_path / "out" / "schedules.txt"

    fall = Schedule(exams=[
        ScheduledExam(course=c1, exam_date=date(2026, 2, 1)),
        ScheduledExam(course=c2, exam_date=date(2026, 2, 6)),
    ])
    writer.write_schedules({("FALL", "Aleph"): iter([fall])}, str(output_file))

    metrics_line = next(
        line for line in output_file.read_text(encoding="utf-8").splitlines()
        if is_metrics_line(line)
    )
    parsed = parse_metrics_line(metrics_line)

    expected = MetricsCalculator().compute(fall)
    assert parsed.as_tuple() == expected.as_tuple()
    # two mandatory exams 5 days apart, same program/year
    assert parsed.min_gap_mandatory == 5.0
    assert parsed.max_exams_per_day == 1.0


def test_schedule_body_format_unchanged(tmp_path, sample_courses):
    # PLAN-488: the schedule body (header, Date: lines, separator) is intact.
    c1, c2 = sample_courses
    writer = FileOutputWriter()
    output_file = tmp_path / "out" / "schedules.txt"

    fall = Schedule(exams=[
        ScheduledExam(course=c1, exam_date=date(2026, 2, 1)),
        ScheduledExam(course=c2, exam_date=date(2026, 2, 6)),
    ])
    writer.write_schedules({("FALL", "Aleph"): iter([fall])}, str(output_file))

    content = output_file.read_text(encoding="utf-8")
    assert "=== Complete Academic Year Schedules ===" in content
    assert "--- FULL SYSTEM OPTION 1 ---" in content
    assert "Date: 01-02-2026 | Course: 83102 - Physics 1 | Instructor: Prof. O. Some" in content
    assert "-" * 60 in content
    # METRICS sits before the separator, after the exam body
    body, _, after = content.partition("METRICS|")
    assert "Date: 06-02-2026" in body
    assert after.lstrip().startswith("\n") or after.startswith("\n") or "\n" in after


# --- collection manager still parses files with METRICS lines ---------------
class _DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []


def test_collection_manager_ignores_metrics_lines(tmp_path, sample_courses):
    c1, c2 = sample_courses
    writer = FileOutputWriter()
    output_file = tmp_path / "out" / "schedules.txt"

    fall = Schedule(exams=[
        ScheduledExam(course=c1, exam_date=date(2026, 2, 1)),
        ScheduledExam(course=c2, exam_date=date(2026, 2, 6)),
    ])
    writer.write_schedules({("FALL", "Aleph"): iter([fall])}, str(output_file))

    dm = DataManager(parser=_DummyParser())
    dm.courses = {c1.course_id: c1, c2.course_id: c2}

    manager = ScheduleCollectionManager(str(output_file), dm)
    assert manager.get_total_count() == 1

    parsed_schedule = manager.get_current_schedule()
    # the METRICS line must not leak into the parsed schedule's exams
    course_ids = sorted(e.course.course_id for e in parsed_schedule.exams)
    assert course_ids == ["83102", "83112"]
