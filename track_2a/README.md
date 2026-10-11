# Schnupper Interview Coach

**Hack Apertus · Track 2A · FHGR: AI-Powered Job Interview Coach**

A practice job interview for school students (about 14-16) applying for an apprenticeship in Switzerland.
The candidate picks an occupation, a language and an interviewer style, answers questions in a chat,
gets a short tip after every answer, and receives a feedback report at the end.
All runtime inference uses **Apertus v1.5 8B**.

- **Languages:** German, French, Italian, and Swiss German (`gsw`, beta)
- **Occupations:** e.g. Informatiker/in EFZ, Kaufmann/-frau EFZ, Fachmann/-frau Gesundheit EFZ (from `data/occupations.yaml`)
- **Modes:** *training* (tip and scores after every answer) or *rehearsal* (feedback only at the end)
- **Interviewer styles:** friendly (du/tu) or strict (Sie/vous/Lei)

Team: Iago (backend), Anina (frontend)

## Run it

Requirements: Docker with Compose v2 and an Apertus API key from CSCS. No GPU and no local model weights are needed.
Apertus is called through the [CSCS LLM inference API](https://docs.cscs.ch/services/inference/api/#llm-inference-api-service).

```bash
cp .env.example .env      # fill in LLM_NAME, LLM_BASE_URL, LLM_API_KEY
make run                  # = docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:8080 |
| Backend API | http://localhost:8000/api/v1 |

`.env` needs these three variables (see `.env.example`):

```
LLM_NAME=swiss-ai/Apertus-v1.5-8B
LLM_BASE_URL=https://api.inference.cscs.ch/v1
LLM_API_KEY=<your CSCS key>
```

Without `.env` the services still start and `/api/v1/health` works, but every endpoint that needs Apertus
returns `502 LLM_UNAVAILABLE`.

Quick check without the web app:

```bash
curl localhost:8000/api/v1/health
curl -X POST localhost:8000/api/v1/sessions -H 'Content-Type: application/json' \
     -d '{"language": "de", "occupation_id": "informatiker_efz", "interviewer_style": "friendly", "mode": "training"}'
curl -X POST localhost:8000/api/v1/sessions/<session_id>/answers -H 'Content-Type: application/json' \
     -d '{"question_id": "q1", "text": "Ich bin Lara und baue gerne PCs zusammen."}'
curl localhost:8000/api/v1/sessions/<session_id>/report     # after the last answer
```

## How it works

```
Browser (React) ──> FastAPI backend ──> LangGraph turn ──> Apertus v1.5 8B (CSCS)
                                         │
                       analysis call (6 criteria, JSON) ─> interviewer call (next question)
```

- **Two LLM calls per answer.** An *analysis call* scores the answer from 1 to 5 on six criteria
  (`relevance`, `structure`, `examples`, `motivation`, `language`, `self_reflection`) and writes a short tip.
  An *interviewer call* then asks the next question or a follow-up.
- **The phase flow is decided in code, not by the LLM,** so every interview follows the same structure:
  intro (1 question) → motivation (2) → strengths/weaknesses (2) → situational (2) → candidate questions → closing.
  That makes 8 main questions. Each phase allows at most one follow-up when an answer is vague.
  In the candidate-questions phase the candidate asks and the interviewer answers (not scored).
- **Robust JSON.** The model's output is repaired in code where possible (code fences, extra text,
  trailing commas, scores like `"4/5"`, …). Only unusable output is retried, up to 3 attempts.
- **The report** is generated with one LLM call when first requested, then cached. Scores and the overall
  score are averages computed in code. The LLM writes the comments, strengths and improvement tips.
  Quotes used as evidence are kept only if the candidate really said them.

### LLM call budget (gate: average < 5 per answer)

| Step | Calls |
|---|---|
| Answer in a scored phase | 2 (max 4 with JSON retries) |
| Answer in the candidate-questions phase | 1 (0 if the candidate has no more questions) |
| Opening question | 1 |
| Final report | 1 (max 3 with JSON retries), once per session |

A full interview without retries is about 2 calls per answer. Every LLM call is logged as one JSON line
(`"event": "llm_call"`), and every answer logs its `calls_per_answer`:

```bash
docker compose logs backend | grep '"event": "answer"'
```

## API

The frontend and backend share the contract in [docs/api.md](docs/api.md): endpoints, JSON shapes, error codes.
All errors use `{"error": {"code": "...", "message": "..."}}`.

## Project structure

| Path | What it is |
|---|---|
| `src/backend/main.py` | FastAPI app: endpoints, error format, CORS |
| `src/backend/llm.py` | Apertus client (OpenAI-compatible) and LLM call counter |
| `src/backend/accounts.py` | Accounts, login tokens and saved interviews (SQLite) |
| `src/backend/config.py` | Setup options (languages, occupations, styles, modes) |
| `src/backend/interview/graph.py` | LangGraph turn: analysis → interviewer |
| `src/backend/interview/phases.py` | Phase logic and progress |
| `src/backend/interview/prompts.py` | Criteria, phase goals and all prompts |
| `src/backend/interview/parsing.py` | Robust JSON parsing and retries |
| `src/backend/interview/report.py` | Final report |
| `src/backend/tests/` | Tests (fake LLM, no network) |
| `frontend/` | React web app (see `frontend/README.md`) |
| `data/` | Occupations and interviewer styles (YAML) |
| `docs/` | API contract, diagrams |
| `technical_report.md` | Architecture, use of Apertus, evaluation, limitations |

## Development

Backend tests (Python 3.12):

```bash
pip install -r src/backend/requirements-dev.txt
pytest
```

Backend without Docker:

```bash
pip install -r src/backend/requirements.txt
PYTHONPATH=src uvicorn backend.main:app --reload --port 8000
```

Frontend dev server (http://localhost:5173): see `frontend/README.md`.

## Limitations

- Running interviews are kept in memory and are lost when the backend restarts. Interviews of logged-in users are also saved in SQLite (Docker volume `storage`), so they stay readable, but an unfinished one cannot be continued after a restart.
- Accounts are minimal: username and password only, no e-mail, no password reset, no rate limiting.
- Swiss German (`gsw`) is a beta: the 8B model may mix in Standard German or spell inconsistently.
- The interviewer knows nothing about a specific company, so it answers candidate questions in general terms.

## Data

`data/` holds only small YAML configuration files (limit: 100 MB). Guests leave no data on the server. Only if someone creates an account, the username, a password hash and the
saved interviews (including the optional candidate details) are stored in `storage/app.db`. Use fake data in demos.

## Hack Apertus

- Challenges and judging criteria: [Getting Started guide](https://hackapertus.notion.site/getting-started-guide-onlinehack)
- Submission: http://hackapertus.ch/online-hack/submissions (not on Devpost)
- Licence: all Hack Apertus projects are open source, see [Terms & Conditions](https://hackapertus.ch/terms-and-conditions) (6. What you build is open source)
- Questions: Discord or hello@hackapertus.ch
