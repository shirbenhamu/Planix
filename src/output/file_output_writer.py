import os
import itertools
import time
from typing import Dict, Tuple, Iterator, List
from src.output.i_output_generator import IOutputGenerator
from src.MVP.models.schedule import Schedule

DEFAULT_MAX_RUNTIME_SECONDS = 29
MAX_PER_PERIOD = 2000

"""
This module responsible for generating a formatted text of the calculated exam schedules.
"""

class FileOutputWriter(IOutputGenerator):
    # Defines a safety timeout for generating the output
    def __init__(self, max_time_seconds: int = DEFAULT_MAX_RUNTIME_SECONDS):
        self.max_time_seconds = max_time_seconds

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

        # Limit each period's generator to a maximum number of items to prevent memory exhaustion
        capped_generators = [
            itertools.islice(schedules_generators[key], MAX_PER_PERIOD)
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

                # Write a visual separator after finishing one full-year option
                f.write("-" * 60 + "\n\n")

                # Check if the cumulative execution time has exceeded the allowed limit
                if time.time() - start_time >= self.max_time_seconds:
                    # Explain why the execution was terminated prematurely
                    f.write(
                        "Execution stopped dynamically to guarantee meeting performance requirements.\n")
                    break

            # If the loop finished without finding any results
            if count == 0 and not append:
                f.write("No valid full-year combinations could be formed.\n")
