from src.data_manager import DataManager
from src.parsers.text_file_parser import TextFileParser
from src.MVP.models.planix_model import PlanixModel


class TestCacheAndFilesLoading:
    def _reset_data_manager_singleton(self):
        """Reset the DataManager singleton so each test starts with isolated cache state."""
        DataManager._instance = None

    def _write_courses_file(self, file_path, course_id="10001", course_name="Intro to Software Engineering"):
        """Create a valid courses file with one exam-based course."""
        file_path.write_text(
            f"""{course_name}
            {course_id}
            Dr. Cohen
            83108, 1, FALL, Obligatory
            Exam
            """,
            encoding="utf-8"
        )

    def _write_second_courses_file(self, file_path):
        """Create a second valid courses file for append and replacement scenarios."""
        file_path.write_text(
            """Data Structures
            10002
            Dr. Levi
            83108, 1, FALL, Obligatory
            Exam
            """,
            encoding="utf-8"
        )

    def _write_corrupted_courses_file(self, file_path):
        """Create a corrupted courses file with an invalid evaluation method."""
        file_path.write_text(
            """Broken Course
            99999
            Dr. Error
            83108, 1, FALL, Obligatory
            InvalidEvaluationMethod
            """,
            encoding="utf-8"
        )

    def _write_exam_periods_file(self, file_path):
        """Create a valid exam-periods file."""
        file_path.write_text(
            """FALL, Aleph
            01-02-2026, 05-02-2026
            """,
            encoding="utf-8"
        )

    def _write_selected_programs_file(self, file_path):
        """Create a valid selected-programs file."""
        file_path.write_text("83108", encoding="utf-8")

    def _load_files(self, data_manager, courses_path, periods_path, selected_programs_path, mode="replace"):
        """Load all required input files through DataManager."""
        data_manager.load_data(
            courses_path=str(courses_path),
            exam_periods_path=str(periods_path),
            selected_programs_path=str(selected_programs_path),
            mode=mode
        )

    # ======= PLAN-321. Valid File Upload Verification =======

    def test_valid_file_upload_loads_courses_periods_and_selected_programs(self, tmp_path):
        """Verify that valid input files are parsed and cached correctly inside DataManager."""
        # Arrange
        self._reset_data_manager_singleton()

        courses_path = tmp_path / "courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"

        self._write_courses_file(courses_path)
        self._write_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())

        # Act
        self._load_files(data_manager, courses_path, periods_path, selected_programs_path)

        # Assert
        courses = data_manager.get_courses()
        periods = data_manager.get_exam_periods()
        selected_programs = data_manager.get_selected_programs()

        assert len(courses) == 1
        assert courses[0].course_id == "10001"
        assert courses[0].course_name == "Intro to Software Engineering"

        assert len(periods) == 1
        assert periods[0].semester == "FALL"
        assert periods[0].moed == "Aleph"

        assert selected_programs == ["83108"]

    # ======= PLAN-322. Corrupted File Handling Verification =======

    def test_corrupted_courses_file_raises_error_and_keeps_existing_cache_state(self, tmp_path):
        """Verify that corrupted upload input raises an error without destroying previously loaded cache."""
        # Arrange
        self._reset_data_manager_singleton()

        valid_courses_path = tmp_path / "valid_courses.txt"
        corrupted_courses_path = tmp_path / "corrupted_courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"

        self._write_courses_file(valid_courses_path)
        self._write_corrupted_courses_file(corrupted_courses_path)
        self._write_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())

        self._load_files(data_manager, valid_courses_path, periods_path, selected_programs_path)

        # Act
        try:
            self._load_files(data_manager, corrupted_courses_path, periods_path, selected_programs_path)
            raised_error = None
        except ValueError as error:
            raised_error = error

        # Assert
        assert raised_error is not None
        assert "Invalid evaluation method" in str(raised_error)

        cached_courses = data_manager.get_courses()
        assert len(cached_courses) == 1
        assert cached_courses[0].course_id == "10001"

    # ======= PLAN-323. Full Replacement Mode Verification =======

    def test_replace_mode_clears_previous_courses_before_loading_new_file(self, tmp_path):
        """Verify that replace mode fully replaces the cached course collection."""
        # Arrange
        self._reset_data_manager_singleton()

        first_courses_path = tmp_path / "first_courses.txt"
        second_courses_path = tmp_path / "second_courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"

        self._write_courses_file(first_courses_path, course_id="10001")
        self._write_second_courses_file(second_courses_path)
        self._write_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())

        self._load_files(data_manager, first_courses_path, periods_path, selected_programs_path)

        # Act
        self._load_files(
            data_manager,
            second_courses_path,
            periods_path,
            selected_programs_path,
            mode="replace"
        )

        # Assert
        cached_course_ids = {course.course_id for course in data_manager.get_courses()}

        assert cached_course_ids == {"10002"}
        assert "10001" not in cached_course_ids

    # ======= PLAN-324. Incremental Upload Behavior Verification =======

    def test_append_mode_keeps_previous_courses_and_adds_new_courses(self, tmp_path):
        """Verify that append mode preserves existing cache and adds newly uploaded courses."""
        # Arrange
        self._reset_data_manager_singleton()

        first_courses_path = tmp_path / "first_courses.txt"
        second_courses_path = tmp_path / "second_courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"

        self._write_courses_file(first_courses_path, course_id="10001")
        self._write_second_courses_file(second_courses_path)
        self._write_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())

        self._load_files(data_manager, first_courses_path, periods_path, selected_programs_path)

        # Act
        self._load_files(
            data_manager,
            second_courses_path,
            periods_path,
            selected_programs_path,
            mode="append"
        )

        # Assert
        cached_course_ids = {course.course_id for course in data_manager.get_courses()}

        assert cached_course_ids == {"10001", "10002"}

    # ======= PLAN-325. Multi-Load Consistency Verification =======

    def test_repeated_replace_loads_remain_consistent_without_duplicate_cache_entries(self, tmp_path):
        """Verify that loading the same files multiple times in replace mode keeps cache state stable."""
        # Arrange
        self._reset_data_manager_singleton()

        courses_path = tmp_path / "courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"

        self._write_courses_file(courses_path)
        self._write_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())

        # Act
        self._load_files(data_manager, courses_path, periods_path, selected_programs_path)
        first_load_course_ids = [course.course_id for course in data_manager.get_courses()]

        self._load_files(data_manager, courses_path, periods_path, selected_programs_path)
        second_load_course_ids = [course.course_id for course in data_manager.get_courses()]

        # Assert
        assert first_load_course_ids == ["10001"]
        assert second_load_course_ids == ["10001"]
        assert data_manager.get_selected_programs() == ["83108"]
        assert len(data_manager.get_exam_periods()) == 1

    # ======= PLAN-335. Cache-To-Model Integration Consistency Verification =======

    def test_loaded_cache_integrates_consistently_with_planix_model(self, tmp_path):
        """Verify that DataManager cache state can be transferred into PlanixModel without data loss."""
        # Arrange
        self._reset_data_manager_singleton()

        courses_path = tmp_path / "courses.txt"
        periods_path = tmp_path / "exam_periods.txt"
        selected_programs_path = tmp_path / "selected_programs.txt"

        self._write_courses_file(courses_path)
        self._write_exam_periods_file(periods_path)
        self._write_selected_programs_file(selected_programs_path)

        data_manager = DataManager(parser=TextFileParser())
        self._load_files(data_manager, courses_path, periods_path, selected_programs_path)

        model = PlanixModel(data_manager=data_manager)

        # Act
        model.set_selected_programs(data_manager.get_selected_programs())
        available_programs = model.build_available_programs()

        # Assert
        assert model.get_selected_programs() == ["83108"]
        assert available_programs == {"83108": "Software Engineering"}
        assert model.get_available_programs() == {"83108": "Software Engineering"}
        assert model.data_manager.get_courses()[0].course_id == "10001"