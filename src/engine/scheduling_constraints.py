# src/engine/scheduling_constraints.py
from dataclasses import dataclass, field
from typing import List

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
    
    selected_religions: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        rules = [
            ("min_days_mandatory_enabled",     "min_days_mandatory_k",     1),
            ("min_days_any_enabled",           "min_days_any_k",           1),
            ("span_mandatory_enabled",         "span_mandatory_k",         1),
            ("max_exams_per_day_enabled",      "max_exams_per_day_k",      1),
            ("max_elective_conflicts_enabled", "max_elective_conflicts_k", 0),
        ]
 
        for enabled_attr, k_attr, minimum in rules:
            if not getattr(self, enabled_attr):
                continue  # disabled constraint: its k is irrelevant.
 
            k = getattr(self, k_attr)
            # bool is a subclass of int (True == 1), so reject it explicitly.
            if isinstance(k, bool) or not isinstance(k, int) or k < minimum:
                bound = "a positive integer (>= 1)" if minimum == 1 \
                    else "a non-negative integer (>= 0)"
                raise ValueError(
                    f"Constraint {k_attr} must be {bound} when enabled (got {k!r})."
                )
 
