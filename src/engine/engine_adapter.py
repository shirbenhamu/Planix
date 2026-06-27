from __future__ import annotations

import os
from multiprocessing import Process, Queue, Value
from pathlib import Path
from typing import List, Optional

from src.data_manager import DataManager
from src.engine.advanced_exam_scheduler import AdvancedExamScheduler  # Imported our new advanced engine
from src.engine.scheduling_constraints import SchedulingConstraints  # Imported constraints class
from src.MVP.models.course import Course
from src.MVP.models.planix_model import PlanixModel
from src.output.file_output_writer import FileOutputWriter

# Adapter that bridges the MVP model layer to the advanced, constraint-aware scheduler.
class PlanixEngineAdapter:

    def __init__(self) -> None:
        self._worker_process: Optional[Process] = None
        # Separate handle for the lightweight "count the total" worker so it can
        # run alongside / independently of a normal generation run. Its result
        # comes back over an in-memory Queue (the total can be a huge arbitrary-
        # precision int, so a shared C integer would overflow) — no temp file.
        self._count_process: Optional[Process] = None
        self._count_queue = None
        self._last_total: Optional[int] = None
        # Deep-search scanned counter lives in shared memory (a plain int that
        # comfortably fits int64), updated live by the worker — also no file.
        self._deep_scanned = None

    # Builds the (courses, exam_periods, selected_programs, constraints) tuple the
    # scheduler workers need from the live model. Shared by every worker entry
    # point so they stay in lock-step on filtering and constraints.
    def _build_generation_inputs(self, model: PlanixModel):
        selected_programs = model.get_selected_programs()
        filtered_courses = self._filter_courses_by_selected_programs(
            model.data_manager.get_courses(),
            selected_programs,
        )
        exam_periods = list(model.data_manager.get_exam_periods())
        constraints = getattr(model, "constraints", SchedulingConstraints())
        return filtered_courses, exam_periods, selected_programs, constraints

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
        constraints: SchedulingConstraints,  # Injected constraints parameter as strictly the 6th element
    ) -> None:
        # Instantiating our new AdvancedExamScheduler with user-selected constraints
        scheduler = AdvancedExamScheduler(constraints=constraints)
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

        Converts the model state and its current active scheduling constraints into 
        the advanced scheduler's expected inputs, keeping file generation asynchronous.
        """
        self._validate_model(model)
        self._validate_output_path(output_path)

        model.is_generating = True

        filtered_courses, exam_periods, selected_programs, constraints = (
            self._build_generation_inputs(model)
        )

        # If skip_count > 0, the base output file must already exist
        if skip_count > 0 and not os.path.exists(output_path):
            raise FileNotFoundError(
                f"Cannot 'Load More', base schedule file does not exist at: {output_path}")
            
        # We run the generation in a separate process to avoid blocking the UI.
        # Explicit sequential binding matching the static worker definition signature perfectly.
        self._worker_process = Process(
            target=PlanixEngineAdapter._generate_and_write_worker,
            args=(filtered_courses, exam_periods, selected_programs, output_path, skip_count, constraints),
            daemon=True,
        )
        self._worker_process.start()
        return output_path

    # ===== Deep search: keep only the top-N best across a bounded scan =========

    @staticmethod
    def _deep_search_worker(
        filtered_courses: List[Course],
        exam_periods,
        selected_programs: List[str],
        constraints: SchedulingConstraints,
        sort_spec,
        top_n: int,
        max_scan,
        max_seconds,
        output_path: str,
        scanned_value,
    ) -> None:
        scheduler = AdvancedExamScheduler(constraints=constraints)

        def report(scanned: int) -> None:
            # Publish progress to shared memory (read live by the UI process).
            try:
                scanned_value.value = scanned
            except Exception:
                pass

        best, scanned = scheduler.find_best_schedules(
            filtered_courses, exam_periods, selected_programs,
            sort_spec=sort_spec, top_n=top_n, max_scan=max_scan, max_seconds=max_seconds,
            progress_callback=report,
        )
        # Persist only the top-N (best-first) — disk stays bounded by N.
        FileOutputWriter().write_schedule_list(best, output_path)
        report(scanned)

    def deep_search_from_model(
        self,
        model: PlanixModel,
        output_path: str,
        sort_spec,
        top_n: int,
        max_scan=None,
        max_seconds=None,
    ) -> str:
        """Launch a background deep search that streams full-year combinations
        (bounded by ``max_seconds`` and/or ``max_scan``), keeps only the
        ``top_n`` best for ``sort_spec``, and writes just those to
        ``output_path``. The scanned count is published in shared memory and
        read via ``read_deep_search_scanned()``."""
        self._validate_model(model)
        self._validate_output_path(output_path)

        model.is_generating = True
        filtered_courses, exam_periods, selected_programs, constraints = (
            self._build_generation_inputs(model)
        )
        self._deep_scanned = Value("q", 0)
        self._worker_process = Process(
            target=PlanixEngineAdapter._deep_search_worker,
            args=(filtered_courses, exam_periods, selected_programs, constraints,
                  sort_spec, top_n, max_scan, max_seconds, output_path, self._deep_scanned),
            daemon=True,
        )
        self._worker_process.start()
        return output_path

    def read_deep_search_scanned(self) -> int:
        """How many schedules the deep search has scanned so far (0 if none)."""
        value = self._deep_scanned
        try:
            return int(value.value) if value is not None else 0
        except Exception:
            return 0

    def cancel_active_worker(self) -> bool:
        """Forcibly stop the running background worker (e.g. a deep search the
        user cancelled). Returns True if a worker was terminated."""
        process = self._worker_process
        if process is None:
            return False
        try:
            if process.is_alive():
                process.terminate()
                process.join(timeout=2)
        except Exception:
            pass
        self._worker_process = None
        return True

    # ===== Total-count pre-pass (powers the "X remaining" indicator) ==========

    @staticmethod
    def _count_worker(
        filtered_courses: List[Course],
        exam_periods,
        selected_programs: List[str],
        constraints: SchedulingConstraints,
        result_queue,
    ) -> None:
        scheduler = AdvancedExamScheduler(constraints=constraints)
        try:
            total = scheduler.count_total_schedules(
                filtered_courses, exam_periods, selected_programs,
            )
        except Exception:
            # No valid schedules / bad inputs: report zero rather than crash.
            total = 0
        result_queue.put(total)

    def count_total_from_model(self, model: PlanixModel) -> None:
        """Launch a background pass that counts the TOTAL number of valid
        schedules; the result returns over an in-memory queue (read via
        ``read_total_count()``). Powers the 'X schedules remaining' indicator."""
        self._validate_model(model)

        filtered_courses, exam_periods, selected_programs, constraints = (
            self._build_generation_inputs(model)
        )
        self._count_queue = Queue()
        self._last_total = None
        self._count_process = Process(
            target=PlanixEngineAdapter._count_worker,
            args=(filtered_courses, exam_periods, selected_programs, constraints, self._count_queue),
            daemon=True,
        )
        self._count_process.start()

    def is_count_active(self) -> bool:
        if self._count_process is None:
            return False
        try:
            if self._count_process.is_alive():
                return True
            self._count_process = None
            return False
        except Exception:
            self._count_process = None
            return False

    def read_total_count(self) -> Optional[int]:
        """The total once the count worker has produced it, else None. Intended
        to be called after ``is_count_active()`` is False; the result is cached
        so repeated reads are cheap."""
        if self._last_total is not None:
            return self._last_total
        queue = self._count_queue
        if queue is None:
            return None
        try:
            # The worker has finished, so the value is already buffered — this
            # returns immediately; the timeout is only a safety net.
            self._last_total = queue.get(timeout=2.0)
        except Exception:
            self._last_total = None
        return self._last_total

    # This method allows the UI to check if an engine generation process is currently active
    def is_generation_active(self) -> bool:
        if self._worker_process is None:
            return False
        try:
            # Check if the process is still alive
            if self._worker_process.is_alive():
                return True
            else:
                # Process finished; clear the reference immediately so filter/search isn't blocked
                self._worker_process = None
                return False
        except Exception:
            # If there's any error checking the process, clear it and allow operations
            self._worker_process = None
            return False

    # This method allows the UI to clear the worker reference once it has detected that the process has finished,
    # ensuring that subsequent generation runs can be initiated without stale state interference.
    def clear_finished_worker(self) -> None:
        if self._worker_process is not None and not self._worker_process.is_alive():
            self._worker_process = None

    # This method allows exporting a single schedule to a new file, which can be used for "saving" a schedule from the UI.
    def export_active_schedule(
        self,
        source_path: str,
        destination_path: str,
        schedule_content: str,
    ) -> str:
        """Export a single schedule text payload to a new file path."""
        self._validate_existing_path(source_path)
        self._validate_output_path(destination_path)

        destination = Path(destination_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(schedule_content, encoding="utf-8")
        return destination_path

    # The following private methods are for internal validation and data transformation.
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