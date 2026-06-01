import time
from MVP.models.planix_model import PlanixModel
from MVP.models.schedule_collection_manager import ScheduleCollectionManager
from MVP.presenters.input_presenter import InputPresenter
from MVP.presenters.calendar_presenter import CalendarPresenter

# Precise absolute import matching your physical directory structure (src/engine/engine_adapter.py)
from src.engine.engine_adapter import PlanixEngineAdapter

class AppController:
    def __init__(self, app_window, data_manager):
        """
        Acts as the central router and unified execution state context for the application (PLAN-265).
        Coordinates screen transitions and orchestrates data layer interactions.
        """
        self.app_window = app_window
        self.data_manager = data_manager

        # Initialize the single source of truth for application state (PLAN-267)
        self.model = PlanixModel(data_manager=self.data_manager)
        
        # Instantiate the engine adapter to handle background schedule generation
        self.engine_adapter = PlanixEngineAdapter()
        
        # Define the centralized output file path where the algorithm writes results
        self.output_path = "output_results/final_schedules.txt"
        self.collection_manager = ScheduleCollectionManager(output_file_path=self.output_path, data_manager=data_manager)

        # Instantiate child presenters, injecting the shared persistent state context
        self.input_presenter = InputPresenter(view=self.app_window.input_view, model=self.model)
        self.calendar_presenter = CalendarPresenter(
            view=self.app_window.calendar_view, 
            model=self.model, 
            collection_manager=self.collection_manager
        )

        # Intercept and bind view-switching notifications sent from the UI (PLAN-266)
        self.app_window.on_navigation_requested = self._handle_navigation

        # Establish default startup view configuration (Data Input screen)
        self._handle_navigation("input")

    def _handle_navigation(self, target_view: str) -> None:
        """
        Coordinates screen transitions while keeping underlying data configurations persistent.
        """
        if target_view == "calendar":
            print("[AppController] Triggering exam generation engine via adapter...")
            
            # 1. Invoke the generation algorithm in a background thread via the adapter
            # This populates the final_schedules.txt file with calculated timetables
            self.engine_adapter.generate_from_model(model=self.model, output_path=self.output_path)
            
            # 2. Briefly allow the background thread to initialize and create the file context
            # This prevents a race condition where the presenter reads an empty file instantly
            time.sleep(0.5)
            
            # 3. Command the calendar presenter to load and render the newly generated results
            self.calendar_presenter.refresh_presenter_state()

        # Command the window layout manager to switch the visible views in the UI
        self.app_window.switch_view(target_view)