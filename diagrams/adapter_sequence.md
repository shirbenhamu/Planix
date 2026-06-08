# Adapter Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant C as Controller
    participant A as EngineAdapter
    participant P as Process
    participant E as Engine
    participant F as OutputFile

    User->>C: Request schedules (Run / Sync)
    C->>A: generate_from_model()
    Note over A: Prepare models (filter courses, build args)
    A->>P: Create and start background process
    A-->>C: Return immediately (non-blocking)
    P->>E: Run scheduling algorithm
    E->>F: Write schedules in real time
    loop While engine is running
        C->>F: Read available schedules
        F-->>C: Partial results
        C-->>User: Display schedules (live)
    end
    E-->>P: Algorithm finished
    P-->>A: Process complete