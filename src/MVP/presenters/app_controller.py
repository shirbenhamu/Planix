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
        self.collection_manager = ScheduleCollectionManager(
            output_file_path=self.output_path, data_manager=data_manager)

        # Instantiate child presenters, injecting the shared persistent state context
        self.input_presenter = InputPresenter(
            view=self.app_window.input_view, model=self.model)
        self.calendar_presenter = CalendarPresenter(
            view=self.app_window.calendar_view,
            model=self.model,
            collection_manager=self.collection_manager
        )
        self.calendar_presenter.controller = self

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

        # Guard against overlapping generation runs that can overload the UI thread.
        if self.engine_adapter.is_generation_active():
            print(
                "[AppController] Generation already in progress. Reusing current snapshot flow.")
            self.app_window.switch_view("calendar")
            self.app_window.after(100, self._load_snapshot_schedules)
            return

        if hasattr(self.model, "is_generating") and self.model.is_generating:
            self.model.is_generating = False

        self.collection_manager.snapshot_mode = False
        self.engine_adapter.generate_from_model(
            model=self.model, output_path=self.output_path)
        self.app_window.switch_view("calendar")
        self.app_window.after(500, self._load_snapshot_schedules)

    def _load_snapshot_schedules(self) -> None:
        def run():
            self.collection_manager.build_snapshot_index()
            self.app_window.after(
                0, self.calendar_presenter.refresh_presenter_state)

            # Keep polling while generation is active; release snapshot mode once idle.
            if self.engine_adapter.is_generation_active():
                self.app_window.after(500, self._load_snapshot_schedules)
            else:
                self.collection_manager.snapshot_mode = False
                if hasattr(self.model, "is_generating") and self.model.is_generating:
                    self.model.is_generating = False
                self.engine_adapter.clear_finished_worker()
                print(
                    "[AppController] Engine idle. Snapshot mode disabled for full file access.")

        # Run the snapshot loading in a separate thread to avoid blocking the UI during file I/O operations.
        threading.Thread(target=run, daemon=True).start()

    def load_more_schedules(self, skip_count: int) -> None:
        """
        Triggers a new dynamic 29-second generation run, 
        appending new schedules to the existing file while skipping the already generated ones.
        """
        # Prevent concurrent generation runs if else generation process is active
        if self.engine_adapter.is_generation_active():
            print(
                "[AppController] Generation process is already active. Request denied.")
            return

        print(
            f"[AppController] Activating 'Load More' pipeline. Skip target: {skip_count}")

        # Enable snapshot mode to allow seamless calendar UI browsing during writes
        if hasattr(self.model, "is_generating"):
            self.model.is_generating = True
        self.collection_manager.snapshot_mode = True

        # Invoke the adapter with skip_count to append new solutions to the output file
        self.engine_adapter.generate_from_model(
            model=self.model,
            output_path=self.output_path,
            skip_count=skip_count
        )

        # Trigger the periodic polling mechanism to monitor progress and load updates
        self.app_window.after(
            500, lambda: self._monitor_load_more_progress(previous_count=skip_count))

    def _monitor_load_more_progress(self, previous_count: int) -> None:
        """Background thread polling monitor dedicated for tracking 'Load More' actions"""
        def run():
            # Rebuild the snapshot index from the text file
            self.collection_manager.build_snapshot_index()
            # Safely dispatch UI state refresh to the main thread
            self.app_window.after(
                0, self.calendar_presenter.refresh_presenter_state)

            # Continue polling every 500ms if the background worker remains active
            if self.engine_adapter.is_generation_active():
                self.app_window.after(
                    500, lambda: self._monitor_load_more_progress(previous_count))
            else:
                # Execution complete: teardown state flags and release worker resources
                self.collection_manager.snapshot_mode = False
                if hasattr(self.model, "is_generating") and self.model.is_generating:
                    self.model.is_generating = False

                self.engine_adapter.clear_finished_worker()
                print(
                    "[AppController] Load More background worker has finished execution.")

                # Evaluate if the backtracking engine discovered new branches or exhausted the search space
                try:
                    with open(self.output_path, "r", encoding="utf-8") as f:
                        final_count = f.read().count("--- FULL SYSTEM OPTION")

                    if final_count == previous_count:
                        print(
                            "[AppController] Exhausted all options. No new schedules found.")
                        # Notify the view to inform the user that no more schedules exist
                        if hasattr(self.calendar_presenter.view, "show_no_more_results"):
                            self.app_window.after(
                                0, self.calendar_presenter.view.show_no_more_results)
                except Exception as e:
                    print(
                        f"[AppController] Error evaluating post-run final counts: {e}")

        # Spawn a daemonized background thread to prevent disk I/O from blocking the GUI loop
        threading.Thread(target=run, daemon=True).start()