# Questions

`questions.jsonl`: the question bank for interviewer agents. The field reference is in [../SCHEMA.md](../SCHEMA.md#questionsquestionsjsonl) and the counts are in [../STATS.md](../STATS.md).

| Category (`category`) | Ids | Origin |
|---|---|---|
| `general`: 10 interview phases (greeting … closing) | `Q-01-01` … `Q-10-04` | FHGR *Beispielfragen*, verbatim |
| `occupation_specific`: 22 *Berufsfelder* (Natur … Bildung/Soziales) | `Q-BF01-01` … `Q-BF22-05` | FHGR *Beispielfragen*, verbatim |
| `situational`: "Stell dir vor …" | `Q-SIT-01` … `Q-SIT-12` | synthetic (the challenge flow requires situational questions) |
| `difficult`: pressure and unexpected questions | `Q-DIF-01` … `Q-DIF-10` | synthetic (trains the criterion *Umgang mit schwierigen Fragen*) |
| `other_situation`: phone call, trial talk, online interview, assessment, follow-up interview | `Q-OTH-01` … `Q-OTH-14` | synthetic, based on *Unterschiedliche Bewerbungssituationen* |

## Key fields

- **`text.de` / `text.fr` / `text.it`**: the German text is the master. The French and Italian texts are translations: Swiss usage, «tu», unreviewed (`translation_review`).
- **`gsw_variants`**: spoken Swiss German versions: `zh` and `be` for all general, situational and difficult questions; `bs`, `gr` and `vs` for the 30 most common ones. All need native-speaker review.
- **`phase` / `flow_stage`**: `phase` is the FHGR phase (1–10); `flow_stage` is the challenge flow stage. See [../docs/interview_flow.md](../docs/interview_flow.md).
- **`criteria`**: the rubric criteria the question mainly draws out. Use them to decide what to evaluate after each answer.
- **`difficulty`**: `easy`, `medium` or `hard`, for adaptive difficulty.
- **`condition`**: ask only if the condition holds, e.g. `Q-06-06` (Stellwerk) only if the candidate took the test.
- **`berufsfeld`**: set for occupation-specific questions. Match it with `postings[].occupation.berufsfeld_key`.

## Example

```json
{"id": "Q-05-03", "category": "general", "phase": 5, "phase_key": "strengths_development",
 "flow_stage": "strengths_weaknesses", "subtopic": "weaknesses", "type": "reflective", "difficulty": "hard",
 "criteria": ["self_reflection", "concrete_examples", "difficult_questions"],
 "text": {"de": "Welche Schwäche möchtest du verbessern?", "fr": "…", "it": "…"},
 "gsw_variants": [{"dialect": "zh", "text": "…"}, {"dialect": "be", "text": "…"}], "source": "Beispielfragen Vorstellungsgespräch.docx"}
```

## Building an interview plan

```python
plan = [q for q in questions if q["category"] == "general" and q["difficulty"] != "hard"][:6]
plan += [q for q in questions if q["berufsfeld"] and q["berufsfeld"]["key"] == posting["occupation"]["berufsfeld_key"]][:2]
plan += [q for q in questions if q["id"] in ("Q-SIT-02", "Q-09-09", "Q-10-01")]
```

`scenarios[].planned_question_ids` has hand-crafted plans for 28 scenarios.
