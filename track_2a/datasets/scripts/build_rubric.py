#!/usr/bin/env python3
"""Build rubric/criteria.json and rubric/feedback_guidelines.json.

Source: source_material/feedbackkriterien.md (FHGR). German texts are verbatim
from the source; English/French/Italian labels and English descriptions are
translations added for the hackathon (non-German-speaking teams, FR/IT feedback).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

LEVELS = [
    {"value": 1, "key": "ungenuegend", "de": "Ungenügend", "en": "Insufficient", "fr": "Insuffisant", "it": "Insufficiente"},
    {"value": 2, "key": "ausbaufaehig", "de": "Ausbaufähig", "en": "Developing", "fr": "À développer", "it": "Da sviluppare"},
    {"value": 3, "key": "gut", "de": "Gut", "en": "Good", "fr": "Bien", "it": "Buono"},
    {"value": 4, "key": "sehr_gut", "de": "Sehr gut", "en": "Very good", "fr": "Très bien", "it": "Molto buono"},
]

# key, core(challenge list), labels, what_de, what_en, levels[(desc_de, example_de, desc_en)]
C = [
    ("clarity", True, {"de": "Klarheit", "en": "Clarity", "fr": "Clarté", "it": "Chiarezza"},
     "Verständlichkeit, Struktur und Nachvollziehbarkeit der Antworten",
     "Comprehensibility, structure and traceability of the answers",
     [("Antworten sind wirr, unvollständig oder schwer verständlich", "„Also ich weiss nicht, halt irgendwie so, ja…“", "Answers are confused, incomplete or hard to follow"),
      ("Grundgedanke erkennbar, aber unstrukturiert oder abschweifend", "Antwort enthält den richtigen Kern, springt aber zwischen Themen hin und her", "Main idea recognisable but unstructured or rambling"),
      ("Klar formuliert, roter Faden erkennbar", "Antwort mit klarem Anfang, Kern und Schluss", "Clearly phrased, a common thread is visible"),
      ("Präzise, strukturiert, auf den Punkt gebracht", "Antwort folgt erkennbar einem Aufbau (z. B. Situation – Handlung – Ergebnis)", "Precise, structured, to the point")]),
    ("relevance", True, {"de": "Relevanz", "en": "Relevance", "fr": "Pertinence", "it": "Pertinenza"},
     "Passt die Antwort zur gestellten Frage und zur angestrebten Lehrstelle?",
     "Does the answer fit the question asked and the apprenticeship applied for?",
     [("Antwort geht am Thema vorbei", "Auf Frage nach Stärken wird über Hobbys erzählt, ohne Bezug", "Answer misses the topic"),
      ("Teilweise passend, enthält aber unnötige Nebeninfos", "Antwort beginnt passend, verliert dann den Bezug zur Frage", "Partly fitting but contains unnecessary side information"),
      ("Antwort bezieht sich klar auf die Frage", "Direkte, themenbezogene Antwort", "Answer clearly addresses the question"),
      ("Antwort ist zielgerichtet und stellt zusätzlich den Bezug zur Lehrstelle her", "„Diese Genauigkeit hilft mir gerade im Beruf X, weil…“", "Answer is targeted and additionally links to the apprenticeship")]),
    ("motivation", True, {"de": "Motivation", "en": "Motivation", "fr": "Motivation", "it": "Motivazione"},
     "Erkennbares echtes Interesse am Beruf und am Betrieb",
     "Recognisable genuine interest in the occupation and the company",
     [("Kein erkennbares Interesse, floskelhafte Aussagen", "„Weil man da halt Geld verdient.“", "No recognisable interest, empty phrases"),
      ("Interesse vorhanden, aber wenig begründet", "„Der Beruf gefällt mir einfach.“", "Interest present but poorly justified"),
      ("Motivation wird nachvollziehbar begründet", "„Mich fasziniert, wie man aus Rohstoffen etwas Fertiges herstellt.“", "Motivation is plausibly justified"),
      ("Motivation ist persönlich, begründet und mit Zukunftsbezug verknüpft", "Bezug auf konkretes Erlebnis (z. B. Schnuppertag) plus langfristiges Ziel", "Motivation is personal, justified and linked to the future")]),
    ("self_reflection", True, {"de": "Selbstreflexion", "en": "Self-awareness", "fr": "Réflexion sur soi", "it": "Autoriflessione"},
     "Fähigkeit, eigene Stärken, Schwächen und Erfahrungen realistisch einzuschätzen",
     "Ability to assess one's own strengths, weaknesses and experiences realistically",
     [("Keine Selbsteinschätzung möglich oder unrealistisch", "„Ich habe keine Schwächen.“", "No or unrealistic self-assessment"),
      ("Schwäche wird genannt, aber ohne Einsicht oder Lernschritt", "„Ich bin manchmal unpünktlich, aber das ist nicht so schlimm.“", "Weakness named but without insight or learning step"),
      ("Realistische Selbsteinschätzung mit Lernansatz", "„Ich war früher schnell nervös, arbeite aber daran, ruhiger zu bleiben.“", "Realistic self-assessment with a learning approach"),
      ("Reflektierte Einschätzung inkl. konkreter Massnahme und Wirkung", "Nennt Schwäche, konkreten Schritt zur Verbesserung und ersten Erfolg", "Reflective assessment incl. concrete measure and effect")]),
    ("communication", True, {"de": "Kommunikationsfähigkeit", "en": "Communication", "fr": "Communication", "it": "Comunicazione"},
     "Ausdrucksweise, Wortwahl, Tonfall, aktives Zuhören",
     "Expression, choice of words, tone, active listening",
     [("Unhöflicher, zu lockerer oder unpassender Ton", "Umgangssprache, Unterbrechungen, einsilbige Antworten", "Impolite, too casual or inappropriate tone"),
      ("Verständlich, aber unsicher oder zu knapp", "Kurze Ja/Nein-Antworten ohne Ausführung", "Understandable but hesitant or too brief"),
      ("Angemessener, freundlicher und klarer Ausdruck", "Vollständige Sätze, höflicher Ton", "Appropriate, friendly and clear expression"),
      ("Sicher, angemessen und situativ passend, geht auf Gesprächspartner ein", "Reagiert auf Rückfragen, hört aktiv zu, formuliert präzise", "Confident, appropriate, responsive to the interviewer")]),
    ("concrete_examples", True, {"de": "Konkrete Beispiele", "en": "Concrete examples", "fr": "Exemples concrets", "it": "Esempi concreti"},
     "Aussagen werden mit echten Erlebnissen/Situationen belegt statt nur behauptet",
     "Statements are backed by real experiences/situations rather than merely claimed",
     [("Nur allgemeine Behauptungen ohne Beleg", "„Ich bin teamfähig.“ (ohne Beispiel)", "Only general claims without evidence"),
      ("Beispiel wird genannt, aber vage", "„Ich habe mal im Sportverein mitgeholfen.“", "Example given but vague"),
      ("Konkretes, nachvollziehbares Beispiel", "Schilderung einer Situation mit Kontext und eigenem Beitrag", "Concrete, comprehensible example"),
      ("Beispiel inkl. Situation, Handlung und Ergebnis", "„Als wir im Projekt X in Verzug waren, habe ich Y organisiert, wodurch wir Z erreicht haben.“", "Example incl. situation, action and result")]),
    ("demeanor", False, {"de": "Auftreten & Wirkung", "en": "Demeanour & impression", "fr": "Attitude & impression", "it": "Atteggiamento & impressione"},
     "Höflichkeit, Selbstsicherheit, Umgangston, Körpersprache (sofern erfassbar)",
     "Politeness, self-confidence, tone, body language (if observable)",
     [("Unsicher, unhöflich oder distanziert wirkend", "Kein Blickkontakt, sehr leise, abweisender Ton", "Appears insecure, impolite or distant"),
      ("Grundsätzlich höflich, aber nervös oder zurückhaltend", "Antworten wirken auswendig gelernt oder gehemmt", "Basically polite but nervous or reserved"),
      ("Freundlich, aufmerksam, angemessen selbstsicher", "Ruhiger Ton, offene Haltung", "Friendly, attentive, appropriately confident"),
      ("Souverän, zugewandt, positive Ausstrahlung", "Wirkt natürlich, reagiert flexibel auf Gesprächsverlauf", "Poised, engaged, positive presence")]),
    ("preparation", False, {"de": "Vorbereitung / Betriebskenntnis", "en": "Preparation / company knowledge", "fr": "Préparation / connaissance de l'entreprise", "it": "Preparazione / conoscenza dell'azienda"},
     "Wissen über den Lehrbetrieb, den Beruf und die Anforderungen",
     "Knowledge of the training company, the occupation and its requirements",
     [("Keine Informationen über Betrieb/Beruf vorhanden", "„Was macht die Firma eigentlich genau?“", "No information about company/occupation"),
      ("Grundwissen vorhanden, aber oberflächlich", "Nennt nur den Firmennamen", "Basic but superficial knowledge"),
      ("Betrieb und Berufsbild sind bekannt", "Nennt Produkte/Dienstleistungen des Betriebs korrekt", "Company and occupation are known"),
      ("Fundiertes Wissen, das aktiv ins Gespräch eingebracht wird", "Bezieht sich auf aktuelle Projekte oder Werte des Betriebs", "Sound knowledge actively brought into the conversation")]),
    ("goal_orientation", False, {"de": "Zielorientierung", "en": "Goal orientation", "fr": "Orientation vers les objectifs", "it": "Orientamento agli obiettivi"},
     "Klarheit über Berufswahl und langfristige Vorstellungen",
     "Clarity about career choice and long-term ideas",
     [("Keine Vorstellung von Zukunft oder Berufswahl", "„Ich weiss noch nicht, was ich danach machen will.“", "No idea about the future or career choice"),
      ("Vage Vorstellung ohne klaren Bezug zur Lehrstelle", "„Ich möchte einfach eine gute Ausbildung machen.“", "Vague idea without clear link to the apprenticeship"),
      ("Klares Ziel, das zur Lehrstelle passt", "„Ich möchte diesen Beruf lernen, weil er zu meinen Stärken passt.“", "Clear goal matching the apprenticeship"),
      ("Klares Ziel mit langfristiger Perspektive", "Nennt auch mögliche Weiterbildungs- oder Entwicklungsschritte nach der Lehre", "Clear goal with long-term perspective")]),
    ("difficult_questions", False, {"de": "Umgang mit schwierigen Fragen", "en": "Handling difficult questions", "fr": "Gestion des questions difficiles", "it": "Gestione delle domande difficili"},
     "Reaktion auf kritische, unerwartete oder unangenehme Fragen",
     "Reaction to critical, unexpected or uncomfortable questions",
     [("Blockiert, ausweichend oder abwehrend", "Wechselt bei kritischer Frage abrupt das Thema", "Blocks, evades or becomes defensive"),
      ("Reagiert, wirkt aber überfordert", "Lange Pausen, unsichere Antwort ohne klaren Inhalt", "Responds but appears overwhelmed"),
      ("Bleibt ruhig und antwortet sachlich", "Nimmt die Frage an und antwortet ehrlich", "Stays calm and answers factually"),
      ("Souveräner, konstruktiver Umgang, ggf. mit positivem Lerneffekt", "Räumt Fehler/Schwäche ein und zeigt, was daraus gelernt wurde", "Poised, constructive handling, possibly with a learning effect")]),
    ("initiative", False, {"de": "Eigeninitiative", "en": "Initiative", "fr": "Initiative", "it": "Iniziativa"},
     "Werden am Ende eigene, sinnvolle Fragen an den Betrieb gestellt?",
     "Does the candidate ask their own meaningful questions to the company at the end?",
     [("Keine Fragen am Ende des Gesprächs", "„Nein, ich habe keine Fragen.“", "No questions at the end"),
      ("Frage wird gestellt, ist aber generisch", "„Wie viele Mitarbeitende hat die Firma?“", "A question is asked but it is generic"),
      ("Frage zeigt echtes Interesse", "„Wie sieht ein typischer Arbeitstag als Lernende/r aus?“", "Question shows genuine interest"),
      ("Frage zeigt Vorbereitung und Weitblick", "„Welche Weiterbildungsmöglichkeiten gibt es nach der Lehre in diesem Betrieb?“", "Question shows preparation and foresight")]),
]

# Guideline rules (source: feedbackkriterien.md, "Leitlinien für altersgerechtes und
# konstruktives Feedback an Jugendliche"). IDs are referenced by feedback_examples.
GL = [
    ("T", "Tonalität", "Tone", [
        ("T1", "Wertschätzend und ermutigend, nie herablassend oder ironisch.", "Appreciative and encouraging, never condescending or ironic."),
        ("T2", "Auf Augenhöhe sprechen – nicht wie ein Lehrer, der eine Note verteilt, sondern wie ein unterstützender Coach.", "Speak at eye level – like a supportive coach, not a teacher handing out grades."),
        ("T3", "Keine Übertreibung ins Positive («perfekt», «genial») und keine Dramatisierung ins Negative («das war schlecht», «das geht gar nicht»).", "No exaggerated praise ('perfect', 'brilliant') and no dramatising ('that was bad')."),
    ]),
    ("S", "Sprache", "Language", [
        ("S1", "Klare, einfache Sätze; keine Fachbegriffe aus Personalwesen oder Psychologie ohne Erklärung (z. B. «geringe Selbstwirksamkeit»).", "Clear, simple sentences; no unexplained HR/psychology jargon."),
        ("S2", "Aktive Sprache statt Passiv («Du hast gut erklärt, wie …» statt «Es wurde gut erklärt, dass …»).", "Active rather than passive voice."),
        ("S3", "Kurze Sätze.", "Short sentences."),
        ("S4", "[Ergänzung, nicht im FHGR-Original] Feedback in der Sprache des Gesprächs geben (de/fr/it; bei Mundart: Standarddeutsch).", "[Addition, not in the FHGR original] Give feedback in the language of the interview (de/fr/it; for dialect: Standard German)."),
    ]),
    ("R", "Struktur des Feedbacks", "Structure", [
        ("R1", "Stärken zuerst nennen, dann Verbesserungspotenzial.", "Strengths first, then room for improvement."),
        ("R2", "Pro Kriterium maximal 1–2 zentrale Punkte, nicht alles gleichzeitig aufzählen.", "At most 1–2 key points per criterion; do not list everything at once."),
        ("R3", "Immer mit einem konkreten, machbaren nächsten Schritt abschliessen («Was du beim nächsten Mal ausprobieren kannst …»).", "Always end with a concrete, feasible next step."),
    ]),
    ("B", "Verhalten statt Person bewerten", "Behaviour, not person", [
        ("B1", "Feedback bezieht sich immer auf das gezeigte Verhalten oder die Antwort, nie auf die Person als Ganzes.", "Feedback always refers to the observed behaviour/answer, never to the person as a whole."),
        ("B2", "Nicht: «Du bist unsicher.» Sondern: «Deine Stimme wurde bei dieser Frage leiser – das kann auf Unsicherheit hindeuten.»", "Not 'You are insecure' but 'Your voice got quieter on this question – this may indicate uncertainty.'"),
        ("B3", "Keine Diagnosen oder Charakterzuschreibungen («introvertiert», «wenig motiviert», «schüchtern»).", "No diagnoses or character labels ('introverted', 'unmotivated', 'shy')."),
    ]),
    ("E", "Entwicklungsorientiert statt bewertend", "Development-oriented", [
        ("E1", "Wachstumsdenken fördern: Fehler als Lernchance rahmen, nicht als Makel.", "Foster a growth mindset: frame mistakes as learning opportunities."),
        ("E2", "Formulierungen wie «noch nicht» statt «nicht» verwenden.", "Use 'not yet' rather than 'not'."),
        ("E3", "Realistische, alterstypische Erwartungen ansetzen – ein 15-Jähriger im ersten Bewerbungsgespräch muss nicht wie ein erfahrener Berufsmann klingen.", "Age-appropriate expectations – a 15-year-old need not sound like an experienced professional."),
    ]),
    ("M", "Emotionale Sicherheit", "Emotional safety", [
        ("M1", "Nervosität, Versprecher oder Pausen nicht negativ bewerten.", "Do not penalise nervousness, slips of the tongue or pauses."),
        ("M2", "Bei besonders schwachen Antworten trotzdem einen ermutigenden Rahmen setzen, ohne die Schwäche zu beschönigen oder zu verschweigen.", "For very weak answers keep an encouraging frame without glossing over or hiding the weakness."),
    ]),
    ("K", "Konkretheit", "Concreteness", [
        ("K1", "Jede Rückmeldung mit einem Zitat oder Verweis auf eine konkrete Stelle im Gespräch belegen.", "Back every point with a quote or reference to a concrete moment in the conversation."),
        ("K2", "Verbesserungstipps müssen konkret umsetzbar sein, keine vagen Ratschläge («mehr Selbstbewusstsein zeigen» ist zu abstrakt).", "Tips must be concretely actionable, not vague ('show more confidence' is too abstract)."),
        ("K3", "Bewerte nie ohne Beleg aus dem Gespräch; fehlt eine Aussage, dies offen sagen statt raten. Nichts erfinden.", "Never rate without evidence; if there is none, say so instead of guessing. Do not invent content."),
    ]),
    ("L", "Grenzen setzen", "Boundaries", [
        ("L1", "Keine Bewertung von Aussehen, Stimme (ausser im Kontext von Nervosität), familiärem Hintergrund oder Persönlichkeitsmerkmalen.", "No judgement of appearance, voice (except re nervousness), family background or personality traits."),
        ("L2", "Keine Angst erzeugen («So wirst du nie eine Lehrstelle finden») – auch nicht implizit.", "Never create fear ('You'll never find an apprenticeship like this'), not even implicitly."),
        ("L3", "Bei Anzeichen von grosser Verunsicherung oder Selbstzweifeln: unterstützend reagieren und ggf. auf eine reale Bezugsperson (Berufsberater/in, Eltern, Lehrperson) verweisen.", "On signs of strong insecurity or self-doubt: respond supportively and refer to a real person (career counsellor, parents, teacher)."),
        ("L4", "Keine Vergleiche mit anderen Jugendlichen oder einem «idealen» Kandidaten.", "No comparisons with other young people or an 'ideal' candidate."),
    ]),
    ("A", "Abschluss jeder Rückmeldung", "Closing", [
        ("A1", "Immer mit einem stärkenden, motivierenden Satz enden, der den Übungscharakter betont.", "Always end with an encouraging sentence that stresses the practice character."),
    ]),
]


def main():
    criteria = []
    for key, core, labels, what_de, what_en, lv in C:
        criteria.append({
            "key": key, "core_challenge_criterion": core, "label": labels,
            "what_is_assessed": {"de": what_de, "en": what_en},
            "levels": [{"value": i + 1, "key": LEVELS[i]["key"], "label_de": LEVELS[i]["de"],
                        "description": {"de": d, "en": e}, "example_de": ex}
                       for i, (d, ex, e) in enumerate(lv)],
        })
    rubric = {
        "name": "FHGR Bewertungsraster Vorstellungsgespräch",
        "source": "Feedbackkriterien zum Vorstellungsgespräch.docx (FHGR / Profolio)",
        "scale": LEVELS,
        "not_observed": {"value": None, "de": "Dazu gab es im Gespräch keine Aussage", "en": "No evidence in the conversation"},
        "criteria": criteria,
    }
    (ROOT / "rubric" / "criteria.json").write_text(json.dumps(rubric, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gl = {"name": "Leitlinien für altersgerechtes und konstruktives Feedback an Jugendliche",
          "source": "Feedbackkriterien zum Vorstellungsgespräch.docx (FHGR / Profolio); K3 and L4 are taken from the feedback prompt in the same document; S4 is an addition for the multilingual setting",
          "groups": [{"key": g, "title_de": tde, "title_en": ten,
                      "rules": [{"id": rid, "de": de, "en": en} for rid, de, en in rules]}
                     for g, tde, ten, rules in GL]}
    (ROOT / "rubric" / "feedback_guidelines.json").write_text(json.dumps(gl, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote rubric/criteria.json, rubric/feedback_guidelines.json")


if __name__ == "__main__":
    main()
