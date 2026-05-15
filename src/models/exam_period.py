# ExamPeriod Class
# ExcludedDate Class
# Will hold information about the dates in which exams can be scheduled

from dataclasses import dataclass
from typing import List, Optional
from datetime import date, timedelta

@dataclass
# represents a date range in which exams cannot be scheduled, along with a comment explaining the reason for the exclusion
class ExcludedDate:
    start_date: date
    end_date: date
    comment: Optional[str] = None

@dataclass
# represents an exam period with its semester, moed, start and end dates, and a list of excluded dates
class ExamPeriod:
    semester: str
    moed: str
    start_date: date
    end_date: date
    excluded_dates: List[ExcludedDate]

    def get_available_dates(self) -> List[date]:
        available_dates = []
        current_date = self.start_date
        while current_date <= self.end_date:
            is_excluded = False
            for excl in self.excluded_dates:
                if excl.start_date <= current_date <= excl.end_date:
                    is_excluded = True
                    break
            if not is_excluded:
                available_dates.append(current_date)
            current_date += timedelta(days=1)
            
        return available_dates
        