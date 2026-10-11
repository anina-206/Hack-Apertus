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
Browser (React) ──REST /api/v1──────────┐          Aegra server (port 8000, Postgres)
                                        ├──> same LangGraph nodes ──> Apertus v1.5 8B (CSCS)
Judge / Agent Chat UI ──Agent Protocol──┘    analysis call (11 criteria, JSON) -> interviewer call
                        graph `agent`
```

- **Two interfaces, one server.** As in the FHGR project template, [Aegra](https://github.com/aegra/aegra) serves
  the LangGraph graph `agent` (`src/backend/agent.py`, chat in / chat out, one thread = one interview) and our
  FastAPI app with the REST API for the frontend (`aegra.json` "http.app"). Both use the same nodes.

- **Two LLM calls per answer.** An *analysis call* scores the answer on the FHGR rubric
  (11 criteria from `datasets/rubric/criteria.json`, 1-4, `null` when the answer shows nothing about
  a criterion) and writes a short tip.
  An *interviewer call* then asks the next question or a follow-up.
- **The phase flow is decided in code, not by the LLM,** so every interview follows the same structure:
  intro (2 questions) → motivation (3) → strengths/weaknesses (3) → situational (3) → candidate questions → closing.
  That makes 12 main questions (FHGR: 10-15). Each phase allows at most one follow-up when an answer is vague.
- **A real company.** Each session uses an FHGR posting (fictional company, real occupation): the interviewer
  plays the posting's trainer, answers the candidate's questions as the company, and the analysis knows
  what a well-prepared candidate could know about it (`preparation`).
  In the candidate-questions phase the candidate asks and the interviewer answers; the question is
  analysed for `initiative`.
- **Robust JSON.** The model's output is repaired in code where possible (code fences, extra text,
  trailing commas, scores like `"3/4"`, …). Only unusable output is retried, up to 3 attempts.
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

## Agent Protocol (graph `agent`)

Any Agent Protocol / LangGraph SDK client can run an interview as a chat (e.g. the FHGR judge or the
[Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui) with deployment URL `http://localhost:8000`,
graph id `agent`). The first message starts the interview; every further message is one answer; at the end the
coach sends the goodbye and the final feedback. Optional setup in the run's `config.configurable`: `language`,
`occupation_id`, `posting_id`, `interviewer_style`, `mode` (default `rehearsal`), `candidate`, `focus`. Without
it, the language is guessed from the first message and the occupation is matched against the FHGR postings.

```bash
T=$(curl -s -X POST localhost:8000/threads -H 'Content-Type: application/json' -d '{}' | jq -r .thread_id)
curl -s -X POST localhost:8000/threads/$T/runs/wait -H 'Content-Type: application/json' \
  -d '{"assistant_id": "agent", "input": {"messages": [{"role": "user", "content": "Hallo, ich bewerbe mich als Informatikerin."}]}}' \
  | jq -r '.messages[-1].content'
```

`SERVER=uvicorn docker compose up` runs only the REST API (no Postgres), as a fallback.

## Project structure

| Path | What it is |
|---|---|
| `aegra.json` | Aegra config: graph `agent` + our FastAPI app |
| `src/backend/agent.py` | Graph `agent` for the Agent Protocol (chat in, chat out) |
| `src/backend/main.py` | FastAPI app: endpoints, error format, CORS |
| `src/backend/llm.py` | Apertus client (OpenAI-compatible) and LLM call counter |
| `src/backend/accounts.py` | Accounts, login tokens and saved interviews (SQLite) |
| `src/backend/config.py` | Setup options (languages, occupations, styles, modes) |
| `src/backend/interview/graph.py` | LangGraph turn: analysis → interviewer |
| `src/backend/interview/phases.py` | Phase logic and progress |
| `src/backend/interview/prompts.py` | Criteria, phase goals and all prompts |
| `src/backend/interview/parsing.py` | Robust JSON parsing and retries |
| `src/backend/interview/report.py` | Final report |
| `src/backend/interview/rubric.py` | FHGR rubric (11 criteria, 1-4) from `datasets/rubric/` |
| `src/backend/interview/safety.py` | Guardrails: crisis, distress, redirect |
| `src/backend/tests/` | Tests (fake LLM, no network) |
| `src/eval/run_interview.py` | Interview runner: plays a full interview against the API |
| `src/eval/bench_*.py` | Benchmarks on the FHGR data (see below) |
| `datasets/`, `fhgr/` | FHGR challenge data, slides and project template (copied unchanged) |
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

## Test a whole interview (interview runner)

`src/eval/run_interview.py` plays one complete interview against the running backend and checks the
LLM call gate. The candidate is scripted (fixed answers) or simulated by Apertus (`--candidate llm`).

```bash
make run    # in a second terminal:
docker compose exec backend python -m eval.run_interview --language de
docker compose exec backend python -m eval.run_interview --language fr --candidate llm --level weak
```

It prints every question, answer, tip and `llm_calls`, then a summary (average and maximum calls per
answer, follow-ups, JSON retries, latency, report score) and saves the run as JSON in `data/eval/runs/`.
Exit code 0 = gate OK, 1 = average ≥ 5 calls per answer, 2 = API error. Options: `--help`.

## Benchmarks (FHGR data)

Three benches measure the coach against the FHGR development data in `datasets/` (not the hidden
benchmark). They call Apertus through the backend code, so run them in the backend container.
Results are saved as JSON in `data/eval/bench/`.

```bash
# 1. Analysis call vs. 706 expert-annotated answers (MAE, agreement, follow-up precision/recall)
docker compose exec backend python -m eval.bench_answers --sample 120
docker compose exec backend python -m eval.bench_answers --sample 120 --variant baseline   # naive prompt

# 2. The 13 gold interviews through analysis + report vs. the reference feedback,
#    deterministic checks (du/Sie, language, empty texts, mojibake) and the LLM judge
docker compose exec backend python -m eval.bench_transcripts --repeat 2

# 3. FHGR scenarios as full interviews through the API, Apertus plays the candidate from the
#    FHGR profile; call gate, checks, consistency, score vs. persona level, scenario success criteria
docker compose exec backend python -m eval.bench_interviews --limit 6 --repeat 2
```

The judge (`src/eval/judge.py`) is an open model, e.g. Apertus 70B, set with `JUDGE_NAME` in `.env`.
It rates the final feedback on grounding, accuracy, actionable next steps, tone and language, using
the FHGR feedback rules. Without `JUDGE_NAME` the judge is skipped. The coach itself only uses Apertus 8B.

## Limitations

- Sessions are stored in SQLite (`data/sessions/sessions.db`, set by `SESSIONS_DB` in docker-compose) and survive a restart. Without `SESSIONS_DB` (tests, local dev) they are kept in memory.
- Running interviews are kept in memory and are lost when the backend restarts. Interviews of logged-in users are also saved in SQLite (Docker volume `storage`), so they stay readable, but an unfinished one cannot be continued after a restart.
- Accounts are minimal: username and password only, no e-mail, no password reset, no rate limiting.
- Swiss German (`gsw`) is a beta: the 8B model may mix in Standard German or spell inconsistently.
- The interviewer knows nothing about a specific company, so it answers candidate questions in general terms.

## Data

`data/` holds only small YAML configuration files (limit: 100 MB). `datasets/` and `fhgr/` are the FHGR
challenge material (synthetic, fictional persons and companies). No real personal data is stored; the optional
candidate details (first name, school level, interests) are kept with the session (SQLite / Postgres).
`data/` holds only small YAML configuration files (limit: 100 MB). Guests leave no data on the server. Only if someone creates an account, the username, a password hash and the
saved interviews (including the optional candidate details) are stored in `storage/app.db`. Use fake data in demos.

## Hack Apertus

- Challenges and judging criteria: [Getting Started guide](https://hackapertus.notion.site/getting-started-guide-onlinehack)
- Submission: http://hackapertus.ch/online-hack/submissions (not on Devpost)
- Licence: all Hack Apertus projects are open source, see [Terms & Conditions](https://hackapertus.ch/terms-and-conditions) (6. What you build is open source)
- Questions: Discord or hello@hackapertus.ch
