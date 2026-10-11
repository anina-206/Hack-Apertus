# FHGR Interview-Coach Datasets — HackApertus 2026, Track 2A



## What is included

Mapped to the resources listed in the challenge description:

| Challenge resource | Where | Format |
|---|---|---|
| Example interview questions (common and role-specific) | [`questions/`](questions/) | JSONL: 10 interview phases, 22 occupational fields (*Berufsfelder*), situational and difficult questions, other application situations. de/fr/it plus Swiss German variants |
| Example candidate answers at different quality levels | [`answers/`](answers/) | JSONL: levels 1–4, classes strong / weak / incomplete / problematic. de, fr, it and 8 Swiss German dialects |
| Expert/didactic annotations (strong, weak, incomplete, problematic) | [`annotations/`](annotations/) | JSONL, one per answer: criterion scores, strengths/weaknesses, expert comment, coach feedback, follow-up question, improved answer, coach action |
| Evaluation criteria | [`rubric/`](rubric/) | JSON: the FHGR 11-criterion × 4-level rubric (the 6 challenge criteria flagged as core) and the feedback rules with ids |
| German examples incl. Swiss German dialect examples | answers with `lang: "gsw"`, `questions[].gsw_variants`, dialect transcripts | — |
| Synthetic candidate profiles and job/apprenticeship descriptions | [`profiles/`](profiles/) | JSONL: 24 candidates, 30 apprenticeship postings linked to real occupations from berufsberatung.ch |
| Sample interview scenarios | [`scenarios/`](scenarios/) | JSONL: 28 scenarios (candidate × posting × situation), with planned questions, adaptive hooks and checkable success criteria for an LLM judge |
| Full example interviews | [`transcripts/`](transcripts/) | JSONL: the FHGR Konstrukteur example (strong and weak) and synthetic interviews in de, fr, it and dialect, each with gold reference feedback |
| Examples of good vs poor AI feedback | [`feedback_examples/`](feedback_examples/) | JSONL: pairs with violated rules and typical LLM failure modes, for single answers, full interviews and spoken (TTS) feedback |
| Guidelines on constructive feedback for adolescents | [`docs/feedback_guidelines.md`](docs/feedback_guidelines.md) | Markdown, including the FHGR reference feedback prompt |
| Suggested interview flow | [`docs/interview_flow.md`](docs/interview_flow.md) | Markdown: FHGR 10 phases ↔ challenge flow ↔ question ids |
| Swiss apprenticeship application/interview process | [`docs/application_process.md`](docs/application_process.md), [`docs/interview_situations.md`](docs/interview_situations.md) | Markdown |
| Swiss education & VET system (EBA/EFZ, BM1/BM2) | [`docs/swiss_vet_system.md`](docs/swiss_vet_system.md) | Markdown |
| Occupation data (all Swiss occupations, incl. 259 apprenticeships) | [`occupations.csv`](occupations.csv) | CSV from berufsberatung.ch: 1,860 occupations with activities, training, requirements and *Berufsfelder*; referenced by `occupation_id` |

## Directory layout

```
datasets/
├── README.md                 ← you are here
├── SCHEMA.md                 ← field-by-field schemas and conventions
├── STATS.md                  ← generated counts and distributions
├── occupations.csv           ← berufsberatung.ch occupation data (1,860 occupations)
├── questions/                questions.jsonl
├── answers/                  answers.jsonl
├── annotations/              annotations.jsonl
├── rubric/                   criteria.json, feedback_guidelines.json
├── profiles/                 candidates.jsonl, postings.jsonl
├── scenarios/                scenarios.jsonl
├── transcripts/              transcripts.jsonl
├── feedback_examples/        feedback_examples.jsonl
├── docs/                     background and didactic documentation
└── scripts/                  validation script (+ the original build scripts, for reference)
```

Each data folder has its own `README.md` with purpose, examples and usage notes.

## Quick start

```python
import json
load = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]

questions   = {q["id"]: q for q in load("datasets/questions/questions.jsonl")}
answers     = {a["id"]: a for a in load("datasets/answers/answers.jsonl")}
annotations = {x["answer_id"]: x for x in load("datasets/annotations/annotations.jsonl")}

# All French answers to "Why this occupation?" with their expert annotation
for a in answers.values():
    if a["question_id"] == "Q-03-01" and a["lang"] == "fr":
        print(a["quality_level"], a["text"], "→", annotations[a["id"]]["coach_feedback"])
```

`pandas.read_json(path, lines=True)` also works for every `.jsonl` file.

## How the pieces fit together

```
postings (P-xx) ──┐                       ┌── questions (Q-…) ── criteria ── rubric
                  ├── scenarios (S-xx) ───┤
candidates (C-xx)─┘         │             └── transcripts (T-…) ── reference_feedback
                            │
answers (A-…) ── question_id / occupation / candidate_id
   └── annotations (answer_id) ── guideline_refs ── feedback_guidelines (T1…A1)
feedback_examples (F-xx) ── poor_feedback_violations ── feedback_guidelines
```

## Suggested uses

| Use | Data |
|---|---|
| **Interviewer prompt / question planning** | `questions` (flow_stage, criteria, condition), `scenarios.planned_question_ids`, `postings` (company facts for answering the candidate's questions) |
| **Adaptive follow-ups** | `annotations.follow_up_question`, `annotations.coach_action`, `scenarios.adaptive_hooks` |
| **Answer assessment** (few-shot or fine-tuning) | `answers` + `annotations.criteria_scores` / `quality_level` / `answer_class` |
| **Feedback generation** | `annotations.coach_feedback`, `transcripts.reference_feedback`, `feedback_examples.good_feedback`, `docs/feedback_guidelines.md` |
| **Guardrails** (distress, manipulation, discrimination) | answers with `answer_class = problematic` and their `problem_flags` / `coach_action` |
| **Candidate simulation for automatic evaluation** | `candidates.simulation_persona`, `scenarios`, `transcripts` |
| **Your own LLM-as-judge checks** | `rubric/criteria.json`, `scenarios.success_criteria_for_coach`, `feedback_examples` (poor vs good), `rubric/feedback_guidelines.json` rule ids |
| **Multilingual consistency** | the same question ids across de / fr / it / gsw; FR and IT answers to the same 14 anchor questions |

> **Note on evaluation:** the official LLM-as-judge metrics and prompts are published separately by the challenge organisers. The data here is for development, not the hidden benchmark. Avoid overfitting to the exact wording of these examples.

## Provenance and generation

| Origin | Records | Flag |
|---|---|---|
| **FHGR / Profolio material**, verbatim | questions from *Beispielfragen*; answers `A-SRC-KR-*` (Kriterienraster) and `A-SRC-KT-*` (Konstrukteur example); transcripts `T-SRC-01/02`; rubric and guidelines | `synthetic: false` / `source` field |
| **Synthetic**, LLM-generated from a fixed specification ([`SCHEMA.md`](SCHEMA.md), rubric, guidelines, FHGR examples as anchors) | all other answers, all annotations, translations, dialect variants, profiles, postings, scenarios, synthetic transcripts, feedback examples | `synthetic: true` |
| **berufsberatung.ch** occupation data | [`occupations.csv`](occupations.csv), used for occupation ids, activities and requirements in postings and answers | `occupation_id` |

The published files are the final, merged output of the generation pipeline. The intermediate generator outputs and the FHGR originals are not part of this repository, so the dataset cannot be rebuilt from here. To check the data (for example after your own changes), run the validator:

```bash
cd datasets
python3 scripts/validate.py   # schema + cross-reference + spelling checks
```

The other scripts in [`scripts/`](scripts/) (`build_questions.py`, `build_rubric.py`, `build_source_answers.py`, `merge_parts.py`) are kept for reference only. **Do not run them:** they write directly into the published files, and most of them depend on inputs that are not included here.

## Limitations

- **Synthetic content is unreviewed** (`review_status: "unreviewed"`, `translation_review: "unreviewed"`). Expert review by FHGR and native speakers is recommended, especially for:
  - **Swiss German dialect** texts (`needs_native_review: true`). Dialect spelling is not standardised, and LLM-written dialect can contain mixed or unnatural forms.
  - French and Italian school-system terms, which vary by canton.
- **Form of address.** The interviewer says «tu» in all French and Italian data, mirroring the German «du» in the FHGR material. In the Romandie and Ticino, «vous» / «Lei» is often more usual (see [docs/application_process.md](docs/application_process.md)), so make it configurable.
- **Source levels.** Five FHGR example answers may deserve a level one lower under a strict reading of the rubric. See [annotations/src_level_proposals.json](annotations/src_level_proposals.json); a decision by FHGR is needed.
- **Annotation levels are one expert view.** Interview answers are judged somewhat subjectively; neighbouring levels (2 vs 3) can legitimately differ.
- **Companies, persons and facts in postings are fictional.** Any resemblance to real companies is unintended. Occupation data (activities, requirements, duration) comes from berufsberatung.ch and can change (e.g. revised training ordinances).
- **Written, not spoken, language.** Real spoken answers contain more disfluencies. For text-to-speech or speech-to-text scenarios, see the spoken feedback examples (F-27, F-28).
- **Coverage**: 30 of the 259 apprenticeships in `occupations.csv` have postings; answers cover all 22 occupational fields, but with few examples per field.

## Licence and attribution

The FHGR/Profolio didactic material (records with `synthetic: false`, the rubric and the feedback guidelines) belongs to FHGR, the University of Applied Sciences of the Grisons, and is provided for use in the HackApertus challenge. Please check with FHGR before other use. Occupation data comes from [berufsberatung.ch](https://www.berufsberatung.ch) (SDBB). Synthetic records are provided for the hackathon under the same conditions.

Contact: Norman Süsstrunk, FHGR (challenge provider).
