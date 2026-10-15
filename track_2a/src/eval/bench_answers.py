"""Bench 1: the analysis call against the 816 expert-annotated FHGR answers.

For each answer, our analysis call (the same code as in the interview) scores the answer;
we compare its 1-4 scores with the annotation's criteria_scores, its follow_up flag with
coach_action == "probe", and its average with the holistic quality_level. The default (`pipeline`, same as `fixed`) shows the same expert-scored examples every time. `--variant similar`
and `--variant mixed` pick examples that fit the question, `--variant no-examples` shows none and `--variant baseline`
runs a naive one-line prompt. The tested question itself is never used as an example.

Inside the backend container:
    docker compose exec backend python -m eval.bench_answers --sample 120
    docker compose exec backend python -m eval.bench_answers --sample 120 --variant baseline
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from statistics import mean
from typing import Optional

from backend.interview.examples import HELD_OUT_IDS
from backend.interview.graph import run_analysis
from backend.interview.parsing import Analysis, complete_json
from backend.interview.prompts import CRITERIA
from backend.interview.safety import PROBLEM_FLAGS, REDIRECT_FLAGS, SUPPORT_FLAGS
from eval import fhgr


def baseline_messages(question: str, answer: str) -> list[dict]:
    """A naive prompt: no level descriptions, no age context, no null rule, no phase focus."""
    keys = ", ".join(CRITERIA)
    return [{"role": "user", "content": (
        f"Rate this job interview answer from 1 to 4 on: {keys}. Also give a short tip and say whether a "
        'follow-up question is needed. Reply as JSON {"scores": {...}, "short_tip": "...", "follow_up": false}.\n\n'
        f"Question: {question}\nAnswer: {answer}")}]


async def analyse(item: dict, variant: str) -> dict:
    answer, gold = item, fhgr.annotations()[item["id"]]
    question = next(iter(answer["question_text"].values()), "")
    phase = fhgr.phase_of(answer.get("question_id"))
    if variant == "baseline":
        result, attempts, _ = await complete_json(baseline_messages(question, answer["text"]), Analysis, "bench_baseline")
        entry = result.model_dump() if result else {"parse_failed": True}
    else:
        entry, attempts = await run_analysis(fhgr.occupation(answer.get("occupation")), answer["lang"], phase,
                                             question, answer["text"],
                                             examples={"pipeline": "fixed", "fixed": "fixed", "basic": "basic", "similar": "similar",
                                                       "mixed": "mixed"}.get(variant, "none"),
                                             # the tested question (and answer) is not used as an example
                                             exclude_questions=frozenset([answer["question_id"]]),
                                             exclude_answers=frozenset([answer["id"]]))
    record = {"answer_id": answer["id"], "lang": answer["lang"], "answer_class": answer["answer_class"],
              "quality_level": answer["quality_level"], "phase": phase, "attempts": attempts,
              "gold_scores": gold["criteria_scores"], "gold_probe": gold["coach_action"] == "probe",
              "problem_flags": gold["problem_flags"]}
    if entry.get("parse_failed"):
        return {**record, "parse_failed": True}
    pred = entry["scores"]
    seen = [v for v in pred.values() if v is not None]
    return {**record, "scores": pred, "short_tip": entry.get("short_tip", ""), "follow_up": entry.get("follow_up"),
            "flags": entry.get("problem_flags", []),
            "mean_score": round(mean(seen), 2) if seen else None,
            **fhgr.compare_scores(pred, gold["criteria_scores"])}


def summarise(records: list[dict]) -> dict:
    ok = [r for r in records if not r.get("parse_failed")]
    summary = {"answers": len(records), "parse_failed": len(records) - len(ok),
               "avg_calls": round(mean(r["attempts"] for r in records), 2) if records else None,
               "scores": fhgr.score_agreement(ok)}
    with_mean = [r for r in ok if r["mean_score"] is not None]
    summary["holistic_spearman"] = fhgr.spearman([r["mean_score"] for r in with_mean],
                                                 [r["quality_level"] for r in with_mean])
    by_class = defaultdict(list)
    for r in with_mean:
        by_class[r["answer_class"]].append(r["mean_score"])
    summary["mean_score_by_class"] = {k: round(mean(v), 2) for k, v in sorted(by_class.items())}
    tp = sum(1 for r in ok if r["follow_up"] and r["gold_probe"])
    fp = sum(1 for r in ok if r["follow_up"] and not r["gold_probe"])
    fn = sum(1 for r in ok if not r["follow_up"] and r["gold_probe"])
    summary["follow_up"] = {"precision": round(tp / (tp + fp), 2) if tp + fp else None,
                            "recall": round(tp / (tp + fn), 2) if tp + fn else None}
    summary["problem_flags"] = _flag_detection(ok)
    for field in ("lang", "answer_class"):
        groups = defaultdict(list)
        for r in ok:
            groups[r[field]].append(r)
        summary[f"by_{field}"] = {k: fhgr.score_agreement(v) for k, v in sorted(groups.items())}
    per_criterion = defaultdict(list)
    for r in ok:
        for key in r["gold_scores"]:
            per_criterion[key].append(fhgr.compare_scores({key: r["scores"].get(key)}, {key: r["gold_scores"][key]}))
    summary["by_criterion"] = {k: fhgr.score_agreement(per_criterion[k]) for k in CRITERIA if per_criterion[k]}
    return summary


def _flag_detection(records: list[dict]) -> dict:
    """Does the analysis flag the answers the experts flagged (only the flags our guardrails use)?"""
    def counts(gold_has, pred_has):
        tp = sum(1 for r in records if gold_has(r) and pred_has(r))
        fp = sum(1 for r in records if not gold_has(r) and pred_has(r))
        fn = sum(1 for r in records if gold_has(r) and not pred_has(r))
        return {"gold": tp + fn, "precision": round(tp / (tp + fp), 2) if tp + fp else None,
                "recall": round(tp / (tp + fn), 2) if tp + fn else None}

    result = {"any": counts(lambda r: bool(set(r["problem_flags"]) & set(PROBLEM_FLAGS)), lambda r: bool(r.get("flags")))}
    # The flags the interview acts on (support or redirect): this is what matters for the guardrails
    acting = SUPPORT_FLAGS | REDIRECT_FLAGS
    result["acting"] = counts(lambda r: bool(set(r["problem_flags"]) & acting), lambda r: bool(set(r.get("flags", [])) & acting))
    for flag in ("distress_signal", "manipulation_attempt", "off_topic", "inappropriate_tone", "discriminatory"):
        result[flag] = counts(lambda r, f=flag: f in r["problem_flags"], lambda r, f=flag: f in r.get("flags", []))
    return result


async def run(sample: Optional[int], variant: str, concurrency: int, log=print, focus: str = "") -> dict:
    # The answers used as calibration examples in the prompt are left out, otherwise the bench would test on them
    pool = [a for a in fhgr.answers() if a["id"] not in HELD_OUT_IDS]
    if focus == "flags":
        # Every answer the experts flagged for the guardrails, plus `sample` ordinary ones (to see false alarms)
        acting = SUPPORT_FLAGS | REDIRECT_FLAGS
        flagged = [a for a in pool if set(fhgr.annotations()[a["id"]]["problem_flags"]) & acting]
        ordinary = [a for a in pool if a not in flagged]
        items = flagged + fhgr.sample(ordinary, sample, key=lambda a: (a["lang"], a["answer_class"]))
    else:
        items = fhgr.sample(pool, sample, key=lambda a: (a["lang"], a["answer_class"]))
    semaphore = asyncio.Semaphore(concurrency)
    done = 0

    async def one(item):
        nonlocal done
        async with semaphore:
            record = await analyse(item, variant)
        done += 1
        if done % 10 == 0 or done == len(items):
            log(f"  {done}/{len(items)}")
        return record

    records = await asyncio.gather(*(one(item) for item in items))
    return {"bench": "answers", "variant": variant, "summary": summarise(records), "records": records}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sample", type=int, default=120, help="answers to use, spread over language x class (0 = all 816)")
    parser.add_argument("--variant", default="pipeline", choices=["pipeline", "fixed", "basic", "similar", "mixed", "no-examples", "baseline"])
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--focus", default="", choices=["", "flags"],
                        help="flags: all answers the experts flagged for the guardrails plus --sample ordinary ones")
    args = parser.parse_args(argv)

    result = asyncio.run(run(args.sample or None, args.variant, args.concurrency, focus=args.focus))
    out = fhgr.save(f"answers-{args.variant}", result)
    s = result["summary"]
    print(json.dumps({k: s[k] for k in ("answers", "parse_failed", "avg_calls", "scores", "holistic_spearman",
                                        "mean_score_by_class", "follow_up", "problem_flags")}, indent=2))
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
