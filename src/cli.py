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

    python -m src.cli --programs 83101,83102 \\
        --sort max_exams_per_day,min_gap_mandatory --window 5 --output top5.txt

Ascending order, options read from a JSON config file:

    python -m src.cli --config my_run.json --ascending

Config file (JSON) — CLI flags override matching config keys:

    {
      "courses": "data/courses.txt",
      "exam_periods": "data/exam_periods.txt",
      "programs": ["83101", "83102"],
      "sort": ["avg_gap_all", "min_gap_mandatory"],
      "ascending": false,
      "window": 10,
      "output": "top.txt"
    }

Valid sort keys (section-3 metrics): min_gap_mandatory, avg_gap_all,
elective_conflicts, mandatory_span, max_exams_per_day.
"""
from __future__ import annotations

import argparse
import json
import os
from typing import List, Optional, Sequence, Tuple

from src.data_manager import DataManager
from src.engine.exam_scheduler import ExamScheduler
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
    ascending,
    window_size: int,
) -> Tuple[List[Schedule], List[Optional[MetricTuple]], int]:
    """Index an already-written results file, then rank + slice it via the very
    same code path the GUI uses (sort_collection + materialize_window)."""
    manager = ScheduleCollectionManager(work_file_path, data_manager)
    # Same sort_collection code path as the GUI (PLAN-416).
    manager.sort_collection(list(sort_keys), ascending=ascending)
    manager.set_window_size(window_size)

    window = manager.materialize_window(0)
    metrics = [manager.get_metrics(i) for i in range(len(window))]
    return window, metrics, manager.get_total_count()


def generate_ranked_window(
    data_manager: DataManager,
    selected_programs: Sequence[str],
    sort_keys: Sequence[str],
    ascending,
    window_size: int,
    work_file_path: str = DEFAULT_WORK_FILE,
    scheduler: Optional[ExamScheduler] = None,
) -> Tuple[List[Schedule], List[Optional[MetricTuple]], int]:
    """Run the scheduler synchronously, persist the results (with METRICS lines),
    then rank and slice them. The output file is identical in shape to the GUI's,
    so both modes share ranking, windowing AND the on-disk format."""
    from src.output.file_output_writer import FileOutputWriter

    scheduler = scheduler or ExamScheduler()
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

    # Boundary indicator, mirroring the GUI's end-of-results behaviour.
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
    return parser


def load_config(config_path: Optional[str]) -> dict:
    if not config_path:
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _split_csv(value) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [part.strip() for part in str(value).split(",") if part.strip()]


def resolve_options(args: argparse.Namespace, config: dict) -> dict:
    """Merge CLI args over config values; CLI takes precedence when provided."""
    sort_keys = _split_csv(args.sort) or _split_csv(config.get("sort")) or list(DEFAULT_SORT_KEYS)
    programs = _split_csv(args.programs) or _split_csv(config.get("programs"))

    # --ascending is a store_true flag: only forces True when passed; otherwise
    # fall back to the config value, then to the documented default.
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
    # Reset the DataManager singleton so the CLI gets a clean instance.
    DataManager._instance = None
    data_manager = DataManager(parser_obj)
    data_manager.courses = {
        course.course_id: course
        for course in parser_obj.parse_courses(opts["courses"])
    }
    data_manager.exam_periods = parser_obj.parse_exam_periods(opts["exam_periods"])

    programs = opts["programs"]
    if not programs:
        # Fall back to the selected-programs file if none were given on the CLI.
        programs = parser_obj.parse_selected_programs(DEFAULT_PROGRAMS_PATH)
    return data_manager, programs


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    config = load_config(args.config)
    opts = resolve_options(args, config)

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
        )
    except ValueError as exc:
        print(f"Error generating schedules: {exc}")
        return 1

    listing = format_window_listing(
        window, metrics, total, opts["window"], opts["sort"], opts["ascending"]
    )

    if opts["output"]:
        os.makedirs(os.path.dirname(opts["output"]) or ".", exist_ok=True)
        with open(opts["output"], "w", encoding="utf-8") as f:
            f.write(listing + "\n")
        print(f"Wrote ranked top-{opts['window']} listing to {opts['output']} ({total} total schedules).")
    else:
        print(listing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
