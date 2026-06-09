# Adapter Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    box Presenter Layer (MVP)
    participant AC as AppController
    participant CP as CalendarPresenter
    end
    participant A as EngineAdapter
    participant P as Process
    participant E as Engine
    participant F as OutputFile

    User->>AC: Request schedules (Run / Sync)
    AC->>A: generate_from_model()
    Note over A: Prepare models (filter courses, build args)
    A->>P: Create and start background process
    A-->>AC: Return immediately (non-blocking)
    AC->>CP: Switch to Monthly view, start live updates
    P->>E: Run scheduling algorithm
    E->>F: Write schedules in real time
    loop While engine is running
        CP->>F: Read available schedules
        F-->>CP: Partial results
        CP-->>User: Display schedules (live)
    end
    E-->>P: Algorithm finished
    P-->>A: Process complete