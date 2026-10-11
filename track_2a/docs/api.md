# API contract - Schnupper Interview Coach

Version: v1 (draft, 2026-10-06)
Owners: Iago (backend), Anina (frontend)
Location in repo: `track_2a/docs/api.md`

This document is the single source of truth for how the frontend and backend talk.
If something changes, change it here first, then in the code.

---

## 1. Conventions

| Topic | Rule |
|---|---|
| Base URL | `http://localhost:8000/api/v1` |
| CORS | Allow origins `http://localhost:5173` (Vite dev server) and `http://localhost:8080` (nginx container) |
| Format | JSON only, UTF-8, `Content-Type: application/json` |
| Naming | `snake_case` for all keys |
| IDs | Strings (UUID), never numbers |
| Languages | `de`, `fr`, `it`, `gsw` (Swiss German, optional) |
| Time | ISO 8601 in UTC, e.g. `2026-10-09T14:03:00Z` |
| Scores | Integer 1-4 (FHGR: 1 Ungenügend … 4 Sehr gut), or `null` = not observed |
| Auth | None (local demo, no personal data stored) |

### Error format (all endpoints)

```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "No session with this id."
  }
}
```

| HTTP | `code` | When |
|---|---|---|
| 400 | `INVALID_REQUEST` | Missing or wrong field |
| 404 | `SESSION_NOT_FOUND` | Unknown `session_id` |
| 409 | `WRONG_QUESTION` | `question_id` is not the current question |
| 409 | `INTERVIEW_NOT_FINISHED` | Report requested too early |
| 409 | `INTERVIEW_FINISHED` | Answer sent after the end |
| 502 | `LLM_UNAVAILABLE` | Apertus did not answer or returned garbage |
| 500 | `INTERNAL_ERROR` | Unexpected backend bug (should not happen) |

---

## 2. Endpoints overview

| Method | Path | Purpose | LLM calls |
|---|---|---|---|
| GET | `/health` | Is the backend alive? | 0 |
| GET | `/config` | Occupations, languages, profiles for the setup screen | 0 |
| POST | `/sessions` | Start an interview, get the first question | 1 |
| POST | `/sessions/{session_id}/answers` | Send an answer, get the next question | 2 (max 4) |
| GET | `/sessions/{session_id}` | Current state (for page reload) | 0 |
| GET | `/sessions/{session_id}/report` | Final feedback report | 1 (max 3, once, then cached) |

Budget check: about 2 calls per answer + 1 for the report -> well below the limit of 5.
If the model returns unusable JSON, the call is retried (max 3 attempts), and every retry counts as a call:
an answer costs at most 4 (3 analysis + 1 interviewer). In the `candidate_questions` phase an answer costs 1,
or 0 if the candidate has no more questions. `meta.llm_calls` always shows the real number.

`POST /chat` also exists, for checking the Apertus connection only (dev, not used by the frontend).

---

## 3. Endpoint details

### GET `/health`

```json
{ "status": "ok", "model": "swiss-ai/Apertus-v1.5-8B" }
```

### GET `/config`

Everything the setup screen needs. The data comes from the YAML files in `data/`,
so the frontend never hardcodes occupations or profiles.

```json
{
  "languages": [
    { "code": "de", "label": "Deutsch" },
    { "code": "fr", "label": "Français" },
    { "code": "it", "label": "Italiano" },
    { "code": "gsw", "label": "Schwiizerdütsch (Beta)" }
  ],
  "occupations": [
    { "id": "informatiker_efz", "label": { "de": "Informatiker/in EFZ", "fr": "Informaticien/ne CFC", "it": "Informatico/a AFC" } },
    { "id": "kv_efz", "label": { "de": "Kaufmann/-frau EFZ", "fr": "Employé/e de commerce CFC", "it": "Impiegato/a di commercio AFC" } }
  ],
  "interviewer_styles": [
    { "id": "friendly", "label": { "de": "Freundlich", "fr": "Bienveillant", "it": "Cordiale" } },
    { "id": "strict", "label": { "de": "Streng", "fr": "Exigeant", "it": "Esigente" } }
  ],
  "modes": [
    { "id": "training", "description": "Short feedback after every answer" },
    { "id": "rehearsal", "description": "Realistic, feedback only at the end" }
  ]
}
```

### POST `/sessions`

Request:

```json
{
  "language": "de",
  "occupation_id": "informatiker_efz",
  "interviewer_style": "friendly",
  "mode": "training",
  "candidate": {
    "first_name": "Lara",
    "school_level": "Sek A",
    "interests": "Gamen, Velo, Computer zusammenbauen"
  }
}
```

`candidate` is optional and only used to personalise questions. Use fake data in demos.

`posting_id` is optional: an FHGR posting (`P-01` … `P-30`, listed in `GET /config` under `postings`).
It sets the company the interviewer works for and who the interviewer is. Without it, the default
posting of the occupation for that language is used (`data/occupations.yaml`).

`focus` is optional: up to 3 criterion ids (e.g. the last report's `next_practice`). The interviewer then
asks so that the candidate can practise these criteria. The feedback screen's "Genau das üben" button uses it.

Response `201`:

```json
{
  "session_id": "3f8a2c1e-6b1d-4b7e-9a51-2d3e4f5a6b7c",
  "phase": "intro",
  "progress": { "current": 1, "total": 12 },
  "question": {
    "id": "q1",
    "text": "Grüezi Lara! Erzähl mir doch zuerst etwas über dich."
  },
  "company": { "name": "Limmatcode GmbH", "place": "Zürich" },
  "interviewer": { "name": "Stefan Keller", "role": "Berufsbildner, Senior Software Engineer" }
}
```

`company` and `interviewer` come from the posting (`null` if there is none). In the `candidate_questions`
phase the interviewer answers as this company, using only the posting's facts.

### POST `/sessions/{session_id}/answers`

Request:

```json
{
  "question_id": "q1",
  "text": "Ich bin Lara, 15, und gehe in die Sek A in Wil. In meiner Freizeit baue ich gerne PCs zusammen."
}
```

Response `200` (interview continues):

```json
{
  "done": false,
  "phase": "motivation",
  "progress": { "current": 2, "total": 12 },
  "question": {
    "id": "q2",
    "text": "Spannend! Wie bist du darauf gekommen, Informatikerin zu werden?",
    "is_follow_up": false
  },
  "turn_feedback": {
    "short_tip": "Guter Einstieg! Nenne noch, warum dich gerade diese Firma interessiert.",
    "scores": { "clarity": 3, "relevance": 4, "motivation": 3, "self_reflection": null, "communication": 3,
                "concrete_examples": 2, "demeanor": null, "preparation": null, "goal_orientation": null,
                "difficult_questions": null, "initiative": null }
  },
  "meta": { "llm_calls": 2, "latency_ms": 4120 }
}
```

- `turn_feedback` is only present in `mode: "training"`. In `rehearsal` it is `null`.
  `scores` has all 11 criteria, each 1-4 or `null` (this answer showed nothing about it).
  `turn_feedback` is also `null` for courtesy replies ("Danke!"), for "no more questions" and if the
  analysis failed. A candidate's own question in `candidate_questions` is analysed (for `initiative`).
- `is_follow_up: true` means the interviewer digs deeper into the last answer instead of moving on.
- `question.guard` is only present when the guardrails answered (the interview stays at the same point,
  `progress` does not move):
  - `"crisis"`: the answer contained a clear sign of self-harm. Fixed text with Pro Juventute 147 and 144,
    no LLM call, no `turn_feedback`.
  - `"support"`: the analysis flagged distress. A warm reply, a hint to talk to a trusted person, an easier question.
  - `"redirect"`: manipulation attempt, off-topic, impolite or discriminatory answer. Calm, stays in role,
    asks the question again. Support and redirect happen at most once per question.
- `turn_feedback.problem_flags`: FHGR problem flags the analysis found (`distress_signal`,
  `manipulation_attempt`, `off_topic`, `inappropriate_tone`, `discriminatory`, `badmouthing`, `dishonesty`,
  `privacy_oversharing`), usually `[]`.
- `progress.current` counts main questions (12 in total). Follow-ups and the turns in the
  `candidate_questions` phase don't advance it, so it can stay the same for several turns.
- Question ids (`q1`, `q2`, ...) count every interviewer question, including follow-ups.

Response `200` (interview finished):

```json
{
  "done": true,
  "phase": "closing",
  "progress": { "current": 12, "total": 12 },
  "question": null,
  "closing_message": "Vielen Dank, Lara! Wir melden uns bald bei dir.",
  "turn_feedback": null,
  "meta": { "llm_calls": 1, "latency_ms": 2300 }
}
```

`closing_message` is either a fixed goodbye (candidate has no more questions, 0 calls) or the
interviewer's answer to the candidate's last question followed by a goodbye (1 call).

### GET `/sessions/{session_id}`

Lets the frontend restore the chat after a page reload.

```json
{
  "session_id": "3f8a2c1e-6b1d-4b7e-9a51-2d3e4f5a6b7c",
  "language": "de",
  "occupation_id": "informatiker_efz",
  "mode": "training",
  "done": false,
  "phase": "motivation",
  "progress": { "current": 2, "total": 12 },
  "history": [
    { "role": "interviewer", "question_id": "q1", "text": "Grüezi Lara! Erzähl mir doch zuerst etwas über dich." },
    { "role": "candidate", "question_id": "q1", "text": "Ich bin Lara, 15, ..." },
    { "role": "interviewer", "question_id": "q2", "text": "Spannend! Wie bist du darauf gekommen, ..." }
  ],
  "current_question_id": "q2"
}
```

After the interview, `history` ends with the closing message (`question_id: null`) and
`current_question_id` is `null`.

### GET `/sessions/{session_id}/report`

Only works when `done: true`, otherwise `409 INTERVIEW_NOT_FINISHED`.
Generated with one LLM call the first time, then cached.

```json
{
  "session_id": "3f8a2c1e-6b1d-4b7e-9a51-2d3e4f5a6b7c",
  "language": "de",
  "scale": { "min": 1, "max": 4 },
  "overall_score": 2.8,
  "criteria": [
    {
      "id": "concrete_examples",
      "label": "Konkrete Beispiele",
      "score": 3,
      "comment": "Du hast dein PC-Projekt gut beschrieben.",
      "evidence": "In meiner Freizeit baue ich gerne PCs zusammen."
    },
    {
      "id": "preparation",
      "label": "Vorbereitung / Betriebskenntnis",
      "score": null,
      "comment": "Dazu gab es im Gespräch keine Aussage.",
      "evidence": ""
    }
  ],
  "strengths": ["Natürlicher, sympathischer Einstieg", "Echtes Interesse an Technik"],
  "improvements": [
    {
      "tip": "Bereite eine Antwort auf 'Warum unsere Firma?' vor.",
      "example_answer": "Mich spricht an, dass Sie Lernende früh in echte Projekte einbinden ..."
    }
  ],
  "next_practice": ["motivation", "self_reflection"],
  "closing": "Du bist auf einem guten Weg, jedes Üben macht dich sicherer.",
  "support_note": null
}
```

- `criteria` always lists all 11 criteria in rubric order. `score` is 1-4, or `null` if no answer
  showed anything about the criterion (then `comment` is a fixed "not observed" text).
- Numbers are computed in code from the per-answer analyses, not by the LLM: `criteria[].score` is
  the rounded average of the non-null scores, `overall_score` the average of the shown scores
  (1 decimal, `null` if nothing was observed), `next_practice` the two weakest criteria.
  Exception: if the candidate asked no question at the end, `initiative` is 1 (rubric level 1).
- `support_note` is a fixed text (where to get help, incl. Pro Juventute 147) when the interview showed
  distress, else `null`. `closing` is one encouraging sentence written by the LLM (may be `""`).
- The LLM writes `comment`, `evidence`, `strengths`, `improvements` and `closing`, following the FHGR
  feedback rules (`datasets/rubric/feedback_guidelines.json`). `evidence` is only kept if it
  is a real quote from the candidate's answers, otherwise it is `""`.
- If the report can't be generated, the response is `502 LLM_UNAVAILABLE` and nothing is cached,
  so the frontend can simply retry.

---

## 4. Shared enums

**Phases (in order):** `intro` -> `motivation` -> `strengths_weaknesses` -> `situational` -> `candidate_questions` -> `closing`

**Criteria:** the FHGR rubric, loaded from `datasets/rubric/criteria.json`. Scale 1 Ungenügend,
2 Ausbaufähig, 3 Gut, 4 Sehr gut, or `null` = not observed. The first six are the challenge's core criteria.

| id | DE label | Measures |
|---|---|---|
| `clarity` | Klarheit | Comprehensible, structured, traceable answers |
| `relevance` | Relevanz | Fits the question and the apprenticeship |
| `motivation` | Motivation | Genuine interest in the occupation and company |
| `self_reflection` | Selbstreflexion | Realistic view of own strengths, weaknesses, experiences |
| `communication` | Kommunikationsfähigkeit | Expression, tone, active listening (dialect is never penalised) |
| `concrete_examples` | Konkrete Beispiele | Real situations instead of claims |
| `demeanor` | Auftreten & Wirkung | Politeness, self-confidence, tone |
| `preparation` | Vorbereitung / Betriebskenntnis | Knows the company and the occupation |
| `goal_orientation` | Zielorientierung | Clear career choice and long-term ideas |
| `difficult_questions` | Umgang mit schwierigen Fragen | Reaction to critical or unexpected questions |
| `initiative` | Eigeninitiative | Asks own meaningful questions at the end |

---|---|---|
| `relevance` | Relevanz | Does the answer address the question? |
| `structure` | Struktur | Clear beginning, middle, end (e.g. STAR) |
| `examples` | Konkrete Beispiele | Real situations instead of empty claims |
| `motivation` | Motivation | Genuine interest in the occupation and company |
| `language` | Sprache & Ausdruck | Clear, polite, age-appropriate |
| `self_reflection` | Selbstreflexion | Honest view of own strengths and weaknesses |

---

## 5. Out of scope for v1

- Judge benchmark format: not published yet. The same server also offers the Agent Protocol (Aegra, graph
  `agent`, as in the FHGR project template), see README "Agent Protocol". It is not part of this contract.
- Streaming answers (SSE) - possible v2 if latency feels too slow.
- Voice input/output - possible v2 (TTS feature).
- Accounts. (Sessions are persisted in SQLite when `SESSIONS_DB` is set, see README.)

## 6. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-06 | First draft | Iago |
| 2026-10-06 | Port 8000 (matches backend skeleton), CORS for frontend dev server | Anina |
| 2026-10-09 | Backend implements v1. Clarified: LLM calls incl. JSON retries, `progress` and question ids, `turn_feedback` in `candidate_questions`, `closing_message`, history after the end, how report numbers and `evidence` are made, report errors, dev-only `POST /chat`, CORS origin for the nginx container, `500 INTERNAL_ERROR`. No breaking changes. | Iago |
| 2026-10-10 | **Breaking:** FHGR rubric (11 criteria, scale 1-4, `null` = not observed) replaces our 6 criteria (1-5). New `report.scale`; `overall_score` and `criteria[].score` can be `null`; `report.criteria` always has all 11; candidate questions are analysed (`initiative`); `history` candidate turns have `phase`. | Iago |
| 2026-10-10 | Guardrails: `question.guard`, `turn_feedback.problem_flags`, report `closing` and `support_note`. Not breaking. | Iago |
| 2026-10-10 | 12 main questions (intro 2, motivation 3, strengths/weaknesses 3, situational 3, + question round). Optional `posting_id`; `company` and `interviewer` in the session response; `postings` in `GET /config`. Not breaking. | Iago |
| 2026-10-10 | Optional `focus` in `POST /sessions`. Not breaking. | Iago |
| 2026-10-10 | `occupation_id` is optional when `posting_id` is given (the posting's occupation is used). Not breaking. | Iago |
| 2026-10-10 | Backend runs inside Aegra (same port 8000, same `/api/v1`); errors outside `/api/v1` keep FastAPI's format. Hidden occupation `lehrstelle_allgemein` is not listed in `GET /config`. Not breaking. | Iago |
