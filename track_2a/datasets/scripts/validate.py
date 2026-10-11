#!/usr/bin/env python3
"""Validate dataset files.

Usage:
  python3 scripts/validate.py                 # validate the merged dataset
  python3 scripts/validate.py FILE [FILE...]  # validate part files (type inferred from name)

Checks JSON syntax, required keys, enum values, id formats, cross references
(questions, answers, candidates, postings, scenarios, guideline rules) and
Swiss spelling (no «ß»). Exit code 1 on errors.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITERIA = {"clarity", "relevance", "motivation", "self_reflection", "communication", "concrete_examples",
            "demeanor", "preparation", "goal_orientation", "difficult_questions", "initiative"}
LANGS = {"de", "fr", "it", "gsw"}
DIALECTS = {"zh", "be", "bs", "lu", "sg", "gr", "vs", "ag", "so", "tg"}
CLASSES = {"strong", "weak", "incomplete", "problematic"}
FLAGS = {"badmouthing", "dishonesty", "inappropriate_tone", "discriminatory", "privacy_oversharing",
         "distress_signal", "off_topic", "manipulation_attempt", "extrinsic_only", "one_word", "memorized_phrases"}
ACTIONS = {"continue", "probe", "redirect", "support_and_refer"}
SITUATIONS = {"apprenticeship_interview", "phone_call_trial", "trial_interview", "online_interview",
              "assessment", "follow_up_interview"}
FAILURE_MODES = {"harsh", "overpraise", "vague", "personality_label", "jargon", "fear", "hallucinated_evidence",
                 "too_long", "no_next_step", "comparison", "wrong_language", "ignores_distress", "grading_not_coaching"}

errors = []


def err(where, msg):
    errors.append(f"{where}: {msg}")


def load(p):
    out = []
    for n, line in enumerate(Path(p).open(encoding="utf-8"), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            err(f"{p}:{n}", f"invalid JSON: {e}")
    return out


def req(rec, keys, where):
    for k in keys:
        if k not in rec:
            err(where, f"missing key '{k}'")


def no_eszett(obj, where):
    s = json.dumps(obj, ensure_ascii=False)
    if "ß" in s:
        err(where, "contains «ß» (use «ss» in Swiss Standard German)")


def ref_sets():
    def ids(path, key="id"):
        p = ROOT / path
        return {r[key] for r in load(p)} if p.exists() else set()
    q = ids("questions/questions.jsonl")
    gl = set()
    p = ROOT / "rubric" / "feedback_guidelines.json"
    if p.exists():
        gl = {r["id"] for g in json.loads(p.read_text(encoding="utf-8"))["groups"] for r in g["rules"]}
    return q, gl


QIDS, GLIDS = ref_sets()
CIDS = {f"C-{i:02d}" for i in range(1, 25)}
PIDS = {f"P-{i:02d}" for i in range(1, 31)}
SIDS = {f"S-{i:02d}" for i in range(1, 29)}


def v_answers(recs, name):
    seen = set()
    for r in recs:
        w = f"{name}:{r.get('id')}"
        req(r, ["id", "question_id", "question_text", "lang", "dialect", "occupation", "candidate_id", "text",
                "quality_level", "answer_class", "source", "synthetic", "needs_native_review"], w)
        if r.get("id") in seen:
            err(w, "duplicate id")
        seen.add(r.get("id"))
        if not re.match(r"^A-[A-Z0-9]+(-[A-Z0-9]+)*-\d{2,4}$", str(r.get("id"))):
            err(w, "bad id format")
        if r.get("question_id") is not None and QIDS and r["question_id"] not in QIDS:
            err(w, f"unknown question_id {r['question_id']}")
        if r.get("lang") not in LANGS:
            err(w, f"bad lang {r.get('lang')}")
        if r.get("lang") == "gsw":
            if r.get("dialect") not in DIALECTS:
                err(w, f"gsw answer needs dialect in {sorted(DIALECTS)}")
            if not r.get("normalized_de"):
                err(w, "gsw answer needs normalized_de")
        if r.get("quality_level") not in (1, 2, 3, 4):
            err(w, "quality_level must be 1..4")
        if r.get("answer_class") not in CLASSES:
            err(w, f"bad answer_class {r.get('answer_class')}")
        if r.get("candidate_id") and r["candidate_id"] not in CIDS:
            err(w, f"unknown candidate_id {r['candidate_id']}")
        if not isinstance(r.get("question_text"), dict) or not r.get("question_text"):
            err(w, "question_text must be a non-empty {lang: text} object")
        if r.get("lang") in ("de", "gsw"):
            no_eszett(r, w)
    return seen


def v_annotations(recs, name, answer_ids=None):
    seen = set()
    for r in recs:
        w = f"{name}:{r.get('answer_id')}"
        req(r, ["answer_id", "quality_level", "answer_class", "criteria_scores", "strengths", "weaknesses",
                "missing_elements", "problem_flags", "coach_action", "expert_comment", "coach_feedback",
                "follow_up_question", "improved_answer", "guideline_refs", "annotator", "review_status"], w)
        if r.get("answer_id") in seen:
            err(w, "duplicate annotation")
        seen.add(r.get("answer_id"))
        if answer_ids is not None and r.get("answer_id") not in answer_ids:
            err(w, "annotation for unknown answer")
        for k, v in (r.get("criteria_scores") or {}).items():
            if k not in CRITERIA:
                err(w, f"unknown criterion {k}")
            if v not in (1, 2, 3, 4, None):
                err(w, f"bad score {k}={v}")
        if not r.get("criteria_scores"):
            err(w, "criteria_scores empty")
        for f in r.get("problem_flags") or []:
            if f not in FLAGS:
                err(w, f"unknown problem flag {f}")
        if r.get("answer_class") == "problematic" and not r.get("problem_flags"):
            err(w, "problematic answer needs problem_flags")
        if r.get("coach_action") not in ACTIONS:
            err(w, f"bad coach_action {r.get('coach_action')}")
        for g in r.get("guideline_refs") or []:
            if GLIDS and g not in GLIDS:
                err(w, f"unknown guideline rule {g}")
        if r.get("quality_level") not in (1, 2, 3, 4):
            err(w, "quality_level must be 1..4")
        no_eszett({k: r.get(k) for k in ("strengths", "weaknesses", "missing_elements", "expert_comment")}, w)
    return seen


def v_candidates(recs, name):
    for r in recs:
        w = f"{name}:{r.get('id')}"
        req(r, ["id", "first_name", "age", "gender", "canton", "place", "interview_language", "dialect", "languages",
                "school", "hobbies", "experiences", "target_posting_id", "career_choice_story", "strengths",
                "development_areas", "future_plans", "simulation_persona", "coach_focus", "synthetic"], w)
        if r.get("id") not in CIDS:
            err(w, "id not in roster")
        if r.get("target_posting_id") not in PIDS:
            err(w, "unknown target_posting_id")
        if r.get("dialect") is not None and r["dialect"] not in DIALECTS:
            err(w, f"bad dialect {r.get('dialect')}")


def v_postings(recs, name):
    for r in recs:
        w = f"{name}:{r.get('id')}"
        req(r, ["id", "occupation", "lang", "company", "posting_text", "requirements", "offers", "bm_possible",
                "start_date", "selection_process", "interviewer", "insider_facts", "synthetic"], w)
        if r.get("id") not in PIDS:
            err(w, "id not in roster")
        if r.get("lang") not in ("de", "fr", "it"):
            err(w, "bad lang")


def v_scenarios(recs, name):
    for r in recs:
        w = f"{name}:{r.get('id')}"
        req(r, ["id", "title", "situation", "candidate_id", "posting_id", "lang", "planned_question_ids",
                "adaptive_hooks", "evaluation_focus", "difficulty", "success_criteria_for_coach", "synthetic"], w)
        if r.get("id") not in SIDS:
            err(w, "id not in roster")
        if r.get("situation") not in SITUATIONS:
            err(w, f"bad situation {r.get('situation')}")
        for q in r.get("planned_question_ids") or []:
            if QIDS and q not in QIDS:
                err(w, f"unknown question id {q}")
        for c in r.get("evaluation_focus") or []:
            if c not in CRITERIA:
                err(w, f"unknown criterion {c}")


def v_transcripts(recs, name):
    for r in recs:
        w = f"{name}:{r.get('id')}"
        req(r, ["id", "scenario_id", "candidate_id", "posting_id", "situation", "lang", "overall_quality", "turns",
                "reference_feedback", "synthetic"], w)
        if r.get("scenario_id") is not None and r["scenario_id"] not in SIDS:
            err(w, "unknown scenario_id")
        for i, t in enumerate(r.get("turns") or []):
            if t.get("speaker") not in ("interviewer", "candidate"):
                err(f"{w}#turn{i}", "speaker must be interviewer|candidate")
            if t.get("question_id") and QIDS and t["question_id"] not in QIDS:
                err(f"{w}#turn{i}", f"unknown question_id {t['question_id']}")
            if t.get("speaker") == "candidate" and t.get("quality_level") not in (1, 2, 3, 4, None):
                err(f"{w}#turn{i}", "bad quality_level")
        fb = r.get("reference_feedback")
        if fb:
            for c in fb.get("criteria", []):
                if c.get("criterion") not in CRITERIA:
                    err(w, f"feedback: unknown criterion {c.get('criterion')}")
                if c.get("level") not in (1, 2, 3, 4, None):
                    err(w, "feedback: bad level")


def v_feedback(recs, name):
    for r in recs:
        w = f"{name}:{r.get('id')}"
        req(r, ["id", "lang", "scope", "context", "good_feedback", "good_feedback_notes", "poor_feedback",
                "poor_feedback_violations", "poor_feedback_notes", "failure_mode", "synthetic"], w)
        for g in r.get("poor_feedback_violations") or []:
            if GLIDS and g not in GLIDS:
                err(w, f"unknown guideline rule {g}")
        if r.get("failure_mode") not in FAILURE_MODES:
            err(w, f"bad failure_mode {r.get('failure_mode')}")


def v_qtrans(recs, name):
    for r in recs:
        w = f"{name}:{r.get('id')}"
        if QIDS and r.get("id") not in QIDS:
            err(w, "unknown question id")
        if not r.get("fr") or not r.get("it"):
            err(w, "fr and it required")
        for g in r.get("gsw_variants") or []:
            if g.get("dialect") not in DIALECTS:
                err(w, f"bad dialect {g.get('dialect')}")


def dispatch(p):
    n = Path(p).name
    recs = load(p)
    if n.startswith("answers"):
        v_answers(recs, n)
    elif n.startswith("annotations"):
        v_annotations(recs, n)
    elif n.startswith("candidates"):
        v_candidates(recs, n)
    elif n.startswith("postings"):
        v_postings(recs, n)
    elif n.startswith("scenarios"):
        v_scenarios(recs, n)
    elif n.startswith("transcripts"):
        v_transcripts(recs, n)
    elif n.startswith("feedback"):
        v_feedback(recs, n)
    elif n.startswith("questions_translations"):
        v_qtrans(recs, n)
    else:
        print(f"skip {p} (unknown type)")
    return len(recs)


def full():
    q = load(ROOT / "questions" / "questions.jsonl")
    for r in q:
        if not all(r["text"].get(l) for l in ("de", "fr", "it")):
            err(f"questions:{r['id']}", "missing de/fr/it text")
        no_eszett(r["text"].get("de"), f"questions:{r['id']}")
    a = load(ROOT / "answers" / "answers.jsonl")
    aids = v_answers(a, "answers")
    ann = load(ROOT / "annotations" / "annotations.jsonl")
    seen = v_annotations(ann, "annotations", aids)
    for m in aids - seen:
        err(f"answers:{m}", "answer has no annotation")
    amap = {x["id"]: x for x in a}
    for x in ann:
        if x["answer_id"] in amap and amap[x["answer_id"]]["quality_level"] != x["quality_level"]:
            err(f"annotations:{x['answer_id']}", "quality_level differs from answer")
    v_candidates(load(ROOT / "profiles" / "candidates.jsonl"), "candidates")
    v_postings(load(ROOT / "profiles" / "postings.jsonl"), "postings")
    v_scenarios(load(ROOT / "scenarios" / "scenarios.jsonl"), "scenarios")
    v_transcripts(load(ROOT / "transcripts" / "transcripts.jsonl"), "transcripts")
    v_feedback(load(ROOT / "feedback_examples" / "feedback_examples.jsonl"), "feedback_examples")


def main():
    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            print(f"{p}: {dispatch(p)} records")
    else:
        full()
    if errors:
        print(f"\n{len(errors)} error(s):")
        for e in errors[:200]:
            print("  -", e)
        sys.exit(1)
    print("OK")


if __name__ == "__main__":
    main()
