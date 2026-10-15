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
| Format | JSON, UTF-8, `Content-Type: application/json`. Exceptions: `POST /transcribe` takes an audio upload (`multipart/form-data`), `POST /speech` returns audio |
| Naming | `snake_case` for all keys |
| IDs | Strings (UUID), never numbers |
| Languages | `de`, `fr`, `it`, `gsw` (Swiss German, optional) |
| Time | ISO 8601 in UTC, e.g. `2026-10-09T14:03:00Z` |
| Scores | Integer 1-4 (FHGR: 1 Ungenügend … 4 Sehr gut), or `null` = not observed |
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
| 429 | `TOO_MANY_REQUESTS` | Too many failed logins or registrations, see section 3b. The `Retry-After` header says how many seconds to wait. |
| 502 | `LLM_UNAVAILABLE` | Apertus did not answer or returned garbage |
| 503 | `VOICE_UNAVAILABLE` | Speech-to-text or text-to-speech is switched off or failed (the frontend then uses the browser's voice features) |
| 500 | `INTERNAL_ERROR` | Unexpected backend bug (should not happen) |

---

## 2. Endpoints overview

| Method | Path | Purpose | LLM calls |
|---|---|---|---|
| GET | `/health` | Is the backend alive? | 0 |
| POST | `/application/extract` | Text of an uploaded application (PDF, .docx, .txt) | 0 |
| GET | `/config` | Occupations, languages, profiles for the setup screen | 0 |
| POST | `/sessions` | Start an interview, get the first question | 1 (+1 with an application letter, +1 for an invented company) |
| POST | `/sessions/{session_id}/answers` | Send an answer, get the next question | 2 (rarely 3, see below) |
| GET | `/sessions/{session_id}` | Current state (for page reload) | 0 |
| GET | `/sessions/{session_id}/report` | Final feedback report | 1 (rarely 2-3, once, then cached) |
| POST | `/transcribe` | Speech to text (Whisper) for a spoken answer | 0 |
| POST | `/speech` | Text to speech (Piper or Azure) for the interviewer | 0 |

Budget check: about 2 calls per answer + 1 for the report -> well below the limit of 5.
If the model returns unusable JSON, the call is retried (max 3 attempts), and every retry counts as a call:
3 analysis attempts at most. The interviewer's reply is asked once more when it asks nothing, repeats an earlier
question, is in English, or answers a candidate's question with thanks only (one retry at most, then a fixed line).
Measured over 12 full interviews: 1.92 calls per answer on average, at most 3. In the `candidate_questions` phase an
answer costs 1, or 0 if the candidate has no more questions. Mundart adds 1 per interviewer text.
`meta.llm_calls` always shows the real number.

Account endpoints (v1.1, section 3b): `POST /auth/register`, `POST /auth/login`, `POST /auth/logout`, `GET /auth/me`, `DELETE /auth/me`, `GET /me/interviews`, `GET /me/interviews/{session_id}`, `DELETE /me/interviews/{session_id}`. No LLM calls.

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
  ],
  "voice": { "stt": true, "tts": "piper" },
  "dialects": [
    { "code": "zh", "label": { "de": "Zürich", "fr": "Zurich", "it": "Zurigo" } },
    { "code": "be", "label": { "de": "Bern", "fr": "Berne", "it": "Berna" } }
  ]
}
```

`voice` says which server voice features are on: `stt` (`POST /transcribe`) and `tts`
(`POST /speech`: `"piper"`, `"azure"` or `null` = off). When one is off, the frontend uses the browser's
own speech recognition or speech synthesis instead.

### POST `/application/extract`

Reads an uploaded application letter so the frontend can put its text into `POST /sessions` (`application_text`).
`multipart/form-data` with one field `file`: PDF, Word (`.docx`) or text (`.txt`, `.md`), max 5 MB (PDF: first 12 pages).
Nothing is stored.

Response `200`:

```json
{ "filename": "bewerbung.pdf", "text": "Ich heisse Lara ...", "chars": 1840, "truncated": false }
```

`text` is cut to 8000 characters (`truncated: true`). Errors are `400 INVALID_REQUEST` with a readable `message`:
wrong type, too large, damaged or password-protected file, or no text found (e.g. a scanned document that is only a picture).

### POST `/sessions`

Request:

```json
{
  "language": "de",
  "occupation_id": "informatiker_efz",
  "occupation_name": null,
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

`dialect` is optional and only used for `language: "gsw"`: `zh` (default), `be`, `bs`, `gr` or `vs`
(`GET /config` lists them under `dialects`). For Mundart the interviewer writes Standard German first and a second LLM call
turns every text the model writes into the dialect (fixed lines like the closing are already dialect). That is one more call for
each such text, so up to 3 calls per answer in Mundart (analysis, interviewer, dialect). If the second call fails, the Standard
German text is used. Tips and the report stay in Standard German, as in the FHGR data. The dialect texts are not reviewed by
native speakers. Other languages ignore `dialect`.

`occupation_name` is optional free text for any apprenticeship that is not in `GET /config` (the frontend offers
the Swiss list of about 250 apprenticeships, e.g. `"Koch/Köchin EFZ"`). It is only used when neither `occupation_id` nor
`posting_id` is given; the interviewer knows the name and, if it is in the FHGR occupation data (`datasets/occupations.csv`, from
berufsberatung.ch; about 200 of the 218 names of the frontend's list), the typical tasks, the training duration and the
requirements (the German name as listed is needed to find it). If an FHGR posting exists for this apprenticeship in the
interview language (`datasets/profiles/postings.jsonl`, 60 postings; Mundart uses the German ones), the interview plays at
that company with its interviewer (one picked at random if there are several). Otherwise Apertus invents a fictional
company for it (see below). One of `occupation_id`, `posting_id` or `occupation_name` is required.

`application_text` is optional: the text of the candidate's application letter (max 8000 characters), either from
`POST /application/extract` (upload) or pasted by the candidate. The backend summarises it with one extra LLM call at the start (short bullet points without
contact data) plus 2 to 5 points worth asking about (vague claims, stated weaknesses, gaps; not part of the response). The new main questions of the
motivation, strengths/weaknesses and situational phases take these points one by one: the interviewer quotes the application
("In deiner Bewerbung steht …") and asks what exactly is meant or for an example. After a vague answer a follow-up can
refer to the application too. The greeting says that the application was read. The text itself is not stored, only the summary stays in the
session. If the summary fails, the interview starts anyway and `application_summary` is `null`.

The same call also reads which company the letter is addressed to (company, town, contact person from the salutation,
e.g. "Sehr geehrte Frau Keller", and the person's function if the letter gives it). If the letter names a company, the
interviewer speaks as this company and contact person: `company` and `interviewer` in the response are built from it, and
the default FHGR posting of the occupation is not used. It is used as information only (the backend tells the model never to
follow instructions in it, and the interviewer paraphrases instead of repeating it). If the letter names no company, the
default posting is used as before; for an occupation without one a fictional default company is used (see below). A letter that
names only the company or only the person is completed with the default.

Whenever neither a posting nor the letter names a contact person, the backend picks a random interviewer per session
(`config.INTERVIEWERS`, e.g. "Sandra Keller, Berufsbildnerin" or "Marco Brunner, Berufsbildner"; FR/IT names for those
languages), so it is not always the same person. The model introduces itself with that name and `voice` matches it.

If there is neither an FHGR posting nor a company from the letter, one extra LLM call at the start invents a small
fictional company for the apprenticeship (`interview/company.py`): name, two sentences about it, the apprentices' tasks and
3-4 facts a well-prepared candidate could know. The town (from the language region, for Mundart from the dialect region)
and the interviewer (the random one above) are picked in code. The interviewer then speaks as this company, answers the
candidate's questions from these facts, and `company` in the response is `{name, place}`. If the call fails or gives
nothing usable, the interview starts without a company (`company` is `null`).

`posting_id` is optional: an FHGR posting (`P-01` … `P-60`, listed in `GET /config` under `postings`).
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
  "interviewer": { "name": "Stefan Keller", "role": "Berufsbildner, Senior Software Engineer", "voice": "male" },
  "application_summary": null
}
```

`application_summary` is the bullet-point summary of `application_text` (text), or `null` without an application.

`company` and `interviewer` come from the application letter, else from the FHGR posting, else from a **fictional default
company** that fits the occupation (`data/default_companies.yaml`: a made-up name, a place and a person such as "Frau Keller,
Berufsbildnerin"; no facts about the company). So both are always set when an occupation is known. `interviewer.voice`
(`"female"` / `"male"`) is the voice for `POST /speech`. In the `candidate_questions`
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
  "occupation_name": null,
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
Generated with one LLM call the first time, then cached. It is asked once more when it talks about the candidate
in the third person, or when it broke off and 3 or more comments are missing.

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
  feedback rules (`datasets/rubric/feedback_guidelines.json`). If a comment is still missing after the retry, it is
  the per-answer tip of the answer that scored lowest on that criterion. `evidence` is only kept if it
  is a real quote from the candidate's answers, otherwise it is `""`.
- `application_feedback` is the review of the application letter, or `null` without an uploaded letter (or if the review
  failed). It is made at the start of the interview, in parallel to the summary (one more LLM call there, none in the
  report), written in the interview language (Mundart: Standard German) and shown in both modes:

  ```json
  "application_feedback": {
    "scale": { "min": 1, "max": 4 },
    "overall_score": 2.8,
    "criteria": [
      { "id": "motivation", "label": "Motivation für den Beruf", "score": 3, "comment": "Du nennst einen echten Grund.",
        "evidence": "Seit der Schnupperlehre weiss ich" }
    ],
    "strengths": ["Du nennst ein Erlebnis aus der Schnupperlehre"],
    "improvements": [{ "tip": "Schreibe, was dich an genau dieser Firma anspricht.", "example_answer": "Mich spricht an, dass [Firma] ..." }]
  }
  ```

  Criteria ids: `motivation`, `company`, `strengths`, `structure`, `language`; the scores are 1-4 like in the interview,
  `overall_score` is their average, and `evidence` is only kept if it is a real quote of the letter. The letter text itself
  is not stored.
- If the report can't be generated, the response is `502 LLM_UNAVAILABLE` and nothing is cached,
  so the frontend can simply retry.

---

### POST `/transcribe`

Speech to text with Whisper (faster-whisper, runs in the backend container; nothing leaves the server).
For `de` and `gsw` a Swiss German fine-tune is used: Mundart comes back as Standard German text.

Request: `multipart/form-data` with

| Field | Type | Notes |
|---|---|---|
| `audio` | file | What the browser's `MediaRecorder` records (`audio/webm`, `audio/ogg`, `audio/mp4`, `audio/wav`). At most 60 seconds / 5 MB |
| `language` | string | `de`, `fr`, `it` or `gsw` |
| `session_id` | string, optional | The running interview: Whisper then gets the occupation and company as a hint and spells their words better. Unknown ids are ignored |

Response `200`:

```json
{ "text": "Ich baue gerne Computer zusammen.", "language": "gsw", "duration_ms": 3200, "model": "whisper-large-v3-turbo-swiss-german" }
```

`text` is `""` if nothing was said. Errors: `400 INVALID_REQUEST` (no audio, too long, unknown language),
`503 VOICE_UNAVAILABLE` (switched off with `STT_ENABLED=false`, or the model could not be loaded).

### POST `/speech`

Text to speech for the interviewer's lines.

```json
{ "text": "Wie bist du auf diesen Beruf gekommen?", "language": "de", "voice": "female" }
```

| Field | Type | Notes |
|---|---|---|
| `text` | string | 1-1000 characters |
| `language` | string | `de`, `fr`, `it` or `gsw` |
| `voice` | string | optional, `female` (default) or `male`; use `interviewer.voice` from `POST /sessions` |

Response `200`: the audio (`audio/wav` from Piper, `audio/mpeg` from Azure), header `X-TTS-Engine: piper|azure`.
The engine is set in the backend with `TTS_ENGINE` (`piper`, `azure` or `off`). Azure needs `AZURE_SPEECH_KEY`
and `AZURE_SPEECH_REGION` and uses Swiss voices (de-CH, fr-CH). Errors: `400 INVALID_REQUEST`, `503 VOICE_UNAVAILABLE`.

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

### DELETE `/auth/me`

Deletes the account with all saved interviews and all tokens. Needs a token and the password again
(so a stolen token alone cannot delete the account).

Request: `{ "password": "geheim1234" }`

Response `204`, no body. Wrong password: `401 INVALID_CREDENTIALS` (counts as a failed login, see below).
Without a token: `401 UNAUTHORIZED`.

### Rate limiting

Counted in memory per client IP (a backend restart resets it), only failed attempts count:

| What | Limit | Window |
|---|---|---|
| Failed logins (or wrong password on `DELETE /auth/me`) for the same IP and username | 5 | 15 minutes |
| Failed logins from the same IP, any username | 20 | 15 minutes |
| Registration attempts from the same IP | 10 | 1 hour |

When a limit is reached the answer is `429 TOO_MANY_REQUESTS` with the header `Retry-After: <seconds>`, even if the
password would have been right. A successful login clears the counter of that IP and username.

### GET `/me/interviews`

Needs a token. Newest first.

```json
{
  "interviews": [
    {
      "session_id": "3f8a2c1e-...",
      "language": "de",
      "occupation_id": "informatiker_efz",
      "occupation_name": null,
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

### DELETE `/me/interviews/{session_id}`

Needs a token. Deletes one saved interview of the user: the saved copy (conversation, tips, scores, report) and the
backend's own record of the running session, so `GET /sessions/{id}` answers `404 SESSION_NOT_FOUND` afterwards.
Response `204`, no body. Unknown id or someone else's interview: `404 INTERVIEW_NOT_FOUND` (nothing is deleted);
without a token: `401 UNAUTHORIZED`. Deleting twice gives `404` the second time.

### GET `/me/interviews/{session_id}`

Needs a token, else `401`. Unknown id or someone else's interview: `404 INTERVIEW_NOT_FOUND`.

```json
{
  "session_id": "3f8a2c1e-...",
  "language": "de",
  "occupation_id": "informatiker_efz",
  "occupation_name": null,
  "interviewer_style": "friendly",
  "mode": "training",
  "candidate": { "first_name": "Lara" },
  "company": { "name": "Limmatcode GmbH", "place": "Zürich" },
  "interviewer": { "name": "Stefan Keller", "role": "Berufsbildner, Senior Software Engineer" },
  "created_at": "2026-10-10T10:03:00Z",
  "done": true,
  "phase": "closing",
  "progress": { "current": 12, "total": 12 },
  "current_question_id": null,
  "history": [
    { "role": "interviewer", "question_id": "q1", "text": "Grüezi Lara! ..." },
    { "role": "candidate", "question_id": "q1", "text": "Ich bin Lara, ...",
      "turn_feedback": { "short_tip": "...", "scores": { "clarity": 3, "relevance": 4, "motivation": null } } }
  ],
  "report": null
}
```

- `turn_feedback` is only on `candidate` entries, only in `training`, and can be `null` (same rules as in section 3).
- `report` has the shape of `GET /sessions/{id}/report`, or `null` if it was not created yet.
- This is a read-only copy of the saved conversation. It stays readable after a restart.

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

---

## 5. Out of scope for v1

- Judge benchmark format: not published yet. The same server also offers the Agent Protocol (Aegra, graph
  `agent`, as in the FHGR project template), see README "Agent Protocol". It is not part of this contract.
- Streaming answers (SSE) - possible v2 if latency feels too slow.
- Voice input/output - possible v2 (TTS feature).
- Continuing an unfinished interview from a saved copy (sessions survive a restart only through `SESSIONS_DB`, see README).
- E-mail, password reset, social login, rate limiting.

## 6. Change log

| Date | Change | By |
|---|---|---|
| 2026-10-06 | First draft | Iago |
| 2026-10-06 | Port 8000 (matches backend skeleton), CORS for frontend dev server | Anina |
| 2026-10-09 | Backend implements v1. Clarified: LLM calls incl. JSON retries, `progress` and question ids, `turn_feedback` in `candidate_questions`, `closing_message`, history after the end, how report numbers and `evidence` are made, report errors, dev-only `POST /chat`, CORS origin for the nginx container, `500 INTERNAL_ERROR`. No breaking changes. | Iago |
| 2026-10-10 | v1.1: optional accounts (`/auth/*`), saved interviews (`/me/interviews`), new error codes. Guest use unchanged, no breaking change. | Anina |
| 2026-10-10 | **Breaking:** FHGR rubric (11 criteria, scale 1-4, `null` = not observed) replaces our 6 criteria (1-5). New `report.scale`; `overall_score` and `criteria[].score` can be `null`; `report.criteria` always has all 11; candidate questions are analysed (`initiative`); `history` candidate turns have `phase`. | Iago |
| 2026-10-10 | Guardrails: `question.guard`, `turn_feedback.problem_flags`, report `closing` and `support_note`. Not breaking. | Iago |
| 2026-10-10 | 12 main questions (intro 2, motivation 3, strengths/weaknesses 3, situational 3, + question round). Optional `posting_id`; `company` and `interviewer` in the session response; `postings` in `GET /config`. Not breaking. | Iago |
| 2026-10-10 | Optional `focus` in `POST /sessions`. Not breaking. | Iago |
| 2026-10-10 | `occupation_id` is optional when `posting_id` is given (the posting's occupation is used). Not breaking. | Iago |
| 2026-10-10 | Backend runs inside Aegra (same port 8000, same `/api/v1`); errors outside `/api/v1` keep FastAPI's format. Hidden occupation `lehrstelle_allgemein` is not listed in `GET /config`. Not breaking. | Iago |
| 2026-10-11 | v1.2: `DELETE /auth/me` (delete account), rate limiting on `/auth/login`, `/auth/register` and `DELETE /auth/me`, new error `429 TOO_MANY_REQUESTS`. Not breaking. | Anina |
| 2026-10-11 | v1.3: optional `occupation_name` in `POST /sessions` (any apprenticeship by name, no company); `occupation_name` in `GET /sessions/{id}` and `/me/interviews`. Not breaking. | Anina |
| 2026-10-11 | v1.4: optional `company` in `POST /sessions` (the candidate's own company and contact person, replaces the default FHGR posting); saved interviews return the matching `company` and `interviewer`. Not breaking. | Anina |
| 2026-10-11 | v1.5: removed `company.posting_text` again. New `POST /application/extract` (text of an uploaded application), optional `application_text` in `POST /sessions`, `application_summary` in the response. Starting costs one extra LLM call when an application is given. Not breaking. | Anina |
| 2026-10-11 | v1.6: removed `company` from `POST /sessions` (v1.4) again. The company and contact person now come from the application letter (`application_text`), the response still has `company` and `interviewer`. Not breaking for clients that never sent `company`. | Anina |
| 2026-10-11 | v1.7: optional `dialect` in `POST /sessions` and `dialects` in `GET /config` (Mundart: zh, be, bs, gr, vs). One extra LLM call per interviewer text in Mundart. Not breaking. | Anina |
| 2026-10-11 | v1.8: `DELETE /me/interviews/{session_id}` (delete one saved interview). Not breaking. | Anina |
| 2026-10-11 | v1.9: `occupation_name` (and the five occupations of `GET /config`, and the FHGR postings) now bring the typical tasks, duration and requirements from `datasets/occupations.csv` into the prompts. No change to the fields. | Anina |
| 2026-10-11 | v1.10: `POST /transcribe` (Whisper) and `POST /speech` (Piper/Azure); `voice` in `GET /config`; `interviewer.voice` in `POST /sessions`; error `503 VOICE_UNAVAILABLE`. Not breaking. | Iago |
| 2026-10-11 | v1.11: `company` and `interviewer` of `POST /sessions` and of saved interviews are never `null` any more: without a letter and without an FHGR posting a fictional default company and contact person fitting the occupation are used (`data/default_companies.yaml`). Not breaking. | Anina |
| 2026-10-11 | v1.12: `application_feedback` in the report: review of the uploaded application letter (5 criteria, 1-4, strengths, tips). One more LLM call at the start of an interview with a letter. Not breaking. | Anina |
| 2026-10-11 | v1.13: optional `session_id` in `POST /transcribe` (vocabulary hint for Whisper). Not breaking. | Iago |
| 2026-10-15 | No field changes: retries of the interviewer reply and of the report, fallback comment from the answer tips; call counts above updated with measured values. | Iago |
