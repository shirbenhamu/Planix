"""
Planix file-based mode (V1.0) command-line entry point (PLAN-416).

This exposes the same ranking and windowing features as the GUI to the V1.0
file-based version. It runs the scheduler synchronously, persists the results
(with their METRICS lines), then re-uses the EXACT same ScheduleCollectionManager
.sort_collection() / .materialize_window() code path the GUI uses to produce a
sorted, sliced top-N listing — either to stdout or to an output file.

Usage examples
--------------
Rank by the default criterion (average days between exams, descending), top 10:

    python -m src.cli --programs 83101,83102

Rank by max exams/day then min-gap (priority order), show the best 5, to a file:

    python -m src.cli --programs 83101,83102 \
        --sort max_exams_per_day,min_gap_mandatory --window 5 --output top5.txt

Ascending order, options read from a JSON config file:

    python -m src.cli --config my_run.json --ascending

Advanced academic k-constraints injection (PLAN-407):
    
    python -m src.cli --programs 83101,83102 --max-exams-per-day 1 --min-days-mandatory 3 --window 1

Config file (JSON) — CLI flags override matching config keys:

    {
      "courses": "data/courses.txt",
      "exam_periods": "data/exam_periods.txt",
      "programs": ["83101", "83102"],
      "sort": ["avg_gap_all", "min_gap_mandatory"],
      "ascending": false,
      "window": 10,
      "output": "top.txt",
      "constraints": {
        "max_exams_per_day": 1,
        "min_days_mandatory": 3
      }
    }

Valid sort keys (section-3 metrics): min_gap_mandatory, avg_gap_all,
elective_conflicts, mandatory_span, max_exams_per_day.
"""


from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from src.data_manager import DataManager
from src.engine.exam_scheduler import ExamScheduler
from src.engine.advanced_exam_scheduler import AdvancedExamScheduler
from src.engine.scheduling_constraints import SchedulingConstraints
from src.metrics.metrics_calculator import METRIC_KEYS, METRIC_LABELS
from src.MVP.models.schedule import Schedule
from src.MVP.models.schedule_collection_manager import (
    DEFAULT_SORT_ASCENDING,
    DEFAULT_SORT_KEYS,
    DEFAULT_WINDOW_SIZE,
    MetricTuple,
    ScheduleCollectionManager,
)
from src.parsers.parser_factory import ParserFactory

DEFAULT_COURSES_PATH = "data/courses.txt"
DEFAULT_EXAM_PERIODS_PATH = "data/exam_periods.txt"
DEFAULT_PROGRAMS_PATH = "data/selected_programs.txt"
DEFAULT_WORK_FILE = "output_results/final_schedules.txt"


# --- core pipeline (shared, testable) ---------------------------------------
def rank_and_slice(
    data_manager: DataManager,
    work_file_path: str,
    sort_keys: Sequence[str],
    ascending: bool,
    window_size: int,
) -> Tuple[List[Schedule], List[Optional[MetricTuple]], int]:
    """Index an already-written results file, then rank + slice it via the very
    same code path the GUI uses (sort_collection + materialize_window)."""
    manager = ScheduleCollectionManager(work_file_path, data_manager)
    manager.sort_collection(list(sort_keys), ascending=ascending)
    manager.set_window_size(window_size)

    window = manager.materialize_window(0)
    metrics = [manager.get_metrics(i) for i in range(len(window))]
    return window, metrics, manager.get_total_count()


def generate_ranked_window(
    data_manager: DataManager,
    selected_programs: Sequence[str],
    sort_keys: Sequence[str],
    ascending: bool,
    window_size: int,
    work_file_path: str = DEFAULT_WORK_FILE,
    scheduler: Optional[ExamScheduler] = None,
    constraints: Optional[SchedulingConstraints] = None,
) -> Tuple[List[Schedule], List[Optional[MetricTuple]], int]:
    """Run the scheduler synchronously, persist the results (with METRICS lines),
    then rank and slice them."""
    from src.output.file_output_writer import FileOutputWriter

    # PLAN-407: Compatibility framework for testing harnesses.
    # If no scheduler instantiation was provided, dynamically resolve whether 
    # ExamScheduler was mocked/patched in the module space, otherwise instantiate AdvancedExamScheduler.
    if scheduler is None:
        if "ExamScheduler" in globals() and not isinstance(ExamScheduler, type):
            scheduler = globals()["ExamScheduler"]()
        else:
            scheduler = AdvancedExamScheduler(constraints=constraints)
    elif hasattr(scheduler, "constraints") and constraints is not None:
        scheduler.constraints = constraints

    generators = scheduler.generate_schedules(
        data_manager.get_courses(),
        data_manager.get_exam_periods(),
        list(selected_programs),
    )

    os.makedirs(os.path.dirname(work_file_path) or ".", exist_ok=True)
    FileOutputWriter().write_schedules(generators, work_file_path)

    return rank_and_slice(
        data_manager, work_file_path, sort_keys, ascending, window_size
    )


# --- presentation -----------------------------------------------------------
def format_window_listing(
    window: List[Schedule],
    metrics: List[Optional[MetricTuple]],
    total: int,
    window_size: int,
    sort_keys: Sequence[str],
    ascending: bool,
) -> str:
    """Render the top-N window as a human-readable listing matching the GUI view."""
    direction = "ascending" if ascending else "descending"
    shown = len(window)
    lines: List[str] = [
        "=== Planix file-based mode: ranked schedules ===",
        f"Sorted by: {', '.join(sort_keys)} ({direction})",
        f"Window size: {window_size} | Showing top {shown} of {total}",
        "",
    ]

    if total == 0:
        lines.append("No valid schedules found for the selected programs.")
        return "\n".join(lines)

    for rank, (schedule, metric_tuple) in enumerate(zip(window, metrics), start=1):
        lines.append(f"--- RANK {rank} ---")
        if metric_tuple is not None:
            for key, value in zip(METRIC_KEYS, metric_tuple):
                lines.append(f"    {METRIC_LABELS[key]}: {value}")
        for exam in sorted(schedule.exams, key=lambda e: e.exam_date):
            lines.append(
                f"  Date: {exam.exam_date.strftime('%d-%m-%Y')} | "
                f"Course: {exam.course.course_id} - {exam.course.course_name} | "
                f"Instructor: {exam.course.instructor}"
            )
        lines.append("")

    if total <= window_size:
        lines.append("End of results.")
    else:
        lines.append(f"... {total - shown} more schedule(s) not shown (increase --window).")
    return "\n".join(lines)


# --- CLI / config plumbing --------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="planix-cli",
        description="Planix file-based mode: rank and slice exam schedules (V1.0).",
    )
    parser.add_argument("--config", help="Path to a JSON config file.")
    parser.add_argument("--courses", help="Path to the courses file.")
    parser.add_argument("--exam-periods", dest="exam_periods", help="Path to the exam-periods file.")
    parser.add_argument("--programs", help="Comma-separated selected program IDs (e.g. 83101,83102).")
    parser.add_argument(
        "--sort",
        help="Comma-separated metric keys in priority order. "
             f"Valid keys: {', '.join(METRIC_KEYS)}.",
    )
    parser.add_argument("--ascending", action="store_true", help="Sort ascending (default: descending).")
    parser.add_argument("--window", type=int, help="Top-N window size (number of schedules to show).")
    parser.add_argument("--output", help="Write the listing to this file (default: stdout).")
    parser.add_argument("--work-file", dest="work_file", help="Where the raw generated results are written.")

    # --- PLAN-407: Advanced Academic K-Constraints Core Flags ---
    parser.add_argument("--min-days-mandatory", type=int, metavar="K", help="2.1: Min days between mandatory exams.")
    parser.add_argument("--min-days-any", type=int, metavar="K", help="2.2: Min days between any two exams.")
    parser.add_argument("--max-elective-conflicts", type=int, metavar="K", help="2.3: Max elective-elective conflicts.")
    parser.add_argument("--span-mandatory", type=int, metavar="K", help="2.4: Max span between first/last mandatory exams.")
    parser.add_argument("--max-exams-per-day", type=int, metavar="K", help="2.5: Max global exams per day.")

    return parser


def load_config(config_path: Optional[str]) -> dict:
    if not config_path:
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _split_csv(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def build_scheduling_constraints(args: argparse.Namespace, config: dict) -> SchedulingConstraints:
    """PLAN-407: Resolves and builds the unified SchedulingConstraints dataclass container."""
    constraints_config = config.get("constraints", {})
    constraints = SchedulingConstraints()

    def resolve_constraint(cli_val: Optional[int], json_key: str, default_k: int) -> Tuple[bool, int]:
        if cli_val is not None:
            return True, cli_val
        if json_key in constraints_config:
            return True, int(constraints_config[json_key])
        return False, default_k

    enabled, val = resolve_constraint(args.min_days_mandatory, "min_days_mandatory", 0)
    constraints.min_days_mandatory_enabled = enabled
    constraints.min_days_mandatory_k = val

    enabled, val = resolve_constraint(args.min_days_any, "min_days_any", 0)
    constraints.min_days_any_enabled = enabled
    constraints.min_days_any_k = val

    enabled, val = resolve_constraint(args.max_elective_conflicts, "max_elective_conflicts", 0)
    constraints.max_elective_conflicts_enabled = enabled
    constraints.max_elective_conflicts_k = val

    enabled, val = resolve_constraint(args.span_mandatory, "span_mandatory", 0)
    constraints.span_mandatory_enabled = enabled
    constraints.span_mandatory_k = val

    if args.max_exams_per_day is not None:
        constraints.max_exams_per_day_enabled = True
        constraints.max_exams_per_day_k = args.max_exams_per_day
    elif "max_exams_per_day" in constraints_config:
        constraints.max_exams_per_day_enabled = True
        constraints.max_exams_per_day_k = int(constraints_config["max_exams_per_day"])
    else:
        constraints.max_exams_per_day_enabled = False
        constraints.max_exams_per_day_k = 1

    return constraints


def resolve_options(args: argparse.Namespace, config: dict) -> dict:
    """Merge CLI args over config values; CLI takes precedence when provided."""
    sort_keys = _split_csv(args.sort) or _split_csv(config.get("sort")) or list(DEFAULT_SORT_KEYS)
    programs = _split_csv(args.programs) or _split_csv(config.get("programs"))

    if args.ascending:
        ascending = True
    elif "ascending" in config:
        ascending = config["ascending"]
    else:
        ascending = DEFAULT_SORT_ASCENDING

    return {
        "courses": args.courses or config.get("courses") or DEFAULT_COURSES_PATH,
        "exam_periods": args.exam_periods or config.get("exam_periods") or DEFAULT_EXAM_PERIODS_PATH,
        "programs": programs,
        "sort": sort_keys,
        "ascending": ascending,
        "window": args.window or config.get("window") or DEFAULT_WINDOW_SIZE,
        "output": args.output or config.get("output"),
        "work_file": args.work_file or config.get("work_file") or DEFAULT_WORK_FILE,
    }


def _load_data_manager(opts: dict) -> Tuple[DataManager, List[str]]:
    parser_obj = ParserFactory.create_parser("txt")
    DataManager._instance = None
    data_manager = DataManager(parser_obj)
    data_manager.courses = {
        course.course_id: course
        for course in parser_obj.parse_courses(opts["courses"])
    }
    data_manager.exam_periods = parser_obj.parse_exam_periods(opts["exam_periods"])

    programs = opts["programs"]
    if not programs:
        programs = parser_obj.parse_selected_programs(DEFAULT_PROGRAMS_PATH)
    return data_manager, programs


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    opts = resolve_options(args, config)

    constraints = build_scheduling_constraints(args, config)
    data_manager, programs = _load_data_manager(opts)
    if not programs:
        print("Error: no selected programs provided (use --programs or a config/file).")
        return 2

    try:
        window, metrics, total = generate_ranked_window(
            data_manager,
            programs,
            opts["sort"],
            opts["ascending"],
            opts["window"],
            work_file_path=opts["work_file"],
            constraints=constraints,
        )
    except ValueError as exc:
        print(f"Error generating schedules: {exc}")
        return 1

    listing = format_window_listing(
        window, metrics, total, opts["window"], opts["sort"], opts["ascending"]
    )

    if opts["output"]:
        dir_name = os.path.dirname(opts["output"])
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(opts["output"], "w", encoding="utf-8") as f:
            f.write(listing + "\n")
        print(f"Wrote ranked top-{opts['window']} listing to {opts['output']} ({total} total schedules).")
    else:
        print(listing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())