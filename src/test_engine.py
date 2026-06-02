import os
import time
from parsers.parser_factory import ParserFactory
from data_manager import DataManager
from MVP.models.planix_model import PlanixModel
from engine.engine_adapter import PlanixEngineAdapter
from MVP.models.schedule_collection_manager import ScheduleCollectionManager

def test_run():
    print("=== Starting Engine Integration Test ===")
    
    parser = ParserFactory.create_parser("txt")
    manager = DataManager(parser)
    
    courses_path = "data/courses.txt"
    exam_periods_path = "data/exam_periods.txt"
    selected_programs_path = "data/selected_programs.txt"
    output_path = "output_results/final_schedules.txt"
    
    print("Loading data...")
    manager.load_data(courses_path, exam_periods_path, selected_programs_path)
    manager.selected_programs = ["83101", "83102"]
    print("Data loaded successfully!")
    
    model = PlanixModel(data_manager=manager)
    model.set_selected_programs(["83101", "83102"])
    adapter = PlanixEngineAdapter()
    
    print(f"Launching engine asynchronously, writing to: {output_path}")
    adapter.generate_from_model(model, output_path)
    
    print("Waiting 3 seconds to let the engine generate initial schedules...")
    time.sleep(3)

    if os.path.exists(output_path):
        print(f"Success! Output file created. Current size: {os.path.getsize(output_path)} bytes.")
    else:
        print("Error: Output file was not created!")
        return

    print("Initializing ScheduleCollectionManager over the live file...")
    collection_manager = ScheduleCollectionManager(output_path, manager)
    
    total_found = collection_manager.get_total_count()
    print(f"Schedules indexed so far: {total_found}")
    
    if total_found > 0:
        print("Attempting to retrieve the first schedule lazily from disk...")
        first_schedule = collection_manager.get_current_schedule()
        print(f"Successfully parsed first schedule! It contains {len(first_schedule.exams)} scheduled exams.")
        
    
        exam = first_schedule.exams[0]
        print(f"--> Verified Exam: Course {exam.course.course_id} on Date {exam.exam_date}")
    else:
        print("Error: No schedules were indexed by the manager.")
        
    print("\nChecking if engine is still generating in the background...")
    print(f"Is generating: {model.is_generating}")
    
    print("=== Test Finished Successfully! ===")

if __name__ == "__main__":
    test_run()
