import pytest
from datetime import date
from src.MVP.models.course import Course
from src.MVP.models.course import ProgramCourseInfo
from src.MVP.models.schedule import ScheduledExam
from src.engine.advanced_exam_scheduler import AdvancedExamScheduler
from src.engine.scheduling_constraints import SchedulingConstraints

@pytest.fixture
def mock_context():
    """
    Fixture providing real Course models with correct internal program_info lists
    to properly mirror production data structures and avoid AttributeErrors.
    """
    # Create valid program-course relationships using production models
    mandatory_info = ProgramCourseInfo(program_id="CS_YEAR_1", year=1, semester="A", requirement="Mandatory")
    elective_info = ProgramCourseInfo(program_id="CS_YEAR_1", year=1, semester="A", requirement="Elective")
    
    # Construct courses matching the exact parameters required by the Core Course model
    course_a = Course(course_id="CS101", course_name="Intro to CS", instructor="Dr. Smith", evaluation_method="Exam", program_info=[mandatory_info])
    course_b = Course(course_id="CS102", course_name="Data Structures", instructor="Dr. Doe", evaluation_method="Exam", program_info=[mandatory_info])
    elective_x = Course(course_id="EL201", course_name="Machine Learning", instructor="Dr. Jones", evaluation_method="Exam", program_info=[elective_info])
    elective_y = Course(course_id="EL202", course_name="Web Dev", instructor="Dr. Miller", evaluation_method="Exam", program_info=[elective_info])
    
    return {
        "course_a": course_a,
        "course_b": course_b,
        "elective_x": elective_x,
        "elective_y": elective_y,
        "conflict_matrix": set()
    }

def test_constraint_2_1_min_days_mandatory(mock_context):
    """Verifies constraint 2.1 checks spacing strictly for mandatory same-program courses."""
    constraints = SchedulingConstraints(min_days_mandatory_enabled=True, min_days_mandatory_k=4)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    
    day_1 = date(2026, 1, 20)
    day_2 = date(2026, 1, 21)
    scheduled_exams = []
    
    scheduler._push_state(mock_context["course_a"], day_1, scheduled_exams, mock_context["conflict_matrix"])
    scheduled_exams.append(ScheduledExam(course=mock_context["course_a"], exam_date=day_1))
    
    assert scheduler._can_add_exam_to_schedule(mock_context["course_b"], day_2, scheduled_exams, mock_context["conflict_matrix"]) is False
    assert scheduler._can_add_exam_to_schedule(mock_context["elective_x"], day_2, scheduled_exams, mock_context["conflict_matrix"]) is True

def test_constraint_2_2_min_days_any_exams(mock_context):
    """Verifies constraint 2.2 enforces day spacing between any two exams."""
    constraints = SchedulingConstraints(min_days_any_enabled=True, min_days_any_k=3)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    
    day_1 = date(2026, 1, 10)
    day_2 = date(2026, 1, 11)
    day_3 = date(2026, 1, 15)
    scheduled_exams = []
    
    scheduler._push_state(mock_context["elective_x"], day_1, scheduled_exams, mock_context["conflict_matrix"])
    scheduled_exams.append(ScheduledExam(course=mock_context["elective_x"], exam_date=day_1))
    
    assert scheduler._can_add_exam_to_schedule(mock_context["elective_y"], day_2, scheduled_exams, mock_context["conflict_matrix"]) is False
    assert scheduler._can_add_exam_to_schedule(mock_context["elective_y"], day_3, scheduled_exams, mock_context["conflict_matrix"]) is True

def test_constraint_2_3_max_elective_conflicts(mock_context):
    """Verifies constraint 2.3 limits active elective-elective conflicts on the same date."""
    constraints = SchedulingConstraints(max_elective_conflicts_enabled=True, max_elective_conflicts_k=0)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 25)
    scheduled_exams = []
    
    # First elective course should pass
    assert scheduler._can_add_exam_to_schedule(mock_context["elective_x"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True
    
    scheduler._push_state(mock_context["elective_x"], test_date, scheduled_exams, mock_context["conflict_matrix"])
    scheduled_exams.append(ScheduledExam(course=mock_context["elective_x"], exam_date=test_date))
    
    # Second elective course on the same program/year/day creates a conflict, should be blocked when k=0
    assert scheduler._can_add_exam_to_schedule(mock_context["elective_y"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False

def test_constraint_2_4_span_mandatory(mock_context):
    """Verifies constraint 2.4 enforces the maximum allowed span between first and last mandatory exam."""
    constraints = SchedulingConstraints(span_mandatory_enabled=True, span_mandatory_k=10)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    
    start_date = date(2026, 1, 1)
    invalid_end_date = date(2026, 1, 15)  # Span of 15 days is greater than k=10
    valid_end_date = date(2026, 1, 5)     # Span of 5 days is within k=10
    scheduled_exams = []
    
    scheduler._push_state(mock_context["course_a"], start_date, scheduled_exams, mock_context["conflict_matrix"])
    scheduled_exams.append(ScheduledExam(course=mock_context["course_a"], exam_date=start_date))
    
    assert scheduler._can_add_exam_to_schedule(mock_context["course_b"], invalid_end_date, scheduled_exams, mock_context["conflict_matrix"]) is False
    assert scheduler._can_add_exam_to_schedule(mock_context["course_b"], valid_end_date, scheduled_exams, mock_context["conflict_matrix"]) is True

def test_constraint_2_5_max_exams_per_day(mock_context):
    """Verifies constraint 2.5 limits multiple exams on the same date."""
    constraints = SchedulingConstraints(max_exams_per_day_enabled=True, max_exams_per_day_k=1)
    scheduler = AdvancedExamScheduler(constraints=constraints)
    test_date = date(2026, 1, 29)
    scheduled_exams = []
    
    assert scheduler._can_add_exam_to_schedule(mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True
    
    scheduler._push_state(mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])
    scheduled_exams.append(ScheduledExam(course=mock_context["course_a"], exam_date=test_date))
    
    assert scheduler._can_add_exam_to_schedule(mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is False
    
    scheduled_exams.pop()
    scheduler._pop_state(mock_context["course_a"], test_date, scheduled_exams, mock_context["conflict_matrix"])
    
    assert scheduler._can_add_exam_to_schedule(mock_context["course_b"], test_date, scheduled_exams, mock_context["conflict_matrix"]) is True