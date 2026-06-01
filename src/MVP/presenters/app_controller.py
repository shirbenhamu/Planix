from MVP.models.planix_model import PlanixModel
from MVP.models.schedule_collection_manager import ScheduleCollectionManager
from MVP.presenters.input_presenter import InputPresenter
from MVP.presenters.calendar_presenter import CalendarPresenter

class AppController:
    def __init__(self, app_window, data_manager):
        """
        Acts as the central router and unified execution state context for the application (PLAN-265).
        Refactored to cleanly support dynamic program extraction from loaded courses (PLAN-267).
        """
        self.app_window = app_window
        self.data_manager = data_manager

        # 1. Initialize the single source of truth for application state (PLAN-267)
        self.model = PlanixModel(data_manager=self.data_manager)
        
        # Explicitly configure data paths to ignore the obsolete 3rd programs file
        self.model.set_data_paths(courses_path=None, exam_periods_path=None, selected_programs_path=None)
        
        # Define the path where the core engine saves generated text schedules
        output_path = "output_results/final_schedules.txt"
        self.collection_manager = ScheduleCollectionManager(output_file_path=output_path, data_manager=data_manager)

        # 2. Instantiate child presenters, injecting the shared persistent state context
        self.input_presenter = InputPresenter(view=self.app_window.input_view, model=self.model)
        self.calendar_presenter = CalendarPresenter(
            view=self.app_window.calendar_view, 
            model=self.model, 
            collection_manager=self.collection_manager
        )

        # 3. Intercept view-switching notifications sent from the UI (PLAN-266)
        self.app_window.on_navigation_requested = self._handle_navigation

        # Establish default startup view coordinate configuration
        self._handle_navigation("input")

    def _handle_navigation(self, target_view: str) -> None:
        """
        Coordinates screen transitions while keeping underlying data configurations persistent.
        """
        if target_view == "calendar":
            # Refresh schedule calculations automatically before displaying calendar layout
            self.calendar_presenter.refresh_presenter_state()

        # Command the window layout manager to switch visible views
        self.app_window.switch_view(target_view)