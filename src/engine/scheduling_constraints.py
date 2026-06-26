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
    
    def __post_init__(self):
        # Group A: thresholds that may be zero but never negative (>= 0).
        non_negative_fields = [
            "min_days_mandatory_k", 
            "min_days_any_k", 
            "max_elective_conflicts_k", 
            "span_mandatory_k"
        ]
        
        # Reject anything that is not an int or is below zero.
        for field in non_negative_fields:
            val = getattr(self, field)
            if not isinstance(val, int) or val < 0:
                raise ValueError(f"Constraint {field} must be a non-negative integer (>= 0).")

        # Group B: thresholds that must be strictly positive (>= 1); a 0 cap makes no sense here.
        positive_fields = ["max_exams_per_day_k"]
        
        # Reject anything that is not an int or is below one.
        for field in positive_fields:
            val = getattr(self, field)
            if not isinstance(val, int) or val < 1:
                raise ValueError(f"Constraint {field} must be at least 1.")