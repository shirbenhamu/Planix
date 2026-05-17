# Planix

GitHub repository: 

https://github.com/shirbenhamu/Planix.git

Jira Project Management:

https://shirbenhamo.atlassian.net/jira/software/projects/PLAN/boards/69?atlOrigin=eyJpIjoiNjYwMDQ0NDEyMjc5NDQwZTllNGM4ZmRhMmE4ZDc5ZmIiLCJwIjoiaiJ9

UML Class diagram:

https://lucid.app/lucidchart/5e0624da-5d3d-4cb0-92e7-47b7b6ca4a5f/edit?beaconFlowId=15FC1A3BBBF7DCDA&invitationId=inv_a936cf6e-3384-4679-9bd3-425eb9fd7ba1&page=0_0#

## Description

Planix is an exam scheduling system designed  to help students in the Faculty of Engineering efficiently organize their examination timetables.

Planix version 1.0 includes the base functionalities of the system and provides an automated solution for generating all possible exam schedule combinations without overlaps.

**Main Features:**

Data Processing - The system reads and processes data from three different input files:
A file containing all courses in the system
A file defining the exam period date range
A file containing the student’s selections of courses

Automatic Schedule Generation - The system creates all possible exam schedules while ensuring there are no conflicts between exams.

Organized Output - Each generated schedule clearly displays:
The exam date for each course
The number of the course
The lecturer’s name

Sorting and Classification - The generated schedules are automatically sorted by exam dates and separated into:
Fall Semester and Spring Semester
Moed A and Moed B exam sessions

Exporting Results - 
All generated schedules are exported into an external txt file in a clear and readable format.

**Technical Highlights:**

File-Based Architecture - The system is built around reading and processing structured data files as input.

Conflict Detection Algorithm - The scheduling mechanism checks for overlapping exams and guarantees only valid combinations are generated.

Automated Combination Generation - The software systematically creates all possible valid exam timetable options for the student.

## Launching
| Command | Description | 
|---|---|
|`` |Run the system |
|`` |Run the tests |

## Running Example

![pic1](./proof/1.png)



## Testing Framework

The architecture includes a comprehensive testing suite designed to validate individual component state machines and end-to-end integration boundaries. The suite consists of **31 test cases** built entirely on top of the `pytest` framework.

### Running All 31 Tests at Once
The project includes a root-level configuration file (`pytest.ini`) that points directly to the active test directories. To execute the entire test suite simultaneously from the root directory (`Planix`), open your terminal and run:

```bash
python -m pytest -v
