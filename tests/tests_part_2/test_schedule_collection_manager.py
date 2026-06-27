from datetime import date
from pathlib import Path

import pytest

from src.data_manager import DataManager
from src.MVP.models.course import Course, ProgramCourseInfo
from src.MVP.models.schedule import Schedule
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.parsers.base_parser import BaseParser
from unittest.mock import MagicMock

class DummyParser(BaseParser):
    def parse_courses(self, file_path):
        return []

    def parse_exam_periods(self, file_path):
        return []

    def parse_selected_programs(self, file_path):
        return []


def reset_data_manager_singleton():
    DataManager._instance = None


def create_course(course_id, course_name):
    info = ProgramCourseInfo(
        program_id="83108",
        year=1,
        semester="FALL",
        requirement="Obligatory",
    )

    return Course(
        course_id=course_id,
        course_name=course_name,
        instructor="Teacher",
        evaluation_method="Exam",
        program_info=[info],
    )


def create_data_manager_with_courses(courses):
    reset_data_manager_singleton()
    data_manager = DataManager(DummyParser())
    data_manager.courses = {course.course_id: course for course in courses}
    return data_manager


def write_schedule_file(tmp_path, content):
    output_file = tmp_path / "schedules.txt"
    output_file.write_text(content, encoding="utf-8")
    return output_file


def schedule_block(option_number, course_id, course_name, exam_date, instructor="Teacher"):
    return (
        f"--- FULL SYSTEM OPTION {option_number} ---\n"
        f"Date: {exam_date} | Course: {course_id} - {course_name} | Instructor: {instructor}\n"
        "------------------------------------------------------------\n"
    )


def test_manager_counts_schedules_from_output_file(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + schedule_block(2, "10002", "Course 2", "02-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    assert manager.get_total_count() == 2
    assert manager.get_current_index() == 0


def test_manager_reads_current_schedule_as_schedule_object(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    schedule = manager.get_current_schedule()

    assert isinstance(schedule, Schedule)
    assert len(schedule.exams) == 1
    assert schedule.exams[0].course.course_id == "10001"
    assert schedule.exams[0].course.course_name == "Course 1"
    assert schedule.exams[0].exam_date == date(2026, 2, 1)


def test_next_and_previous_schedule_navigation_respects_bounds(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + schedule_block(2, "10002", "Course 2", "02-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    assert manager.get_current_index() == 0
    assert manager.next_schedule() is True
    assert manager.get_current_index() == 1
    assert manager.next_schedule() is False
    assert manager.get_current_index() == 1

    assert manager.prev_schedule() is True
    assert manager.get_current_index() == 0
    assert manager.prev_schedule() is False
    assert manager.get_current_index() == 0


def test_jump_to_schedule_accepts_valid_index_and_rejects_invalid_index(tmp_path):
    courses = [
        create_course("10001", "Course 1"),
        create_course("10002", "Course 2"),
        create_course("10003", "Course 3"),
    ]
    data_manager = create_data_manager_with_courses(courses)

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + schedule_block(2, "10002", "Course 2", "02-02-2026")
        + schedule_block(3, "10003", "Course 3", "03-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    assert manager.jump_to_schedule(2) is True
    assert manager.get_current_index() == 2

    assert manager.jump_to_schedule(3) is False
    assert manager.get_current_index() == 2

    assert manager.jump_to_schedule(-1) is False
    assert manager.get_current_index() == 2


def test_jump_to_schedule_rejects_non_integer_index(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    with pytest.raises(TypeError, match="index must be an integer"):
        manager.jump_to_schedule("1")


def test_get_current_schedule_raises_when_no_schedules_exist(tmp_path):
    data_manager = create_data_manager_with_courses([])
    output_file = write_schedule_file(tmp_path, "")

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    with pytest.raises(ValueError, match="No schedules are available"):
        manager.get_current_schedule()


def test_manager_detects_new_schedules_after_file_is_appended(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    assert manager.get_total_count() == 1

    with output_file.open("a", encoding="utf-8") as file:
        file.write(schedule_block(2, "10002", "Course 2", "02-02-2026"))

    assert manager.get_total_count() == 2
    assert manager.next_schedule() is True
    assert manager.get_current_schedule().exams[0].course.course_id == "10002"


def test_clear_cache_resets_navigation_and_rebuilds_index(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + schedule_block(2, "10002", "Course 2", "02-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    manager.jump_to_schedule(1)

    manager.clear_cache()

    assert manager.get_current_index() == 0
    assert manager.get_total_count() == 2


def test_incomplete_schedule_block_raises_value_error(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    output_file = write_schedule_file(
        tmp_path,
        "--- FULL SYSTEM OPTION 1 ---\n"
        "Date: 01-02-2026 | Course: 10001 - Course 1 | Instructor: Teacher\n",
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    with pytest.raises(ValueError, match="still being written"):
        manager.get_current_schedule()


def test_unknown_course_id_renders_from_schedule_block(tmp_path):
    """PLAN-594: a course missing from the loaded data must NOT blank the board.

    The schedule file is self-describing (it carries the course id + name), so a
    course the data manager no longer knows about is synthesized from the block
    itself rather than raising and sinking the whole schedule into an empty
    "no schedules" state.
    """
    data_manager = create_data_manager_with_courses([])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "99999", "Unknown Course", "01-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    schedule = manager.get_current_schedule()

    assert len(schedule.exams) == 1
    exam = schedule.exams[0]
    assert exam.course.course_id == "99999"
    assert exam.course.course_name == "Unknown Course"


def test_constructor_rejects_invalid_output_file_path():
    data_manager = create_data_manager_with_courses([])

    with pytest.raises(TypeError, match="output_file_path must be a string"):
        ScheduleCollectionManager(None, data_manager)

    with pytest.raises(ValueError, match="output_file_path cannot be empty"):
        ScheduleCollectionManager("   ", data_manager)


def test_constructor_rejects_invalid_data_manager(tmp_path):
    output_file = tmp_path / "schedules.txt"
    output_file.write_text("", encoding="utf-8")

    with pytest.raises(TypeError, match="data_manager must be a DataManager instance"):
        ScheduleCollectionManager(str(output_file), object())
        
def test_build_index_does_nothing_when_snapshot_mode_is_enabled(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    assert manager.get_total_count() == 1

    manager.snapshot_mode = True

    with output_file.open("a", encoding="utf-8") as file:
        file.write(schedule_block(2, "10001", "Course 1", "02-02-2026"))

    assert manager.get_total_count() == 1


def test_build_index_handles_missing_output_file(tmp_path):
    data_manager = create_data_manager_with_courses([])
    missing_file = tmp_path / "missing_schedules.txt"

    manager = ScheduleCollectionManager(str(missing_file), data_manager)

    assert manager.get_total_count() == 0
    assert manager.total_schedules == 0
    assert manager.get_current_index() == 0


def test_build_index_resets_when_output_file_is_truncated(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + schedule_block(2, "10002", "Course 2", "02-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    assert manager.get_total_count() == 2

    output_file.write_text(
        schedule_block(1, "10001", "Course 1", "03-02-2026"),
        encoding="utf-8",
    )

    assert manager.get_total_count() == 1
    assert manager.get_current_index() == 0

    schedule = manager.get_current_schedule()
    assert schedule.exams[0].course.course_id == "10001"
    assert schedule.exams[0].exam_date == date(2026, 2, 3)


def test_current_index_is_clamped_when_file_shrinks(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + schedule_block(2, "10002", "Course 2", "02-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    assert manager.jump_to_schedule(1) is True

    output_file.write_text(
        schedule_block(1, "10001", "Course 1", "01-02-2026"),
        encoding="utf-8",
    )

    assert manager.get_total_count() == 1
    assert manager.get_current_index() == 0


def test_get_current_schedule_clamps_invalid_internal_index(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    manager._current_index = 5

    schedule = manager.get_current_schedule()

    assert manager.get_current_index() == 0
    assert schedule.exams[0].course.course_id == "10001"
    assert schedule.exams[0].exam_date == date(2026, 2, 1)


def test_parse_schedule_block_ignores_malformed_date_lines_but_uses_valid_exam(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    output_file = write_schedule_file(
        tmp_path,
        "--- FULL SYSTEM OPTION 1 ---\n"
        "Date: malformed line that should be ignored\n"
        "Date: 01-02-2026 | Course: 10001 - Course 1 | Instructor: Teacher\n"
        "------------------------------------------------------------\n",
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    schedule = manager.get_current_schedule()

    assert len(schedule.exams) == 1
    assert schedule.exams[0].course.course_id == "10001"
    assert schedule.exams[0].exam_date == date(2026, 2, 1)


def test_parse_schedule_block_raises_when_all_date_lines_are_malformed(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    output_file = write_schedule_file(
        tmp_path,
        "--- FULL SYSTEM OPTION 1 ---\n"
        "Date: malformed line without course information\n"
        "------------------------------------------------------------\n",
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    with pytest.raises(ValueError, match="does not contain any exams"):
        manager.get_current_schedule()


def test_resolve_course_uses_cached_lookup_after_first_resolution(tmp_path):
    course = create_course("10001", "Course 1")
    data_manager = create_data_manager_with_courses([course])

    original_get_courses = data_manager.get_courses
    data_manager.get_courses = MagicMock(wraps=original_get_courses)

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + "Date: 02-02-2026 | Course: 10001 - Course 1 | Instructor: Teacher\n"
        "------------------------------------------------------------\n",
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    data_manager.get_courses.reset_mock()

    schedule = manager.get_current_schedule()

    assert len(schedule.exams) == 2
    assert schedule.exams[0].course.course_id == "10001"
    assert schedule.exams[1].course.course_id == "10001"
    assert data_manager.get_courses.call_count == 1


def test_build_snapshot_index_handles_missing_output_file(tmp_path):
    data_manager = create_data_manager_with_courses([])
    missing_file = tmp_path / "missing_snapshot.txt"

    manager = ScheduleCollectionManager(str(missing_file), data_manager)

    manager.build_snapshot_index()

    assert manager.snapshot_mode is True
    assert manager.total_schedules == 0
    assert manager.get_current_index() == 0


def test_build_snapshot_index_reads_new_headers_while_snapshot_mode_is_active(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)

    with output_file.open("a", encoding="utf-8") as file:
        file.write(schedule_block(2, "10002", "Course 2", "02-02-2026"))

    manager.build_snapshot_index()

    assert manager.snapshot_mode is True
    assert manager.total_schedules == 2
    assert manager.jump_to_schedule(1) is True
    assert manager.get_current_schedule().exams[0].course.course_id == "10002"


def test_build_snapshot_index_resets_when_file_is_replaced_with_smaller_file(tmp_path):
    course1 = create_course("10001", "Course 1")
    course2 = create_course("10002", "Course 2")
    data_manager = create_data_manager_with_courses([course1, course2])

    output_file = write_schedule_file(
        tmp_path,
        schedule_block(1, "10001", "Course 1", "01-02-2026")
        + schedule_block(2, "10002", "Course 2", "02-02-2026"),
    )

    manager = ScheduleCollectionManager(str(output_file), data_manager)
    assert manager.get_total_count() == 2

    output_file.write_text(
        schedule_block(1, "10001", "Course 1", "03-02-2026"),
        encoding="utf-8",
    )

    manager.build_snapshot_index()

    assert manager.snapshot_mode is True
    assert manager.total_schedules == 1
    assert manager.get_current_index() == 0
    assert manager.get_current_schedule().exams[0].exam_date == date(2026, 2, 3)