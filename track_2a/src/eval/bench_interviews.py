"""Bench 3: FHGR scenarios as complete interviews through the running API, with simulated candidates.

Each scenario (datasets/scenarios) brings a candidate profile (C-xx, incl. a simulation persona)
and a posting (P-xx). Apertus 8B plays the candidate from the profile; the coach runs as in the
app (POST /sessions with posting_id). We measure the call gate, the deterministic report checks,
consistency over repeats, whether the score follows the persona's typical level, and, with
JUDGE_NAME set, the scenario's success criteria and the feedback quality (eval/judge.py).
Calls of the simulated candidate and of the judge are not counted for the gate.

Inside the backend container (the API runs on localhost:8000 there):
    docker compose exec backend python -m eval.bench_interviews --limit 6
    docker compose exec backend python -m eval.bench_interviews --only S-02 S-23 --repeat 3
"""

import argparse
import asyncio
import json
import os
import sys
from collections import defaultdict
from statistics import mean, pstdev
from typing import Optional

import httpx

from backend import config
from eval import checks, fhgr, judge
from eval.run_interview import ApiFailure, run_interview

LANGUAGE_NAMES = {"de": "Swiss Standard German", "fr": "French", "it": "Italian", "gsw": "Swiss German dialect"}
LEVEL_TEXT = {
    1: "very weak: one-word or off-topic answers, no examples",
    2: "weak: short and vague answers, claims without examples",
    3: "good: clear answers, sometimes a concrete example",
    4: "very good: well prepared, structured answers with concrete examples",
}


class ProfileCandidate:
    """A simulated candidate played by Apertus 8B from an FHGR profile (simulation_persona)."""

    def __init__(self, profile: dict, posting: dict, language: str):
        from openai import OpenAI

        self.client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])
        self.model = os.environ["LLM_NAME"]
        self.system = self._prompt(profile, posting, language)
        self.history: list[dict] = []

    @staticmethod
    def _prompt(c: dict, posting: dict, language: str) -> str:
        persona = c.get("simulation_persona", {})
        school = c.get("school", {})
        experiences = "; ".join(e.get("what_happened", "") for e in c.get("experiences", []))
        level = persona.get("typical_quality_level", 3)
        return (
            f"You are {c['first_name']}, {c.get('age', 15)} years old, from {c.get('place', '')}, "
            f"{school.get('level', '')} {school.get('grade', '')}. You are in a job interview for an apprenticeship "
            f"as {posting['occupation']['name_de']} at {posting['company']['name']}.\n"
            f"About you: hobbies: {', '.join(c.get('hobbies', []))}. Experiences: {experiences}. "
            f"Why this occupation: {c.get('career_choice_story', '')} Strengths: {', '.join(c.get('strengths', []))}. "
            f"Still working on: {', '.join(c.get('development_areas', []))}. Future: {c.get('future_plans', '')}\n"
            f"How you answer: {LEVEL_TEXT.get(level, LEVEL_TEXT[3])}. Answer length: {persona.get('answer_length', 'medium')}. "
            f"Nervousness: {persona.get('nervousness', 'medium')}. Style: {persona.get('speech_style', '')} "
            f"Quirks: {'; '.join(persona.get('quirks', []))}.\n"
            f"Answer only as {c['first_name']}, in {LANGUAGE_NAMES[language]}, without stage directions or quotes. "
            "When the interviewer asks whether you have questions, ask one real question the first time and say "
            "you have no more questions after that."
        )

    def answer(self, phase: str, question: str) -> str:
        self.history.append({"role": "user", "content": question})
        response = self.client.chat.completions.create(
            model=self.model, messages=[{"role": "system", "content": self.system}] + self.history, temperature=0.8,
        )
        text = (response.choices[0].message.content or "").strip() or "..."
        self.history.append({"role": "assistant", "content": text})
        return text


def scenario_ids(only: Optional[list[str]], situations: list[str], limit: Optional[int]) -> list[str]:
    ids = [s["id"] for s in fhgr.scenarios().values() if (only and s["id"] in only) or
           (not only and s["situation"] in situations)]
    return ids[:limit] if limit else ids


def run_scenario(client: httpx.Client, scenario_id: str, log=print) -> dict:
    scenario = fhgr.scenarios()[scenario_id]
    profile, posting = fhgr.candidates()[scenario["candidate_id"]], config.postings()[scenario["posting_id"]]
    language = scenario["lang"]
    candidate = ProfileCandidate(profile, posting, language)
    run = run_interview(client, language, None, "friendly", "rehearsal", candidate, log=log, overrides={
        "posting_id": scenario["posting_id"],
        "candidate": {"first_name": profile["first_name"], "school_level": profile.get("school", {}).get("level"),
                      "interests": ", ".join(profile.get("hobbies", []))[:300] or None},
    })
    return {
        "scenario_id": scenario_id, "lang": language, "candidate_id": scenario["candidate_id"],
        "posting_id": scenario["posting_id"],
        "persona_level": profile.get("simulation_persona", {}).get("typical_quality_level"),
        "success_criteria": scenario["success_criteria_for_coach"],
        "summary": run["summary"], "checks": checks.check_report(run["report"], language),
        "turns": run["turns"], "report": run["report"],
    }


def _dialogue(record: dict) -> str:
    lines = []
    for t in record["turns"]:
        lines += [f"INTERVIEWER: {t['question']}", f"CANDIDATE: {t['answer']}"]
    return "\n".join(lines)


async def judge_all(records: list[dict], log=print) -> Optional[str]:
    if not judge.configured():
        log("JUDGE_NAME not set: skipping the judge.")
        return None
    the_judge = judge.Judge()
    for r in records:
        r["judge"] = await the_judge.rate_scenario(_dialogue(r), r["report"], r["success_criteria"])
    return the_judge.model


def summarise(records: list[dict]) -> dict:
    calls = [t["llm_calls"] for r in records for t in r["turns"] if t["llm_calls"] is not None]
    summary = {
        "scenarios": len({r["scenario_id"] for r in records}), "interviews": len(records),
        "llm_calls_avg": round(mean(calls), 2) if calls else None, "llm_calls_max": max(calls) if calls else None,
        "gate_ok": bool(calls) and mean(calls) < 5,
        "checks": checks.summarise([r["checks"] for r in records]),
    }
    rated = [r for r in records if r["report"]["overall_score"] is not None and r["persona_level"]]
    summary["overall_vs_persona_spearman"] = fhgr.spearman([r["report"]["overall_score"] for r in rated],
                                                           [r["persona_level"] for r in rated])
    runs = defaultdict(list)
    for r in records:
        if r["report"]["overall_score"] is not None:
            runs[r["scenario_id"]].append(r["report"]["overall_score"])
    spreads = [pstdev(v) for v in runs.values() if len(v) > 1]
    summary["overall_std_across_repeats"] = round(mean(spreads), 2) if spreads else None
    by_lang = defaultdict(list)
    for r in records:
        if r["report"]["overall_score"] is not None:
            by_lang[r["lang"]].append(r["report"]["overall_score"])
    summary["overall_by_lang"] = {k: round(mean(v), 2) for k, v in sorted(by_lang.items())}
    verdicts = [r["judge"] for r in records if r.get("judge")]
    if verdicts:
        met = [m for v in verdicts for m in v["criteria_met"]]
        summary["judge"] = {"success_criteria_met": round(sum(met) / len(met), 2) if met else None,
                            **{k: round(mean(v["scores"][k] for v in verdicts), 2) for k in judge.DIMENSIONS}}
    return summary


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=os.environ.get("API_URL", "http://localhost:8000/api/v1"))
    parser.add_argument("--only", nargs="*", help="scenario ids, e.g. S-01 S-02")
    parser.add_argument("--situations", nargs="*", default=["apprenticeship_interview"],
                        help="scenario situations to include (default: apprenticeship_interview, 20 scenarios)")
    parser.add_argument("--limit", type=int, help="at most this many scenarios")
    parser.add_argument("--repeat", type=int, default=1, help="runs per scenario (consistency)")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    log = (lambda *_: None) if args.quiet else print
    records = []
    with httpx.Client(base_url=args.base_url, timeout=180) as client:
        for sid in scenario_ids(args.only, args.situations, args.limit):
            for i in range(args.repeat):
                print(f"{sid} run {i + 1}/{args.repeat}")
                try:
                    records.append(run_scenario(client, sid, log=log))
                except ApiFailure as exc:
                    print(f"ERROR in {sid}: {exc}", file=sys.stderr)
    judge_model = asyncio.run(judge_all(records, log=print))
    result = {"bench": "interviews", "judge_model": judge_model, "summary": summarise(records), "records": records}
    out = fhgr.save("interviews", result)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    print(f"Saved: {out}")
    return 0 if records else 2


if __name__ == "__main__":
    sys.exit(main())
