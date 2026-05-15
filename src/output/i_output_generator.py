from abc import ABC, abstractmethod
from typing import Dict, Tuple, Iterator
from src.models.schedule import Schedule

"""
Abstract method to write generated schedules to a destination.
:param schedules_generators: Dictionary mapping (Semester, Moed) to a Schedule iterator.
:param output_file_path: Target path for the output file.
"""

class IOutputGenerator(ABC):
    @abstractmethod
    def write_schedules(
        self, 
        schedules_generators: Dict[Tuple[str, str], Iterator[Schedule]], 
        output_file_path: str
    ) -> None:
        pass