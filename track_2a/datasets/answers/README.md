# Candidate answers

`answers.jsonl`: example answers from young applicants (14–17) at four quality levels. Each answer has exactly one expert annotation in [`../annotations/annotations.jsonl`](../annotations/), joined on `answer_id`. The field reference is in [../SCHEMA.md](../SCHEMA.md#answersanswersjsonl) and the counts are in [../STATS.md](../STATS.md).

## Id prefixes

| Prefix | Content | Language |
|---|---|---|
| `A-SRC-KR-*` | Strong and weak example answers from the FHGR **Kriterienraster**, verbatim; non-verbal cues are in `nonverbal_note` | de |
| `A-SRC-KT-*` | Both answer columns of the FHGR **Konstrukteur/in** example interview, verbatim; editorial strike-throughs applied, original in `source_raw` | de |
| `A-DE1-*`, `A-DE2-*`, `A-DE3-*` | General questions, phases 1–3, 4–5 and 6–10 | de |
| `A-SIT-*`, `A-DIF-*` | Situational and difficult questions | de |
| `A-OCC1-*`, `A-OCC2-*` | Occupation-specific questions (22 Berufsfelder) and other application situations | de (a few gsw) |
| `A-FR-*`, `A-IT-*` | The same 14 anchor questions in French and Italian (Q-01-01, Q-02-01, Q-03-01, Q-03-04, Q-04-04, Q-05-01, Q-05-03, Q-05-05, Q-06-07, Q-07-04, Q-08-02, Q-09-09, Q-SIT-02, Q-DIF-01) | fr / it |
| `A-GSW-*` | Swiss German dialects (zh, be, bs, lu, sg, gr, vs, ag), with a Standard German version in `normalized_de` | gsw |

## Quality levels and classes

Most synthetic questions have one answer per level (1 Ungenügend, 2 Ausbaufähig, 3 Gut, 4 Sehr gut). About a third of the level-2 answers are **`incomplete`** (a key element is missing), and each block has additional **`problematic`** answers that need special handling. The definitions are in [SCHEMA.md](../SCHEMA.md#answer-classes).

The example below shows two answers to the same question (`Q-03-01`, *Warum hast du dich für diesen Beruf entschieden?*):

| Level | Answer (excerpt) |
|---|---|
| 2 | «Meine Mutter arbeitet auch im Spital, und sie hat gesagt, das wäre gut für mich. Und ich helfe gern Leuten.» |
| 4 | «Ich fahre seit vier Jahren Kart, und mit meinem Onkel schraube ich oft am Motor. Einmal hat der Motor gestottert, und wir haben zusammen den Vergaser gereinigt … In der Schnupperlehre … habe ich gesehen, dass heute viel mit Diagnosegeräten und Elektronik gemacht wird …» |

## Notes

- **`question_text`** holds the question exactly as it was asked, in the answer's language. It can differ slightly from the bank text, and FHGR example turns have `question_id: null`.
- **`occupation`** links to [`occupations.csv`](../occupations.csv) via `occupation_id`. **`candidate_id`** links to `profiles/candidates.jsonl`; only a few answers are written for a specific profile.
- **Source answers are expert examples, not real transcripts.** Level assignments for them are pre-assigned by column (strong/weak) and refined in the annotations.
- **Typical uses**: few-shot examples for answer assessment, training or testing a scorer (does it recover the `quality_level`?), and simulating candidates at a target level.
