# BaseParser Interface (Abstract Class)
# text_file_parser will inherit and implement the parse method for text files,
#  but we may need other parsers in the future (like JSONParser)

from abc import ABC, abstractmethod
from typing import List
from src.models.course import Course
from src.models.exam_period import ExamPeriod

# BaseParser is an abstract class that defines the interface for parsing input data
class BaseParser(ABC):
    @abstractmethod
    def parse_courses(self, file_path: str) -> List[Course]:
        pass

    @abstractmethod
    def parse_exam_periods(self, file_path: str) -> List[ExamPeriod]:
        pass

    @abstractmethod
    def parse_selected_programs(self, file_path: str) -> List[str]:
        pass

    