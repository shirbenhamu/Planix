import os
import itertools
import time
from typing import Dict, Tuple, Iterator, List
from src.output.i_output_generator import IOutputGenerator
from src.models.schedule import Schedule

class FileOutputWriter(IOutputGenerator):
    # נשארנו רק עם הטיימר - 20 שניות מקסימום
    def __init__(self, max_time_seconds: int = 20):
        self.max_time_seconds = max_time_seconds

    def write_schedules(
        self, 
        schedules_generators: Dict[Tuple[str, str], Iterator[Schedule]], 
        output_file_path: str
    ) -> None:
        os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

        period_keys = sorted(schedules_generators.keys())
        
        # מעלים ל-2000 כדי שיהיה למערכת מספיק צירופים לייצר עד שהטיימר חותך
        MAX_PER_PERIOD = 2000 
        capped_generators = [
            itertools.islice(schedules_generators[key], MAX_PER_PERIOD) 
            for key in period_keys
        ]

        start_time = time.time()

        with open(output_file_path, 'w', encoding='utf-8') as f:
            f.write("=== Complete Academic Year Schedules ===\n")
            f.write("Each option below represents a FULL schedule for all selected periods.\n\n")

            full_year_combinations = itertools.product(*capped_generators)
            count = 0
            
            for combo in full_year_combinations:
                count += 1
                f.write(f"--- FULL SYSTEM OPTION {count} ---\n")
                
                all_exams_with_info = []
                for i, sub_schedule in enumerate(combo):
                    semester, moed = period_keys[i]
                    for exam in sub_schedule.exams:
                        all_exams_with_info.append((exam, semester, moed))
                
                # מיון כרונולוגי של כל בחינות השנה
                all_exams_with_info.sort(key=lambda x: x[0].exam_date)

                # מעקב אחרי סמסטר ומועד יחד לצורך יצירת כותרות הפרדה
                current_period = ""
                
                for exam, sem, moed in all_exams_with_info:
                    # יצירת כותרת מופרדת גם לסמסטר וגם למועד (דרישה 2.3.3)
                    period_label = f"{sem} - {moed}"
                    if period_label != current_period:
                        f.write(f"  [{period_label}]\n")
                        current_period = period_label
                    
                    # השורה עצמה נשארת נקייה, ללא כפילות של המועד
                    f.write(
                        f"  Date: {exam.exam_date.strftime('%d-%m-%Y')} | "
                        f"Course: {exam.course.course_id} - {exam.course.course_name} | "
                        f"Instructor: {exam.course.instructor}\n"
                    )
                
                f.write("-" * 60 + "\n\n")

                # עצירת חירום יחידה מבוססת זמן
                if time.time() - start_time >= self.max_time_seconds:
                    f.write(f"\n[WARNING] Hard timeout reached ({self.max_time_seconds} seconds).\n")
                    f.write("Execution stopped dynamically to guarantee meeting performance requirements.\n")
                    break

            if count == 0:
                f.write("No valid full-year combinations could be formed.\n")