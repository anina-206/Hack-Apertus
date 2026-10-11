"""Bench 2: the 13 FHGR gold interviews through our analysis + report, against the reference feedback.

Each candidate turn of a gold transcript is analysed with the interviewer question before it
(the same code as in the interview), then the final report is built from those analyses.
We compare the report's 1-4 level per criterion with the reference feedback, run the
deterministic checks (eval/checks.py) and, if JUDGE_NAME is set, let the judge rate the feedback.

Inside the backend container:
    docker compose exec backend python -m eval.bench_transcripts
    docker compose exec backend python -m eval.bench_transcripts --only T-01 T-08 --repeat 3
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from statistics import mean, pstdev
from typing import Optional

from backend import llm
from backend.interview.graph import run_analysis
from backend.interview.report import build_report
from eval import checks, fhgr, judge


def _language(transcript: dict) -> str:
    return transcript["lang"] if transcript["lang"] in ("de", "fr", "it", "gsw") else "de"


async def analyse_transcript(transcript: dict, semaphore: asyncio.Semaphore) -> tuple[dict, int]:
    """Build the interview state our report needs from a gold transcript. Returns (state, llm calls)."""
    language, occupation = _language(transcript), fhgr.occupation(transcript.get("occupation"))
    jobs, turns, question, question_id, fhgr_phase = [], [], "", None, None
    for turn in transcript["turns"]:
        if turn["speaker"] == "interviewer":
            question, question_id, fhgr_phase = turn["text"], turn.get("question_id"), turn.get("phase")
            turns.append({"role": "interviewer", "question_id": question_id, "text": turn["text"]})
            continue
        phase = fhgr.phase_of(question_id, turn.get("phase") or fhgr_phase)
        turns.append({"role": "candidate", "question_id": question_id, "text": turn["text"], "phase": phase})
        jobs.append((phase, question, turn["text"]))

    async def one(phase, q, a):
        async with semaphore:
            return await run_analysis(occupation, language, phase, q, a)

    results = await asyncio.gather(*(one(*job) for job in jobs))
    state = {"language": language, "transcript": turns, "analyses": [entry for entry, _ in results], "done": True}
    return state, sum(attempts for _, attempts in results)


def _reference(transcript: dict) -> dict:
    return {c["criterion"]: c["level"] for c in transcript["reference_feedback"]["criteria"]}


def _dialogue(transcript: dict) -> str:
    return "\n".join(f"{t['speaker'].upper()}: {t['text']}" for t in transcript["turns"])


async def run_one(transcript: dict, semaphore: asyncio.Semaphore, the_judge) -> dict:
    llm.start_request()
    state, analysis_calls = await analyse_transcript(transcript, semaphore)
    async with semaphore:
        report = await build_report(transcript["id"], state, fhgr.occupation(transcript.get("occupation")))
    report_calls = llm.calls_in_request() - analysis_calls
    pred = {c["id"]: c["score"] for c in report["criteria"]}
    record = {
        "transcript_id": transcript["id"], "lang": transcript["lang"], "dialect": transcript.get("dialect"),
        "overall_quality": transcript["overall_quality"],
        "candidate_answers": sum(1 for t in transcript["turns"] if t["speaker"] == "candidate"),
        "analysis_calls": analysis_calls, "report_calls": report_calls,
        "parse_failed": sum(1 for a in state["analyses"] if a.get("parse_failed")),
        "reference_scores": _reference(transcript), "scores": pred, "overall_score": report["overall_score"],
        **fhgr.compare_scores(pred, _reference(transcript)),
        "checks": checks.check_report(report, _language(transcript)),
        "report": report,
    }
    if the_judge:
        async with semaphore:
            record["judge"] = await the_judge.rate_report(_dialogue(transcript), report, transcript["reference_feedback"])
    return record


def summarise(records: list[dict]) -> dict:
    answers = sum(r["candidate_answers"] for r in records)
    summary = {
        "transcripts": len({r["transcript_id"] for r in records}), "runs": len(records),
        "avg_calls_per_answer": round(sum(r["analysis_calls"] for r in records) / answers, 2) if answers else None,
        "levels": fhgr.score_agreement(records),
        "checks": checks.summarise([r["checks"] for r in records]),
    }
    quality = {"weak": 1, "mixed": 2, "strong": 3}
    rated = [r for r in records if r["overall_score"] is not None]
    summary["overall_vs_quality_spearman"] = fhgr.spearman([r["overall_score"] for r in rated],
                                                           [quality[r["overall_quality"]] for r in rated])
    by_lang = defaultdict(list)
    for r in records:
        by_lang[r["lang"]].append(r)
    summary["levels_by_lang"] = {k: fhgr.score_agreement(v) for k, v in sorted(by_lang.items())}
    # Consistency: the same transcript run several times should get the same scores.
    runs = defaultdict(list)
    for r in records:
        runs[r["transcript_id"]].append(r["overall_score"])
    spreads = [pstdev([s for s in v if s is not None]) for v in runs.values() if len([s for s in v if s is not None]) > 1]
    summary["overall_std_across_repeats"] = round(mean(spreads), 2) if spreads else None
    verdicts = [r["judge"] for r in records if r.get("judge")]
    if verdicts:
        summary["judge"] = {k: round(mean(v["scores"][k] for v in verdicts), 2) for k in judge.DIMENSIONS}
        counts = defaultdict(int)
        for v in verdicts:
            for rule in v["violations"]:
                counts[rule] += 1
        summary["judge"]["violations"] = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
    return summary


async def run(only: Optional[list[str]], repeat: int, concurrency: int, use_judge: bool, log=print) -> dict:
    transcripts = [t for t in fhgr.transcripts() if not only or t["id"] in only]
    the_judge = judge.Judge() if use_judge and judge.configured() else None
    if use_judge and not the_judge:
        log("JUDGE_NAME not set: skipping the judge.")
    semaphore = asyncio.Semaphore(concurrency)
    records = []
    for t in transcripts:
        for i in range(repeat):
            records.append(await run_one(t, semaphore, the_judge))
            r = records[-1]
            log(f"  {t['id']} ({t['lang']}, {t['overall_quality']}) run {i + 1}: overall {r['overall_score']}, "
                f"MAE {fhgr.score_agreement([r]).get('mae')}, checks {r['checks']}")
    return {"bench": "transcripts", "judge_model": the_judge.model if the_judge else None,
            "summary": summarise(records), "records": records}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", nargs="*", help="transcript ids, e.g. T-01 T-08 (default: all 13)")
    parser.add_argument("--repeat", type=int, default=1, help="runs per transcript (consistency)")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--no-judge", action="store_true")
    args = parser.parse_args(argv)

    result = asyncio.run(run(args.only, args.repeat, args.concurrency, not args.no_judge))
    out = fhgr.save("transcripts", result)
    print(json.dumps(result["summary"], indent=2, ensure_ascii=False))
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
