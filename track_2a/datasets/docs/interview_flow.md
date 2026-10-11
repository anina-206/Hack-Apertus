# Suggested interview flow

Source: *Möglicher Ablauf eines Bewerbungsgesprächs* and *Beispielfragen Vorstellungsgespräch* (FHGR / Profolio). The original German material is not included in this repository. Its content is available in structured form in [`../questions/`](../questions/) and [`../rubric/`](../rubric/).

A typical Swiss apprenticeship interview (*Vorstellungsgespräch für eine Lehrstelle*) lasts **30–60 minutes**. It is run by the *Berufsbildner/in* (the person responsible for apprentices), sometimes together with a line manager or HR. The interviewer addresses the 14–16-year-old candidate informally (**du / tu**). The FHGR material describes ten phases. The challenge description condenses them into six stages, and the table below shows how they map.

## Phases, subtopics and question ids

| # | FHGR phase (de) | Subtopics | Challenge stage (`flow_stage`) | Question ids | Main criteria |
|---|---|---|---|---|---|
| 1 | Begrüssung und Einstieg | introduce participants, small talk, explain the procedure | introduction | `Q-01-01…05` | demeanor, communication |
| 2 | Vorstellung der Bewerberin / des Bewerbers | school career, hobbies | introduction | `Q-02-01…08` | clarity, communication, self_reflection |
| 3 | Motivation | reasons for the career choice, interest in the occupation, why this company, expectations, personal goals, further development | motivation | `Q-03-01…07` | motivation, relevance, goal_orientation |
| 4 | Kenntnisse über den Beruf und den Betrieb | knowledge of the occupation, information about the company, expectations of the training | motivation | `Q-04-01…10` + occupation-specific `Q-BFxx-yy` | preparation, relevance |
| 5 | Persönliche Stärken und Entwicklung | strengths, weaknesses, handling challenges, willingness to learn | strengths_weaknesses | `Q-05-01…10` | self_reflection, concrete_examples |
| 6 | Schule und Erfahrungen | favourite subjects, report card / Stellwerk / work attitude, Schnupperlehre and internships, projects and achievements | strengths_weaknesses | `Q-06-01…10` | self_reflection, concrete_examples |
| 7 | Soziale Kompetenzen | teamwork, communication, conflict resolution | strengths_weaknesses | `Q-07-01…09` | concrete_examples, communication |
| – | *Situational questions (synthetic)* | behaviour in typical apprenticeship situations | situational | `Q-SIT-01…12` | concrete_examples, relevance, clarity |
| – | *Difficult / unexpected questions (synthetic)* | pressure questions, gaps, grades, plan B | situational | `Q-DIF-01…10` | difficult_questions, self_reflection |
| 8 | Zukunft | career goals | motivation | `Q-08-01…09` | goal_orientation, motivation |
| 9 | Fragen der Bewerberin / des Bewerbers | open questions about the company, the apprenticeship or daily work | candidate_questions | `Q-09-01…09` | initiative, preparation |
| 10 | Abschluss | summary, next steps, goodbye | closing | `Q-10-01…04` | demeanor, communication |
| – | **Feedback** (coach only, not part of a real interview) | criteria-based feedback, see [feedback_guidelines.md](feedback_guidelines.md) | feedback | – | all 11 |

Challenge flow: **introduction → motivation → strengths/weaknesses → situational questions → candidate questions → feedback**.

### Notes for implementation

- **Occupation-specific questions** (`Q-BFxx-yy`) are organised by the 22 *Berufsfelder* (occupational fields of Swiss career guidance). To find a posting's field, use `occupation.berufsfeld_key` in `profiles/postings.jsonl`. For any occupation, the `Berufsfelder` column in [`occupations.csv`](../occupations.csv) gives the same information.
- **Conditional questions**: `Q-06-06` (Stellwerk) should only be asked if the candidate took the Stellwerk test. `Q-DIF-04` and `Q-DIF-06` should only be asked if the profile gives a reason (absences, a low grade). The `condition` field holds these rules.
- **Adaptivity**: every annotation contains a `follow_up_question`. It shows how a good interviewer probes a vague answer ("Kannst du mir ein Beispiel geben?"). Each scenario in `scenarios/scenarios.jsonl` has `adaptive_hooks`.
- **Pacing**: the FHGR example interview has about 24 exchanges in 45 minutes. A practice session for a 15-year-old usually covers **10–15 main questions**, plus follow-ups.
- **Candidate questions (phase 9)**: the coach, acting as the company, must be able to answer plausibly. `profiles/postings.jsonl` gives it `company`, `offers`, `insider_facts` and `selection_process` for that.

## Other application situations

The same logic applies to shorter formats. See [interview_situations.md](interview_situations.md):

| Situation (`situation`) | Typical flow | Question ids |
|---|---|---|
| `phone_call_trial`: call to request a *Schnupperlehre* | greeting and full name → school/class → reason for the call → ask for dates → agree on a date → thanks and goodbye | `Q-OTH-01…03` |
| `trial_interview`: short talk before or at the start of a *Schnupperlehre* | motivation, interest, reliability, expectations (less formal) | `Q-OTH-04…06` + phases 2–3 |
| `online_interview`: video interview | tech check → normal flow; pay attention to camera, sound and background | `Q-OTH-07…08` + all phases |
| `assessment`: structured selection in larger companies | interview + group task + short presentation + reflection | `Q-OTH-09…11` |
| `follow_up_interview`: second interview after a *Schnupperlehre* | impressions, reflection, open questions, next steps | `Q-OTH-12…14` |
