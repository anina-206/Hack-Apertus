# Interview transcripts

`transcripts.jsonl`: complete interviews, turn by turn, each with a **gold reference feedback** that follows the FHGR feedback prompt (11 criteria with level, evidence quote, rationale and tip, then a summary and a closing sentence). Field reference: [../SCHEMA.md](../SCHEMA.md#transcriptstranscriptsjsonl).

| Id | Content |
|---|---|
| `T-SRC-01`, `T-SRC-02` | The FHGR example interview for **Konstrukteur/in EFZ**, strong and weak variant, verbatim. Both variants use identical interviewer turns, so some transitions sound odd in the weak version. Their reference feedback is in `feedback_examples` F-25/F-26. |
| `T-01` … `T-07` | Synthetic German interviews, including a dialect interview (Lucerne), a phone call in Solothurn dialect, a nervous candidate, difficult questions, a second-language speaker and a candidate showing self-doubt |
| `T-08` … `T-13` | Synthetic French (online interview; explaining a broken-off apprenticeship), Italian, an assessment, and an Upper Valais dialect interview |
| `T-14` … `T-21` | Synthetic interviews along the coach's own flow (Einstieg → Motivation → Stärken/Schwächen → Situationsfragen → Fragen → Abschluss) at the postings P-31 … P-56: German (strong; weak with short answers), Bernese and Zurich dialect (mixed), French (strong; mixed) and Italian (strong; weak with a problematic answer). No scenario (`scenario_id: null`) |

## Per-turn fields

- `speaker`: `interviewer` or `candidate`
- `phase`: the FHGR phase 1–10
- `question_id`: set when the interviewer asks a question from the bank
- `quality_level`: set on substantive candidate turns
- `normalized_de`: Standard German, on dialect transcripts
- `note`: stage directions, e.g. during the assessment

## Uses

- few-shot demonstrations of adaptive interviewing
- evaluating end-of-interview feedback against `reference_feedback`
- testing the per-turn scorer against `quality_level`
- long-context tests: do you stay under 5 LLM calls per answer?
