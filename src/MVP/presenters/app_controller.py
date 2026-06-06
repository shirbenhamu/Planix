import threading
from src.MVP.models.planix_model import PlanixModel
from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
from src.MVP.presenters.input_presenter import InputPresenter
from src.MVP.presenters.calendar_presenter import CalendarPresenter

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
        self.app_window.wire_sync_callback(self.calendar_presenter)
        self.calendar_presenter.controller = self
        
        # Wire callbacks to calendar_presenter for date editing (both screens)
        self.app_window.monthly_view.on_range_update_clicked = self.calendar_presenter._handle_range_update
        self.app_window.input_view.on_range_update_clicked = self.calendar_presenter._handle_range_update

        # Intercept and bind view-switching notifications sent from the UI (PLAN-266)
        self.app_window.on_navigation_requested = self._handle_navigation

        # Establish default startup view configuration (Data Input screen)
        self._handle_navigation("input")

    def _handle_navigation(self, target_view: str) -> None:
        """
        Coordinates screen transitions while keeping underlying data configurations persistent.
        """
        if target_view == "calendar":
            self.regenerate_schedules_snapshot()
            return

        self.app_window.switch_view(target_view)

    def regenerate_schedules_snapshot(self) -> None:
        print("[AppController] Constraint changed. Re-running engine...")
            
        if not self.model.get_selected_programs():
            print("[AppController] No programs selected. Skipping generation and clearing schedules.")
            self.collection_manager.clear_cache()
            return
        self.collection_manager.clear_cache()
            
        # Switch to annual (yearly) calendar view immediately (even if engine is still running)
        self.app_window.switch_view("annual")
        
        # Guard against overlapping generation runs that can overload the UI thread.
        if self.engine_adapter.is_generation_active():
            print("[AppController] Generation already in progress. Will refresh when complete.")
            self.app_window.after(500, self._load_snapshot_schedules)
            return

        if hasattr(self.model, "is_generating") and self.model.is_generating:
            self.model.is_generating = False

        self.collection_manager.snapshot_mode = False
        self.engine_adapter.generate_from_model(model=self.model, output_path=self.output_path)
        # Load and display immediately, then refresh as data arrives
        self.app_window.after(100, self._load_snapshot_schedules)

    def _load_snapshot_schedules(self) -> None:
        """Load and display schedules immediately, with background updates."""
        def run():
            # Build the snapshot index from available data
            self.collection_manager.build_snapshot_index()
            # Refresh calendar display immediately with current data
            self.app_window.after(0, self.calendar_presenter.refresh_presenter_state)

            # If engine is still running, schedule another refresh in 1 second
            if self.engine_adapter.is_generation_active():
                print("[AppController] Engine still running. Scheduling next refresh in 1s...")
                self.app_window.after(1000, self._load_snapshot_schedules)
            else:
                self.collection_manager.snapshot_mode = False
                if hasattr(self.model, "is_generating") and self.model.is_generating:
                    self.model.is_generating = False
                self.engine_adapter.clear_finished_worker()
                print("[AppController] Engine idle. Snapshot mode disabled for full file access.")
                
        # Run in a background thread to avoid blocking UI
        threading.Thread(target=run, daemon=True).start()