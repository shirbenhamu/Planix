# TextFileParser class inherits from BaseParser
# Is going to implement the parse method to read data from a text file and convert it
# into a format that can be used by the scheduling engine. It will also handle any
# specific parsing logic related to the structure of the text file, such as delimiters,
# whitespace, etc.
# 
# Will read Programs, Dates and courses files and convert them into a format that can be used by the scheduling engine.

from typing import List
from datetime import datetime
from src.parsers.base_parser import BaseParser
from src.models.course import Course, ProgramCourseInfo
from src.models.exam_period import ExamPeriod, ExcludedDate

class TextFileParser(BaseParser):

    # Helper method to read the content of a text file and split it into records based on the '$$$$' delimiter
    def extract_records(self, file_path: str) -> List[str]:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                return [record.strip() for record in content.split('$$$$') if record.strip()]
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: File {file_path} not found.")
            


    # Parses the selected programs from a text file, where the programs are expected to be separated by commas
    def parse_selected_programs(self, file_path: str) -> List[str]:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                if not content:
                    return []
                programs = [p.strip() for p in content.split(',')]
                if len(programs) > 5:
                    raise ValueError("Error: More than 5 programs selected. Please select up to 5 programs.")
                if len(set(programs)) != len(programs):
                    raise ValueError("Error: Duplicate program IDs found.")
                for prog in programs:
                    if not (prog.isdigit() and len(prog) == 5):
                        raise ValueError(f"Error: Invalid program ID '{prog}'. Program IDs should be 5-digit numbers.")
                return programs
        except FileNotFoundError:
            raise FileNotFoundError(f"Error: File {file_path} not found.")
        except ValueError as e:
            raise ValueError(f"Error parsing selected programs: {e}")



    # Parses courses from a text file, where each course record is separated by '$$$$' and contains lines for course details and program info
    def parse_courses(self, file_path: str) -> List[Course]:
        records = self.extract_records(file_path)
        courses = []

        VALID_EVALUATION_METHODS = ['Exam', 'Project']
        VALID_SEMESTERS = ['FALL', 'SPRI', 'SUMM']
        VALID_REQUIREMENTS = ['Mandatory', 'Elective', 'Obligatory']

        for record in records:
            lines = [line.strip() for line in record.splitlines() if line.strip()]
            if not lines:
                continue
            
            if len(lines) < 4:
                raise ValueError(f"Error: Invalid course format in record: {lines}. Each course must have at least 4 lines for course details.")
            
            course_name = lines[0]
            course_id = lines[1]
            instructor = lines[2]
            evaluation_method = lines[-1]

            program_info = []

            if evaluation_method not in VALID_EVALUATION_METHODS:
                raise ValueError(f"Error: Invalid evaluation method '{evaluation_method}' in record: {lines}. Valid methods are: {VALID_EVALUATION_METHODS}")

            if not course_id.strip():
                raise ValueError(f"Error: Course ID cannot be empty in record: {lines}.")

            if not course_name or not instructor:
                raise ValueError(f"Error: Course name and instructor cannot be empty in record: {lines}.")
            
            if len(lines) < 5:
                raise ValueError(f"Error: Course record must contain program information lines in record: {lines}.")

            for program_line in lines[3:-1]:
                parts = program_line.split(',')
                if len(parts) != 4:
                    raise ValueError(f"Error: Invalid program information format in record: {lines}. Each program line must contain exactly 4 comma-separated values.")
                
                program_id, year_str, semester, req = [p.strip() for p in parts]

                if not program_id.isdigit():
                    raise ValueError(f"Error: Invalid program ID '{program_id}' in record: {lines}. Program IDs should be numeric.")
                try:
                    year = int(year_str)
                    if year < 1 or year > 4:
                        raise ValueError(f"Error: Invalid year '{year}' in record: {lines}. Year should be between 1 and 4.")
                except ValueError:
                    raise ValueError(f"Error: Invalid year '{year_str}' in record: {lines}. Year should be an integer.")
                if semester not in VALID_SEMESTERS:
                    raise ValueError(f"Error: Invalid semester '{semester}' in record: {lines}. Valid semesters are: {VALID_SEMESTERS}")
                if req not in VALID_REQUIREMENTS:
                    raise ValueError(f"Error: Invalid requirement '{req}' in record: {lines}. Valid requirements are: {VALID_REQUIREMENTS}")
                
                program_info.append(ProgramCourseInfo(
                    program_id=program_id,
                    year=year,
                    semester=semester,
                    requirement=req
                    ))
            courses.append(Course(
                course_id=course_id,
                course_name=course_name,
                instructor=instructor,
                evaluation_method=evaluation_method,
                program_info=program_info
                ))
        return courses
    


    # Parses exam periods from a text file, where each period record is separated by '$$$$' and contains lines for period details and excluded dates
    def parse_exam_periods(self, file_path: str) -> List[ExamPeriod]:
        records = self.extract_records(file_path)
        periods = []
        date_format = "%d-%m-%Y"

        VALID_SEMESTERS = ['FALL', 'SPRI', 'SUMM']
        VALID_MOEDS = ['Aleph', 'Bet', 'Gimel']

        for record in records:
            lines = [line.strip() for line in record.split('\n') if line.strip()]
            if len(lines) < 2:
                continue

            header = [p.strip() for p in lines[0].split(',')]
            if len(header) != 2:
                raise ValueError(f"Error: Invalid exam period header format in record: {lines[0]}. Header must contain exactly 2 comma-separated values for semester and moed.")
            
            semester = header[0]
            moed = header[1]
            
            if semester not in VALID_SEMESTERS or moed not in VALID_MOEDS:
                raise ValueError(f"Error: Invalid semester '{semester}' or moed '{moed}' in record: {lines[0]}. Valid semesters are: {VALID_SEMESTERS} and valid moeds are: {VALID_MOEDS}")
            
            date_range = [p.strip() for p in lines[1].split(',')]
        
            try:
                start_date = datetime.strptime(date_range[0], date_format).date()
                end_date = datetime.strptime(date_range[1], date_format).date()

                if start_date > end_date:
                    raise ValueError(f"Error: Start date {start_date} cannot be after end date {end_date}.")

            except (ValueError, IndexError) as e:
                raise ValueError(f"Error: Invalid date format in exam period record: {lines[1]}. {e}")

            excluded_dates = []

            for excl_line in lines[2:]:
                clean_line = excl_line.lstrip('- ').strip()
                if not clean_line:
                    continue
                
                parts = [p.strip() for p in clean_line.split(',')]

                try:
                    first_part_words = parts[0].split()
                    if not first_part_words: 
                        continue
                    first_date_str = first_part_words[0]
                    excl_start = datetime.strptime(first_date_str, date_format).date()
                    if len(parts) > 1:
                        try:
                            second_date_words = parts[1].split()
                            second_date_str = second_date_words[0]
                            excl_end = datetime.strptime(second_date_str, date_format).date()
                            comment = " ".join(second_date_words[1:]) if len(second_date_words) > 1 else " ".join(parts[2:]) if len(parts) > 2 else None
                        except ValueError:
                            excl_end = excl_start
                            comment = parts[1]
                    else:
                        excl_end = excl_start
                        comment = " ".join(first_part_words[1:]) if len(first_part_words) > 1 else None

                    if excl_start > excl_end:
                        raise ValueError(f"Error: Excluded start date {excl_start} cannot be after end date {excl_end}.")

                    excluded_dates.append(ExcludedDate(start_date=excl_start, end_date=excl_end, comment=comment))
                except (ValueError, IndexError) as e:
                    raise ValueError(f"Error: Invalid excluded date format in exam period record: {excl_line}. {e}")

            periods.append(ExamPeriod(
                semester=semester,
                moed=moed,
                start_date=start_date,
                end_date=end_date,
                excluded_dates=excluded_dates
            ))
        return periods

