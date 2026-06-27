import os
import itertools
import time
from typing import Dict, Optional, Tuple, Iterator, List
from src.output.i_output_generator import IOutputGenerator
from src.MVP.models.schedule import Schedule
from src.metrics.metrics_calculator import MetricsCalculator, ScheduleMetrics, format_metrics_line

DEFAULT_MAX_RUNTIME_SECONDS = 29
MAX_PER_PERIOD = 2000

"""
This module responsible for generating a formatted text of the calculated exam schedules.
"""

class FileOutputWriter(IOutputGenerator):
    # Defines a safety timeout and per-period cap for generating the output.
    # Both default to the standard limits; "Load All" passes None for each to
    # compute every valid schedule with no time limit and no per-period cap.
    def __init__(
        self,
        max_time_seconds: Optional[int] = DEFAULT_MAX_RUNTIME_SECONDS,
        max_per_period: Optional[int] = MAX_PER_PERIOD,
    ):
        self.max_time_seconds = max_time_seconds
        self.max_per_period = max_per_period
        # Scores every full-year schedule at write time so the metrics can be
        # persisted next to it (PLAN-409) and parsed later without re-reading
        # the schedule body. Stateless, so a single shared instance is fine.
        self._metrics_calculator = MetricsCalculator()

    def write_schedules(
        self,
        schedules_generators: Dict[Tuple[str, str], Iterator[Schedule]],
        output_file_path: str,
        skip_count: int = 0,  
        append: bool = False
    ) -> None:
        # Create the target directory if it doesn't already exist
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        # Sort the period keys (Semester, Moed) to ensure a consistent processing order
        period_keys = sorted(schedules_generators.keys())

        # Limit each period's generator to a maximum number of items to prevent
        # memory exhaustion. max_per_period is None for "Load All", which streams
        # every valid schedule with no cap.
        if self.max_per_period is None:
            capped_generators = [schedules_generators[key] for key in period_keys]
        else:
            capped_generators = [
                itertools.islice(schedules_generators[key], self.max_per_period)
                for key in period_keys
            ]

        # Record the start time to monitor execution duration
        start_time = time.time()
        
        # Determine file mode: 
        # 'a' = "Load More"
        # 'w' = new generation
        mode = 'a' if append else 'w'

        with open(output_file_path, mode, encoding='utf-8') as f:
            # Write the file header only for new generations
            if not append:
                f.write("=== Complete Academic Year Schedules ===\n")
                f.write(
                    "Each option below represents a FULL schedule for all selected periods.\n\n")

            # Generate all possible full-year combinations
            full_year_combinations = itertools.product(*capped_generators)
            
            # Internal loop counter used for skipping already-generated schedules
            loop_index = 0
            # Continue numbering from previously generated results
            count = skip_count

            # Iterate through each full-year combination generated
            for combo in full_year_combinations:
                
                if loop_index < skip_count:
                    loop_index += 1
                    continue
                loop_index += 1
                
                count += 1
                f.write(f"--- FULL SYSTEM OPTION {count} ---\n")

                all_exams_with_info = []
                for i, sub_schedule in enumerate(combo):
                    semester, moed = period_keys[i]
                    for exam in sub_schedule.exams:
                        all_exams_with_info.append((exam, semester, moed))

                # Sort the entire year's exams by their date in ascending order
                all_exams_with_info.sort(key=lambda x: x[0].exam_date)

                # Initialize a variable to seperate a period
                current_period = ""

                # Iterate through the sorted exams to write them to the file
                for exam, sem, moed in all_exams_with_info:
                    # Define a label for the current semester and moed
                    period_label = f"{sem} - {moed}"
                    # Check if we have moved to a new period to print a sub-header
                    if period_label != current_period:
                        f.write(f"  [{period_label}]\n")
                        current_period = period_label

                    # Write the exam details
                    f.write(
                        f"  Date: {exam.exam_date.strftime('%d-%m-%Y')} | "
                        f"Course: {exam.course.course_id} - {exam.course.course_name} | "
                        f"Instructor: {exam.course.instructor}\n"
                    )

                # Persist the five section-3 metrics for this full-year option on
                # a dedicated METRICS line (PLAN-409). It sits between the exam
                # body and the separator so the values are guaranteed present
                # once a block is closed, and it is ignored by schedule-body
                # parsers (they only read "Date:" lines), keeping V1.0 intact.
                full_year_schedule = Schedule(
                    exams=[exam for exam, _, _ in all_exams_with_info]
                )
                metrics = self._metrics_calculator.compute(full_year_schedule)
                f.write(format_metrics_line(metrics) + "\n")

                # Write a visual separator after finishing one full-year option
                f.write("-" * 60 + "\n\n")

                # Check if the cumulative execution time has exceeded the allowed
                # limit. max_time_seconds is None for "Load All" — run to the end.
                if self.max_time_seconds is not None and time.time() - start_time >= self.max_time_seconds:
                    # Explain why the execution was terminated prematurely
                    f.write(
                        "Execution stopped dynamically to guarantee meeting performance requirements.\n")
                    break

            # If the loop finished without finding any results
            if count == 0 and not append:
                f.write("No valid full-year combinations could be formed.\n")

    def write_schedule_list(self, schedules_with_metrics, output_file_path: str) -> None:
        """Write an already-selected list of ``(Schedule, metrics_tuple)`` pairs
        (e.g. the deep-search top-N, best-first) in the standard block format so
        the ScheduleCollectionManager can read them. The precomputed metrics are
        reused — no recomputation for the kept set, which keeps finalize fast."""
        os.makedirs(os.path.dirname(output_file_path) or ".", exist_ok=True)
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("=== Complete Academic Year Schedules ===\n")
            f.write("Each option below represents a FULL schedule for all selected periods.\n\n")
            count = 0
            for schedule, metrics in schedules_with_metrics:
                count += 1
                f.write(f"--- FULL SYSTEM OPTION {count} ---\n")
                for exam in sorted(schedule.exams, key=lambda e: e.exam_date):
                    f.write(
                        f"  Date: {exam.exam_date.strftime('%d-%m-%Y')} | "
                        f"Course: {exam.course.course_id} - {exam.course.course_name} | "
                        f"Instructor: {exam.course.instructor}\n"
                    )
                f.write(format_metrics_line(ScheduleMetrics.from_iterable(metrics)) + "\n")
                f.write("-" * 60 + "\n\n")
            if count == 0:
                f.write("No valid full-year combinations could be formed.\n")
