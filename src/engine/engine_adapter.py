from __future__ import annotations

import os
from multiprocessing import Process
from pathlib import Path
from typing import List, Optional

from src.data_manager import DataManager
from src.engine.exam_scheduler import ExamScheduler
from src.MVP.models.course import Course
from src.MVP.models.planix_model import PlanixModel
from src.output.file_output_writer import FileOutputWriter

# Adapter that bridges the MVP model layer to the legacy V1.0 scheduler.
class PlanixEngineAdapter:

    def __init__(self) -> None:
        self._worker_process: Optional[Process] = None

    # This method serves as the isolated execution context for the background process worker!

    # Implemented as a static method to ensure it is easily pickleable by python's
    # multiprocessing module, keeping the invocation stateless and detached from
    # live UI or adapter instances. This is ideal for heavy CPU-bound generation runs.
    @staticmethod
    def _generate_and_write_worker(
        filtered_courses: List[Course],
        exam_periods,
        selected_programs: List[str],
        output_path: str,
        skip_count: int,
    ) -> None:
        scheduler = ExamScheduler()
        generated_schedules = scheduler.generate_schedules(
            filtered_courses,
            exam_periods,
            selected_programs,
        )

        writer = FileOutputWriter()

        # If skip_count is greater than zero, this means we are in a 
        # "Load More" scenario and should append schedules to the existing file.
        is_append = skip_count > 0
        # Write the generated schedules directly to the output file.
        writer.write_schedules(generated_schedules,
                               output_path, skip_count=skip_count, append=is_append)

    def generate_from_model(
        self,
        model: PlanixModel,
        output_path: str,
        skip_count: int = 0,
    ) -> str:
        """Generate schedules from the model state and stream them directly to disk.

        The legacy scheduler remains untouched. This adapter converts the model state
        into the scheduler's expected inputs, keeps the schedule output lazy, and
        delegates file generation to the existing FileOutputWriter.
        """
        self._validate_model(model)
        self._validate_output_path(output_path)

        model.is_generating = True

        selected_programs = model.get_selected_programs()
        filtered_courses = self._filter_courses_by_selected_programs(
            model.data_manager.get_courses(),
            selected_programs,
        )
        exam_periods = list(model.data_manager.get_exam_periods())

        # If skip_count > 0, the base output file must already exist
        if skip_count > 0 and not os.path.exists(output_path):
            raise FileNotFoundError(
                f"Cannot 'Load More', base schedule file does not exist at: {output_path}")
            
        # We run the generation in a separate thread to avoid blocking the UI and allow.
        # The process is marked as a daemon so it will automatically exit when the main program exits,
        # preventing orphaned workers if the user closes the UI during generation.
        self._worker_process = Process(
            target=PlanixEngineAdapter._generate_and_write_worker,
            args=(filtered_courses, exam_periods, selected_programs, output_path, skip_count),
            daemon=True,
        )
        self._worker_process.start()
        return output_path

    # This method allows the UI to check if a  engine generation process is currently active
    def is_generation_active(self) -> bool:
        return self._worker_process is not None and self._worker_process.is_alive()

    # This method allows the UI to clear the worker reference once it has detected that the process has finished,
    # ensuring that subsequent generation runs can be initiated without stale state interference.
    def clear_finished_worker(self) -> None:
        if self._worker_process is not None and not self._worker_process.is_alive():
            self._worker_process = None

    #  This method allows exporting a single schedule to a new file, which can be used for "saving" a schedule from the UI.
    def export_active_schedule(
        self,
        source_path: str,
        destination_path: str,
        schedule_content: str,
    ) -> str:
        """Export a single schedule text payload to a new file path.

        The source path is accepted for future compatibility with UI workflows that
        may reference the originating schedule file.
        """
        self._validate_existing_path(source_path)
        self._validate_output_path(destination_path)

        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(schedule_content, encoding="utf-8")
        return destination_path

    #  The following private methods are for internal validation and data transformation.
    def _filter_courses_by_selected_programs(
        self,
        courses: List[Course],
        selected_programs: List[str],
    ) -> List[Course]:
        selected_program_ids = {
            program_id.strip() for program_id in selected_programs if program_id.strip()}
        filtered_courses: List[Course] = []

        for course in courses:
            matching_program_info = [
                program_info
                for program_info in course.program_info
                if program_info.program_id in selected_program_ids
            ]

            if not matching_program_info:
                continue

            filtered_courses.append(
                Course(
                    course_id=course.course_id,
                    course_name=course.course_name,
                    instructor=course.instructor,
                    evaluation_method=course.evaluation_method,
                    program_info=matching_program_info,
                )
            )

        return filtered_courses

    def _validate_model(self, model: PlanixModel) -> None:
        if model is None:
            raise ValueError("model must not be None.")

        data_manager = getattr(model, "data_manager", None)
        if not isinstance(data_manager, DataManager):
            raise ValueError(
                "model.data_manager must be a DataManager instance.")

    def _validate_output_path(self, output_path: str) -> None:
        if not isinstance(output_path, str):
            raise TypeError("output_path must be a string.")

        if not output_path.strip():
            raise ValueError("output_path cannot be empty.")

    def _validate_existing_path(self, file_path: str) -> None:
        if not isinstance(file_path, str):
            raise TypeError("file_path must be a string.")

        if not file_path.strip():
            raise ValueError("file_path cannot be empty.")

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Source file does not exist: {file_path}")
