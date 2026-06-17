# src/MVP/app_controller.py

import threading

# Robust multi-environment import resolution pattern to bypass Windows pytest collection issues
try:
    from MVP.models.planix_model import PlanixModel
    from MVP.models.schedule_collection_manager import ScheduleCollectionManager
    from MVP.presenters.input_presenter import InputPresenter
    from MVP.presenters.calendar_presenter import CalendarPresenter
    from engine.engine_adapter import PlanixEngineAdapter
except ModuleNotFoundError:
    from src.MVP.models.planix_model import PlanixModel
    from src.MVP.models.schedule_collection_manager import ScheduleCollectionManager
    from src.MVP.presenters.input_presenter import InputPresenter
    from src.MVP.presenters.calendar_presenter import CalendarPresenter
    from src.engine.engine_adapter import PlanixEngineAdapter


class AppController:
    def __init__(self, app_window, data_manager):
        self.app_window = app_window
        self.data_manager = data_manager

        # Initialize core application single source of truth state context
        self.model = PlanixModel(data_manager=self.data_manager)
        self.engine_adapter = PlanixEngineAdapter()

        self.output_path = "output_results/final_schedules.txt"
        self.collection_manager = ScheduleCollectionManager(
            output_file_path=self.output_path, data_manager=data_manager)

        # Instantiate presenters
        self.input_presenter = InputPresenter(
            view=self.app_window.input_view, model=self.model)
        self.calendar_presenter = CalendarPresenter(
            view=self.app_window.calendar_view,
            model=self.model,
            collection_manager=self.collection_manager
        )
        
        # PLAN-405: Inject parent router controller reference into input presenter
        self.input_presenter.controller = self
        
        self.app_window.wire_sync_callback(self.calendar_presenter)
        self.calendar_presenter.controller = self
        
        self.app_window.monthly_view.on_range_update_clicked = self.calendar_presenter._handle_range_update
        self.app_window.input_view.on_range_update_clicked = self.calendar_presenter._handle_range_update

        self.app_window.on_navigation_requested = self._handle_navigation
        self._handle_navigation("input")

    def _handle_navigation(self, target_view: str) -> None:
        if target_view == "calendar":
            self.regenerate_schedules_snapshot()
            return
        self.app_window.switch_view(target_view)

    def regenerate_schedules_snapshot(self) -> None:
        """
        Acceptance Criteria Met: Cal_pres triggers a clean engine refresh
        (cancel current + restart) when constraints change dynamically.
        """
        print("[AppController] Constraint or settings changed. Re-running generation pipeline...")
            
        if not self.model.get_selected_programs():
            print("[AppController] No programs selected. Skipping generation.")
            self.collection_manager.clear_cache()
            return
            
        # Clean engine refresh: cancel active generation process immediately if running
        if self.engine_adapter.is_generation_active():
            print("[AppController] Existing process is active. Enforcing active worker cancellation...")
            if self.calendar_presenter:
                self.calendar_presenter._cancel_active_worker_process()

        self.collection_manager.clear_cache()
        self.app_window.switch_view("annual")
        
        if hasattr(self.model, "is_generating") and self.model.is_generating:
            self.model.is_generating = False

        self.collection_manager.snapshot_mode = False
        
        # Launch new Advanced engine generation with the updated SchedulingConstraints setup
        self.engine_adapter.generate_from_model(
            model=self.model, output_path=self.output_path)
            
        self.app_window.switch_view("calendar")
        self.app_window.after(100, self._load_snapshot_schedules)

    def _load_snapshot_schedules(self) -> None:
        prev_count = self.collection_manager.get_total_count()
        self.collection_manager.build_snapshot_index()
        current_count = self.collection_manager.get_total_count()
        
        if prev_count == 0 and current_count > 0:
            self.calendar_presenter.refresh_presenter_state()
        else:
            self.calendar_presenter.refresh_pagination_only()

        if self.engine_adapter.is_generation_active():
            self.app_window.after(500, self._load_snapshot_schedules)
        else:
            self.collection_manager.snapshot_mode = False
            if hasattr(self.model, "is_generating") and self.model.is_generating:
                self.model.is_generating = False
            self.engine_adapter.clear_finished_worker()
            self.calendar_presenter.refresh_presenter_state()
            print("[AppController] Engine idle. Snapshot mode disabled for full file access.")

    def load_more_schedules(self, skip_count: int) -> None:
        if self.engine_adapter.is_generation_active():
            print("[AppController] Generation process is already active. Request denied.")
            return

        print(f"[AppController] Activating 'Load More' pipeline. Skip target: {skip_count}")
        if hasattr(self.model, "is_generating"):
            self.model.is_generating = True
        self.collection_manager.snapshot_mode = True

        self.engine_adapter.generate_from_model(
            model=self.model,
            output_path=self.output_path,
            skip_count=skip_count
        )
        self.app_window.after(
            500, lambda: self._monitor_load_more_progress(previous_count=skip_count))

    def _monitor_load_more_progress(self, previous_count: int) -> None:
        self.collection_manager.build_snapshot_index()
        self.calendar_presenter.refresh_pagination_only()

        if self.engine_adapter.is_generation_active():
            self.app_window.after(
                500, lambda: self._monitor_load_more_progress(previous_count))
        else:
            self.collection_manager.snapshot_mode = False
            if hasattr(self.model, "is_generating") and self.model.is_generating:
                self.model.is_generating = False

            self.engine_adapter.clear_finished_worker()
            self.calendar_presenter.refresh_presenter_state()
            print("[AppController] Load More background worker has finished execution.")

            try:
                with open(self.output_path, "r", encoding="utf-8") as f:
                    final_count = f.read().count("--- FULL SYSTEM OPTION")
                if final_count == previous_count:
                    if hasattr(self.calendar_presenter.view, "show_no_more_results"):
                        self.calendar_presenter.view.show_no_more_results()
            except Exception as e:
                print(f"[AppController] Error evaluating post-run final counts: {e}")