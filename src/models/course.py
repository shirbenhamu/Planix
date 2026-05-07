# Course Class
# ProgramCourseInfo Class
# Will hold course_id, course_name, instructor, program_course_info...

from dataclasses import dataclass
from typing import List

@dataclass
# represents the connection between a course and a program (each course can be part of multiple programs with different requirements)
class ProgramCourseInfo:
    program_id: str
    year: int
    semester: str
    requirement: str

@dataclass
# represents a course with its details and the list of program course info
class Course:
    course_id: str
    course_name: str
    instructor: str
    evaluation_method: str
    program_info: List[ProgramCourseInfo]

