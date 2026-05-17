import pytest
import os
from src.data_manager import DataManager
from src.parsers.text_file_parser import TextFileParser

@pytest.fixture(autouse=True)
def reset_data_manager_singleton():
    """
    cleanup for DataManager singleton instance before and after each test.
     - Before each test, it sets DataManager._instance to None to ensure a fresh start
    """
    DataManager._instance = None
    yield
    DataManager._instance = None


def test_data_manager_happy_path_and_getters(tmp_path):
    """
    verifies successful data loading from end to end.
    ensures that the data from the temporary files is parsed and stored correctly in the DataManager.
    """
    parser = TextFileParser()
    manager = DataManager(parser)

    #  creating temporary files with valid data for courses, periods, and programs
    courses_file = tmp_path / "courses.txt"
    courses_file.write_text(
        "Infinitesimal Calculus 1\n83101\nProf. Newton\n83108, 1, FALL, Obligatory\nExam", 
        encoding="utf-8"
    )

    periods_file = tmp_path / "periods.txt"
    periods_file.write_text(
        "FALL, Aleph\n29-01-2026, 11-03-2026\n- 31-01-2026 Shabat", 
        encoding="utf-8"
    )

    programs_file = tmp_path / "programs.txt"
    programs_file.write_text("83108", encoding="utf-8")

    #running the data loading process
    manager.load_data(str(courses_file), str(periods_file), str(programs_file))

    # validating that the data was loaded correctly by checking the getters
    assert len(manager.get_courses()) == 1
    assert manager.get_courses()[0].course_id == "83101"
    assert len(manager.get_exam_periods()) == 1
    assert manager.get_exam_periods()[0].semester == "FALL"
    assert manager.get_selected_programs() == ["83108"]


def test_data_manager_validation_fails_for_non_existent_program(tmp_path):
    """
    verifies that the data manager correctly validates selected programs.
    ensures that a ValueError is raised when a selected program does not exist in any course.
    """
    parser = TextFileParser()
    manager = DataManager(parser)

    # courses file contains one course with ID 83101, but the programs file references a non-existent program ID 99999
    courses_file = tmp_path / "courses.txt"
    courses_file.write_text(
        "Infinitesimal Calculus 1\n83101\nProf. Newton\n83108, 1, FALL, Obligatory\nExam", 
        encoding="utf-8"
    )

    periods_file = tmp_path / "periods.txt"
    periods_file.write_text("FALL, Aleph\n29-01-2026, 11-03-2026", encoding="utf-8")

    # choosing a program ID 99999 that does not exist in the courses file above
    programs_file = tmp_path / "programs.txt"
    programs_file.write_text("99999", encoding="utf-8")

    # verifying that the system raises a ValueError and identifies that the program does not exist in the courses
    with pytest.raises(ValueError, match="Selected program ID '99999' does not exist"):
        manager.load_data(str(courses_file), str(periods_file), str(programs_file))


def test_data_manager_raises_file_not_found_for_missing_paths():
    """
    verifies that the data manager raises a FileNotFoundError when provided with non-existent file paths.
     - This test ensures that the system correctly handles cases where the specified data files cannot be found, which is crucial for robustness and user feedback.
     - By using completely fake paths, we can confirm that the error handling is working as expected without relying on any actual files on disk.
     - The test expects a FileNotFoundError to be raised, indicating that the system is correctly identifying and responding to missing files.
    """
    parser = TextFileParser()
    manager = DataManager(parser)

    # sending completely fake paths that do not exist on disk
    with pytest.raises(FileNotFoundError):
        manager.load_data("fake_path_courses.txt", "fake_path_periods.txt", "fake_path_programs.txt")