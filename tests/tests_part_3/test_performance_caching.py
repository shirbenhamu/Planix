"""
internal caching -
If the courses/dates file has not changed, the data should load from the
program's internal cache without re-reading it from the source file.
"""

import pytest
from src.data_manager import DataManager
from src.parsers.base_parser import BaseParser

class _CountingParser(BaseParser):
    """Counts how many times parse_courses is invoked."""
    def __init__(self):
        self.parse_courses_calls = 0

    def parse_courses(self, file_path):
        self.parse_courses_calls += 1
        return []

    def parse_exam_periods(self, file_path): return []
    def parse_selected_programs(self, file_path): return []

@pytest.fixture(autouse=True)
def _reset_singleton():
    """
    Ensures that the DataManager singleton instance is cleared 
    before and after each test to prevent cross-test interference.
    """
    DataManager._instance = None
    yield
    DataManager._instance = None

def test_unchanged_input_is_not_reparsed(tmp_path):
    """
    Verifies that if the input files remain unchanged, the DataManager 
    loads data from its internal cache instead of re-parsing the files.
    """
    parser = _CountingParser()
    dm = DataManager(parser=parser)

    # Prepare dummy files
    courses_file = tmp_path / "courses.txt"
    periods_file = tmp_path / "periods.txt"
    programs_file = tmp_path / "programs.txt"
    for f in (courses_file, periods_file, programs_file):
        f.write_text("dummy data\n", encoding="utf-8")

    # First load - the parser should be called
    dm.load_data(str(courses_file), str(periods_file), str(programs_file))
    first = parser.parse_courses_calls
    
    # Second load (with no changes to the files) - should use cache
    dm.load_data(str(courses_file), str(periods_file), str(programs_file))
    second = parser.parse_courses_calls

    # Assert that no additional parsing calls occurred
    assert second == first, (
        f"Files were re-parsed despite no changes! "
        f"Expected {first} calls, but got {second}."
    )