# ISchedulingEngine Interface (Abstract Class)
# We may have other scheduling engines in the future

from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Iterator
from src.models.course import Course
from src.models.schedule import Schedule
from src.models.exam_period import ExamPeriod

class ISchedulingEngine(ABC):
    @abstractmethod
    def generate_schedules(
        self,
        courses: List[Course],
        exam_periods: List[ExamPeriod],
        selected_programs: List[str]
    ) -> Dict[Tuple[str, str], Iterator[Schedule]]:
        pass
        