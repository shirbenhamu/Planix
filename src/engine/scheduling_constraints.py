# src/engine/scheduling_constraints.py
from dataclasses import dataclass

@dataclass
class SchedulingConstraints:
    # 2.1: Min days between mandatory exams
    min_days_mandatory_enabled: bool = False
    min_days_mandatory_k: int = 0

    # 2.2: Min days between any two exams
    min_days_any_enabled: bool = False
    min_days_any_k: int = 0

    # 2.3: Max elective-elective conflicts
    max_elective_conflicts_enabled: bool = False
    max_elective_conflicts_k: int = 0

    # 2.4: Span between first and last mandatory exam
    span_mandatory_enabled: bool = False
    span_mandatory_k: int = 0

    # 2.5: Max exams per day
    max_exams_per_day_enabled: bool = False
    max_exams_per_day_k: int = 1