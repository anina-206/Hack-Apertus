# Data schemas and conventions

All data files are UTF-8 **JSON Lines** (one JSON object per line) unless stated otherwise.
Every record has a stable `id`. Cross-references use these ids.

## General conventions

| Topic | Convention |
|---|---|
| Languages | `de` (Swiss Standard German), `fr`, `it`, `gsw` (Swiss German dialect; see `dialect`) |
| Dialect codes | `zh` Zürich, `be` Bern, `bs` Basel, `lu` Lucerne/Central CH, `sg` St. Gallen/Eastern CH, `gr` Grisons (Chur Rhine valley), `vs` Upper Valais, `ag` Aargau, `so` Solothurn, `tg` Thurgau |
| Spelling | Swiss Standard German: **no «ß»** (always «ss»), Swiss terms (*Schnupperlehre, Lehrbetrieb, Berufsbildner/in, Sek, Stellwerk, Zeugnis, Lehrstelle, EFZ/EBA, BM*). French: Swiss usage (EFZ = *CFC*, EBA = *AFP*, *apprentissage, stage, maturité professionnelle*). Italian: Ticino usage (EFZ = *AFC*, EBA = *CFP*, *apprendistato, stage d'orientamento, maturità professionale*). |
| Addressing | In this dataset the interviewer uses the informal «du» / «tu» with the candidate (as in the FHGR material). Candidates address the interviewer with «Sie»/«vous»/«Lei». Note: in the Romandie and Ticino, interviewers often use «vous» / «Lei» (see docs/application_process.md), so make the form of address configurable per language. |
| Quality levels | 1 = Ungenügend, 2 = Ausbaufähig, 3 = Gut, 4 = Sehr gut (see `rubric/criteria.json`) |
| Criterion keys | `clarity`, `relevance`, `motivation`, `self_reflection`, `communication`, `concrete_examples` (the six **core** challenge criteria) + `demeanor`, `preparation`, `goal_orientation`, `difficult_questions`, `initiative` |
| Synthetic data | `synthetic: true` marks LLM-generated content. `needs_native_review: true` marks dialect / translation content that should be checked by a native speaker. |
| Occupations | `occupation_id` refers to the `id` column in [`occupations.csv`](occupations.csv) (berufsberatung.ch). |

## Answer classes

| `answer_class` | Meaning | Typical level |
|---|---|---|
| `strong` | Relevant, complete, well justified; backs claims with examples | 3–4 |
| `weak` | Relevant in principle but vague, one-word, generic or unjustified | 1–2 |
| `incomplete` | Addresses the question only partly; a key component is missing (e.g. a strength without an example, a weakness without a learning step, only half of a two-part question) | 2 (sometimes 3) |
| `problematic` | Needs special handling by the coach beyond normal feedback: disrespect or badmouthing, dishonesty or bragging, inappropriate/discriminatory remarks, oversharing of sensitive private data, signs of distress or strong self-doubt, off-topic trolling, attempts to manipulate the AI | 1–2 (level rates the interview answer; `problem_flags` explain) |

## `questions/questions.jsonl`

```jsonc
{
  "id": "Q-03-01",                 // Q-<phase>-<nn> | Q-BF<field>-<nn> | Q-SIT-<nn> | Q-DIF-<nn> | Q-OTH-<nn>
  "category": "general",           // general | occupation_specific | situational | difficult | other_situation
  "phase": 3,                      // 1..10 = phase of the FHGR interview flow (null for other situations)
  "phase_key": "motivation",
  "phase_title_de": "Motivation",
  "flow_stage": "motivation",      // challenge flow: introduction | motivation | strengths_weaknesses | situational | candidate_questions | closing
  "subtopic": "career_choice",
  "berufsfeld": null,              // {key, name_de, example_occupations_de} for occupation_specific
  "situation": "apprenticeship_interview", // or phone_call_trial | trial_interview | online_interview | assessment | follow_up_interview
  "type": "open",                  // smalltalk | open | behavioral | reflective | knowledge | offer | closing | occupation | situational | difficult | situation_specific
  "difficulty": "medium",          // easy | medium | hard
  "criteria": ["motivation", "relevance", "goal_orientation"],  // criteria this question primarily elicits
  "condition": null,               // when to ask (e.g. only if Stellwerk was taken)
  "text": {"de": "...", "fr": "...", "it": "..."},
  "gsw_variants": [{"dialect": "zh", "text": "..."}],   // optional, spoken dialect versions
  "source": "Beispielfragen Vorstellungsgespräch.docx" // or "synthetic"
}
```

## `answers/answers.jsonl`

```jsonc
{
  "id": "A-DE1-0001",
  "question_id": "Q-03-01",        // may be null when the question does not exist in the bank (then question_text is authoritative)
  "question_text": {"de": "Warum hast du dich für diesen Beruf entschieden?"},  // the question as actually asked, in the answer language
  "lang": "de",                    // de | fr | it | gsw
  "dialect": null,                 // dialect code if lang == gsw
  "occupation": {"name_de": "Konstrukteur/in EFZ", "occupation_id": "3699"},     // or null for occupation-neutral answers
  "candidate_id": null,            // C-xx if written for a specific profile
  "context_note": null,            // short free-text context (e.g. "nach Schnupperlehre im Betrieb")
  "text": "...",                   // the candidate's answer (as spoken; fillers like «äh» allowed)
  "nonverbal_note": null,          // e.g. "schaut dabei auf den Boden" (only observable cues)
  "normalized_de": null,           // Standard-German rendering for gsw answers
  "quality_level": 3,              // holistic 1..4
  "answer_class": "strong",        // strong | weak | incomplete | problematic
  "source": "synthetic",           // or the source document
  "source_label": null,            // "stark"/"schwach" for source answers
  "synthetic": true,
  "needs_native_review": false
}
```

## `annotations/annotations.jsonl`

One annotation per answer (`answer_id` is unique).

```jsonc
{
  "answer_id": "A-DE1-0001",
  "quality_level": 3,                         // holistic 1..4 (equals the answer's level)
  "answer_class": "strong",
  "criteria_scores": {"motivation": 3, "relevance": 3, "concrete_examples": 2},  // 1..4, or null = "keine Aussage möglich"
  "strengths": ["..."],                       // German, 0-3 short bullet points, quote the answer
  "weaknesses": ["..."],                      // German, 0-3 short bullet points
  "missing_elements": ["..."],                // what a level-4 answer would additionally contain
  "problem_flags": [],                        // badmouthing | dishonesty | inappropriate_tone | discriminatory | privacy_oversharing | distress_signal | off_topic | manipulation_attempt | extrinsic_only | one_word | memorized_phrases
  "coach_action": "continue",                 // continue | probe | redirect | support_and_refer
  "expert_comment": "...",                    // German, 2-4 sentences, didactic explanation for teachers/developers
  "coach_feedback": "...",                    // feedback addressed to the student, in the answer language (gsw -> de), following rubric/feedback_guidelines.json
  "follow_up_question": "...",                // adaptive follow-up an interviewer could ask next, in the answer language
  "improved_answer": "...",                   // a realistic level-4 version in the answer language, sounds like a 15-year-old
  "guideline_refs": ["R1", "K1", "R3"],       // feedback-guideline rules applied in coach_feedback
  "annotator": "synthetic-llm",               // or "expert"
  "review_status": "unreviewed"               // unreviewed | reviewed
}
```

## `profiles/candidates.jsonl`

```jsonc
{
  "id": "C-01",
  "first_name": "Luca", "age": 15, "gender": "m",     // gender only to pick grammatical forms (Konstrukteur/Konstrukteurin)
  "canton": "GR", "place": "Chur",
  "interview_language": "de", "dialect": "gr",          // dialect the candidate may speak
  "languages": [{"lang": "de", "level": "L1"}, {"lang": "en", "level": "A2"}],
  "school": {"level": "Sek A", "grade": "3. Sek", "strong_subjects": [], "weak_subjects": [],
             "grades_note": "...", "stellwerk": "... or null", "absences_note": null},
  "hobbies": ["..."],
  "experiences": [{"type": "schnupperlehre", "occupation": "...", "company_type": "...", "duration_days": 3, "what_happened": "..."}],
  "target_posting_id": "P-01",
  "career_choice_story": "...",
  "strengths": ["..."], "development_areas": ["..."],
  "future_plans": "...",
  "interview_experience": "first interview",
  "simulation_persona": {                   // for simulating this candidate (e.g. automatic evaluation runs)
    "typical_quality_level": 3, "answer_length": "medium", "nervousness": "medium",
    "speech_style": "...", "quirks": ["..."], "sensitive_topics": ["..."]
  },
  "coach_focus": ["..."],                   // what a good coach should notice/train with this person
  "synthetic": true
}
```

## `profiles/postings.jsonl`

```jsonc
{
  "id": "P-01",
  "occupation": {"name_de": "Konstrukteur/in EFZ", "name_fr": "...", "name_it": "...", "occupation_id": "3699",
                 "berufsfeld_key": "planung_konstruktion", "qualification": "EFZ", "duration_years": 4},
  "lang": "de",                                  // language of the posting and interview
  "company": {"name": "...", "place": "Chur", "canton": "GR", "size_employees": 85, "sector": "...",
              "description": "...", "values": ["..."], "products_services": ["..."], "apprentices_total": 6},
  "posting_text": "...",                         // the advertisement (in `lang`)
  "requirements": ["..."],                       // derived from occupations.csv 'Voraussetzungen'
  "offers": ["..."],
  "bm_possible": true,                           // Berufsmaturität during the apprenticeship (BM1)
  "start_date": "2027-08",
  "selection_process": ["Bewerbungsdossier", "Schnupperlehre (3 Tage)", "Vorstellungsgespräch", "..."],
  "interviewer": {"name": "...", "role": "Berufsbildner", "style": "freundlich-strukturiert", "notes": "..."},
  "insider_facts": ["..."],                      // facts a well-prepared candidate could know (for 'preparation' evaluation)
  "synthetic": true
}
```

## `scenarios/scenarios.jsonl`

```jsonc
{
  "id": "S-01",
  "title": "...",
  "situation": "apprenticeship_interview",   // phone_call_trial | trial_interview | online_interview | apprenticeship_interview | assessment | follow_up_interview
  "candidate_id": "C-01", "posting_id": "P-01",
  "lang": "de", "dialect_expected": "gr",    // null if the candidate speaks standard language
  "duration_min": 30,
  "interviewer_style": "...",
  "planned_question_ids": ["Q-01-01", "..."],   // suggested sequence following the flow
  "adaptive_hooks": ["If the candidate mentions X, ask Y"],
  "evaluation_focus": ["motivation", "concrete_examples"],
  "difficulty": "medium",
  "success_criteria_for_coach": ["..."],     // what a good AI coach must do in this scenario (for LLM-as-judge)
  "synthetic": true
}
```

## `transcripts/transcripts.jsonl`

```jsonc
{
  "id": "T-01",
  "scenario_id": "S-01", "candidate_id": "C-01", "posting_id": "P-01",
  "occupation": {"name_de": "...", "occupation_id": "..."},
  "situation": "apprenticeship_interview", "lang": "de", "dialect": null,
  "overall_quality": "strong",               // strong | mixed | weak
  "title": "...",
  "turns": [
    {"speaker": "interviewer", "text": "...", "phase": 1, "question_id": "Q-01-01"},
    {"speaker": "candidate", "text": "...", "phase": 1, "quality_level": 3, "answer_id": null, "note": null}
  ],
  "reference_feedback": {                    // gold-standard final feedback following the FHGR feedback prompt
    "lang": "de",
    "criteria": [{"criterion": "clarity", "level": 3, "evidence": "...", "rationale": "...", "tip": "..."}],
    "summary": "...", "closing": "..."
  },
  "notes": "...", "source": "synthetic", "synthetic": true
}
```

## `feedback_examples/feedback_examples.jsonl`

```jsonc
{
  "id": "F-01",
  "lang": "de",
  "scope": "single_answer",                  // single_answer | full_interview
  "context": {"question": "...", "answer": "...", "occupation": "...", "candidate_age": 15, "transcript_id": null},
  "good_feedback": "...",
  "good_feedback_notes": "...",              // why it is good (German), guideline rule ids
  "poor_feedback": "...",
  "poor_feedback_violations": ["T3", "B3", "K2"],   // rule ids from rubric/feedback_guidelines.json
  "poor_feedback_notes": "...",              // why it is poor (German)
  "failure_mode": "harsh",                   // harsh | overpraise | vague | personality_label | jargon | fear | hallucinated_evidence | too_long | no_next_step | comparison | wrong_language | ignores_distress | grading_not_coaching
  "synthetic": true
}
```

## `occupations.csv`

Occupation data scraped from [berufsberatung.ch](https://www.berufsberatung.ch) (SDBB), one row per occupation (1,860 rows, German only). Comma-separated with a header row; long text fields are quoted and flattened to one line.

| Column | Meaning |
|---|---|
| `Beruf` | occupation name incl. qualification, e.g. `Hotel-Kommunikationsfachmann/-frau EFZ` |
| `id` | berufsberatung.ch id; target of `occupation_id` in answers and postings |
| `url` | profile page on berufsberatung.ch |
| `Bildungstypen` | type of training: `Grundbildung (Lehre)` (259 apprenticeships), `Berufsfunktion / Spezialisierung`, `Weiterbildungsberuf`, `Hochschulberuf` |
| `Branchen` | industries, comma-separated (sub-items joined with ` - `) |
| `Berufsfelder` | occupational field(s), matching the 22 *Berufsfelder* used for `Q-BFxx` questions |
| `Swissdoc` | Swissdoc classification code |
| `Tätigkeiten` | typical activities |
| `Ausbildung` | training path, duration, vocational school, BM options |
| `Voraussetzungen` | prior education (`Vorbildung`) and requirements (`Anforderungen`) |
| `Bemerkungen` | remarks (often empty) |
| `Weitere Informationen` | addresses and links of professional associations |

For apprenticeship interviews, filter on `Bildungstypen == "Grundbildung (Lehre)"`:

```python
import pandas as pd

occ = pd.read_csv("datasets/occupations.csv", dtype={"id": str})
apprenticeships = occ[occ["Bildungstypen"].str.contains("Grundbildung")]
```

## Optional extra fields

Some generators added fields that are not in the core schemas above. They are optional and may be absent:

| File | Field | Meaning |
|---|---|---|
| postings | `occupation.fachrichtung`, `occupation.schwerpunkt` | specialisation of the apprenticeship (e.g. Applikationsentwicklung, Garten- und Landschaftsbau) |
| postings | `occupation.alternative` | alternative qualification offered (P-24: Logistiker/in EBA) |
| candidates | `school.leistungstest`, `school.multicheck` | results of cantonal performance tests (e.g. Check S3) or aptitude tests |
| transcripts | `needs_native_review` | true for fr / it / gsw transcripts |
| transcripts → turns | `normalized_de` | Standard German rendering of a dialect turn |
| transcripts → turns | `note` | stage direction (e.g. assessment group task, looking at notes) |
| questions | `translation_review` | review status of the fr/it/gsw texts |
| answers (source) | `source_features_de`, `source_raw` | FHGR's own characteristics of the answer; the original text before editorial corrections |
