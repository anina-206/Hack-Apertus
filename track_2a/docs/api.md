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
| Scores | Integer 1-5 (1 = weak, 5 = excellent) |
| Auth | Optional. Without a token everything works as before (guest). With `Authorization: Bearer <token>` (see section 3b) interviews are saved to the user's account. |

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
| 409 | `USERNAME_TAKEN` | Registration with an existing username |
| 401 | `INVALID_CREDENTIALS` | Wrong username or password |
| 401 | `UNAUTHORIZED` | Missing, invalid or expired token on an endpoint that needs one |
| 404 | `INTERVIEW_NOT_FOUND` | Saved interview does not exist or belongs to someone else |
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

Account endpoints (v1.1, section 3b): `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `GET /me/interviews`, `GET /me/interviews/{session_id}`. No LLM calls.

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

Response `201`:

```json
{
  "session_id": "3f8a2c1e-6b1d-4b7e-9a51-2d3e4f5a6b7c",
  "phase": "intro",
  "progress": { "current": 1, "total": 8 },
  "question": {
    "id": "q1",
    "text": "Grüezi Lara! Erzähl mir doch zuerst etwas über dich."
  }
}
```

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
  "progress": { "current": 2, "total": 8 },
  "question": {
    "id": "q2",
    "text": "Spannend! Wie bist du darauf gekommen, Informatikerin zu werden?",
    "is_follow_up": false
  },
  "turn_feedback": {
    "short_tip": "Guter Einstieg! Nenne noch, warum dich gerade diese Firma interessiert.",
    "scores": { "relevance": 4, "structure": 3, "examples": 4, "motivation": 3, "language": 4, "self_reflection": 3 }
  },
  "meta": { "llm_calls": 2, "latency_ms": 4120 }
}
```

- `turn_feedback` is only present in `mode: "training"`. In `rehearsal` it is `null`.
  It is also `null` in the `candidate_questions` phase (not scored) and if the analysis failed.
- `is_follow_up: true` means the interviewer digs deeper into the last answer instead of moving on.
- `progress.current` counts main questions (8 in total). Follow-ups and the turns in the
  `candidate_questions` phase don't advance it, so it can stay the same for several turns.
- Question ids (`q1`, `q2`, ...) count every interviewer question, including follow-ups.

Response `200` (interview finished):

```json
{
  "done": true,
  "phase": "closing",
  "progress": { "current": 8, "total": 8 },
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
  "progress": { "current": 2, "total": 8 },
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
  "overall_score": 3.6,
  "criteria": [
    {
      "id": "examples",
      "label": "Konkrete Beispiele",
      "score": 4,
      "comment": "Du hast dein PC-Projekt gut beschrieben.",
      "evidence": "In meiner Freizeit baue ich gerne PCs zusammen."
    }
  ],
  "strengths": ["Natürlicher, sympathischer Einstieg", "Echtes Interesse an Technik"],
  "improvements": [
    {
      "tip": "Bereite eine Antwort auf 'Warum unsere Firma?' vor.",
      "example_answer": "Mich spricht an, dass Sie Lernende früh in echte Projekte einbinden ..."
    }
  ],
  "next_practice": ["motivation", "self_reflection"]
}
```

- Numbers are computed in code from the per-answer analyses, not by the LLM: `criteria[].score` is
  the rounded average per criterion, `overall_score` the average of all criteria (1 decimal),
  `next_practice` the two weakest criteria.
- The LLM writes `comment`, `evidence`, `strengths` and `improvements`. `evidence` is only kept if it
  is a real quote from the candidate's answers, otherwise it is `""`.
- If the report can't be generated, the response is `502 LLM_UNAVAILABLE` and nothing is cached,
  so the frontend can simply retry.

---

## 3b. Accounts and saved interviews (v1.1)

Optional. A guest can still use everything. A logged-in user gets every interview saved
(setup, all messages, tips and scores per answer, final report) and can open it again later.

Rules: `username` 3-30 characters (letters, digits, `_`, `.`, `-`, not case-sensitive), `password` at least 8 characters.
Passwords are stored hashed (scrypt). The token is random, valid for 30 days, and sent as `Authorization: Bearer <token>`.
Data lives in a SQLite file in a Docker volume (`storage/`). No e-mail address or real name is asked for.

### POST `/auth/register` and POST `/auth/login`

Request: `{ "username": "lara", "password": "geheim1234" }`

Response `201` (register) / `200` (login):

```json
{ "token": "x7Qe...", "user": { "id": "5b1c...", "username": "lara" } }
```

### POST `/auth/logout`

Needs a token. Invalidates it. Response `204`, no body.

### GET `/auth/me`

Needs a token. Response: `{ "id": "5b1c...", "username": "lara" }`

### POST `/sessions` with a token

Same request and response as in section 3. If a valid token is sent, the interview is attached to the user.
An invalid token returns `401 UNAUTHORIZED` (no silent fallback to guest).
`/answers` and `/report` save automatically when the session belongs to a user.

### GET `/me/interviews`

Needs a token. Newest first.

```json
{
  "interviews": [
    {
      "session_id": "3f8a2c1e-...",
      "language": "de",
      "occupation_id": "informatiker_efz",
      "interviewer_style": "friendly",
      "mode": "training",
      "created_at": "2026-10-10T10:03:00Z",
      "updated_at": "2026-10-10T10:12:00Z",
      "done": true,
      "overall_score": 3.6
    }
  ]
}
```

`overall_score` is `null` until the report was created.

### GET `/me/interviews/{session_id}`

Needs a token, else `401`. Unknown id or someone else's interview: `404 INTERVIEW_NOT_FOUND`.

```json
{
  "session_id": "3f8a2c1e-...",
  "language": "de",
  "occupation_id": "informatiker_efz",
  "interviewer_style": "friendly",
  "mode": "training",
  "candidate": { "first_name": "Lara" },
  "created_at": "2026-10-10T10:03:00Z",
  "done": true,
  "phase": "closing",
  "progress": { "current": 8, "total": 8 },
  "current_question_id": null,
  "history": [
    { "role": "interviewer", "question_id": "q1", "text": "Grüezi Lara! ..." },
    { "role": "candidate", "question_id": "q1", "text": "Ich bin Lara, ...",
      "turn_feedback": { "short_tip": "...", "scores": { "relevance": 4 } } }
  ],
  "report": null
}
```

- `turn_feedback` is only on `candidate` entries, only in `training`, and can be `null` (same rules as in section 3).
- `report` has the shape of `GET /sessions/{id}/report`, or `null` if it was not created yet.
- This is a read-only copy. An unfinished interview can only be continued while the backend still holds the session in memory
  (it is lost on restart, see README limitations); after a restart it stays readable here.

---

## 4. Shared enums

**Phases (in order):** `intro` -> `motivation` -> `strengths_weaknesses` -> `situational` -> `candidate_questions` -> `closing`

**Criteria (proposal, align with FHGR feedback guidelines after the Q&A on 8.10):**

| id | DE label | Measures |
|---|---|---|
| `relevance` | Relevanz | Does the answer address the question? |
| `structure` | Struktur | Clear beginning, middle, end (e.g. STAR) |
| `examples` | Konkrete Beispiele | Real situations instead of empty claims |
| `motivation` | Motivation | Genuine interest in the occupation and company |
| `language` | Sprache & Ausdruck | Clear, polite, age-appropriate |
| `self_reflection` | Selbstreflexion | Honest view of own strengths and weaknesses |

---

## 5. Out of scope for v1

- Judge benchmark format: handled by a separate adapter (CLI) that calls the same core logic. Defined after the Q&A on 8.10.
- Streaming answers (SSE) - possible v2 if latency feels too slow.
- Voice input/output - possible v2 (TTS feature).
- E-mail, password reset, social login, rate limiting.
- Continuing an unfinished interview after a backend restart.

## 6. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-06 | First draft | Iago |
| 2026-10-06 | Port 8000 (matches backend skeleton), CORS for frontend dev server | Anina |
| 2026-10-10 | v1.1: optional accounts (`/auth/*`), saved interviews (`/me/interviews`), new error codes. Guest use unchanged, no breaking change. | Anina |
| 2026-10-09 | Backend implements v1. Clarified: LLM calls incl. JSON retries, `progress` and question ids, `turn_feedback` in `candidate_questions`, `closing_message`, history after the end, how report numbers and `evidence` are made, report errors, dev-only `POST /chat`, CORS origin for the nginx container, `500 INTERNAL_ERROR`. No breaking changes. | Iago |
