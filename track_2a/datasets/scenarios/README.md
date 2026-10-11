# Interview scenarios

`scenarios.jsonl` (S-01 … S-28): each scenario combines a candidate (`candidate_id`), a posting (`posting_id`) and a situation (apprenticeship interview, online interview, phone call, trial talk, assessment, follow-up talk) in one language. Field reference: [../SCHEMA.md](../SCHEMA.md#scenariosscenariosjsonl).

| Field | Use |
|---|---|
| `planned_question_ids` | a suggested question sequence following the interview flow (10–17 questions) |
| `adaptive_hooks` | "if the candidate says X → ask/do Y": tests adaptivity |
| `evaluation_focus` | the rubric criteria this scenario mainly trains |
| `success_criteria_for_coach` | 4–6 **checkable statements** about the coach's behaviour (e.g. "Der Coach bewertet das Deutschniveau nicht"). Use them as judge items in your own LLM-as-judge tests. |
| `difficulty`, `dialect_expected` | for stratified evaluation (consistency across scenarios and languages is 25 % of the score) |

## Suggested evaluation loop

1. Load a scenario together with its posting and candidate.
2. Let a simulator LLM play the candidate using `candidate.simulation_persona`.
3. Run your coach through the interview and final feedback.
4. Let a judge LLM check the rubric plus `success_criteria_for_coach`.
5. Aggregate the results by `lang`, `situation` and `difficulty`.

Thirteen scenarios have a fully written example run in [`../transcripts/`](../transcripts/).
