from __future__ import annotations

import os
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.data_manager import DataManager
from src.metrics.metrics_calculator import (
    METRIC_KEYS,
    METRICS_LINE_PREFIX,
    parse_metrics_line,
)
from src.MVP.models.course import Course
from src.MVP.models.schedule import Schedule, ScheduledExam

# Each index entry is a schedule's byte offset paired with its five parsed
# metric values (or None when the block predates / lacks a METRICS line).
MetricTuple = Tuple[float, ...]
IndexEntry = Tuple[int, Optional[MetricTuple]]

# Default sort policy (PLAN-413): when the user has not explicitly chosen a sort,
# schedules are ranked by the AVERAGE number of days between exams (metric 3.2),
# descending. This is the documented, agreed default so the very first window the
# user sees already reflects a meaningful ranking. A user-selected sort overrides
# it for the rest of the session.
DEFAULT_SORT_KEYS: Tuple[str, ...] = ("avg_gap_all",)
DEFAULT_SORT_ASCENDING: bool = False

# Top-N window policy (PLAN-414): how many full schedules are materialized into
# RAM at once. The rest of the (possibly millions of) results stay as lightweight
# (offset, metric_tuple) index entries until their window is requested.
DEFAULT_WINDOW_SIZE: int = 10

#   Memory-efficient index manager for schedules exported to a text file by the engine.


class ScheduleCollectionManager:
    """
    The manager scans the file once to store byte offsets for each schedule block
    and reads only the active schedule block on demand.
    """

    _HEADER_MARKER = b"--- FULL SYSTEM OPTION "
    _SEPARATOR_MARKER = b"-" * 60
    _METRICS_MARKER = (METRICS_LINE_PREFIX + "|").encode("utf-8")
    _EXAM_LINE_PATTERN = re.compile(
        r"^\s*Date:\s*(?P<date>\d{2}-\d{2}-\d{4})\s*\|\s*"
        r"Course:\s*(?P<course_id>[^|]+?)\s*-\s*(?P<course_name>[^|]+?)\s*\|\s*"
        r"Instructor:\s*(?P<instructor>.*)$"
    )

    #  The constructor initializes the manager with the output file path and a reference to the data manager for course lookups.
    def __init__(
        self,
        output_file_path: str,
        data_manager: DataManager,
        lock: Optional[threading.Lock] = None,
    ):
        self._output_file_path = self._validate_output_file_path(
            output_file_path)
        self._data_manager = self._validate_data_manager(data_manager)
        self._course_lookup: Dict[str, Course] = {}
        self._lock = lock or threading.Lock()
        # Sparse index: holds ONLY (byte_offset, metric_tuple) per schedule —
        # never the schedule body — so memory stays flat for millions of results.
        self._offsets: List[IndexEntry] = []
        self._scan_position: int = 0
        self._current_index: int = 0
        self.total_schedules: int = 0
        self.snapshot_mode = False
        # Active sort order as a list of (metric_position, ascending) in priority
        # order, or None when the index is in natural (file) order. PLAN-412 reads
        # this to keep newly-indexed blocks ordered during snapshot generation.
        self._sort_spec: Optional[List[Tuple[int, bool]]] = None
        # True once the user explicitly picks a sort; the default sort is then
        # never auto-applied again for the rest of the session (PLAN-413/498).
        self._user_sorted: bool = False
        # Top-N window state (PLAN-414): only window_size schedules are ever held
        # in RAM at once; _window_start is the index of the first one shown.
        self._window_size: int = DEFAULT_WINDOW_SIZE
        self._window_start: int = 0
        self._build_index()

    #  The _build_index method scans the output file for schedule blocks and stores their byte offsets for quick access.
    def _build_index(self) -> None:
        # Snapshot mode ON = engine is still generating, so stop scanning the output file after a fixed
        # point (output file size after 0.5 seconds) to allow the UI to access some schedules
        # as we are generating the rest in the background without waiting for the entire generation to complete.
        if self.snapshot_mode:
            return

        with self._lock:
            if not os.path.exists(self._output_file_path):
                self.total_schedules = len(self._offsets)
                return

            file_size = os.path.getsize(self._output_file_path)
            if self._scan_position > file_size:
                self._offsets.clear()
                self._scan_position = 0
                self._current_index = 0

            # If we've already scanned the entire file, no need to scan again.
            # This allows the manager to be initialized before the engine starts writing and to pick up new schedules as they are generated.
            # The engine is idle here (snapshot_mode is off), so the file is
            # complete: a trailing header with no METRICS line is a finished
            # legacy/old-format block and is finalized with metrics=None.
            count_before = len(self._offsets)
            with open(self._output_file_path, "rb") as file_handle:
                self._scan_for_blocks(
                    file_handle, byte_limit=None, finalize_trailing_header=True
                )

            # Keep newly-indexed blocks ordered under the active sort (PLAN-412),
            # preserving the user's current position rather than jumping to top.
            if self._sort_spec is not None and len(self._offsets) != count_before:
                self._sort_offsets_locked(reset_to_top=False)

            # Apply the documented default ranking the first time results load
            # (PLAN-413), unless the user has already chosen a sort.
            self._apply_default_sort_if_needed_locked()

            self.total_schedules = len(self._offsets)
            if self.total_schedules == 0:
                self._current_index = 0
            elif self._current_index >= self.total_schedules:
                self._current_index = self.total_schedules - 1

    # The build_snapshot_index method is used when the engine is actively generating schedules
    # and writing to the output file. It performs a full scan of the current output file to build the index of
    # schedule offsets, allowing the UI to access schedules as they are generated without needing
    # to wait for the entire generation process to complete.
    def build_snapshot_index(self) -> None:
        self.snapshot_mode = True

        with self._lock:
            if not os.path.exists(self._output_file_path):
                self.total_schedules = 0
                return

            snapshot_file_size = os.path.getsize(self._output_file_path)

            # If the file was truncated or replaced, restart from the beginning.
            if self._scan_position > snapshot_file_size:
                self._offsets.clear()
                self._scan_position = 0
                self._current_index = 0

            # The engine is still writing, so a trailing header whose METRICS
            # line hasn't been flushed yet must NOT be finalized: we rewind to it
            # so the next poll picks up its metrics once the block is complete.
            count_before = len(self._offsets)
            with open(self._output_file_path, "rb") as file_handle:
                self._scan_for_blocks(
                    file_handle,
                    byte_limit=snapshot_file_size,
                    finalize_trailing_header=False,
                )

            # Re-sort the streamed-in blocks under the active sort (PLAN-412) so
            # the displayed window stays ordered as the engine keeps generating,
            # without re-running the engine and preserving the current position.
            if self._sort_spec is not None and len(self._offsets) != count_before:
                self._sort_offsets_locked(reset_to_top=False)

            # Apply the documented default ranking the first time results load
            # (PLAN-413), unless the user has already chosen a sort.
            self._apply_default_sort_if_needed_locked()

            self.total_schedules = len(self._offsets)
            if self.total_schedules == 0:
                self._current_index = 0
            elif self._current_index >= self.total_schedules:
                self._current_index = self.total_schedules - 1

    # Shared single-pass scanner used by both _build_index (engine idle, reads to
    # EOF) and build_snapshot_index (engine writing, reads up to a frozen size).
    # It records one (offset, metric_tuple) entry per schedule header and parses
    # the METRICS line that follows the exam body. Callers must hold self._lock.
    def _scan_for_blocks(
        self,
        file_handle,
        byte_limit: Optional[int],
        finalize_trailing_header: bool,
    ) -> None:
        file_handle.seek(self._scan_position)

        pending_offset: Optional[int] = None
        pending_metrics: Optional[MetricTuple] = None
        # Everything strictly before resume_position has been fully processed;
        # the next incremental scan restarts here.
        resume_position = self._scan_position

        while True:
            offset = file_handle.tell()
            if byte_limit is not None and offset >= byte_limit:
                break

            line = file_handle.readline()
            if not line:
                resume_position = file_handle.tell()
                break

            # A line spilling past the frozen snapshot boundary may be only
            # partially written; stop and reprocess it from its start next time.
            if byte_limit is not None and file_handle.tell() > byte_limit:
                resume_position = offset
                break

            if line.startswith(self._HEADER_MARKER):
                # A second header before a separator means the previous block was
                # never terminated (malformed/legacy); finalize it metrics-less.
                if pending_offset is not None:
                    self._append_block(pending_offset, pending_metrics)
                    resume_position = offset
                pending_offset = offset
                pending_metrics = None
                continue

            if pending_offset is None:
                continue

            # The METRICS line (when present) is written right before the
            # separator, so it is captured before the block is finalized.
            if line.lstrip().startswith(self._METRICS_MARKER):
                pending_metrics = self._parse_metrics_bytes(line)
                continue

            # The separator is the true block terminator in both the old and new
            # output formats — finalize the block here with whatever metrics we saw.
            if line.rstrip(b"\r\n") == self._SEPARATOR_MARKER:
                self._append_block(pending_offset, pending_metrics)
                resume_position = file_handle.tell()
                pending_offset = None
                pending_metrics = None

        # Resolve a header whose block never reached a separator.
        if pending_offset is not None:
            if finalize_trailing_header:
                # File is complete (engine idle): count the unterminated block.
                self._append_block(pending_offset, pending_metrics)
            else:
                # Engine still writing: rewind so the block is finalized once its
                # separator (and METRICS line) have been flushed.
                resume_position = pending_offset

        self._scan_position = resume_position

    # Appends one sparse-index entry, guarding against re-adding the same offset.
    def _append_block(self, offset: int, metric_tuple: Optional[MetricTuple]) -> None:
        if self._offsets and self._offsets[-1][0] == offset:
            return
        self._offsets.append((offset, metric_tuple))

    # Parses a raw METRICS line (bytes) into a tuple of five metric values.
    def _parse_metrics_bytes(self, line: bytes) -> Optional[MetricTuple]:
        try:
            return parse_metrics_line(line.decode("utf-8")).as_tuple()
        except (ValueError, UnicodeDecodeError):
            # A malformed/partial METRICS line should never sink the whole scan.
            return None

    # The following public methods allow navigation through the indexed schedules and retrieval of the active schedule on demand.
    def get_current_index(self) -> int:
        return self._current_index

    def get_total_count(self) -> int:
        self._build_index()
        return self.total_schedules

    # The next_schedule, prev_schedule, and jump_to_schedule methods update the current index while ensuring it stays within valid bounds.
    def next_schedule(self) -> bool:
        self._build_index()
        if self._current_index + 1 >= self.total_schedules:
            return False

        self._current_index += 1
        return True

    def prev_schedule(self) -> bool:
        self._build_index()
        if self._current_index <= 0:
            return False

        self._current_index -= 1
        return True

    def jump_to_schedule(self, index: int) -> bool:
        self._build_index()
        if not isinstance(index, int):
            raise TypeError("index must be an integer.")

        if index < 0 or index >= self.total_schedules:
            return False

        self._current_index = index
        return True

    # Re-orders the sparse index in place by one or more metrics, in priority
    # order (primary key first), descending by default (PLAN-411). This is a pure
    # in-memory operation on _offsets: no file I/O and no schedule materialization.
    #
    #   sort_keys: ordered list of metric keys (from METRIC_KEYS); the first is the
    #              primary sort key, the next is the tie-breaker, and so on.
    #   ascending: direction control, defaulting to descending for every key:
    #              * None / omitted -> all descending
    #              * bool           -> applied to every key
    #              * list[bool]     -> one flag per key (same length as sort_keys)
    #              * dict[str,bool] -> per-key flag; unlisted keys descend
    #
    # Schedules without parsed metrics (legacy blocks indexed as None) always sink
    # to the bottom, regardless of direction.
    def sort_collection(self, sort_keys, ascending=None) -> None:
        resolved = self._resolve_sort_spec(sort_keys, ascending)

        with self._lock:
            self._sort_spec = resolved
            # A user-selected sort overrides the default for the rest of the
            # session (PLAN-498) and jumps to the new best schedule (top).
            self._user_sorted = True
            self._sort_offsets_locked(reset_to_top=True)

    # Clears any active sort, leaving the index in its current order. Subsequent
    # incremental scans will no longer re-sort newly-indexed blocks. The default
    # sort is not re-applied, since the user has already taken control of sorting.
    def clear_sort(self) -> None:
        with self._lock:
            self._sort_spec = None
            self._user_sorted = True

    # Applies the documented default sort (PLAN-413) the first time the collection
    # is loaded, unless the user has already chosen a sort. Caller must hold the
    # lock. Once applied, _sort_spec is non-None and the PLAN-412 path keeps it
    # ordered as new blocks stream in.
    def _apply_default_sort_if_needed_locked(self) -> None:
        if self._user_sorted or self._sort_spec is not None or not self._offsets:
            return
        self._sort_spec = self._resolve_sort_spec(
            list(DEFAULT_SORT_KEYS), DEFAULT_SORT_ASCENDING
        )
        self._sort_offsets_locked(reset_to_top=True)

    # Sorts _offsets in place using the active _sort_spec. The caller MUST hold
    # self._lock. When reset_to_top is False the schedule currently being viewed
    # is kept selected by re-locating its byte offset after the reorder, so a
    # background re-sort during snapshot generation does not yank the user's view.
    def _sort_offsets_locked(self, reset_to_top: bool) -> None:
        if not self._offsets:
            self._current_index = 0
            return
        if self._sort_spec is None:
            if reset_to_top:
                self._current_index = 0
                self._window_start = 0
            return

        self._offsets.sort(key=self._build_sort_key(self._sort_spec))

        if reset_to_top:
            # A user-selected/default sort jumps to the new best (page 1).
            self._current_index = 0
            self._window_start = 0
        else:
            # A background re-sort (new schedules streaming in during generation,
            # or a refresh) keeps the user's PAGE position stable — page N always
            # means rank N, only the content at that page updates. The page number
            # changes only when the user navigates, never on its own. Just clamp.
            self._current_index = min(self._current_index, len(self._offsets) - 1)

    # Validates the requested keys/directions and resolves them into an ordered
    # list of (metric_position, ascending) pairs.
    def _resolve_sort_spec(self, sort_keys, ascending) -> List[Tuple[int, bool]]:
        if isinstance(sort_keys, str):
            raise TypeError("sort_keys must be a list of metric keys, not a single string.")

        keys = list(sort_keys)
        if not keys:
            raise ValueError("sort_keys must contain at least one metric key.")

        unknown = [key for key in keys if key not in METRIC_KEYS]
        if unknown:
            raise ValueError(
                f"Unknown metric key(s): {unknown}. Valid keys are: {list(METRIC_KEYS)}."
            )

        ascending_flags = self._resolve_ascending_flags(keys, ascending)
        return [
            (METRIC_KEYS.index(key), ascending_flags[position])
            for position, key in enumerate(keys)
        ]

    def _resolve_ascending_flags(self, keys, ascending) -> List[bool]:
        # Default: descending for every key.
        if ascending is None:
            return [False] * len(keys)

        if isinstance(ascending, bool):
            return [ascending] * len(keys)

        if isinstance(ascending, dict):
            return [bool(ascending.get(key, False)) for key in keys]

        flags = list(ascending)
        if len(flags) != len(keys):
            raise ValueError(
                "ascending list length must match sort_keys length "
                f"({len(flags)} != {len(keys)})."
            )
        if not all(isinstance(flag, bool) for flag in flags):
            raise TypeError("ascending list must contain only booleans.")
        return flags

    # Builds the key function for list.sort. Entries with metrics come first;
    # within them, descending keys are negated so a single ascending tuple sort
    # yields the requested per-key direction.
    def _build_sort_key(self, resolved: List[Tuple[int, bool]]):
        def sort_key(entry: IndexEntry):
            _offset, metric_tuple = entry
            has_metrics = metric_tuple is not None
            if not has_metrics:
                return (1, ())

            ordered_values = tuple(
                metric_tuple[position] if is_ascending else -metric_tuple[position]
                for position, is_ascending in resolved
            )
            return (0, ordered_values)

        return sort_key

    # The get_current_schedule method retrieves the currently active schedule by reading the corresponding block
    # from the output file and parsing it into a Schedule object.
    def get_current_schedule(self) -> Schedule:
        self._build_index()
        if self.total_schedules == 0:
            raise ValueError("No schedules are available in the collection.")

        if self._current_index < 0 or self._current_index >= self.total_schedules:
            raise IndexError("Current schedule index is out of range.")

        offset, _metrics = self._offsets[self._current_index]
        block_text = self._read_schedule_block(offset)
        return self._parse_schedule_block(block_text)

    # Returns the five metric values for the active schedule straight from the
    # sparse index (no file read, no schedule body materialization). None when
    # the block has no METRICS line (legacy/old-format output).
    def get_current_metrics(self) -> Optional[MetricTuple]:
        self._build_index()
        if self.total_schedules == 0:
            raise ValueError("No schedules are available in the collection.")
        if self._current_index < 0 or self._current_index >= self.total_schedules:
            raise IndexError("Current schedule index is out of range.")
        return self._offsets[self._current_index][1]

    # Returns the metric tuple for any indexed schedule by position.
    def get_metrics(self, index: int) -> Optional[MetricTuple]:
        self._build_index()
        if not isinstance(index, int):
            raise TypeError("index must be an integer.")
        if index < 0 or index >= self.total_schedules:
            raise IndexError("Schedule index is out of range.")
        return self._offsets[index][1]

    # ===== Top-N window: materialize only window_size schedules (PLAN-414) =====

    # Configures how many full schedules are loaded into RAM at once (e.g. 5/10).
    def set_window_size(self, size: int) -> None:
        if not isinstance(size, int) or isinstance(size, bool):
            raise TypeError("window size must be an integer.")
        if size <= 0:
            raise ValueError("window size must be a positive integer.")
        with self._lock:
            self._window_size = size

    def get_window_size(self) -> int:
        return self._window_size

    def get_window_start(self) -> int:
        return self._window_start

    # Materializes the window of up to window_size schedules beginning at
    # start_index (defaulting to the current window start), reading each block by
    # seeking directly to its byte offset — never scanning the whole file. The
    # remaining schedules stay as lightweight index entries, so peak memory is
    # bounded by window_size x average_schedule_size regardless of result count.
    def materialize_window(self, start_index: Optional[int] = None) -> List[Schedule]:
        self._build_index()

        with self._lock:
            if start_index is None:
                start_index = self._window_start
            if not isinstance(start_index, int) or isinstance(start_index, bool):
                raise TypeError("start_index must be an integer.")

            start = min(max(start_index, 0), self.total_schedules)
            end = min(start + self._window_size, self.total_schedules)
            self._window_start = start
            # Snapshot just the byte offsets while holding the lock; the actual
            # reads happen below WITHOUT the lock (_read_schedule_block re-locks).
            window_offsets = [self._offsets[i][0] for i in range(start, end)]

        schedules: List[Schedule] = []
        for offset in window_offsets:
            try:
                block_text = self._read_schedule_block(offset)
                schedules.append(self._parse_schedule_block(block_text))
            except ValueError:
                # A block still being flushed during snapshot generation is
                # skipped; it will materialize once complete on the next request.
                continue
        return schedules

    # ===== Refresh-feed mechanism (PLAN-415) ===================================

    # The core refresh primitive: ingest any newly generated blocks from disk
    # (NO engine run), re-rank the FULL _offsets collection under the active sort
    # so freshly discovered schedules are factored into the displayed results,
    # then lazily materialize only the active window batch. The active sort
    # criterion is reused automatically — the user never has to re-select it
    # (PLAN-505).
    def apply_sort_and_refresh(self, reset_to_top: bool = False) -> List[Schedule]:
        if not isinstance(reset_to_top, bool):
            raise TypeError("reset_to_top must be a boolean.")

        # Pull in new blocks. Snapshot scan while the engine writes, full scan
        # once it is idle; both append to _offsets without re-running the engine.
        if self.snapshot_mode:
            self.build_snapshot_index()
        else:
            self._build_index()

        # Force a full re-rank even when no new blocks were added. Manual refresh
        # jumps back to the current top-N window; background/auto refresh preserves
        # the user's page position.
        with self._lock:
            if self._sort_spec is not None:
                self._sort_offsets_locked(reset_to_top=reset_to_top)
            elif reset_to_top:
                self._current_index = 0
                self._window_start = 0

        return self.materialize_window(0 if reset_to_top else None)

    # Whether there are indexed schedules beyond the current window (used to keep
    # the "Next" action enabled / decide when to show "End of results").
    def has_more_after_window(self) -> bool:
        with self._lock:
            return (self._window_start + self._window_size) < self.total_schedules

    # Advances the display window to the next batch. Returns False when the
    # current window already reaches the end of the indexed collection.
    def advance_window(self) -> bool:
        self._build_index()
        with self._lock:
            next_start = self._window_start + self._window_size
            if next_start >= self.total_schedules:
                return False
            self._window_start = next_start
            self._current_index = next_start
            return True

    #  This method reads a schedule block from the output file based on its byte offset. It ensures that the block is fully written before returning its content.
    def _read_schedule_block(self, offset: int) -> str:
        with self._lock:
            with open(self._output_file_path, "rb") as file_handle:
                file_handle.seek(offset)
                block_lines: List[bytes] = []
                first_line = True
                block_closed = False

                while True:
                    line_offset = file_handle.tell()
                    line = file_handle.readline()
                    if not line:
                        break

                    # The block is considered closed when we encounter the next header marker or the separator marker,
                    # which indicates the end of the current schedule block. If we reach the end of the file without finding a closing marker,
                    # we assume that the block is still being written and raise an error.
                    if not first_line and line.startswith(self._HEADER_MARKER):
                        file_handle.seek(line_offset)
                        block_closed = True
                        break

                    block_lines.append(line)
                    if line.rstrip(b"\r\n") == self._SEPARATOR_MARKER:
                        block_closed = True

                    first_line = False

        if not block_closed:
            raise ValueError("Current schedule block is still being written.")

        return b"".join(block_lines).decode("utf-8")

    #  This method parses a schedule block into a Schedule object.
    def _parse_schedule_block(self, block_text: str) -> Schedule:
        scheduled_exams: List[ScheduledExam] = []

        # The method iterates through each line of the block, looking for lines that match the expected format for exam entries.
        for raw_line in block_text.splitlines():
            stripped_line = raw_line.strip()
            if not stripped_line.startswith("Date:"):
                continue

            match = self._EXAM_LINE_PATTERN.match(raw_line)
            if match is None:
                continue
            # The date is expected to be in the format "dd-mm-yyyy".
            # The course ID is extracted and used to look up the corresponding Course object from the data manager.
            exam_date = datetime.strptime(
                match.group("date"), "%d-%m-%Y").date()
            course_id = match.group("course_id").strip()
            course = self._resolve_course(course_id)

            scheduled_exams.append(
                ScheduledExam(course=course, exam_date=exam_date)
            )

        if not scheduled_exams:
            raise ValueError(
                "The current schedule block does not contain any exams.")

        return Schedule(exams=scheduled_exams)

    def _resolve_course(self, course_id: str) -> Course:
        if course_id not in self._course_lookup:
            self._course_lookup = {
             course.course_id: course
             for course in self._data_manager.get_courses()
        }
        try:
            return self._course_lookup[course_id]
        except KeyError as exc:
            raise ValueError(
                f"Course '{course_id}' could not be resolved from the data manager."
            ) from exc

    def _validate_output_file_path(self, output_file_path: str) -> str:
        if not isinstance(output_file_path, str):
            raise TypeError("output_file_path must be a string.")

        normalized_path = output_file_path.strip()
        if not normalized_path:
            raise ValueError("output_file_path cannot be empty.")

        return normalized_path

    def _validate_data_manager(self, data_manager: DataManager) -> DataManager:
        if not isinstance(data_manager, DataManager):
            raise TypeError("data_manager must be a DataManager instance.")

        return data_manager

    # Clears the cached offsets and resets the scanning state, allowing the manager to rebuild the index from scratch on the next access.
    # This is useful when the underlying data has changed significantly, such as after a new generation run, to ensure that the manager 
    # has an up-to-date view of the available schedules.
    def clear_cache(self) -> None:
        with self._lock:
            self._offsets.clear()
            self._scan_position = 0
            self._current_index = 0
            self.total_schedules = 0
            self.snapshot_mode = False
            self._window_start = 0
            # The active sort (default or user-selected) persists across a fresh
            # generation so the new results keep the same ordering (PLAN-413/498).
            print("[ScheduleCollectionManager] Cache cleared. Ready for fresh scan.")