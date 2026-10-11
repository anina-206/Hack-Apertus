# AI-Powered Job Interview Coach — HackApertus 2026, Track 2A (FHGR)

Public repository for the FHGR challenge at **HackApertus 2026**. It contains the challenge presentation, the datasets and a project template to start your implementation.

## The challenge

Young people in Switzerland usually apply for an apprenticeship straight out of lower secondary school, often in their very first formal interview, at age 14–16. Teachers cannot run repeated one-to-one mock interviews with individual feedback for every student.

**Your task:** build an **Apertus-based coach** that runs realistic apprenticeship interviews and gives constructive feedback.

| | |
|---|---|
| **Adaptive interview** | Asks questions, listens, follows up on vague answers, adapts to the candidate and the job. |
| **Useful feedback** | Based on the criteria, age-appropriate, with a concrete next step for each teenager. |
| **Multilingual** | German, French and Italian. Swiss German dialects are a plus. |
| **Voice-ready** | Designed so that real-time text-to-speech can be added later. |

### Interview flow

The coach should cover six stages, mapped to FHGR's ten interview phases (details: [datasets/docs/interview_flow.md](datasets/docs/interview_flow.md)):

1. **Introduction**: greeting, small talk, self-presentation
2. **Motivation**: why this job and company, knowledge, future goals
3. **Strengths & weaknesses**: self-reflection, school, trial days (*Schnupperlehre*), teamwork
4. **Situational**: «Stell dir vor …», job-specific and difficult questions
5. **Candidate questions**: the coach answers as the company
6. **Feedback**: coach only, on the 11 criteria, with next steps

A practice session usually covers 10–15 main questions plus follow-ups.

### Rules

- **Model:** Apertus 1.5 · 8B
- **Hardware:** < 32 GB VRAM, consumer hardware, on-premise
- **Efficiency:** < 5 LLM calls per candidate answer, on average
- **Deliverables:** Docker container, source code, documentation and a visual overview

### Judging

| Weight | Criterion |
|---:|---|
| 50 % | **Performance**: LLM-as-judge benchmark |
| 25 % | **Consistency**: across scenarios, profiles and languages |
| 25 % | **Innovation**: methods and architectures |

The judge metrics and prompts are published separately by the organisers. The datasets in this repository are for development and are **not** the hidden benchmark.

## Repository layout

```
.
├── presentation/       challenge_and_datasets.pdf (slides from the info session)
├── datasets/           questions, answers, annotations, rubric, profiles, scenarios,
│                       transcripts, feedback examples, occupation data and background docs
└── project-template/   starter project (LangGraph + Aegra + Agent Chat UI)
```

## Datasets

The data builds on the didactic material of the FHGR / Profolio platform, extended with carefully specified synthetic data and real occupation data from berufsberatung.ch. All data files are JSON Lines, except the occupation data (CSV).

| Data | Records | Folder |
|---|---:|---|
| Interview questions (de/fr/it, plus 296 Swiss German variants) | 242 | [datasets/questions/](datasets/questions/) |
| Candidate answers at 4 quality levels (de, fr, it, 8 dialects) | 706 | [datasets/answers/](datasets/answers/) |
| Expert annotations, one per answer | 706 | [datasets/annotations/](datasets/annotations/) |
| Rubric (11 criteria × 4 levels) and 27 feedback rules | — | [datasets/rubric/](datasets/rubric/) |
| Candidate profiles / apprenticeship postings | 24 / 30 | [datasets/profiles/](datasets/profiles/) |
| Interview scenarios with judge criteria | 28 | [datasets/scenarios/](datasets/scenarios/) |
| Full interviews with reference feedback | 15 (444 turns) | [datasets/transcripts/](datasets/transcripts/) |
| Good vs poor AI feedback pairs | 30 | [datasets/feedback_examples/](datasets/feedback_examples/) |
| Occupation data from berufsberatung.ch (incl. 259 apprenticeships) | 1,860 | [datasets/occupations.csv](datasets/occupations.csv) |
| Background: Swiss VET system, application process, feedback guidelines | — | [datasets/docs/](datasets/docs/) |

```python
import pandas as pd

answers = pd.read_json("datasets/answers/answers.jsonl", lines=True)
occupations = pd.read_csv("datasets/occupations.csv", dtype={"id": str})
```

Start with [datasets/README.md](datasets/README.md). Field-by-field schemas are in [SCHEMA.md](datasets/SCHEMA.md), counts in [STATS.md](datasets/STATS.md).

**Please keep in mind:**

- The synthetic content was checked automatically but **has not yet been reviewed by experts**.
- Swiss German spelling is not standardised, and LLM-written dialect can be off.
- Companies and persons are fictional. The occupation data (from berufsberatung.ch) is real.
- Generalise rather than copying the wording of the examples. The benchmark uses different data.

## Getting started with the project template

[project-template/](project-template/) is a minimal [LangGraph](https://github.com/langchain-ai/langgraph) agent served by [Aegra](https://github.com/aegra/aegra), which you can chat with through the [Agent Chat UI](https://github.com/langchain-ai/agent-chat-ui). The graph in [src/main.py](project-template/src/main.py) currently just echoes the user's message. Replace it with your coach.

**Prerequisites:** Python ≥ 3.12, [uv](https://docs.astral.sh/uv/), Docker (Aegra starts PostgreSQL via Docker Compose), Node.js and pnpm.

```bash
# 1. Start the agent server (port 2026)
cd project-template
cp .env.example .env
uv run aegra dev

# 2. In a separate terminal and directory, start the chat UI
git clone https://github.com/langchain-ai/agent-chat-ui.git
cd agent-chat-ui
pnpm install
pnpm dev
```

Open the Agent Chat UI in your browser, set the deployment URL to port `2026`, keep the graph id `agent`, and click **Continue**.

To run the full stack (API, PostgreSQL and Redis) in Docker, as needed for the submission:

```bash
cd project-template
uv run aegra up
```

See [project-template/README.md](project-template/README.md) for details.

## Contact

Norman Süsstrunk, norman.suesstrunk@fhgr.ch
