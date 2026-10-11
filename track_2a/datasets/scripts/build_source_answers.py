#!/usr/bin/env python3
"""Extract answers and transcripts that come verbatim from the FHGR material.

Writes:
  _parts/answers_src.jsonl      answers from the Kriterienraster and the Konstrukteur example
  _parts/transcripts_src.jsonl  the Konstrukteur example as two full transcripts (strong / weak)

Editorial strike-throughs (<del>) in the Konstrukteur document are removed, i.e. the
corrected version of the answer is used; the original is kept in `source_raw`.
Holistic quality levels are an expert pre-assignment (strong column -> 3/4,
weak column -> 1/2/3) and are refined in the annotations.
"""
import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SM = ROOT / "source_material"


def clean(cell, keep_del=False):
    if not keep_del:
        cell = re.sub(r"<del>.*?</del>", "", cell, flags=re.S)
    cell = re.sub(r"</?del>", "", cell)
    cell = re.sub(r"<[^>]+>", " ", cell)
    return re.sub(r"\s+", " ", html.unescape(cell)).strip()


# --- Kriterienraster --------------------------------------------------------
# subtopic label -> (question_id, strong_level, weak_level)
KR_MAP = {
    "Erster Eindruck / Auftreten": ("Q-01-01", 4, 1),
    "Schulischer Werdegang": ("Q-02-04", 4, 1),
    "Freizeit und Hobbys": ("Q-02-05", 4, 1),
    "Beweggründe für die Berufswahl": ("Q-03-01", 4, 1),
    "Motivation für die Bewerbung beim Lehrbetrieb": ("Q-03-04", 4, 1),
    "Erwartungen an die Lehre": ("Q-03-05", 4, 1),
    "Persönliche Ziele und Zukunftsvorstellungen": ("Q-08-02", 3, 1),
    "Interesse an der beruflichen Weiterentwicklung": ("Q-03-07", 3, 2),
    "Wissen über das Berufsbild": ("Q-04-04", 4, 1),
    "Informationen über den Lehrbetrieb": ("Q-04-01", 4, 1),
    "Erwartungen an die Ausbildung": ("Q-04-07", 3, 1),
    "Stärken": ("Q-05-01", 4, 1),
    "Schwächen und Umgang mit Herausforderungen": ("Q-05-03", 4, 1),
    "Lernbereitschaft": ("Q-05-08", 3, 1),
    "Lieblingsfächer / Arbeitshaltung": ("Q-06-03", 4, 1),
    "Zeugnis / Stellwerk": ("Q-06-04", 4, 1),
    "Praktika oder Schnupperlehren": ("Q-06-07", 4, 1),
    "Besondere Projekte oder Erfolge": ("Q-06-10", 4, 1),
    "Teamfähigkeit": ("Q-07-02", 4, 2),
    "Kommunikation": ("Q-07-09", 3, 1),
    "Konfliktlösung": ("Q-07-04", 4, 1),
    "Berufliche Ziele": ("Q-08-01", 4, 1),
    "Eigeninitiative und Interesse": ("Q-09-09", 4, 1),
    "Zusammenfassung und Verbindlichkeit": ("Q-10-01", 4, 1),
}


def kr_answers(questions):
    t = (SM / "kriterienraster.md").read_text(encoding="utf-8")
    out = []
    for row in re.findall(r"<tr>(.*?)</tr>", t, re.S):
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(cells) != 3:
            continue
        label = clean(cells[0])
        if label not in KR_MAP:
            raise SystemExit(f"unmapped Kriterienraster row: {label}")
        qid, lv_s, lv_w = KR_MAP[label]
        for col, lv, tag in ((cells[1], lv_s, "stark"), (cells[2], lv_w, "schwach")):
            m = re.search(r"<em>(.*?)</em>", col, re.S)
            quote = clean(m.group(1))
            nv = re.search(r"\(([^)]*)\)\s*$", quote)
            nonverbal = nv.group(1) if nv else None
            if nv:
                quote = quote[:nv.start()]
            quote = quote.strip("„“\" ")
            feats = [clean(x).lstrip("• ").strip() for x in re.split(r"<p>|<li>", col.split("Beispiel:")[0]) if clean(x).lstrip("• ").strip() and "Merkmal" not in clean(x)]
            out.append({
                "id": f"A-SRC-KR-{len(out) + 1:02d}", "question_id": qid,
                "question_text": {"de": questions[qid]["text"]["de"]}, "lang": "de", "dialect": None,
                "occupation": None, "candidate_id": None,
                "context_note": f"Kriterienraster, Kriterium «{label}»",
                "text": quote, "nonverbal_note": nonverbal, "normalized_de": None,
                "quality_level": lv, "answer_class": "strong" if tag == "stark" else "weak",
                "source": "Kriterienraster Bewerbungsgespräch.docx", "source_label": tag,
                "source_features_de": feats,
                "synthetic": False, "needs_native_review": False,
            })
    return out


# --- Konstrukteur example ---------------------------------------------------
# row index -> (question_id or None, strong_level, weak_level)
KT_MAP = {
    0: ("Q-01-01", 4, 2), 1: (None, 3, 2), 2: ("Q-02-01", 4, 1), 3: ("Q-05-02", 4, 2),
    4: ("Q-03-01", 4, 1), 5: ("Q-03-04", 4, 1), 6: ("Q-03-05", 4, 1), 7: ("Q-04-04", 4, 1),
    8: ("Q-04-10", 3, 1), 9: ("Q-05-01", 4, 1), 10: ("Q-05-03", 4, 2), 11: ("Q-05-05", 4, 2),
    12: ("Q-06-01", 4, 1), 13: ("Q-06-05", 4, 2), 14: ("Q-06-07", 4, 2), 15: ("Q-07-01", 4, 1),
    16: ("Q-07-04", 3, 1), 17: ("Q-08-02", 4, 1), 18: ("Q-09-02", 4, 3), 19: (None, 4, 2),
    20: (None, 3, 2), 21: ("Q-10-01", 4, 1), 22: ("Q-10-04", 3, 2), 23: (None, 4, 1),
}
PHASE_OF_ROW = {0: 1, 1: 1, 2: 2, 3: 2, 4: 3, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5, 10: 5, 11: 5,
                12: 6, 13: 6, 14: 6, 15: 7, 16: 7, 17: 8, 18: 9, 19: 9, 20: 9, 21: 10, 22: 10, 23: 10}
OCC = {"name_de": "Konstrukteur/in EFZ", "occupation_id": "3699"}


def kt_rows():
    t = (SM / "beispielgespraech_konstrukteur.md").read_text(encoding="utf-8")
    rows = re.findall(r"<tr>(.*?)</tr>", t, re.S)[1:]
    return [re.findall(r"<td>(.*?)</td>", r, re.S) for r in rows]


def kt_answers(questions, start):
    out = []
    for i, cells in enumerate(kt_rows()):
        qid, lv_s, lv_w = KT_MAP[i]
        asked = clean(cells[0])
        for col, lv, tag in ((cells[1], lv_s, "stark"), (cells[2], lv_w, "schwach")):
            raw = clean(col, keep_del=True)
            txt = clean(col)
            out.append({
                "id": f"A-SRC-KT-{len(out) + 1:02d}", "question_id": qid,
                "question_text": {"de": asked}, "lang": "de", "dialect": None,
                "occupation": OCC, "candidate_id": None,
                "context_note": f"Beispiel-Vorstellungsgespräch Konstrukteur/in, Gesprächsschritt {i + 1}",
                "text": txt, "nonverbal_note": None, "normalized_de": None,
                "quality_level": lv, "answer_class": "strong" if lv >= 3 else "weak",
                "source": "Beispiel eines Vorstellungsgesprächs-Lehrstelle als Konstrukteur.docx",
                "source_label": tag, "source_raw": raw if raw != txt else None,
                "synthetic": False, "needs_native_review": False,
            })
    return out


def kt_transcripts(answers):
    rows = kt_rows()
    trs = []
    for variant, col, label in (("strong", 1, "starke"), ("weak", 2, "schwache")):
        turns = []
        for i, cells in enumerate(rows):
            ph = PHASE_OF_ROW[i]
            qid = KT_MAP[i][0]
            aid = next(a["id"] for a in answers if a["context_note"].endswith(f"Gesprächsschritt {i + 1}") and a["source_label"] == ("stark" if col == 1 else "schwach"))
            turns.append({"speaker": "interviewer", "text": clean(cells[0]), "phase": ph, "question_id": qid})
            turns.append({"speaker": "candidate", "text": clean(cells[col]), "phase": ph, "answer_id": aid,
                          "quality_level": KT_MAP[i][1 if col == 1 else 2]})
        trs.append({
            "id": f"T-SRC-0{1 if variant == 'strong' else 2}", "scenario_id": None, "candidate_id": None,
            "posting_id": "P-01", "occupation": OCC, "situation": "apprenticeship_interview", "lang": "de",
            "dialect": None, "overall_quality": variant,
            "title": f"Vorstellungsgespräch Konstrukteur/in – {label} Antworten (FHGR-Beispiel)",
            "turns": turns, "reference_feedback": None,
            "notes": "Verbatim aus dem FHGR-Beispiel. Die Fragen der Ausbildnerin/des Ausbildners sind in beiden Varianten identisch; in der schwachen Variante wirken einige Überleitungen deshalb unnatürlich (z. B. «Das ist eine gute Idee.»). Namen sind im Original anonymisiert (XX/YY/ZZ).",
            "source": "Beispiel eines Vorstellungsgesprächs-Lehrstelle als Konstrukteur.docx", "synthetic": False,
        })
    return trs


def main():
    questions = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "questions" / "questions.jsonl").open(encoding="utf-8")}
    a = kr_answers(questions)
    b = kt_answers(questions, len(a))
    (ROOT / "_parts").mkdir(exist_ok=True)
    with (ROOT / "_parts" / "answers_src.jsonl").open("w", encoding="utf-8") as f:
        for x in a + b:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    with (ROOT / "_parts" / "transcripts_src.jsonl").open("w", encoding="utf-8") as f:
        for t in kt_transcripts(b):
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    print(f"wrote {len(a)} Kriterienraster answers, {len(b)} Konstrukteur answers, 2 transcripts")


if __name__ == "__main__":
    main()
