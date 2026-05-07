# Schedule Class
# ScheduledExam Class
# schedule is a list of scheduled exams, each scheduled exam contains a course and the date of the exam.

from dataclasses import dataclass
from typing import List
from datetime import date
from .course import Course

@dataclass
# represents a scheduled exam with its course and the date of the exam
class ScheduledExam:
    course: Course
    exam_date: date

@dataclass
# represents a schedule with a list of scheduled exams
class Schedule:
    exams: List[ScheduledExam]
