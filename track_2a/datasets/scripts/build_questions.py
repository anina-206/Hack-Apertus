#!/usr/bin/env python3
"""Build questions/questions.jsonl (German master texts).

Sources:
  - source_material/beispielfragen.md (FHGR/Profolio, phases 1-10 + 22 Berufsfelder)
  - synthetic additions (situational questions, difficult/unexpected questions,
    questions for other application situations), flagged with source="synthetic".

French/Italian translations and Swiss-German variants are added afterwards by
scripts/merge_parts.py from _parts/questions_translations.jsonl, so this script
only owns the German master text and the metadata.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = "Beispielfragen Vorstellungsgespräch.docx"

PHASES = {
    1: ("greeting", "Begrüssung und Einstieg", "introduction"),
    2: ("self_presentation", "Vorstellung der Bewerberin / des Bewerbers", "introduction"),
    3: ("motivation", "Motivation", "motivation"),
    4: ("knowledge", "Kenntnisse über den Beruf und den Betrieb", "motivation"),
    5: ("strengths_development", "Persönliche Stärken und Entwicklung", "strengths_weaknesses"),
    6: ("school_experience", "Schule und Erfahrungen", "strengths_weaknesses"),
    7: ("social_skills", "Soziale Kompetenzen", "strengths_weaknesses"),
    8: ("future", "Zukunft", "motivation"),
    9: ("candidate_questions", "Fragen der Bewerberin / des Bewerbers", "candidate_questions"),
    10: ("closing", "Abschluss", "closing"),
}

PHASE_CRITERIA = {
    1: ["demeanor", "communication"],
    2: ["clarity", "communication", "self_reflection"],
    3: ["motivation", "relevance", "goal_orientation"],
    4: ["preparation", "relevance"],
    5: ["self_reflection", "concrete_examples"],
    6: ["self_reflection", "concrete_examples"],
    7: ["concrete_examples", "communication", "self_reflection"],
    8: ["goal_orientation", "motivation"],
    9: ["initiative", "preparation"],
    10: ["demeanor", "communication"],
}

# (text, subtopic, type, difficulty, extra_criteria, condition)
# type: smalltalk | open | behavioral | reflective | knowledge | closing | offer
G = {
    1: [
        ("Hast du den Weg zu uns gut gefunden?", "small_talk", "smalltalk", "easy"),
        ("Wie geht es dir heute?", "small_talk", "smalltalk", "easy"),
        ("Wie war deine Anreise?", "small_talk", "smalltalk", "easy"),
        ("Ist das dein erstes Bewerbungsgespräch für eine Lehrstelle?", "small_talk", "smalltalk", "easy"),
        ("Gibt es etwas, das du vor dem Gespräch noch ansprechen möchtest?", "procedure", "open", "easy"),
    ],
    2: [
        ("Erzähl uns etwas über dich.", "general", "open", "medium"),
        ("Wie würdest du dich in wenigen Sätzen beschreiben?", "general", "reflective", "medium"),
        ("Was sollten wir unbedingt über dich wissen?", "general", "open", "medium"),
        ("Wie würdest du deinen schulischen Werdegang beschreiben?", "school_career", "open", "easy"),
        ("Welche Hobbys hast du?", "hobbies", "open", "easy"),
        ("Was machst du gerne in deiner Freizeit?", "hobbies", "open", "easy"),
        ("Wie würden deine Freunde dich beschreiben?", "general", "reflective", "medium"),
        ("Worauf bist du besonders stolz?", "general", "behavioral", "medium"),
    ],
    3: [
        ("Warum hast du dich für diesen Beruf entschieden?", "career_choice", "open", "medium"),
        ("Wie bist du auf diesen Beruf aufmerksam geworden?", "career_choice", "open", "easy"),
        ("Was fasziniert dich an diesem Beruf besonders?", "interest_in_occupation", "open", "medium"),
        ("Weshalb möchtest du deine Lehre gerade bei unserem Betrieb absolvieren?", "company_motivation", "open", "medium"),
        ("Was erwartest du von deiner Ausbildung?", "expectations", "open", "medium"),
        ("Welche Erfahrungen haben dein Interesse an diesem Beruf geweckt?", "career_choice", "behavioral", "medium"),
        ("Wie möchtest du dich während der Lehre persönlich und fachlich weiterentwickeln?", "further_development", "reflective", "medium"),
    ],
    4: [
        ("Was weisst du über unseren Betrieb?", "company_knowledge", "knowledge", "medium"),
        ("Wie hast du dich über unseren Betrieb informiert?", "company_knowledge", "knowledge", "easy"),
        ("Was gefällt dir an unserem Unternehmen?", "company_knowledge", "open", "medium"),
        ("Welche Aufgaben gehören deiner Meinung nach zu diesem Beruf?", "occupation_knowledge", "knowledge", "medium"),
        ("Welche Anforderungen bringt dieser Beruf mit sich?", "occupation_knowledge", "knowledge", "medium"),
        ("Was glaubst du, ist in diesem Beruf besonders wichtig?", "occupation_knowledge", "knowledge", "medium"),
        ("Was erwartest du von deinem Lehrbetrieb?", "training_expectations", "open", "medium"),
        ("Was erwartest du von deiner Berufsbildnerin oder deinem Berufsbildner?", "training_expectations", "open", "medium"),
        ("Welche Eigenschaften sollte eine lernende Person in diesem Beruf mitbringen?", "occupation_knowledge", "reflective", "medium"),
        ("Was glaubst du, wird in der Lehre die grösste Herausforderung sein?", "training_expectations", "reflective", "hard"),
    ],
    5: [
        ("Was sind deine grössten Stärken?", "strengths", "reflective", "medium"),
        ("Welche Eigenschaft zeichnet dich besonders aus?", "strengths", "reflective", "medium"),
        ("Welche Schwäche möchtest du verbessern?", "weaknesses", "reflective", "hard"),
        ("Wie gehst du mit Fehlern um?", "handling_challenges", "behavioral", "hard"),
        ("Wie reagierst du auf Kritik?", "handling_challenges", "behavioral", "hard"),
        ("Kannst du ein Beispiel nennen, bei dem du eine Herausforderung erfolgreich gemeistert hast?", "handling_challenges", "behavioral", "hard"),
        ("Wie lernst du am besten?", "willingness_to_learn", "reflective", "medium"),
        ("Was tust du, wenn du etwas nicht verstehst?", "willingness_to_learn", "behavioral", "medium"),
        ("Wie motivierst du dich bei schwierigen Aufgaben?", "willingness_to_learn", "reflective", "medium"),
        ("Worin möchtest du dich persönlich noch weiterentwickeln?", "weaknesses", "reflective", "medium"),
    ],
    6: [
        ("Welche Schulfächer machen dir besonders Freude?", "favourite_subjects", "open", "easy"),
        ("Welche Fächer fallen dir schwerer?", "favourite_subjects", "reflective", "medium"),
        ("Wie würdest du deine Arbeitshaltung in der Schule beschreiben?", "work_attitude", "reflective", "medium"),
        ("Wie zufrieden bist du mit deinen bisherigen schulischen Leistungen?", "report_card", "reflective", "medium"),
        ("Gibt es etwas in deinem Zeugnis, das du gerne erklären möchtest?", "report_card", "reflective", "hard"),
        ("Gibt es etwas im Stellwerk, das du gerne erklären möchtest?", "report_card", "reflective", "hard",
         "Nur stellen, wenn das Stellwerk absolviert worden ist."),
        ("Welche Erfahrungen hast du während Schnupperlehren oder Praktika gesammelt?", "trial_apprenticeship", "behavioral", "medium"),
        ("Was hat dir an einer Schnupperlehre besonders gefallen?", "trial_apprenticeship", "behavioral", "easy"),
        ("Welche Erkenntnisse hast du aus deinen bisherigen Schnupperlehren mitgenommen?", "trial_apprenticeship", "reflective", "medium"),
        ("Auf welches schulische oder private Projekt bist du besonders stolz?", "projects_achievements", "behavioral", "medium"),
    ],
    7: [
        ("Arbeitest du lieber alleine oder im Team? Warum?", "teamwork", "reflective", "medium"),
        ("Welche Rolle übernimmst du häufig in einer Gruppe?", "teamwork", "reflective", "medium"),
        ("Wie gehst du mit unterschiedlichen Meinungen um?", "conflict_resolution", "behavioral", "medium"),
        ("Wie löst du Konflikte mit anderen?", "conflict_resolution", "behavioral", "hard"),
        ("Wie reagierst du, wenn dich jemand kritisiert?", "communication", "behavioral", "hard"),
        ("Wie würden deine Lehrpersonen deine Zusammenarbeit mit anderen beschreiben?", "teamwork", "reflective", "medium"),
        ("Wie unterstützt du andere Personen?", "teamwork", "behavioral", "medium"),
        ("Wie wichtig ist dir ein gutes Arbeitsklima?", "teamwork", "open", "easy"),
        ("Was macht für dich eine gute Zusammenarbeit aus?", "teamwork", "reflective", "medium"),
    ],
    8: [
        ("Welche beruflichen Ziele hast du?", "career_goals", "open", "medium"),
        ("Wo siehst du dich nach der Lehre?", "career_goals", "open", "medium"),
        ("Welche Weiterbildung kannst du dir nach der Lehre vorstellen?", "career_goals", "knowledge", "medium"),
        ("Welche Fähigkeiten möchtest du während der Lehre erwerben?", "career_goals", "reflective", "medium"),
        ("Was möchtest du nach deiner Ausbildung erreichen?", "career_goals", "open", "medium"),
        ("Welche Entwicklung wünschst du dir für deine berufliche Zukunft?", "career_goals", "open", "medium"),
        ("Kannst du dir vorstellen, nach der Lehre im Betrieb zu bleiben?", "career_goals", "open", "easy"),
        ("Welche Ziele möchtest du während der Lehre erreichen?", "career_goals", "open", "medium"),
        ("Was motiviert dich langfristig in deinem Berufsleben?", "career_goals", "reflective", "hard"),
    ],
    9: [
        ("Hast du Fragen zu unserem Betrieb?", "company_questions", "offer", "medium"),
        ("Gibt es etwas, das du über die Lehre genauer wissen möchtest?", "training_questions", "offer", "medium"),
        ("Hast du Fragen zum Team?", "company_questions", "offer", "medium"),
        ("Interessierst du dich für den Ablauf der Ausbildung?", "training_questions", "offer", "easy"),
        ("Möchtest du etwas über Weiterbildungsmöglichkeiten wissen?", "training_questions", "offer", "easy"),
        ("Hast du Fragen zu unseren Erwartungen an Lernende?", "training_questions", "offer", "medium"),
        ("Gibt es etwas, das wir bisher noch nicht angesprochen haben?", "company_questions", "offer", "medium"),
        ("Möchtest du mehr über die nächsten Schritte erfahren?", "next_steps", "offer", "easy"),
        ("Hast du weitere Fragen an uns?", "company_questions", "offer", "medium"),
    ],
    10: [
        ("Gibt es noch etwas, das du uns gerne mitteilen möchtest?", "summary", "closing", "medium"),
        ("Haben wir etwas Wichtiges vergessen zu besprechen?", "summary", "closing", "easy"),
        ("Möchtest du abschliessend noch etwas ergänzen?", "summary", "closing", "medium"),
        ("Dürfen wir dich kontaktieren, falls wir weitere Fragen haben?", "next_steps", "closing", "easy"),
    ],
}

# 22 Berufsfelder (occupational fields, SDBB classification) with example occupations
BF = [
    ("natur", "Natur", "Landwirt/in, Forstwart/in, Gärtner/in, Tierpfleger/in, Winzer/in", [
        "Warum interessierst du dich für die Arbeit mit Tieren, Pflanzen oder in der Natur?",
        "Wie gehst du mit Arbeit im Freien bei jedem Wetter um?",
        "Wie gehst du mit körperlich anstrengender Arbeit um?",
        "Welche Erfahrungen hast du bereits in der Natur, mit Tieren oder Pflanzen gesammelt?",
        "Wie gehst du mit frühen Arbeitszeiten oder unregelmässigen Einsätzen um, z. B. bei der Tierpflege?",
        "Was bedeutet für dich ein sorgsamer Umgang mit Lebewesen und Umwelt?",
        "Wie reagierst du, wenn du auch bei unangenehmen Arbeiten wie Reinigen oder Misten anpacken musst?",
    ]),
    ("nahrung", "Nahrung", "Bäcker/in-Konditor/in, Metzger/in, Lebensmitteltechnologe/in, Käser/in", [
        "Warum interessierst du dich für die Herstellung von Lebensmitteln?",
        "Wie gehst du mit frühen Arbeitszeiten um, z. B. in einer Bäckerei?",
        "Was bedeutet für dich Hygiene und Sauberkeit am Arbeitsplatz?",
        "Wie gehst du mit körperlicher Arbeit und dem Stehen über längere Zeit um?",
        "Welche Erfahrungen hast du bereits beim Kochen, Backen oder Verarbeiten von Lebensmitteln gesammelt?",
        "Wie wichtig ist dir Genauigkeit beim Einhalten von Rezepturen und Mengenangaben?",
    ]),
    ("gastgewerbe", "Gastgewerbe, Hotellerie", "Koch/Köchin, Restaurationsfachfrau/-mann, Hotelfachfrau/-mann", [
        "Warum interessierst du dich für die Arbeit mit Gästen?",
        "Wie gehst du mit Stress in einer hektischen Küche oder im Service um?",
        "Was bedeutet für dich Gastfreundschaft?",
        "Wie würdest du mit einem unzufriedenen Gast umgehen?",
        "Wie gehst du mit unregelmässigen Arbeitszeiten und Wochenendarbeit um?",
        "Kannst du auch unter Zeitdruck ruhig und freundlich bleiben?",
    ]),
    ("textilien", "Textilien, Mode", "Bekleidungsgestalter/in, Textiltechnologe/in", [
        "Was fasziniert dich an der Verarbeitung von Textilien, Leder oder Stoffen?",
        "Welche Erfahrungen hast du bereits im Nähen, Gestalten oder handwerklichen Arbeiten gesammelt?",
        "Wie wichtig ist dir Genauigkeit und ein Sinn für Formen und Materialien?",
        "Wie gehst du mit sich wiederholenden, feinmotorischen Arbeitsschritten um?",
        "Wie gehst du vor, wenn ein Produkt nicht wie gewünscht gelingt?",
        "Wie stellst du dir die Zusammenarbeit mit Kundinnen und Kunden bei Massanfertigungen vor?",
    ]),
    ("schoenheit_sport", "Schönheit, Sport", "Coiffeuse/Coiffeur, Kosmetikerin/Kosmetiker, Fachfrau/-mann Bewegung und Gesundheit", [
        "Was bedeutet für dich guter Kundenkontakt und persönliche Beratung?",
        "Wie gehst du mit körperlicher Nähe zu Kundinnen und Kunden um?",
        "Welche Erfahrungen hast du bereits in diesem Bereich gesammelt?",
        "Wie wichtig ist dir ein gepflegtes Erscheinungsbild?",
        "Wie gehst du mit stehender Tätigkeit und Arbeit am Samstag um?",
    ]),
    ("gestaltung", "Gestaltung, Kunsthandwerk", "Grafiker/in, Fotograf/in, Goldschmied/in, Interactive Media Designer/in", [
        "Was fasziniert dich am kreativen Gestalten?",
        "Kannst du uns ein eigenes gestalterisches Projekt zeigen oder beschreiben?",
        "Wie gehst du mit Kritik an deinen eigenen Ideen um?",
        "Wie gehst du vor, wenn dir die Inspiration fehlt?",
        "Wie wichtig ist es dir, dich an die Vorgaben eines Kunden, einer Kundin zu halten?",
        "Wie gehst du mit engen Zeitplänen bei kreativen Projekten um?",
    ]),
    ("druck", "Druck", "Polygraf/in, Printmedienverarbeiter/in, Interactive-Media-Berufe im Druckbereich", [
        "Was interessiert dich an der Herstellung von Druckerzeugnissen und Medien?",
        "Wie wichtig ist dir genaues und sorgfältiges Arbeiten?",
        "Welche Erfahrungen hast du bereits mit Gestaltungsprogrammen gesammelt?",
        "Wie gehst du mit repetitiven Arbeitsschritten in der Produktion um?",
        "Wie stellst du dir die Zusammenarbeit zwischen Gestaltung und Produktion vor?",
    ]),
    ("bau", "Bau", "Maurer/in, Strassenbauer/in, Bodenleger/in", [
        "Wie gehst du mit Arbeit im Freien bei jedem Wetter um?",
        "Was bedeutet für dich Teamarbeit auf einer Baustelle?",
        "Wie gehst du mit körperlich fordernder Arbeit um?",
        "Wie schätzt du deine handwerklichen Fähigkeiten ein?",
        "Wie gehst du mit strikten Sicherheitsvorschriften auf der Baustelle um?",
    ]),
    ("gebaeudetechnik", "Gebäudetechnik", "Sanitärinstallateur/in, Heizungsinstallateur/in, Elektroinstallateur/in", [
        "Warum interessierst du dich für technische Installationen in Gebäuden?",
        "Wie gehst du mit der Arbeit in engen Räumen, auf Leitern oder Gerüsten um?",
        "Wie wichtig ist dir Sicherheit im Umgang mit Strom, Wasser oder Gas?",
        "Wie schätzt du deine handwerklichen Fähigkeiten ein?",
        "Wie stellst du dir den Arbeitsalltag auf wechselnden Baustellen vor?",
    ]),
    ("holz", "Holz, Innenausbau", "Schreiner/in, Möbelschreiner/in, Innendekorateur/in", [
        "Was fasziniert dich an der Arbeit mit Holz und anderen Materialien?",
        "Wie wichtig ist dir sorgfältiges und genaues Arbeiten?",
        "Welche Erfahrungen hast du bereits im Umgang mit Holz und Maschinen gesammelt?",
        "Wie gehst du mit Lärm und Staub in der Werkstatt um?",
        "Wie gehst du vor, wenn ein Werkstück nicht wie geplant gelingt?",
        "Wie stellst du dir die Zusammenarbeit mit Kundinnen und Kunden bei Massanfertigungen vor?",
    ]),
    ("fahrzeuge", "Fahrzeuge", "Automobil-Fachmann/-frau, Carrosserielackierer/in, Zweiradmechaniker/in", [
        "Warum interessierst du dich für die Technik von Fahrzeugen?",
        "Welche Erfahrungen hast du bereits im Umgang mit Fahrzeugen oder Mechanik gesammelt?",
        "Wie wichtig ist dir sauberes und genaues Arbeiten unter Zeitdruck?",
        "Wie gehst du mit Lärm, Öl oder Schmutz am Arbeitsplatz um?",
        "Hast du Freude daran, mit Kundinnen und Kunden zu kommunizieren?",
    ]),
    ("elektrotechnik", "Elektrotechnik", "Elektroniker/in, Automatiker/in, Montage-Elektriker/in", [
        "Was fasziniert dich an Elektrotechnik und elektronischen Systemen?",
        "Wie wichtig ist dir logisches und systematisches Denken?",
        "Welche Erfahrungen hast du bereits mit elektronischen Bauteilen oder Schaltungen gesammelt?",
        "Wie wichtig ist dir Sicherheit im Umgang mit Strom?",
        "Liegen dir Tätigkeiten, bei denen präzises und sorgfältiges Arbeiten gefragt ist? Kannst du ein Beispiel nennen?",
    ]),
    ("metall", "Metall, Maschinen, Uhren", "Polymechaniker/in, Metallbauer/in", [
        "Was reizt dich an der Arbeit mit Maschinen und Metall?",
        "Wie wichtig ist dir Genauigkeit?",
        "Welche Erfahrungen hast du bereits mit Werkzeugmaschinen oder technischen Zeichnungen gesammelt?",
        "Wie gehst du mit Lärm und körperlicher Arbeit in der Werkstatt um?",
        "Wie gehst du vor, wenn ein Werkstück nicht den geforderten Massen entspricht?",
        "Wie leicht fällt es dir, dir ein fertiges Produkt anhand einer Zeichnung oder Skizze vorzustellen?",
    ]),
    ("chemie_physik", "Chemie, Physik", "Chemie- und Pharmatechnologe/in, Laborant/in", [
        "Was fasziniert dich an naturwissenschaftlichen Fragestellungen?",
        "Wie wichtig ist dir exaktes und sauberes Arbeiten?",
        "Welche Erfahrungen hast du bereits in Naturwissenschaften oder im Labor gesammelt?",
        "Wie gehst du mit dem Einhalten von Sicherheitsvorschriften im Umgang mit Chemikalien um?",
        "Wie gehst du vor, wenn ein Experiment nicht das erwartete Ergebnis liefert?",
        "Wie wichtig ist dir eine strukturierte, protokollgenaue Arbeitsweise?",
    ]),
    ("planung_konstruktion", "Planung, Konstruktion", "Zeichner/in Fachrichtung Architektur, Bauzeichner/in, Landschaftsgärtner/in Planung", [
        "Was fasziniert dich am Planen und Konstruieren?",
        "Fällt es dir leicht, dir Gegenstände oder Bauteile räumlich vorzustellen?",
        "Welche Erfahrungen hast du bereits mit technischem Zeichnen oder Planungsprogrammen gesammelt?",
        "Wie gehst du mit genauem und detailorientiertem Arbeiten am Bildschirm um?",
        "Wie stellst du dir die Zusammenarbeit mit verschiedenen Fachpersonen auf einer Baustelle vor?",
    ]),
    ("verkauf", "Verkauf, Einkauf", "Detailhandelsfachfrau/-mann, Detailhandelsassistent/in", [
        "Was bedeutet für dich guter Kundenkontakt?",
        "Wie würdest du auf einen schwierigen oder unzufriedenen Kunden reagieren?",
        "Wie gehst du mit stressigen Stosszeiten um, z. B. vor Feiertagen?",
        "Wie wichtig ist dir ein gepflegtes Erscheinungsbild?",
        "Wie gehst du mit stehender Tätigkeit über längere Zeit um?",
        "Kannst du dir vorstellen, auch am Samstag oder abends zu arbeiten?",
    ]),
    ("wirtschaft", "Wirtschaft, Verwaltung, Tourismus", "Kauffrau/Kaufmann", [
        "Wie sicher fühlst du dich im Umgang mit Zahlen?",
        "Wie gehst du mit vertraulichen Informationen um?",
        "Welche Erfahrungen hast du im Umgang mit Programmen wie Word oder Excel?",
        "Was bedeutet für dich eine strukturierte und organisierte Arbeitsweise?",
        "Wie gehst du mit wiederkehrenden, administrativen Aufgaben um?",
        "Wie schätzt du deine schriftliche Ausdrucksfähigkeit ein?",
    ]),
    ("logistik", "Verkehr, Logistik, Sicherheit", "Logistiker/in, Strassentransportfachmann/-frau, Fachmann/-frau öffentlicher Verkehr", [
        "Was interessiert dich an der Organisation von Warenflüssen oder am Verkehr?",
        "Wie wichtig ist dir eine sorgfältige und exakte Arbeitsweise?",
        "Wie gehst du mit körperlicher Arbeit, z. B. beim Heben und Bewegen von Waren, um?",
        "Wie gehst du mit Zeitdruck bei engen Lieferfristen um?",
        "Welche Erfahrungen hast du bereits im Umgang mit Lager- oder Transportprozessen gesammelt?",
        "Wie gehst du mit unregelmässigen Arbeitszeiten oder Schichtarbeit um?",
    ]),
    ("informatik", "Informatik", "Informatiker/in EFZ, Mediamatiker/in, ICT-Fachmann/-frau", [
        "Was fasziniert dich an Computern und Technologie?",
        "Hast du bereits eigene Projekte programmiert oder ausprobiert?",
        "Wie gehst du vor, wenn ein Programm nicht wie erwartet funktioniert?",
        "Wie hältst du dich über neue technische Entwicklungen auf dem Laufenden?",
        "Wie schätzt du deine Fähigkeit zum logischen und analytischen Denken ein?",
        "Wie gehst du mit stundenlanger, konzentrierter Arbeit am Bildschirm um?",
    ]),
    ("kultur_medien", "Kultur, Medien", "Buchhändler/in, Musikinstrumentenbauer/in, Fachmann/-frau Kulturvermittlung", [
        "Was interessiert dich an Sprache, Medien oder kulturellen Themen?",
        "Wie wichtig ist dir der Kontakt mit Kundinnen und Kunden zu kulturellen oder literarischen Themen?",
        "Welche Erfahrungen hast du bereits im Bereich Kultur, Musik oder Literatur gesammelt?",
        "Wie gehst du mit vielfältigen, wechselnden Aufgaben im Arbeitsalltag um?",
        "Wie wichtig ist dir eine gepflegte mündliche und schriftliche Ausdrucksweise?",
        "Wie stellst du dir die Beratung von Kundinnen und Kunden in diesem Bereich vor?",
    ]),
    ("gesundheit", "Gesundheit", "Fachfrau/Fachmann Gesundheit FaGe, Dentalassistent/in, Pharma-Assistent/in", [
        "Warum möchtest du mit Menschen arbeiten, die Unterstützung oder Pflege brauchen?",
        "Wie gehst du mit belastenden oder emotionalen Situationen um?",
        "Was bedeutet für dich Diskretion im Umgang mit Patientendaten?",
        "Wie gehst du mit körperlicher Nähe im Berufsalltag um?",
        "Welche Erfahrungen hast du bereits im Gesundheitsbereich gesammelt?",
        "Wie gehst du mit unregelmässigen Arbeitszeiten und Schichtarbeit um?",
    ]),
    ("bildung_soziales", "Bildung, Soziales", "Fachfrau/Fachmann Betreuung FaBe, Fachfrau/-mann Kindererziehung", [
        "Warum interessierst du dich für die Arbeit mit Kindern, älteren Menschen oder Menschen mit Behinderung?",
        "Wie gehst du mit belastenden oder emotionalen Situationen um?",
        "Was bedeutet für dich Geduld im Umgang mit anderen Menschen?",
        "Welche Erfahrungen hast du bereits in der Betreuung oder Erziehung gesammelt?",
        "Wie gehst du mit unregelmässigen Arbeitszeiten um, z. B. am Wochenende?",
    ]),
]

# Synthetic: situational questions (flow stage "situational"; the source material
# has no dedicated block for them, the challenge flow requires one).
SIT = [
    ("Stell dir vor, du hast bei einer Arbeit einen Fehler gemacht und niemand hat es bemerkt. Was machst du?", "honesty_errors", ["self_reflection", "relevance", "clarity"]),
    ("Stell dir vor, deine Berufsbildnerin gibt dir einen Auftrag, den du nicht ganz verstanden hast. Sie ist gerade sehr beschäftigt. Wie gehst du vor?", "asking_for_help", ["communication", "relevance", "clarity"]),
    ("Du hast am Freitag eine wichtige Prüfung an der Berufsfachschule und im Betrieb ist gleichzeitig sehr viel los. Wie organisierst du dich?", "time_management", ["concrete_examples", "clarity", "goal_orientation"]),
    ("Ein anderer Lernender macht seine Arbeit regelmässig nicht fertig und du musst sie übernehmen. Was machst du?", "team_conflict", ["communication", "concrete_examples", "relevance"]),
    ("Du merkst am Morgen, dass du wegen eines Zugausfalls zu spät zur Arbeit kommen wirst. Was tust du?", "reliability", ["relevance", "clarity", "communication"]),
    ("Eine Kundin oder ein Kunde ist unfreundlich zu dir, obwohl du nichts falsch gemacht hast. Wie reagierst du?", "difficult_customer", ["communication", "demeanor", "relevance"]),
    ("Du bekommst eine Aufgabe, die dir langweilig erscheint, zum Beispiel aufräumen oder putzen. Wie gehst du damit um?", "motivation_routine", ["motivation", "self_reflection", "relevance"]),
    ("Deine Kollegin sagt dir, dass du eine Arbeit falsch gemacht hast. Du bist aber überzeugt, dass du es richtig gemacht hast. Was machst du?", "disagreement", ["communication", "self_reflection", "difficult_questions"]),
    ("Stell dir vor, du beobachtest, wie jemand im Betrieb eine Sicherheitsregel nicht einhält. Wie reagierst du?", "safety", ["relevance", "communication", "clarity"]),
    ("Du hast dir eine Aufgabe vorgenommen, kommst aber nicht weiter und die Zeit wird knapp. Was machst du?", "problem_solving", ["concrete_examples", "clarity", "self_reflection"]),
    ("Im ersten Lehrjahr merkst du, dass dir ein Teil der Arbeit weniger gefällt als erwartet. Wie gehst du damit um?", "expectation_mismatch", ["motivation", "self_reflection", "goal_orientation"]),
    ("Stell dir vor, du arbeitest in einer Gruppe und niemand übernimmt die Führung. Was tust du?", "initiative_team", ["concrete_examples", "communication", "initiative"]),
]

# Synthetic: difficult / unexpected questions (criterion "difficult_questions").
DIF = [
    ("Warum sollten wir gerade dich nehmen und nicht jemand anderen?", "self_marketing", ["difficult_questions", "motivation", "self_reflection"]),
    ("Bei wie vielen anderen Betrieben hast du dich auch beworben?", "other_applications", ["difficult_questions", "motivation", "communication"]),
    ("Was machst du, wenn du diese Lehrstelle nicht bekommst?", "plan_b", ["difficult_questions", "goal_orientation", "self_reflection"]),
    ("In deinem Zeugnis sehe ich einige unentschuldigte Absenzen. Kannst du mir das erklären?", "absences", ["difficult_questions", "self_reflection", "clarity"]),
    ("Was war der grösste Misserfolg, den du bisher erlebt hast?", "failure", ["difficult_questions", "self_reflection", "concrete_examples"]),
    ("Deine Mathematiknote ist eher tief. Dieser Beruf verlangt aber viel Rechnen. Wie siehst du das?", "grade_mismatch", ["difficult_questions", "self_reflection", "goal_orientation"]),
    ("Was sagen deine Eltern zu deiner Berufswahl?", "family_view", ["difficult_questions", "motivation", "self_reflection"]),
    ("Wenn du nicht in diesem Beruf arbeiten könntest, was würdest du sonst machen?", "alternative_career", ["difficult_questions", "motivation", "goal_orientation"]),
    ("Was würde deine Klassenlehrperson über dich sagen, das dir vielleicht nicht so gefällt?", "external_view", ["difficult_questions", "self_reflection", "communication"]),
    ("Du wirkst etwas nervös. Möchtest du kurz durchatmen?", "nervousness", ["difficult_questions", "demeanor", "communication"]),
]

# Synthetic: questions for other application situations (see source_material/bewerbungssituationen.md)
OTHER = [
    # (situation, text, subtopic, criteria)
    ("phone_call_trial", "Grüezi, hier ist die Firma. Was kann ich für dich tun?", "call_opening", ["clarity", "demeanor", "communication"]),
    ("phone_call_trial", "Für welche Woche hättest du dir eine Schnupperlehre vorgestellt?", "scheduling", ["clarity", "preparation"]),
    ("phone_call_trial", "Hast du bereits eine Bewerbung geschickt oder soll ich dir sagen, was wir brauchen?", "documents", ["preparation", "communication"]),
    ("trial_interview", "Was möchtest du während der Schnupperlehre bei uns herausfinden?", "trial_goals", ["motivation", "goal_orientation"]),
    ("trial_interview", "Hast du schon in anderen Berufen geschnuppert? Welche?", "trial_history", ["concrete_examples", "self_reflection"]),
    ("trial_interview", "Wie kommst du während der Schnupperwoche jeweils zu uns?", "logistics", ["preparation", "clarity"]),
    ("online_interview", "Hörst und siehst du mich gut?", "tech_check", ["demeanor", "communication"]),
    ("online_interview", "Wie hast du dich auf dieses Online-Gespräch vorbereitet?", "online_preparation", ["preparation", "self_reflection"]),
    ("assessment", "Ihr habt als Gruppe 20 Minuten Zeit, einen Stand für den Tag der offenen Tür zu planen. Wie gehst du vor?", "group_task", ["initiative", "communication", "concrete_examples"]),
    ("assessment", "Wie hast du die Gruppenarbeit eben erlebt? Was war deine Rolle?", "group_task_reflection", ["self_reflection", "communication"]),
    ("assessment", "Bitte stell uns in zwei Minuten einen Gegenstand vor, der dir wichtig ist.", "short_presentation", ["clarity", "communication", "demeanor"]),
    ("follow_up_interview", "Wie hast du die Schnupperlehre bei uns erlebt?", "trial_debrief", ["self_reflection", "concrete_examples", "motivation"]),
    ("follow_up_interview", "Was hat dich während der Schnupperwoche überrascht?", "trial_debrief", ["self_reflection", "concrete_examples"]),
    ("follow_up_interview", "Unsere Fachperson hat gesagt, dass du am zweiten Tag etwas zurückhaltend warst. Wie hast du das selbst erlebt?", "feedback_reaction", ["difficult_questions", "self_reflection", "communication"]),
]


def main():
    out = []
    for ph, items in G.items():
        key, title, stage = PHASES[ph]
        for i, it in enumerate(items, 1):
            text, sub, typ, diff = it[:4]
            cond = it[4] if len(it) > 4 else None
            crit = list(PHASE_CRITERIA[ph])
            if typ == "behavioral" and "concrete_examples" not in crit:
                crit.append("concrete_examples")
            if diff == "hard" and "difficult_questions" not in crit:
                crit.append("difficult_questions")
            out.append({
                "id": f"Q-{ph:02d}-{i:02d}", "category": "general",
                "phase": ph, "phase_key": key, "phase_title_de": title, "flow_stage": stage,
                "subtopic": sub, "berufsfeld": None, "situation": "apprenticeship_interview",
                "type": typ, "difficulty": diff, "criteria": crit, "condition": cond,
                "text": {"de": text}, "source": SRC,
            })
    for n, (key, title, examples, qs) in enumerate(BF, 1):
        for i, text in enumerate(qs, 1):
            out.append({
                "id": f"Q-BF{n:02d}-{i:02d}", "category": "occupation_specific",
                "phase": 4, "phase_key": "occupation_specific", "phase_title_de": f"Berufsbezogene Fragen – {title}",
                "flow_stage": "situational", "subtopic": key,
                "berufsfeld": {"key": key, "name_de": title, "example_occupations_de": examples},
                "situation": "apprenticeship_interview", "type": "occupation", "difficulty": "medium",
                "criteria": ["relevance", "preparation", "motivation", "concrete_examples"], "condition": None,
                "text": {"de": text}, "source": SRC,
            })
    for i, (text, sub, crit) in enumerate(SIT, 1):
        out.append({
            "id": f"Q-SIT-{i:02d}", "category": "situational", "phase": 5, "phase_key": "situational",
            "phase_title_de": "Situative Fragen", "flow_stage": "situational", "subtopic": sub,
            "berufsfeld": None, "situation": "apprenticeship_interview", "type": "situational",
            "difficulty": "hard", "criteria": crit, "condition": None, "text": {"de": text}, "source": "synthetic",
        })
    for i, (text, sub, crit) in enumerate(DIF, 1):
        out.append({
            "id": f"Q-DIF-{i:02d}", "category": "difficult", "phase": 5, "phase_key": "difficult",
            "phase_title_de": "Schwierige / unerwartete Fragen", "flow_stage": "situational", "subtopic": sub,
            "berufsfeld": None, "situation": "apprenticeship_interview", "type": "difficult",
            "difficulty": "hard", "criteria": crit,
            "condition": "Nur stellen, wenn das Kandidatenprofil passende Hinweise enthält (z. B. Absenzen, tiefe Note)." if sub in ("absences", "grade_mismatch") else None,
            "text": {"de": text}, "source": "synthetic",
        })
    for i, (sit, text, sub, crit) in enumerate(OTHER, 1):
        out.append({
            "id": f"Q-OTH-{i:02d}", "category": "other_situation", "phase": None, "phase_key": sit,
            "phase_title_de": None, "flow_stage": "introduction" if sub in ("call_opening", "tech_check") else "situational",
            "subtopic": sub, "berufsfeld": None, "situation": sit, "type": "situation_specific",
            "difficulty": "medium", "criteria": crit, "condition": None, "text": {"de": text}, "source": "synthetic",
        })
    p = ROOT / "questions" / "questions.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for q in out:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"wrote {len(out)} questions -> {p}")


if __name__ == "__main__":
    main()
