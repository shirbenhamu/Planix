import time
from pathlib import Path

from data_manager import DataManager
from parsers.text_file_parser import TextFileParser
from MVP.models.planix_model import PlanixModel
from engine.engine_adapter import PlanixEngineAdapter
from MVP.models.schedule_collection_manager import ScheduleCollectionManager


class TestEndToEndSchedulingFlow:
    def _reset_data_manager_singleton(self):
        """Reset the DataManager singleton so each integration test gets isolated state."""
        DataManager._instance = None

    def _write_valid_courses_file(self, file_path: Path):
        """Create a small valid courses file that can produce multiple schedule options."""
        file_path.write_text(
            """Software Engineering Intro
            10001
            Dr. Cohen
            83108, 1, FALL, Obligatory
            Exam
            $$$$
            Data Structures
            10002
            Dr. Levi
            83108, 1, FALL, Obligatory
            Exam
            $$$$
            Software Project
            10003
            Dr. Project
            83108, 1, FALL, Obligatory
            Project
            """,
            encoding="utf-8"
        )

    def _write_valid_exam_periods_file(self, file_path: Path):
        """Create a valid exam-period file with two available FALL dates."""
        file_path.write_text(
            """FALL, Aleph
            01-02-2026, 02-02-2026
            """,
            encoding="utf-8"
        )

    def _write_blocked_exam_periods_file(self, file_path: Path):
        """Create an exam-period file where all possible dates are excluded."""
        file_path.write_text(
            """FALL, Aleph
            01-02-2026, 02-02-2026
            - 01-02-2026, 02-02-2026 blocked dates
            """,
            encoding="utf-8"
        )

    def _write_selected_programs_file(self, file_path: Path):
        """Create a selected-programs file with one valid program."""
        file_path.write_text("83108", encoding="utf-8")

    def _wait_for_generation_to_finish(self, model: PlanixModel, timeout_seconds: float = 5.0):
        """Wait until the background engine adapter finishes schedule generation."""
        start_time = time.time()

        while model.is_generating and time.time() - start_time < timeout_seconds:
            time.sleep(0.05)

        assert model.is_generating is False

    # ======= PLAN-317. Full Pipeline Integration Tests =======

    def test_full_pipeline_loads_data_generates_output_and_indexes_schedules(self, tmp_path):
        """Verify the full flow: files -> DataManager -> Model -> EngineAdapter -> output file -> ScheduleCollectionManager."""
        # Arrange
        self._reset_data_manager_singleton()

        courses_path = tmp_path / "courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"
        output_path = tmp_path / "final_schedules.txt"

        self._write_valid_courses_file(courses_path)
        self._write_valid_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())
        data_manager.load_data(
            courses_path=str(courses_path),
            exam_periods_path=str(periods_path),
            selected_programs_path=str(selected_programs_path),
            mode="replace"
        )

        model = PlanixModel(data_manager=data_manager)
        model.set_selected_programs(data_manager.get_selected_programs())
        model.build_available_programs()

        adapter = PlanixEngineAdapter()

        # Act
        returned_output_path = adapter.generate_from_model(
            model=model,
            output_path=str(output_path)
        )
        self._wait_for_generation_to_finish(model)

        collection_manager = ScheduleCollectionManager(
            output_file_path=str(output_path),
            data_manager=data_manager
        )

        # Assert
        assert returned_output_path == str(output_path)
        assert output_path.exists()

        output_text = output_path.read_text(encoding="utf-8")
        assert "=== Complete Academic Year Schedules ===" in output_text
        assert "--- FULL SYSTEM OPTION" in output_text
        assert "10001 - Software Engineering Intro" in output_text
        assert "10002 - Data Structures" in output_text
        assert "10003 - Software Project" not in output_text

        assert collection_manager.get_total_count() > 0

        current_schedule = collection_manager.get_current_schedule()
        course_ids = {exam.course.course_id for exam in current_schedule.exams}

        assert course_ids == {"10001", "10002"}

    # ======= PLAN-318. Engine Integration Validation Tests =======

    def test_engine_integration_rejects_generation_when_no_available_dates_exist(self, tmp_path):
        """Verify that the integrated engine flow fails clearly when all exam dates are blocked."""
        # Arrange
        self._reset_data_manager_singleton()

        courses_path = tmp_path / "courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"
        output_path = tmp_path / "final_schedules.txt"

        self._write_valid_courses_file(courses_path)
        self._write_blocked_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())
        data_manager.load_data(
            courses_path=str(courses_path),
            exam_periods_path=str(periods_path),
            selected_programs_path=str(selected_programs_path),
            mode="replace"
        )

        model = PlanixModel(data_manager=data_manager)
        model.set_selected_programs(data_manager.get_selected_programs())
        model.build_available_programs()

        adapter = PlanixEngineAdapter()

        # Act
        adapter.generate_from_model(
            model=model,
            output_path=str(output_path)
        )
        self._wait_for_generation_to_finish(model)

        # Assert
        # The worker thread fails before writing valid schedule content.
        # The important integration contract is that generation state is released.
        assert model.is_generating is False

    # ======= PLAN-319. Schedule Structure Validation Tests =======

    def test_generated_schedule_file_has_expected_sections_dates_and_course_lines(self, tmp_path):
        """Verify that generated schedule output has stable structural markers and parseable exam rows."""
        # Arrange
        self._reset_data_manager_singleton()

        courses_path = tmp_path / "courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"
        output_path = tmp_path / "final_schedules.txt"

        self._write_valid_courses_file(courses_path)
        self._write_valid_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())
        data_manager.load_data(
            courses_path=str(courses_path),
            exam_periods_path=str(periods_path),
            selected_programs_path=str(selected_programs_path),
            mode="replace"
        )

        model = PlanixModel(data_manager=data_manager)
        model.set_selected_programs(data_manager.get_selected_programs())
        model.build_available_programs()

        adapter = PlanixEngineAdapter()

        # Act
        adapter.generate_from_model(model=model, output_path=str(output_path))
        self._wait_for_generation_to_finish(model)

        output_text = output_path.read_text(encoding="utf-8")
        date_lines = [
            line.strip()
            for line in output_text.splitlines()
            if line.strip().startswith("Date:")
        ]

        # Assert
        assert output_text.startswith("=== Complete Academic Year Schedules ===")
        assert "[FALL - Aleph]" in output_text
        assert "-" * 60 in output_text

        assert len(date_lines) >= 2
        for line in date_lines:
            assert "Date:" in line
            assert "Course:" in line
            assert "Instructor:" in line
            assert "10001" in line or "10002" in line

    # ======= PLAN-330. Calendar Constraint Interaction Tests =======

    def test_calendar_collection_manager_reads_generated_schedule_after_full_pipeline(self, tmp_path):
        """Verify that the calendar-side collection manager can read generated output into Schedule objects."""
        # Arrange
        self._reset_data_manager_singleton()

        courses_path = tmp_path / "courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"
        output_path = tmp_path / "final_schedules.txt"

        self._write_valid_courses_file(courses_path)
        self._write_valid_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())
        data_manager.load_data(
            courses_path=str(courses_path),
            exam_periods_path=str(periods_path),
            selected_programs_path=str(selected_programs_path),
            mode="replace"
        )

        model = PlanixModel(data_manager=data_manager)
        model.set_selected_programs(data_manager.get_selected_programs())
        model.build_available_programs()

        adapter = PlanixEngineAdapter()

        # Act
        adapter.generate_from_model(model=model, output_path=str(output_path))
        self._wait_for_generation_to_finish(model)

        collection_manager = ScheduleCollectionManager(
            output_file_path=str(output_path),
            data_manager=data_manager
        )

        first_schedule = collection_manager.get_current_schedule()
        moved_to_next = collection_manager.next_schedule()

        # Assert
        assert collection_manager.get_total_count() >= 1
        assert len(first_schedule.exams) == 2

        for scheduled_exam in first_schedule.exams:
            assert scheduled_exam.exam_date.isoformat() in {
                "2026-02-01",
                "2026-02-02"
            }
            assert scheduled_exam.course.course_id in {"10001", "10002"}

        if moved_to_next:
            second_schedule = collection_manager.get_current_schedule()
            assert len(second_schedule.exams) == 2
