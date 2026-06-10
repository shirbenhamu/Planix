# Planix

<img src="./images/logo.png" width="300">

GitHub repository: 

https://github.com/shirbenhamu/Planix.git

Jira Project Management:

https://shirbenhamo.atlassian.net/jira/software/projects/PLAN/boards/69?atlOrigin=eyJpIjoiNjYwMDQ0NDEyMjc5NDQwZTllNGM4ZmRhMmE4ZDc5ZmIiLCJwIjoiaiJ9

Presentation:

https://canva.link/tz751xhsp8qb7r7

UML Class diagram: In Folder "diagrams".

## Description

Planix is an exam scheduling system designed to help students in the Faculty of Engineering efficiently organize their examination timetables.

Planix version 2.0 includes advanced scheduling management capabilities, improved user experience, and a modern visual interface for planning exam schedules .

**Main Features:**

Interactive User Interface - The system provides dedicated input and output screens that allow users to easily manage, browse, and review possible exam schedules in a user-friendly and intuitive way.

Multi-Language Support - The application supports both English and Hebrew interfaces, allowing users to work comfortably in their preferred language.

Dark Mode & Light Mode - The system includes both day mode and night mode themes to improve accessibility and user comfort.

Flexible Calendar Views - Users can switch between monthly and yearly calendar displays for better visualization.

Data Management - Users can load, replace, and update course and exam period data files directly through the system interface without restarting the application.

Detailed Program Information - Each academic program displays its full list of courses, including semester, academic year, mandatory/elective classification, and evaluation method.

Exam Period Management - Users can view and edit exam period dates, including modifying semester exam ranges and excluding specific unavailable dates.

Comprehensive Schedule Details - Each generated schedule includes complete course information such as course number, course name, related academic program, and mandatory/elective status.

Exporting Results - Users can save selected exam schedules into external files in a readable and organized format.

Filtering and Future Expansion Support - The architecture supports future implementations of schedule filtering and sorting capabilities planned for version 3.0.

**Technical Highlights:**

MVP Architecture (Model–View–Presenter) - The software is built using the MVP architecture to reduce coupling between components, improving separation of concerns, maintainability, and testability.

Persistent Internal Caching - The application maintains an internal cache while it is running, enabling fast data reloading and minimizing unnecessary file I/O operations. This supports efficient Persistent Internal Data Handling and improves overall performance.

Responsive Performance - The system is optimized to provide fast and responsive user interaction without noticeable delays.

Scalable System Design - The architecture is designed to support future feature expansions and additional scheduling functionalities.

Agile Development Workflow - The project is managed using Agile methodologies alongside Git version control and Jira task management systems.

## Launching
| Command | Description | 
|---|---|
|`pip install -r requirements.txt` |Install Dependencies|
|`python -m src.main` |Run the system|
|`python -m pytest tests/tests_part_2 -q` |Run version 2.0 tests|
|`python -m pytest tests` |Run all the tests|

## Running Example

**Input page**

![pic1](./images/inputScreen.png)

![pic1](./images/inputScreen2.png)

**Monthly view output page**

![pic1](./images/monthlyView.png)

**Yearly view output page**

![pic1](./images/yearlyView.png)

**LightMode**

![pic1](./images/lightMode.png)

**Running the tests**

![pic1](./images/runningTests2.png)
