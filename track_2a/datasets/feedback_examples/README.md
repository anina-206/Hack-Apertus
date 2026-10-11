# Good vs poor AI feedback

`feedback_examples.jsonl` (F-01 … F-30): each record pairs a **good** coach feedback with a **poor** one for the same context. Every poor feedback shows one typical LLM failure, labelled with a `failure_mode` and with the violated guideline rules (`poor_feedback_violations`, ids from [`../rubric/feedback_guidelines.json`](../rubric/feedback_guidelines.json)). The notes on both feedbacks are in German.

| Ids | Scope | Language |
|---|---|---|
| F-01 … F-24 | single answer | 16 de, 4 fr, 4 it |
| F-25, F-26 | full interview (FHGR Konstrukteur example, strong / weak): the good feedback uses the exact FHGR table format | de |
| F-27, F-28 | full interview, **spoken** feedback for text-to-speech (about 110 words, no table) vs reading the table aloud or reading out grades | de |
| F-29, F-30 | full interview (short excerpt) | fr, it |

**Failure modes covered:** harsh · overpraise · vague · personality_label · jargon · fear · hallucinated_evidence · too_long · no_next_step · comparison · wrong_language · ignores_distress · grading_not_coaching.

## Uses

- contrastive few-shot examples in the feedback prompt ("do this, not that")
- unit tests for your own feedback checker: does it flag the poor version with the right rules?
- preference pairs (chosen = good, rejected = poor) for DPO-style fine-tuning
