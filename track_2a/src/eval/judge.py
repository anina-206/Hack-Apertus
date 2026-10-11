"""LLM-as-judge for the final feedback, using an open model (Apertus 70B), only in the eval.

The coach itself only uses Apertus 8B. Configure the judge with JUDGE_NAME (e.g. the
Apertus 70B model id on the CSCS API); JUDGE_BASE_URL and JUDGE_API_KEY default to the
LLM_* values. Without JUDGE_NAME the benches skip the judge.
"""

import json
import os
from typing import Optional

from pydantic import BaseModel, field_validator

from backend.interview.parsing import JSONParseError, parse_json
from eval.fhgr import DATASETS

# What the judge rates, 1-5 each. The FHGR rule ids refer to datasets/rubric/feedback_guidelines.json.
DIMENSIONS = {
    "grounding": "Every point refers to something the candidate really said; nothing is invented (K1, K3).",
    "accuracy": "Strengths and weaknesses match the transcript and the reference feedback.",
    "actionable": "Concrete, feasible next steps instead of vague advice (R3, K2).",
    "tone": "Encouraging and age-appropriate; about behaviour, not the person; no fear, no comparisons (T, B, E, M, L).",
    "language": "Language of the interview, informal du/tu, short and simple sentences (S).",
}


class Verdict(BaseModel):
    scores: dict[str, int]
    violations: list[str] = []
    comment: str = ""

    @field_validator("scores", mode="before")
    @classmethod
    def _all_dimensions(cls, raw):
        if not isinstance(raw, dict):
            raise ValueError("scores must be an object")
        scores = {k: max(1, min(5, int(round(float(v))))) for k, v in raw.items() if k in DIMENSIONS}
        missing = [k for k in DIMENSIONS if k not in scores]
        if missing:
            raise ValueError(f"missing scores: {', '.join(missing)}")
        return scores


class ScenarioVerdict(Verdict):
    criteria_met: list[bool]  # one per success criterion of the scenario, in order


def _guidelines() -> str:
    with open(DATASETS / "rubric" / "feedback_guidelines.json", encoding="utf-8") as f:
        groups = json.load(f)["groups"]
    return "\n".join(f"{r['id']}: {r['en']}" for g in groups for r in g["rules"])


def configured() -> bool:
    return bool(os.environ.get("JUDGE_NAME"))


class Judge:
    def __init__(self):
        from openai import AsyncOpenAI

        self.model = os.environ["JUDGE_NAME"]
        self.client = AsyncOpenAI(base_url=os.environ.get("JUDGE_BASE_URL") or os.environ["LLM_BASE_URL"],
                                  api_key=os.environ.get("JUDGE_API_KEY") or os.environ["LLM_API_KEY"])
        self.calls = 0

    async def _ask(self, system: str, user: str, model):
        for _ in range(2):
            self.calls += 1
            response = await self.client.chat.completions.create(
                model=self.model, temperature=0.0,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            )
            try:
                return parse_json(response.choices[0].message.content or "", model).model_dump()
            except JSONParseError:
                continue
        return None

    async def rate_scenario(self, transcript: str, report: dict, success_criteria: list[str]) -> Optional[dict]:
        """A whole interview (coach questions + final feedback) against an FHGR scenario's success criteria."""
        ours = {k: report[k] for k in ("criteria", "strengths", "improvements", "closing")}
        numbered = "\n".join(f"{i + 1}. {c}" for i, c in enumerate(success_criteria))
        dimensions = "\n".join(f"- {k}: {v}" for k, v in DIMENSIONS.items())
        system = (
            "You are a strict evaluator of an AI interview coach for 14-16 year olds applying for an apprenticeship "
            "in Switzerland. You get the whole practice interview and the coach's final feedback.\n"
            f"1. For each success criterion, decide if the coach met it (true/false):\n{numbered}\n"
            f"2. Rate the final feedback from 1 (poor) to 5 (excellent) on:\n{dimensions}\n\n"
            f"Feedback rules (FHGR):\n{_guidelines()}\n\n"
            'Respond with ONLY a JSON object: {"criteria_met": [true, false, ...], "scores": {"grounding": 1-5, ...}, '
            '"violations": ["rule ids the feedback breaks"], "comment": "one sentence"}'
        )
        user = f"Interview:\n{transcript}\n\nFinal feedback (JSON):\n{json.dumps(ours, ensure_ascii=False)}"
        verdict = await self._ask(system, user, ScenarioVerdict)
        if verdict:
            verdict["criteria_met"] = (verdict["criteria_met"] + [False] * len(success_criteria))[:len(success_criteria)]
        return verdict

    async def rate_report(self, transcript: str, report: dict, reference: Optional[dict] = None) -> Optional[dict]:
        """Rate one final report. Returns the verdict as a dict, or None if the judge's JSON was unusable."""
        ours = {k: report[k] for k in ("criteria", "strengths", "improvements")}
        dimensions = "\n".join(f"- {k}: {v}" for k, v in DIMENSIONS.items())
        system = (
            "You are a strict evaluator of feedback that an AI coach gave a 14-16 year old after a practice job "
            "interview for an apprenticeship in Switzerland. Rate the AI feedback on each dimension from "
            "1 (poor) to 5 (excellent):\n"
            f"{dimensions}\n\nFeedback rules (FHGR):\n{_guidelines()}\n\n"
            'Respond with ONLY a JSON object: {"scores": {"grounding": 1-5, ...}, '
            '"violations": ["rule ids that the AI feedback breaks"], "comment": "one sentence"}'
        )
        user = f"Transcript:\n{transcript}\n\nAI feedback (JSON):\n{json.dumps(ours, ensure_ascii=False)}"
        if reference:
            user += f"\n\nReference feedback written by an expert (JSON):\n{json.dumps(reference, ensure_ascii=False)}"
        return await self._ask(system, user, Verdict)
