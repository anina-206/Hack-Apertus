# Architecture

Everything below the browser runs in Docker on one machine (`make run`). The only external service is the
CSCS endpoint that serves Apertus v1.5 8B.

```mermaid
flowchart LR
    subgraph Browser
        UI["React web app<br/>Setup · Chat / call view · Feedback"]
        MIC["Microphone + speaker<br/>(Web Audio)"]
    end

    subgraph Docker["docker compose (make run)"]
        NGINX["frontend<br/>nginx :8080"]
        subgraph Backend["backend · Aegra :8000"]
            REST["REST API /api/v1<br/>(FastAPI, docs/api.md)"]
            AP["Agent Protocol<br/>graph `agent`"]
            GRAPH["LangGraph nodes<br/>analyze → interviewer<br/>→ (dialect) → report"]
            STT["Whisper STT<br/>faster-whisper, CPU"]
            TTS["Piper TTS<br/>CPU"]
            DB[("SQLite<br/>sessions, accounts")]
        end
        PG[("Postgres<br/>Aegra threads")]
    end

    APERTUS["Apertus v1.5 8B<br/>CSCS inference API"]
    DATA["FHGR datasets/<br/>rubric, postings, questions,<br/>annotated answers"]

    UI -- HTTP --> NGINX
    UI -- JSON --> REST
    MIC -- "audio (POST /transcribe)" --> STT
    TTS -- "audio (POST /speech)" --> MIC
    REST --> GRAPH
    AP --> GRAPH
    AP --- PG
    REST --- DB
    GRAPH -- "2 calls per answer" --> APERTUS
    DATA -. prompts, examples .-> GRAPH
```

## One answer, step by step

```mermaid
sequenceDiagram
    participant C as Candidate (browser)
    participant API as REST API
    participant G as LangGraph
    participant A as Apertus 8B

    C->>API: POST /sessions/{id}/answers (typed, or text from POST /transcribe)
    API->>G: answer + interview state
    G->>G: guardrails (crisis, manipulation) in code
    G->>A: call 1: analysis (11 criteria 1-4 or null, tip, flags) as JSON
    A-->>G: scores, short tip, follow-up?
    G->>G: phase logic in code: follow-up or next question
    G->>A: call 2: interviewer (next question, in the posting's persona)
    A-->>G: question
    opt Mundart
        G->>A: call 3: Standard German → dialect (with examples)
    end
    G-->>API: next question, tip (training mode), progress
    API-->>C: JSON; in hands-free mode the question is read aloud (POST /speech)
```
