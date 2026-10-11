# Expert / didactic annotations

`annotations.jsonl`: one annotation per answer in [`../answers/answers.jsonl`](../answers/), joined on `answer_id`. The annotations explain what makes an answer strong, weak, incomplete or problematic, and show how a good coach would respond. The field reference is in [../SCHEMA.md](../SCHEMA.md#annotationsannotationsjsonl).

| Field | Language | Use |
|---|---|---|
| `quality_level`, `answer_class` | – | holistic label (identical to the answer) |
| `criteria_scores` | – | per-criterion levels 1–4; `null` means no evidence in this answer (never guessed) |
| `strengths`, `weaknesses`, `missing_elements` | de | didactic analysis, quoting the answer |
| `problem_flags` | – | e.g. `distress_signal`, `manipulation_attempt`, `badmouthing`, `discriminatory` … |
| `coach_action` | – | `continue` · `probe` (ask for an example) · `redirect` (back on topic / decline a manipulation attempt) · `support_and_refer` (take distress seriously, point to a real person) |
| `expert_comment` | de | why this level, and what separates it from the next level |
| `coach_feedback` | answer language (gsw → de) | model feedback to the student, following the FHGR guidelines |
| `guideline_refs` | – | the rules from [`rubric/feedback_guidelines.json`](../rubric/feedback_guidelines.json) that the feedback applies |
| `follow_up_question` | answer language | what an adaptive interviewer would ask next |
| `improved_answer` | answer language | a realistic level-4 version (same facts where possible, sounds like a teenager) |

## Example (answer `A-DE1-0034`, level 2)

```json
{"criteria_scores": {"motivation": 2, "relevance": 3, "goal_orientation": 2},
 "weaknesses": ["Wirkt von aussen bestimmt: «sie hat gesagt»", "Kein eigenes Erlebnis"],
 "coach_action": "probe",
 "coach_feedback": "Du hast gesagt, dass du gern Leuten hilfst. Das passt sehr gut zum Beruf Fachfrau Gesundheit. Im Moment klingt es aber noch so, als hätte vor allem deine Mutter entschieden. Erzähl lieber, wo du selbst gemerkt hast, dass dir das liegt, zum Beispiel beim Schnuppern. Dann wird klar, dass es deine eigene Entscheidung ist.",
 "follow_up_question": "Wann hast du selbst gemerkt, dass dir das Helfen liegt?",
 "guideline_refs": ["R1", "K1", "R2", "K2", "A1"]}
```

## Caveats

- `annotator: "synthetic-llm"` and `review_status: "unreviewed"` for all records. The annotations follow the FHGR rubric closely, but have not yet been checked by FHGR experts.
- Neighbouring levels (2/3) are partly subjective. Evaluate with tolerance (e.g. ±1 agreement), not only exact match.
- Annotations of dialect answers never penalise the dialect itself. Annotations of second-language answers never penalise the language level.

## Proposed level changes for FHGR source answers

The source answers (`A-SRC-*`) keep the levels pre-assigned from the FHGR columns. During annotation, 5 of them were judged one level lower under a strict reading of the rubric; for example, «zu perfektionistisch» counts as a hidden strength, which the Kriterienraster itself lists as a weak-answer feature. The proposals are in [`src_level_proposals.json`](src_level_proposals.json) for a decision by FHGR. To apply one, change the level maps in `scripts/build_source_answers.py` and the matching annotation.
