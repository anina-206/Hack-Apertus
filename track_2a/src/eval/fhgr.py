"""FHGR development data (datasets/, see datasets/SCHEMA.md) and shared metrics for the benches."""

import csv
import json
import random
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Optional

DATASETS = Path(__file__).resolve().parents[2] / "datasets"

# FHGR flow stage / interview phase (1-10) -> our phase (backend/interview/phases.py).
FLOW_STAGE_TO_PHASE = {"introduction": "intro", "motivation": "motivation", "strengths_weaknesses": "strengths_weaknesses",
                       "situational": "situational", "candidate_questions": "candidate_questions",
                       "closing": "candidate_questions"}
FHGR_PHASE_TO_PHASE = {1: "intro", 2: "intro", 3: "motivation", 4: "motivation", 5: "strengths_weaknesses",
                       6: "strengths_weaknesses", 7: "strengths_weaknesses", 8: "motivation",
                       9: "candidate_questions", 10: "candidate_questions"}


def _jsonl(name: str) -> list[dict]:
    with open(DATASETS / name, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@lru_cache
def answers() -> list[dict]:
    return _jsonl("answers/answers.jsonl")


@lru_cache
def annotations() -> dict[str, dict]:
    return {a["answer_id"]: a for a in _jsonl("annotations/annotations.jsonl")}


@lru_cache
def questions() -> dict[str, dict]:
    return {q["id"]: q for q in _jsonl("questions/questions.jsonl")}


@lru_cache
def transcripts() -> list[dict]:
    """Only the full interviews that come with reference feedback."""
    return [t for t in _jsonl("transcripts/transcripts.jsonl") if t.get("reference_feedback")]


@lru_cache
def scenarios() -> dict[str, dict]:
    return {s["id"]: s for s in _jsonl("scenarios/scenarios.jsonl")}


@lru_cache
def candidates() -> dict[str, dict]:
    return {c["id"]: c for c in _jsonl("profiles/candidates.jsonl")}


@lru_cache
def _occupation_rows() -> dict[str, dict]:
    with open(DATASETS / "occupations.csv", encoding="utf-8") as f:
        return {row["id"]: row for row in csv.DictReader(f)}


def occupation(info: Optional[dict]) -> dict:
    """An occupation dict as the prompts expect it ({"label": {"de"}, "description"}) from an FHGR reference."""
    if not info:
        return {"label": {"de": "eine Lehrstelle (Beruf offen)"}, "description": "occupation not specified"}
    row = _occupation_rows().get(str(info.get("occupation_id")), {})
    description = (row.get("Tätigkeiten") or "").strip()[:300] or "see berufsberatung.ch"
    return {"label": {"de": info.get("name_de") or row.get("Beruf", "")}, "description": description}


def phase_of(question_id: Optional[str], fhgr_phase: Optional[int] = None) -> str:
    q = questions().get(question_id or "")
    if q:
        return FLOW_STAGE_TO_PHASE.get(q["flow_stage"], "situational")
    if question_id and question_id.startswith(("Q-SIT", "Q-DIF")):
        return "situational"
    return FHGR_PHASE_TO_PHASE.get(fhgr_phase or 0, "situational")


def sample(items: list[dict], n: Optional[int], key, seed: int = 7) -> list[dict]:
    """Up to n items, spread evenly over the groups given by key(item) (e.g. language x answer class)."""
    if not n or n >= len(items):
        return list(items)
    groups = defaultdict(list)
    for item in items:
        groups[key(item)].append(item)
    rng = random.Random(seed)
    for group in groups.values():
        rng.shuffle(group)
    picked, queues = [], list(groups.values())
    while len(picked) < n:
        for queue in queues:
            if queue and len(picked) < n:
                picked.append(queue.pop())
    return picked


# --- Metrics ---------------------------------------------------------------------------------------

def compare_scores(pred: dict[str, Optional[int]], gold: dict[str, Optional[int]]) -> dict:
    """Per-item comparison: score pairs where both rated, plus which criteria were seen at all."""
    gold_seen = {k for k, v in gold.items() if v is not None}
    pred_seen = {k for k, v in pred.items() if v is not None}
    pairs = [(pred[k], gold[k]) for k in sorted(gold_seen & pred_seen)]
    return {"pairs": pairs, "gold_seen": len(gold_seen), "pred_seen": len(pred_seen),
            "both_seen": len(gold_seen & pred_seen)}


def score_agreement(items: list[dict]) -> dict:
    """Aggregate compare_scores results: MAE, exact and +-1 agreement, coverage of the gold criteria."""
    pairs = [p for item in items for p in item["pairs"]]
    if not pairs:
        return {"pairs": 0}
    errors = [abs(p - g) for p, g in pairs]
    gold_seen = sum(i["gold_seen"] for i in items)
    pred_seen = sum(i["pred_seen"] for i in items)
    both = sum(i["both_seen"] for i in items)
    return {
        "pairs": len(pairs),
        "mae": round(mean(errors), 2),
        "exact": round(sum(e == 0 for e in errors) / len(errors), 2),
        "within_1": round(sum(e <= 1 for e in errors) / len(errors), 2),
        "bias": round(mean(p - g for p, g in pairs), 2),  # > 0: we score higher than the experts
        "coverage": round(both / gold_seen, 2) if gold_seen else None,  # gold criteria we also rated
        "extra": round((pred_seen - both) / pred_seen, 2) if pred_seen else None,  # rated, but not by the gold
    }


def spearman(xs: list[float], ys: list[float]) -> Optional[float]:
    """Rank correlation (ties get average ranks). None if there is no variation."""
    if len(xs) < 3:
        return None

    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        result = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                result[order[k]] = (i + j) / 2
            i = j + 1
        return result

    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    var = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return round(cov / var, 2) if var else None


def save(name: str, payload: dict) -> Path:
    from datetime import datetime

    out = Path(__file__).resolve().parents[2] / "data" / "eval" / "bench" / f"{datetime.now():%Y%m%d-%H%M%S}-{name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out
