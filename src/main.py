import os
import time
from src.parsers.parser_factory import ParserFactory
from src.data_manager import DataManager
from MVP.app_window import AppWindow
from MVP.presenters.app_controller import AppController

def main():
    print("Planix Exam Scheduler - Initializing Central Controller Framework...")
    start_time = time.time()

    # 1. Define input paths only for the remaining active core files
    courses_path = "data/courses.txt"
    exam_periods_path = "data/exam_periods.txt"

    # 2. Verify core input files exist before boot (ignoring the obsolete programs file)
    for path in [courses_path, exam_periods_path]:
        if not os.path.exists(path):
            print(f"Critical Error: Missing required system file {path}")
            return

    # Initialize core system data parser infrastructure
    parser = ParserFactory.create_parser("txt")
    manager = DataManager(parser)
    
    try:
        print("Launching User Interface Core Window...")
        app = AppWindow()
        
        # Instantiate the application master controller to wire up views and models
        controller = AppController(app_window=app, data_manager=manager)
        
        # Begin application main loop session
        app.mainloop()

        duration = time.time() - start_time
        print(f"\nCentral UI session lifecycle ended cleanly after {duration:.2f} seconds.")

    except Exception as e:
        print(f"\nExecution runtime crash intercepted: {e}")

if __name__ == "__main__":
    main()
