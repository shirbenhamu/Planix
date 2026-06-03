from __future__ import annotations

import os
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional

from src.data_manager import DataManager
from src.MVP.models.course import Course
from src.MVP.models.schedule import Schedule, ScheduledExam

#   Memory-efficient index manager for schedules exported to a text file by the engine.


class ScheduleCollectionManager:
    """
    The manager scans the file once to store byte offsets for each schedule block
    and reads only the active schedule block on demand.
    """

    _HEADER_MARKER = b"--- FULL SYSTEM OPTION "
    _SEPARATOR_MARKER = b"-" * 60
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
        self._offsets: List[int] = []
        self._scan_position: int = 0
        self._current_index: int = 0
        self.total_schedules: int = 0
        self.snapshot_mode = False
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
            with open(self._output_file_path, "rb") as file_handle:
                file_handle.seek(self._scan_position)

                while True:
                    offset = file_handle.tell()
                    line = file_handle.readline()
                    if not line:
                        break

                    if line.startswith(self._HEADER_MARKER):
                        if not self._offsets or self._offsets[-1] != offset:
                            self._offsets.append(offset)
                # Update the scan position to the end of the file for the next incremental scan.
                self._scan_position = file_handle.tell()

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

            with open(self._output_file_path, "rb") as file_handle:
                file_handle.seek(self._scan_position)

                while file_handle.tell() < snapshot_file_size:
                    offset = file_handle.tell()
                    line = file_handle.readline()
                    if not line:
                        break

                    if file_handle.tell() > snapshot_file_size:
                        break

                    if line.startswith(self._HEADER_MARKER):
                        if not self._offsets or self._offsets[-1] != offset:
                            self._offsets.append(offset)

                self._scan_position = snapshot_file_size

            self.total_schedules = len(self._offsets)
            if self.total_schedules == 0:
                self._current_index = 0
            elif self._current_index >= self.total_schedules:
                self._current_index = self.total_schedules - 1

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

    # The get_current_schedule method retrieves the currently active schedule by reading the corresponding block
    # from the output file and parsing it into a Schedule object.
    def get_current_schedule(self) -> Schedule:
        self._build_index()
        if self.total_schedules == 0:
            raise ValueError("No schedules are available in the collection.")

        if self._current_index < 0 or self._current_index >= self.total_schedules:
            raise IndexError("Current schedule index is out of range.")

        block_text = self._read_schedule_block(
            self._offsets[self._current_index])
        return self._parse_schedule_block(block_text)

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