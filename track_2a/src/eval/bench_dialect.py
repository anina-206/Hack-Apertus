"""Bench: does the interviewer really write dialect when language is "gsw"?

For every dialect it starts a few interviews, lets a candidate answer twice and counts the interviewer texts that
look like dialect (backend.interview.dialect.looks_like_dialect: at least two typical dialect words). It prints
the texts, so you can judge them yourself; the count is only a rough check, not a quality measure.

Inside the backend container:
    docker compose exec backend python -m eval.bench_dialect
    docker compose exec backend python -m eval.bench_dialect --dialect be --runs 3
"""

import argparse
import asyncio
import uuid
from typing import Optional

from backend.interview import dialect as swiss_german
from backend.interview.graph import InterviewEngine

ANSWERS = ["Ich bi d Lara, gang i d Sek A und bau gärn PCs zäme.", "Mi fasziniert d Technik, und i bastle scho lang a Computer ume."]
OCCUPATIONS = ["informatiker_efz", "kv_efz", "schreiner_efz"]


async def interview(engine: InterviewEngine, dialect: str, occupation: str, style: str) -> list[str]:
    session = str(uuid.uuid4())
    setup = {"language": "gsw", "dialect": dialect, "occupation_id": occupation, "interviewer_style": style,
             "mode": "training", "candidate": {"first_name": "Lara"}, "posting_id": None}
    state = await engine.start(session, setup)
    texts = [state["current_question"]["text"]]
    for answer in ANSWERS:
        state = await engine.answer(session, answer)
        texts.append(state["current_question"]["text"])
    return texts


async def run(dialects: list[str], runs: int, log=print) -> dict:
    engine = InterviewEngine()
    result = {}
    for dialect in dialects:
        texts = []
        for i in range(runs):
            texts += await interview(engine, dialect, OCCUPATIONS[i % len(OCCUPATIONS)], "friendly" if i % 2 == 0 else "strict")
        share = sum(swiss_german.looks_like_dialect(t) for t in texts) / len(texts)
        result[dialect] = {"texts": len(texts), "dialect_share": round(share, 2)}
        log(f"\n=== {swiss_german.DIALECTS[dialect]}: {share:.0%} of {len(texts)} texts look like dialect")
        for text in texts:
            log("  - " + text.replace("\n", " "))
    return result


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--dialect", choices=list(swiss_german.DIALECTS), help="only this dialect (default: all five)")
    parser.add_argument("--runs", type=int, default=2, help="interviews per dialect (3 texts each)")
    args = parser.parse_args(argv)
    asyncio.run(run([args.dialect] if args.dialect else list(swiss_german.DIALECTS), args.runs))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
