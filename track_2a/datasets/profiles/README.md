# Candidate profiles and apprenticeship postings

These files are for personalised interviews. The interviewer adapts its questions to the posting and the candidate, and a simulator can play the candidate. Field reference: [../SCHEMA.md](../SCHEMA.md#profilescandidatesjsonl).

## `postings.jsonl` (P-01 … P-30)

Fictional companies, each linked to a **real apprenticeship** from berufsberatung.ch (`occupation.occupation_id` → [`occupations.csv`](../occupations.csv)). Requirements, duration, EFZ/EBA and whether the vocational baccalaureate (BM) is possible come from that data.

- **Languages**: 22 German, 5 French (Romandie) and 3 Italian (Ticino). All 22 *Berufsfelder* are covered, plus two EBA apprenticeships.
- **`posting_text`**: a realistic apprenticeship ad in the posting language.
- **`interviewer`**: persona (name, role, style, notes). Use it for the interviewer's voice.
- **`insider_facts`**: facts a well-prepared candidate could know. The coach uses them to evaluate *preparation* and to answer the candidate's questions.
- **`selection_process`**: the company's steps (dossier, aptitude test, Schnupperlehre, interview, assessment …).
- **Extra keys** beyond the schema appear on some postings: `occupation.fachrichtung` / `occupation.schwerpunkt` (specialisation), and `occupation.alternative` (P-24: EBA alternative).
- **P-01** reproduces the setting of the FHGR Konstrukteur example interview.

## `candidates.jsonl` (C-01 … C-24)

Synthetic 15–17-year-old school leavers from all language regions. They differ in school level, grades, experiences, personality, dialect and background, and include deliberately sensitive cases:

| Case | Candidate | What the coach must do |
|---|---|---|
| Dyslexia | C-07 | do not assess spelling or the German grade |
| German as a second language (B1), recently arrived | C-20 | do not assess the language level; use simple language |
| Gender-atypical choice | C-02, C-18, C-24 | no stereotyped questions |
| Broken-off apprenticeship (Lehrabbruch) | C-17 | practise explaining it constructively |
| Weak grades, absences | C-15 | practise difficult questions fairly |
| Overconfidence | C-16, C-21 | support self-reflection |
| Self-doubt | C-23 | respond supportively and point to a real person (guideline L3) |

- **`simulation_persona`**: describes how to role-play the candidate (typical level, answer length, nervousness, speech style, quirks). Use it for automatic evaluation runs, where one LLM plays the candidate.
- **`coach_focus`**: 3–5 things a good coach should work on with this candidate. These can be checked by an LLM judge.
- **Extra keys** beyond the schema: some candidates have `school.leistungstest` (e.g. Check S3) or `school.multicheck`.

All persons and companies are fictional.
