# DataManager Class holds a reference of BaseParser
# Will hold a SelectedPrograms List

from typing import List
from src.parsers.base_parser import BaseParser
from src.models.course import Course
from src.models.exam_period import ExamPeriod

class DataManager:
    def __init__(self, parser: BaseParser):
        self.parser = parser
        self.courses: List[Course] = []
        self.exam_periods: List[ExamPeriod] = []
        self.selected_programs: List[str] = []

    def load_data(self, courses_path: str, exam_periods_path: str, selected_programs_path: str):
        self.courses = self.parser.parse_courses(courses_path)
        self.exam_periods = self.parser.parse_exam_periods(exam_periods_path)
        self.selected_programs = self.parser.parse_selected_programs(selected_programs_path)

        self.validate_selected_programs()
        print("Data loaded successfully.")

    def validate_selected_programs(self):
        existing_program_ids = set()
        for course in self.courses:
            for prog_info in course.program_info:
                existing_program_ids.add(prog_info.program_id)

        for prog_id in self.selected_programs:
            if prog_id not in existing_program_ids:
                raise ValueError(f"Error: Selected program ID '{prog_id}' does not exist in the course data.")

    def get_courses(self) -> List[Course]:
        return self.courses
    
    def get_exam_periods(self) -> List[ExamPeriod]:
        return self.exam_periods
    
    def get_selected_programs(self) -> List[str]:
        return self.selected_programs
    
