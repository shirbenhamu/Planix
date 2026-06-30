# Planix

<img src="./images/logo.png" width="300">

GitHub repository: 

https://github.com/shirbenhamu/Planix.git

Jira Project Management:

https://shirbenhamo.atlassian.net/jira/software/projects/PLAN/boards/69?atlOrigin=eyJpIjoiNjYwMDQ0NDEyMjc5NDQwZTllNGM4ZmRhMmE4ZDc5ZmIiLCJwIjoiaiJ9

Presentation:

[https://canva.link/tz751xhsp8qb7r7](https://canva.link/0gfho7y1n4ir21z)

UML Class diagram: In Folder "diagrams".

## Description

Planix is an advanced exam scheduling system designed to help engineering faculties efficiently generate, evaluate, and manage examination timetables while satisfying complex academic constraints. 

Version 34.0 extends the scheduling engine with advanced optimization capabilities, Advanced Scheduling Constraints, Schedule Ranking & Quality Metrics, manual schedule editing, intelligent ranking mechanisms, holiday-aware scheduling, and external calendar integration. The system provides both a command-line interface and a GUI application, allowing users to generate, compare, modify, and export high-quality exam schedules.

## Main Features

**Advanced Scheduling Constraints -** Users can define additional scheduling constraints, including minimum gap between mandatory exams, minimum gap between all exams within the same academic program, maximum number of elective exam conflicts, maximum examination span for mandatory courses, maximum number of exams scheduled on the same day.

**Schedule Ranking & Quality Metrics -** Every generated schedule is evaluated using multiple quality metrics. Users can sort schedules according to one or more ranking criteria, allowing them to identify the most balanced examination timetable.

**Deep Search Optimization -** Planix introduces a background optimization engine capable of exploring a significantly larger solution space. During execution, the system continuously searches for better schedules while maintaining only the highest-ranked results in memory.

**Manual Schedule Editing -** Users can manually move exams using drag-and-drop. Every modification is validated against all scheduling constraints before being accepted, ensuring that manually edited schedules remain valid.

**Holiday-Aware Scheduling -** Users may select one or more religions before schedule generation. The system automatically retrieves official holiday dates and prevents exams from being scheduled on those days.

**Export Options -** Selected schedules can be exported either as text files, or standard iCalendar (.ics) files compatible with Google Calendar, Outlook, Apple Calendar, and other calendar applications.

**Flexible Calendar Views -** Schedules can be displayed using monthly and yearly calendar views for improved visualization.

**Multi-Language Support -** The application supports both Hebrew and English user interfaces.

**Dark Mode & Light Mode -** Day and night themes improve accessibility and user comfort.

**Dual Interface Support (GUI & CLI) -** planix supports both a modern Graphical User Interface (GUI) and a Command-Line Interface (CLI).

**Color-Coded Calendar Visualization -** The calendar provides a clear visual distinction between exam types. Mandatory course exams are displayed in one color, while elective course exams are displayed in a different color, allowing users to quickly identify the nature of each exam and better understand the overall schedule at a glance.

## Technical Highlights

**MVP Architecture (Model–View–Presenter) -** The software is built using the MVP architecture to reduce coupling between components, improving separation of concerns, maintainability, and testability.

**Advanced Scheduling Engine -** Version 4.0 introduces an extended scheduling engine capable of validating advanced constraints during schedule generation while maintaining high performance.

**Multi-Process Background Execution -** Computationally intensive scheduling operations execute in separate background processes, keeping the graphical interface fully responsive throughout schedule generation.

**Quality Metrics Engine -** Each generated schedule is automatically evaluated using multiple quality metrics without requiring additional schedule analysis.

**Efficient Result Management -** Schedules are indexed rather than fully loaded into memory, allowing efficient sorting and browsing of large result sets with minimal memory usage.

**Persistent Internal Caching -** The application maintains an internal cache while it is running, enabling fast data reloading and minimizing unnecessary file I/O operations. This supports efficient Persistent Internal Data Handling and improves overall performance.

**Responsive Performance -** The system is optimized to provide fast and responsive user interaction without noticeable delays.

**Scalable System Design -** The architecture is designed to support future feature expansions and additional scheduling functionalities.

**Agile Development Workflow -** The project is managed using Agile methodologies alongside Git version control and Jira task management systems.

## Launching
| Command | Description | 
|---|---|
|`pip install -r requirements.txt` |Install Dependencies|
|`python -m src.main` |Run the GUI version|
|`python -m src.cli --programs 83101,83102` |Run the file-based version with specific programs|
|`python -m src.cli --programs 83101,83102 --sort max_exams_per_day,min_gap_mandatory --window 5` |Run the file-based version with custom sorting - primary sort by maximum exams per day, then by minimum mandatory exam gap, showing only the top 5 results|
|`python -m src.cli --programs 83101,83102 --output my_results.txt` |Run the file-based version and save the output to a file|
|`python -m src.cli --programs 83101,83102 --ascending` |Run with ascending sorting (lowest values first)|
|`python -m src.cli --programs 83101,83102 --max-exams-per-day 1` |Run the file-based versionwith a constraint of at most 1 exam per day|
|`python -m src.cli --programs 83101,83102 --min-days-mandatory 3` |Run the file-based version with a minimum gap of 3 days between mandatory exams|
|`python -m src.cli --programs 83101,83102 --max-exams-per-day 1 --min-days-mandatory 3 --window 1` |Run the file-based version with multiple constraints simultaneously|
|`python -m src.cli --config my_run.json` |Run the file-based version using a JSON configuration file (all settings are defined in the file)|
|`python -m src.cli --config my_run.json --window 20 --ascending` |Run the file-based version using a configuration file while overriding settings with CLI arguments (CLI takes precedence over the config file)|
|`python -m src.cli --courses custom_courses.txt --exam-periods custom_dates.txt --programs 83101,83102` |Run the file-based version with custom input file paths|
|`python -m src.cli --programs 83101,83102 --sort max_exams_per_day,avg_gap_all --ascending --window 10 --max-exams-per-day 2 --min-days-mandatory 2 --output top_schedules.txt` |Run with all options together - custom sorting, constraints, and output to a file|
|`python -m pytest tests/tests_part_3 -q` |Run version 3.0 tests|
|`python -m pytest tests/tests_part_4 -q` |Run version 4.0 tests|
|`python -m pytest tests` |Run all the tests|

## Running Example

**Constraint Selection**

![pic1](./images/constraintSelection.png)

**Sort Order Selection**

![pic1](./images/sortOrderSelection.png)

**Manual Edit Feature**

![pic1](./images/manualEdit.png)

**Calendar Export**

![pic1](./images/calendarExport.png)

![pic1](./images/export.png)

**Religious Exclusions**

![pic1](./images/religiousExclusions.png)

**Advanced Search**

![pic1](./images/advancedSearch.png)

**file-based version (CLI)**

![pic1](./images/cli.png)


**Running the tests**

![pic1](./images/runningTests3.png)
