"""Play one complete interview against the running backend and report the LLM calls per answer.

The candidate is either scripted (fixed answers, no extra LLM calls) or simulated by Apertus
with a persona level (weak / medium / strong). Calls made for the simulated candidate are not
counted: `meta.llm_calls` only counts the backend's calls.

Inside the backend container (no local Python needed):
    docker compose exec backend python -m eval.run_interview --language de
Locally:
    PYTHONPATH=src python -m eval.run_interview --language fr --candidate llm --level weak

Exit code 0 = finished and average calls per answer < 5, 1 = gate missed, 2 = API error.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx

GATE_MAX_AVG_CALLS = 5
MAX_TURNS = 40  # safety stop if the interview never ends

# Scripted answers by phase. candidate_questions: first a question, then "no more questions".
SCRIPTED = {
    "de": {
        "intro": "Ich heisse Lara, bin 15 und gehe in die Sek A. In der Freizeit spiele ich Volleyball und baue gerne Sachen.",
        "motivation": "In der Schnupperlehre hat mir gefallen, dass man am Abend sieht, was man gemacht hat. Ich habe mich informiert und die Arbeit passt zu mir.",
        "strengths_weaknesses": "Ich bin zuverlässig: Im Volleyball bin ich nie zu spät und helfe beim Aufräumen. Manchmal bin ich ungeduldig, daran arbeite ich.",
        "situational": "In einem Gruppenprojekt hat jemand nichts gemacht. Ich habe mit ihm geredet und wir haben die Aufgaben neu verteilt. Am Ende hat es geklappt.",
        "candidate_questions": ["Wie sieht ein typischer Arbeitstag für Lernende aus?", "Nein, danke. Ich habe keine Fragen mehr."],
    },
    "fr": {
        "intro": "Je m'appelle Lara, j'ai 15 ans et je suis en dernière année. Pendant mon temps libre, je joue au volley et je bricole.",
        "motivation": "Pendant mon stage, j'ai aimé voir le résultat de mon travail à la fin de la journée. Je me suis renseignée et ce métier me correspond.",
        "strengths_weaknesses": "Je suis fiable: au volley, je ne suis jamais en retard et j'aide à ranger. Parfois je suis impatiente, j'y travaille.",
        "situational": "Dans un projet de groupe, quelqu'un ne faisait rien. Je lui ai parlé et nous avons réparti les tâches autrement. À la fin, ça a marché.",
        "candidate_questions": ["Comment se passe une journée typique pour un apprenti?", "Non, merci. Je n'ai plus de questions."],
    },
    "it": {
        "intro": "Mi chiamo Lara, ho 15 anni e frequento l'ultimo anno di scuola media. Nel tempo libero gioco a pallavolo e mi piace costruire cose.",
        "motivation": "Durante lo stage mi è piaciuto vedere a fine giornata cosa avevo fatto. Mi sono informata e questo lavoro fa per me.",
        "strengths_weaknesses": "Sono affidabile: a pallavolo non arrivo mai in ritardo e aiuto a riordinare. A volte sono impaziente, ci sto lavorando.",
        "situational": "In un progetto di gruppo un compagno non faceva niente. Gli ho parlato e abbiamo ridistribuito i compiti. Alla fine ha funzionato.",
        "candidate_questions": ["Come si svolge una giornata tipica per un apprendista?", "No, grazie. Non ho altre domande."],
    },
    "gsw": {
        "intro": "Ich heisse Lara, bi 15i und gang i d Sek A. I de Freiziit spiel ich Volleyball und bau gern Sache.",
        "motivation": "I de Schnupperlehr hät mir gfalle, dass mer am Abig gseht, was mer gmacht hät. Ich ha mich informiert und de Bruef passt zu mir.",
        "strengths_weaknesses": "Ich bi zueverlässig: Im Volleyball bin ich nie z spät und hilf bim Ufruume. Mängisch bin ich ungeduldig, dra schaff ich.",
        "situational": "Imene Gruppeprojekt hät öpper nüt gmacht. Ich ha mit ihm gredt und mir händ d Ufgabe neu verteilt. Am Schluss hätts klappt.",
        "candidate_questions": ["Wie gseht en typische Arbeitstag für Lehrlinge us?", "Nei, merci. Ich ha kei Frage meh."],
    },
}

LEVELS = {
    "weak": "You answer very briefly and vaguely (one short sentence), without examples, sometimes a bit off-topic.",
    "medium": "You answer honestly in 2-3 sentences, sometimes with an example, but not always well structured.",
    "strong": "You answer well prepared in 3-4 sentences, with concrete examples from school, hobbies or your Schnupperlehre.",
}
LANGUAGE_NAMES = {"de": "German", "fr": "French", "it": "Italian", "gsw": "Swiss German dialect"}


class ApiFailure(RuntimeError):
    pass


class ScriptedCandidate:
    def __init__(self, language: str):
        self.answers = SCRIPTED[language]
        self.candidate_turns = 0

    def answer(self, phase: str, question: str) -> str:
        if phase == "candidate_questions":
            options = self.answers["candidate_questions"]
            text = options[min(self.candidate_turns, len(options) - 1)]
            self.candidate_turns += 1
            return text
        return self.answers.get(phase, self.answers["intro"])


class LLMCandidate:
    """A simulated candidate played by Apertus (same LLM_* env vars as the backend)."""

    def __init__(self, language: str, level: str, occupation: str):
        from openai import OpenAI

        self.client = OpenAI(base_url=os.environ["LLM_BASE_URL"], api_key=os.environ["LLM_API_KEY"])
        self.model = os.environ["LLM_NAME"]
        self.system = (
            "You are a school student (15 years old) in Switzerland in a job interview for an apprenticeship "
            f"as {occupation}. {LEVELS[level]} Answer only as the candidate, in {LANGUAGE_NAMES[language]}, "
            "without any comments or quotation marks. When the interviewer asks whether you have questions, "
            "ask one short question about the apprenticeship the first time, and say you have no more questions after that."
        )
        self.history: list[dict] = []

    def answer(self, phase: str, question: str) -> str:
        self.history.append({"role": "user", "content": question})
        response = self.client.chat.completions.create(
            model=self.model, messages=[{"role": "system", "content": self.system}] + self.history, temperature=0.8,
        )
        text = (response.choices[0].message.content or "").strip() or "..."
        self.history.append({"role": "assistant", "content": text})
        return text


def _call(client: httpx.Client, method: str, path: str, **kwargs) -> dict:
    try:
        resp = client.request(method, path, **kwargs)
    except httpx.HTTPError as exc:
        raise ApiFailure(f"{method} {path}: backend not reachable ({exc})") from exc
    body = resp.json() if resp.content else {}
    if resp.status_code >= 400:
        error = body.get("error", {})
        raise ApiFailure(f"{method} {path}: {resp.status_code} {error.get('code')} {error.get('message')}")
    return body


def run_interview(client: httpx.Client, language: str, occupation_id: Optional[str], style: str, mode: str,
                  candidate=None, log=print, overrides: Optional[dict] = None) -> dict:
    """Run one interview through the API. Returns the full run record (turns, summary, report).

    `overrides` are extra POST /sessions fields, e.g. {"posting_id": "P-01", "candidate": {...}}.
    """
    config = _call(client, "GET", "/config")
    if occupation_id and not any(o["id"] == occupation_id for o in config["occupations"]):
        raise ApiFailure(f"unknown occupation '{occupation_id}', available: {[o['id'] for o in config['occupations']]}")
    candidate = candidate or ScriptedCandidate(language)

    started = time.perf_counter()
    turn = _call(client, "POST", "/sessions", json={
        "language": language, "occupation_id": occupation_id, "interviewer_style": style, "mode": mode,
        "candidate": {"first_name": "Lara", "school_level": "Sek A"}, **(overrides or {}),
    })
    session_id = turn["session_id"]
    log(f"Session {session_id} ({language}, {occupation_id}, {style}, {mode})\n")
    log(f"[{turn['question']['id']}] {turn['phase']}: {turn['question']['text']}")

    turns = []
    question = turn["question"]
    phase = turn["phase"]
    while len(turns) < MAX_TURNS:
        answer = candidate.answer(phase, question["text"])
        log(f"  > {answer}")
        turn = _call(client, "POST", f"/sessions/{session_id}/answers", json={"question_id": question["id"], "text": answer})
        meta = turn.get("meta") or {}
        record = {
            "question_id": question["id"], "phase": phase, "is_follow_up": bool(question.get("is_follow_up")),
            "question": question["text"], "answer": answer,
            "llm_calls": meta.get("llm_calls"), "latency_ms": meta.get("latency_ms"),
            "turn_feedback": turn.get("turn_feedback"),
        }
        turns.append(record)
        tip = (turn.get("turn_feedback") or {}).get("short_tip")
        log(f"    calls={record['llm_calls']} latency={record['latency_ms']}ms" + (f" tip: {tip}" if tip else ""))
        if turn["done"]:
            log(f"\n[closing] {turn['closing_message']}")
            break
        question, phase = turn["question"], turn["phase"]
        log(f"[{question['id']}] {phase}{' (follow-up)' if question.get('is_follow_up') else ''}: {question['text']}")
    else:
        raise ApiFailure(f"interview did not finish after {MAX_TURNS} answers")

    report = _call(client, "GET", f"/sessions/{session_id}/report")
    calls = [t["llm_calls"] for t in turns if t["llm_calls"] is not None]
    summary = {
        "answers": len(turns),
        "llm_calls_total": sum(calls),
        "llm_calls_avg": round(sum(calls) / len(calls), 2) if calls else None,
        "llm_calls_max": max(calls) if calls else None,
        "answers_with_retries": sum(1 for t in turns if (t["llm_calls"] or 0) > 2),  # normal turns use 0-2 calls
        "follow_ups": sum(1 for t in turns if t["is_follow_up"]),
        "latency_avg_ms": round(sum(t["latency_ms"] or 0 for t in turns) / len(turns)) if turns else None,
        "duration_s": round(time.perf_counter() - started, 1),
        "overall_score": report.get("overall_score"),
    }
    summary["gate_ok"] = summary["llm_calls_avg"] is not None and summary["llm_calls_avg"] < GATE_MAX_AVG_CALLS
    return {"session_id": session_id, "language": language, "occupation_id": occupation_id, "style": style,
            "mode": mode, "turns": turns, "summary": summary, "report": report}


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default=os.environ.get("API_URL", "http://localhost:8000/api/v1"))
    parser.add_argument("--language", default="de", choices=sorted(SCRIPTED))
    parser.add_argument("--occupation", default="informatiker_efz")
    parser.add_argument("--style", default="friendly", choices=["friendly", "strict"])
    parser.add_argument("--mode", default="training", choices=["training", "rehearsal"])
    parser.add_argument("--candidate", default="scripted", choices=["scripted", "llm"])
    parser.add_argument("--level", default="medium", choices=sorted(LEVELS), help="only with --candidate llm")
    parser.add_argument("--out", help="where to save the run as JSON (default: data/eval/runs/<timestamp>.json)")
    parser.add_argument("--quiet", action="store_true", help="only print the summary")
    args = parser.parse_args(argv)

    log = (lambda *_: None) if args.quiet else print
    try:
        with httpx.Client(base_url=args.base_url, timeout=180) as client:
            candidate = None
            if args.candidate == "llm":
                config = _call(client, "GET", "/config")
                labels = {o["id"]: o["label"].get("de", o["id"]) for o in config["occupations"]}
                candidate = LLMCandidate(args.language, args.level, labels.get(args.occupation, args.occupation))
            run = run_interview(client, args.language, args.occupation, args.style, args.mode, candidate, log)
    except ApiFailure as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    run["candidate"] = args.candidate if args.candidate == "scripted" else f"llm:{args.level}"
    run["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    out = Path(args.out) if args.out else Path("data/eval/runs") / f"{datetime.now():%Y%m%d-%H%M%S}-{args.language}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    s = run["summary"]
    print(f"\nAnswers: {s['answers']} (follow-ups: {s['follow_ups']}, with JSON retries: {s['answers_with_retries']})")
    print(f"LLM calls per answer: avg {s['llm_calls_avg']}, max {s['llm_calls_max']}, total {s['llm_calls_total']}")
    print(f"Latency per answer: avg {s['latency_avg_ms']} ms · total {s['duration_s']} s")
    print(f"Report overall score: {s['overall_score']}")
    print(f"Gate (avg < {GATE_MAX_AVG_CALLS} calls per answer): {'OK' if s['gate_ok'] else 'MISSED'}")
    print(f"Saved: {out}")
    return 0 if s["gate_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
