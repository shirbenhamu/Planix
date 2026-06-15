import pytest
from datetime import date
from src.MVP.models.schedule import ScheduledExam
from src.engine.advanced_exam_scheduler import AdvancedExamScheduler
from src.engine.scheduling_constraints import SchedulingConstraints

# mock classes to simulate the necessary fields for the engine's constraints without full model dependencies
class MockCourse:
    def __init__(self, course_id: str, name: str, is_mandatory: bool, program_id: str):
        self.id = course_id
        self.course_id = course_id  
        self.name = name
        self.is_mandatory = is_mandatory
        self.program_id = program_id

@pytest.fixture
def mock_context():
    """Fixture providing decoupled mock objects with exactly the fields the engine checks."""
    course_a = MockCourse("CS101", "Intro to CS", True, "CS_YEAR_1")
    course_b = MockCourse("CS102", "Data Structures", True, "CS_YEAR_1")
    elective_x = MockCourse("EL201", "Machine Learning", False, "")
    elective_y = MockCourse("EL202", "Web Dev", False, "")
    
    return {
        "course_a": course_a,
        "course_b": course_b,
        "elective_x": elective_x,
        "elective_y": elective_y,
        "conflict_matrix": set()
    }

def test_constraint_2_5_max_exams_per_day(mock_context):
    """Verifies constraint 2.5 limits multiple exams on the same date."""
    constraints = SchedulingConstraints(
        max_exams_per_day_enabled=True,
        max_exams_per_day_k=1
    )
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)
    scheduled_exams = []
    
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"]
    ) is True
    
    scheduler._push_state(mock_context["course_a"], test_date, mock_context["conflict_matrix"], scheduled_exams)
    scheduled_exams.append(ScheduledExam(course=mock_context["course_a"], exam_date=test_date))
    
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]
    ) is False
    
    scheduled_exams.pop()
    scheduler._pop_state(mock_context["course_a"], test_date, mock_context["conflict_matrix"], scheduled_exams)
    
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]
    ) is True

def test_constraint_2_2_min_days_any_exams(mock_context):
    """Verifies constraint 2.2 enforces day spacing between any two exams."""
    constraints = SchedulingConstraints(
        min_days_any_enabled=True,
        min_days_any_k=3
    )
    scheduler = AdvancedExamScheduler(constraints=constraints)
    
    day_1 = date(2026, 1, 10)
    day_2 = date(2026, 1, 11)
    day_3 = date(2026, 1, 15)
    scheduled_exams = []
    
    scheduler._push_state(mock_context["elective_x"], day_1, mock_context["conflict_matrix"], scheduled_exams)
    scheduled_exams.append(ScheduledExam(course=mock_context["elective_x"], exam_date=day_1))
    
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_y"], day_2, scheduled_exams, mock_context["conflict_matrix"]
    ) is False
    
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_y"], day_3, scheduled_exams, mock_context["conflict_matrix"]
    ) is True

def test_constraint_2_1_min_days_mandatory(mock_context):
    """Verifies constraint 2.1 checks spacing strictly for mandatory same-program courses."""
    constraints = SchedulingConstraints(
        min_days_mandatory_enabled=True,
        min_days_mandatory_k=4
    )
    scheduler = AdvancedExamScheduler(constraints=constraints)
    
    day_1 = date(2026, 1, 20)
    day_2 = date(2026, 1, 21)
    scheduled_exams = []
    
    scheduler._push_state(mock_context["course_a"], day_1, mock_context["conflict_matrix"], scheduled_exams)
    scheduled_exams.append(ScheduledExam(course=mock_context["course_a"], exam_date=day_1))
    
    assert scheduler._can_add_exam_to_schedule(
        mock_context["course_b"], day_2, scheduled_exams, mock_context["conflict_matrix"]
    ) is False
    
    assert scheduler._can_add_exam_to_schedule(
        mock_context["elective_x"], day_2, scheduled_exams, mock_context["conflict_matrix"]
    ) is True