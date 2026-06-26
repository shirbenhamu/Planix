# Data Manager class to handle loading and managing course and exam period data.
# It uses a parser to read data from files and provides methods to access the loaded data.

import os
from typing import Dict, List
from src.parsers.base_parser import BaseParser
from src.MVP.models.course import Course
from src.MVP.models.exam_period import ExamPeriod

class DataManager:
    _instance = None

    # Implementing Singleton pattern to ensure only one instance of DataManager exists
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(DataManager, cls).__new__(cls)
            cls._instance.__initialized = False
        return cls._instance

    # The constructor is designed to be called only once due to the Singleton pattern.
    def __init__(self, parser: BaseParser = None):
        if self.__initialized:
            return
        if parser is None:
            raise ValueError("Parser must be provided to DataManager.")
        self.parser = parser
        self.courses: Dict[str, Course] = {}
        self.exam_periods: List[ExamPeriod] = []
        self.selected_programs: List[str] = []
        self._parse_cache: dict = {}
        self.__initialized = True
        
    @staticmethod
    def _file_signature(path: str):
        try:
            st = os.stat(path)
            return (st.st_mtime_ns, st.st_size)
        except OSError:
            return None
            
    def _parse_cached(self, kind: str, path: str, parse_fn):
        """
        Loads data using the provided parsing function, only if the 
        file signature has changed or the data is not in cache.
        """
        if not hasattr(self, "_parse_cache"): 
            self._parse_cache = {}
        sig = self._file_signature(path)
        entry = self._parse_cache.get((kind, path))
        # Return cached result if the file signature matches
        if entry is not None and sig is not None and entry[0] == sig:
            return entry[1]       
        # Otherwise, parse the file and update cache         
        result = parse_fn(path)
        self._parse_cache[(kind, path)] = (sig, result)
        return result
    
    # Method to load data from files using the parser
    def load_data(
        self,
        courses_path: str,
        exam_periods_path: str,
        selected_programs_path: str,
        mode: str = "replace"
    ):

        if mode not in ("replace", "append"):
            raise ValueError("mode must be either 'replace' or 'append'.")

        parsed_courses = self._parse_cached("courses", courses_path, self.parser.parse_courses)

        if mode == "replace":
            self.courses.clear()
        for course in parsed_courses:
            self.courses[course.course_id] = course

        self.exam_periods = list(self._parse_cached(
            "exam_periods", exam_periods_path, self.parser.parse_exam_periods))
        self.selected_programs = list(self._parse_cached(
            "programs", selected_programs_path, self.parser.parse_selected_programs))

        self.validate_selected_programs()
        print("Data loaded successfully.")

    # Method to validate that selected program IDs exist in the course data
    def validate_selected_programs(self):
        existing_program_ids = set()
        for course in self.courses.values():
            for prog_info in course.program_info:
                existing_program_ids.add(prog_info.program_id)

        for prog_id in self.selected_programs:
            if prog_id not in existing_program_ids:
                raise ValueError(f"Error: Selected program ID '{prog_id}' does not exist in the course data.")

    def get_courses(self) -> List[Course]:
        return list(self.courses.values())
    
    def get_exam_periods(self) -> List[ExamPeriod]:
        return self.exam_periods
    
    def get_selected_programs(self) -> List[str]:
        return self.selected_programs
    
