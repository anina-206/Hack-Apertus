# The Swiss Education and Vocational Training System (for Apprenticeship Applicants)

> Background document for HackApertus Track 2A (FHGR): *AI-powered job-interview coach*.
> Audience: developers building prompts and personas. It covers what a Swiss 14–16-year-old applying for an apprenticeship has behind them, what they are applying for, and where it can lead. The last section turns this into concrete guidance for the coach.
> Status: September 2026. Figures are cited with source and year; everything else describes the system in general terms.

---

## 1. The big picture in one paragraph

Switzerland has **26 cantons**, and they run compulsory schooling. School structures and names therefore differ from canton to canton. After compulsory school (age ~15), **about two-thirds of young people start vocational education and training (VET)**, the *berufliche Grundbildung*, usually called a *Lehre* (apprenticeship) (SBFI, *Berufsbildung in der Schweiz kurz erklärt*, 2025). Most of the rest go to a general-education school (Gymnasium or Fachmittelschule). An apprenticeship does **not** end a person's education. The system is designed to be *durchlässig* (permeable): after an apprenticeship you can continue to professional education (tertiary B), to a university of applied sciences through the vocational baccalaureate, and from there, via the *Passerelle*, even to a university or ETH. In Switzerland an apprenticeship is a normal, respected path. It is not a fallback for weak students.

```
Age ~4–15   Compulsory school (11 years, HarmoS)
              └─ Primary (incl. 2 years kindergarten) → Lower secondary (Sek I)
Age ~15/16  TRANSITION ("Nahtstelle I") ── Bridge offers if no solution yet
              ├─ VET / apprenticeship: EBA (2 yrs) or EFZ (3–4 yrs) [± BM1]
              └─ General education: Gymnasium / Fachmittelschule
Age ~18–20  EFZ ─┬─ Work
                 ├─ BM2 (after EFZ) → Fachhochschule (→ Passerelle → University/ETH)
                 └─ Tertiary B: Berufsprüfung, höhere Fachprüfung, höhere Fachschule HF
```

---

## 2. Compulsory school (obligatorische Schule) and HarmoS

- The **HarmoS concordat** (EDK, the intercantonal agreement on harmonising compulsory schooling) sets **11 years of compulsory school**: **8 years of primary level including 2 years of kindergarten**, then **3 years of lower secondary (Sekundarstufe I)**. Ticino keeps its 4-year *scuola media* as an exception (after a correspondingly shorter primary school), so the total is still 11 years.
- School years are often counted in **HarmoS years (1H–11H)**. **9H–11H = Sek I**, which corresponds to the old "7th–9th school year". French-speaking Switzerland commonly uses the "9H/10H/11H" labels. German-speaking Switzerland usually says "1./2./3. Sek" or "1./2./3. Oberstufe".
- Not all cantons joined HarmoS. By the end of the implementation period (2015), **15 cantons** had joined and several had rejected it in popular votes. The structural parameters (duration of levels, school entry age) were nevertheless adopted almost everywhere (EDK).

### Sek I levels differ by canton

Sek I is organised in one of three models (EDK cantonal survey):

| Model | How it works | Where (examples) |
|---|---|---|
| **Separated** (*geteilt*) | 2–4 separate school types by performance level | Most widespread in German-speaking cantons |
| **Cooperative** (*kooperativ*) | Base classes by level, plus ability groups in some subjects | Exclusively used in VD and GR, for example |
| **Integrated** (*integriert*) | Mixed classes, levels only in some subjects | Exclusively used in JU, NE, OW, TI, VS, for example |

Level names vary a lot. Examples: *Sek A / B / C*, *Sekundarschule / Realschule*, *Bezirksschule* (AG), *Sek E / G* (e.g. BS), *voie prégymnasiale / voie générale* (VD), and *corso attitudinale / corso base* in Ticino. **Why it matters:** the Sek I level strongly shapes which apprenticeships are realistic. Demanding EFZ occupations (e.g. Informatiker/in, Konstrukteur/in, Kaufmann/-frau, Laborant/in) often expect the higher level, while many craft and EBA occupations are open to all levels. An interviewer will typically ask about the school level, the report card (*Zeugnis*) and test results (see *application_process.md*).

---

## 3. Vocational education and training (berufliche Grundbildung)

### 3.1 Two federal certificates: EBA and EFZ

About **250 occupations** can be learned (SBFI 2025). Each is regulated by a federal *Bildungsverordnung* (training ordinance) and a *Bildungsplan* (training plan) written by the professional associations.

| | **EBA** — Eidgenössisches Berufsattest | **EFZ** — Eidgenössisches Fähigkeitszeugnis |
|---|---|---|
| English | Federal VET Certificate | Federal VET Diploma |
| French | AFP — Attestation fédérale de formation professionnelle | CFC — Certificat fédéral de capacité |
| Italian | CFP — Certificato federale di formazione pratica | AFC — Attestato federale di capacità |
| Duration | 2 years | 3 or 4 years |
| Target group | Mainly practically gifted young people. Recognised qualification with its own occupational profile | Qualifies for independent practice of the occupation |
| Next step | Access to an EFZ in the same field, often shortened (e.g. directly into the 2nd year) | Work, BM, tertiary B (höhere Berufsbildung) |
| Share of apprenticeship places | 8% of places offered (2026) | 91% of places offered (2026) |

Sources: SBFI 2025; Nahtstellenbarometer 2026 (SBFI, 11 June 2026).

> Watch out: the **Italian abbreviations are confusingly "swapped"** compared with French. **CFC (fr) = AFC (it) = EFZ** (3–4 years), while **AFP (fr) = CFP (it) = EBA** (2 years). Prompts must not mix these up.

Example pairs (EBA → EFZ): *Büroassistent/in EBA* → *Kaufmann/Kauffrau EFZ*; *Detailhandelsassistent/in EBA* → *Detailhandelsfachmann/-frau EFZ*; *Informatikpraktiker/in EBA* → *Informatiker/in EFZ*; *Assistent/in Gesundheit und Soziales EBA* → *Fachmann/Fachfrau Gesundheit (FaGe) EFZ*.

### 3.2 The dual system: three learning locations (drei Lernorte)

| Learning location | DE / FR / IT | What happens there |
|---|---|---|
| **Host company** | Lehrbetrieb / entreprise formatrice / azienda formatrice | Practical training, most of the week. A trained *Berufsbildner/in* (company trainer) is responsible for the apprentice |
| **Vocational school** | Berufsfachschule / école professionnelle / scuola professionale | Typically 1–2 days per week: occupation-specific theory plus general education (*ABU – allgemeinbildender Unterricht*) and sport |
| **Branch courses** | Überbetriebliche Kurse (ÜK) / cours interentreprises (CI) / corsi interaziendali (CI) | Block courses run by the professional association that teach basic practical skills |

Some occupations can also be learned **school-based** (full-time vocational schools, *Lehrwerkstätten*, *écoles de métiers*, commercial schools). This model is noticeably **more common in French-speaking Switzerland and Ticino** than in German-speaking Switzerland.

The system is run jointly by the **Confederation** (strategy, ordinances; SBFI/SEFRI), the **cantons** (implementation, supervision of apprenticeships, vocational schools, career guidance) and the **organisations of the world of work (OdA)** (content, qualifications). Companies train **voluntarily**. On average training pays off for them, because the apprentice's productive work exceeds the training costs (SBFI 2025). This explains why companies choose their apprentices carefully.

### 3.3 Apprenticeship contract (Lehrvertrag)

- A written contract between the host company and the apprentice. It is **co-signed by a parent or legal guardian** if the apprentice is a minor, which is almost always the case.
- The company submits it to the **cantonal VET office** (*Amt für Berufsbildung* / *office de la formation professionnelle* / *Divisione della formazione professionale*), which **approves** it (BBG Art. 14).
- **Probation period (Probezeit): 1–3 months.** The canton can extend it to a maximum of 6 months.
- It fixes the occupation, duration, apprentice wage (*Lehrlingslohn*, set by the company, often following association recommendations), working hours and holidays.

### 3.4 Final examination: Qualifikationsverfahren (QV)

At the end, the **Qualifikationsverfahren** (*procédure de qualification* / *procedura di qualificazione*) tests practical work, occupational knowledge and general education. Passing it gives the EBA or EFZ. It is informally called the *LAP (Lehrabschlussprüfung)*, and many people still use that term.

---

## 4. Federal Vocational Baccalaureate (Berufsmaturität, BM)

The **Berufsmaturität** (*maturité professionnelle, MP* / *maturità professionale, MP*) combines an **EFZ** with extended general education. It gives **exam-free access to a Fachhochschule** (university of applied sciences; *HES* in French, *SUP* in Italian) in a related field (SBFI 2025).

| | **BM1** (during the apprenticeship) | **BM2** (after the apprenticeship) |
|---|---|---|
| When | In parallel with the EFZ apprenticeship | After obtaining the EFZ |
| Format | Usually one extra school half-day or day per week, from the 1st year | Full-time about 1 year, or part-time about 1.5–2.5 years |
| Access | Entrance exam or school grades, depending on the canton. The **host company must agree**, because the apprentice spends less time at work | Entrance exam or grades, depending on the canton |
| FR / IT | MP1 / MP1 ("maturité intégrée") | MP2 ("post-CFC") / MP2 |

The five BM orientations (*Ausrichtungen*) are Technology, Architecture & Life Sciences; Nature, Landscape & Food; Business & Services; Art & Design; Health & Social Care (SBFI 2025).

**Passerelle:** with a BM (or Fachmaturität) and the one-year **Ergänzungsprüfung Passerelle** (supplementary exam, organised by SBFI), a person gains access to **all Swiss universities, ETH and teacher-training universities** (SBFI).

In the 2026 Nahtstellenbarometer, **27%** of young people heading for an apprenticeship said they planned to do the BM in parallel (SBFI, June 2026). A candidate for a demanding EFZ who mentions "BM1" is therefore quite common. For the company it has consequences (more school days), so interviewers often ask about it.

---

## 5. Tertiary level B: higher vocational education (höhere Berufsbildung)

Higher vocational education builds on an EFZ and work experience. It is mostly done **part-time while working**. About **470 qualifications** exist (SBFI 2025).

| Qualification | DE | FR | IT |
|---|---|---|---|
| Federal professional exam → *eidg. Fachausweis* | Berufsprüfung (BP) | examen professionnel (brevet fédéral) | esame di professione (attestato professionale federale) |
| Advanced federal exam → *eidg. Diplom* (e.g. "Meister") | höhere Fachprüfung (HFP) | examen professionnel supérieur (diplôme fédéral) | esame professionale superiore (diploma federale) |
| College of higher education → *Diplom HF* | höhere Fachschule (HF) | école supérieure (ES) | scuola specializzata superiore (SSS) |

These degrees are well recognised on the labour market. According to SBFI (2025), graduates of higher vocational education earn **almost 30% more on average** than people with only an upper-secondary vocational qualification.

**Permeability summary:** EBA → EFZ → (BM) → FH / HF / BP / HFP → (Passerelle) → university. There are no dead ends. For a 15-year-old this means that choosing an apprenticeship does not rule out later studies.

---

## 6. Transition problems and bridge offers (Brückenangebote)

Not everyone has a place when compulsory school ends. In the 2025 Nahtstellenbarometer, **16%** of the ~93,000 school leavers surveyed chose an interim solution (SBFI, Oct 2025). Cantonal **bridge offers** (*Brückenangebote* / *solutions transitoires* / *soluzioni transitorie*) include:

| Offer | DE / FR / IT | Content |
|---|---|---|
| 10th school year | 10. Schuljahr, Berufsvorbereitungsjahr / 12e année (varies by canton) / anno di preparazione | Closes school gaps, continues career choice. Name and content vary by canton |
| Pre-apprenticeship | Vorlehre / préapprentissage / pretirocinio (di orientamento, d'integrazione) | Around 3–4 days per week in a company plus school |
| Motivation semester | Motivationssemester SEMO / semestre de motivation / semestre di motivazione | For young people with no solution, registered via the RAV (public employment office): work practice, school, application coaching |
| Integration pre-apprenticeship | Integrationsvorlehre (INVOL) / préapprentissage d'intégration / pretirocinio d'integrazione | For recently arrived refugees and migrants: language plus work practice |

**Why it matters for the coach:** some realistic personas are **16–18 years old**, come from a bridge offer or from abroad, or are changing apprenticeship. Asking "why did you do a 10th year?" is a normal interview question. The answer should be framed positively ("I used the year to find the right occupation and do more Schnupperlehren"), not treated as a failure.

---

## 7. Career guidance: BIZ / Berufsberatung and the 22 Berufsfelder

- Each canton offers free **career, study and career-path guidance**. In German-speaking Switzerland the information centres are called **BIZ (Berufsinformationszentrum)**. In French-speaking Switzerland it is *orientation scolaire et professionnelle (OSP)*, with centres such as *CIO* or *OFPC* depending on the canton. In Ticino it is *orientamento scolastico e professionale (UOSP)*.
- The national portal is **berufsberatung.ch / orientation.ch / orientamento.ch**, run by SDBB on behalf of the cantons (EDK) with federal support. It has occupation profiles, the list of open apprenticeship places (**LENA — Lehrstellennachweis**), Schnupper-offers, and bridge offers.
- Career-choice lessons (*Berufliche Orientierung*, part of Lehrplan 21 in German-speaking cantons) are part of school in Sek I. Teachers, parents and BIZ counsellors support the process.
- Occupations are grouped into **22 occupational fields (Berufsfelder)**, sometimes grouped further into 9 interest fields:

| # | Berufsfeld | # | Berufsfeld |
|---|---|---|---|
| 1 | Natur (agriculture, gardening, animals, forestry) | 12 | Elektrotechnik |
| 2 | Nahrung (food) | 13 | Metall, Maschinen, Uhren |
| 3 | Gastgewerbe, Hotellerie | 14 | Chemie, Physik |
| 4 | Textilien, Mode | 15 | Planung, Konstruktion |
| 5 | Schönheit, Sport | 16 | Verkauf, Einkauf |
| 6 | Gestaltung, Kunsthandwerk | 17 | Wirtschaft, Verwaltung, Tourismus |
| 7 | Druck | 18 | Verkehr, Logistik, Sicherheit |
| 8 | Bau | 19 | Informatik |
| 9 | Gebäudetechnik | 20 | Kultur, Medien |
| 10 | Holz, Innenausbau | 21 | Gesundheit |
| 11 | Fahrzeuge | 22 | Bildung, Soziales |

The FHGR question bank (*Beispielfragen*, see [`../questions/`](../questions/)) organises occupation-specific questions along these 22 fields. They are a natural key for selecting job profiles, personas and question pools.

---

## 8. Terminology: German / French / Italian

| English | German (CH) | French (Romandie) | Italian (Ticino / GR-it) |
|---|---|---|---|
| VET / basic vocational training | berufliche Grundbildung, Lehre | formation professionnelle initiale, apprentissage | formazione professionale di base, tirocinio |
| Apprentice | Lernende/r (colloquially "Lehrling", "Stift") | apprenti/e | apprendista |
| Apprenticeship place | Lehrstelle | place d'apprentissage | posto di tirocinio |
| Host company | Lehrbetrieb | entreprise formatrice | azienda formatrice |
| Company trainer | Berufsbildner/in | formateur/trice en entreprise | formatore/trice (in azienda) |
| Taster apprenticeship | Schnupperlehre, Schnuppertage | stage (d'information / de découverte) | stage (di orientamento) |
| Apprenticeship contract | Lehrvertrag | contrat d'apprentissage | contratto di tirocinio |
| 3–4-yr diploma | EFZ | CFC | AFC |
| 2-yr certificate | EBA | AFP | CFP |
| Vocational baccalaureate | Berufsmaturität (BM1/BM2) | maturité professionnelle (MP1/MP2) | maturità professionale (MP1/MP2) |
| Vocational school | Berufsfachschule | école professionnelle | scuola professionale |
| Branch courses | überbetriebliche Kurse (ÜK) | cours interentreprises (CI) | corsi interaziendali (CI) |
| Final exam | Qualifikationsverfahren (QV, "LAP") | procédure de qualification (PQ) | procedura di qualificazione |
| University of applied sciences | Fachhochschule (FH) | haute école spécialisée (HES) | scuola universitaria professionale (SUP) |
| College of higher education | höhere Fachschule (HF) | école supérieure (ES) | scuola specializzata superiore (SSS) |
| Lower secondary school | Sekundarstufe I, Oberstufe, Sek | secondaire I, cycle d'orientation | scuola media |
| Academic high school | Gymnasium, Kantonsschule | gymnase / collège / lycée (varies by canton) | liceo |
| Bridge offer | Brückenangebot | solution transitoire | soluzione transitoria |
| Pre-apprenticeship | Vorlehre | préapprentissage | pretirocinio |
| Career guidance | Berufsberatung, BIZ | orientation (scolaire et) professionnelle | orientamento (scolastico e) professionale |
| School report | Zeugnis | bulletin scolaire | pagella |

---

## 9. Implications for the interview coach

1. **Calibrate to age 14–16.** The typical candidate is in the 2nd or 3rd year of Sek I (10H/11H). They have **no work experience**. Their "experience" comes from **Schnupperlehren**, school projects, sports clubs, scouts (Pfadi), babysitting, pocket-money jobs, and family duties. Good answers use these as examples. The coach should **not expect professional jargon, career plans spanning decades, or STAR-perfect answers** (see also the FHGR feedback criteria in [feedback_guidelines.md](feedback_guidelines.md): "A 15-year-old does not have to sound like an experienced professional").
2. **What a candidate can realistically know:** the main tasks of the occupation (from Schnupperlehre and berufsberatung.ch), the basic structure of the apprenticeship (years, school days, ÜK), what the company does (website), and perhaps BM1 or later options. They usually **do not** know about wages in detail, the Bildungsverordnung, or QV details. Do not penalise that.
3. **EBA vs EFZ candidates:** EBA candidates are often practically strong but may have weaker school results, less linguistic confidence, and sometimes a migration background or a bridge year. The persona and the interviewer should use **simpler language, shorter questions and more concrete prompts**. Frame EBA positively, including the option of continuing to an EFZ afterwards. Never treat EBA as "second class".
4. **BM ambitions:** for demanding EFZ occupations, a candidate may mention BM1, the FH, or a "Passerelle to ETH". This is legitimate and a good sign of goal orientation. A realistic interviewer may still ask: *"How will you manage the extra school day? What if your grades drop?"* Loyalty to the occupation matters to companies, so "I only do the apprenticeship to study later" is a weaker answer than "I want to learn the job properly and maybe build on it later with the BM/FH".
5. **School level and grades:** questions about the *Sek level*, the *Zeugnis*, *Stellwerk* or *Multicheck/Basic-Check* are normal in Switzerland and not discriminatory. The coach should help candidates explain weaker grades constructively.
6. **Use Swiss concepts only.** Avoid foreign concepts that confuse candidates or signal a non-Swiss model:
   - no *Abitur*, *Realschulabschluss*, *Mittlere Reife*, *IHK-Prüfung*, *Ausbildungsplatz*/*Azubi* (Germany; use *Lehrstelle*/*Lernende/r*)
   - no *bac*, *BEP/CAP*, *alternance*, *lycée professionnel* in the French-system sense (France; use *CFC/AFP*, *apprentissage dual*, *maturité professionnelle*)
   - no *maturità* in the Italian-state sense, *istituto tecnico*, *ITS* (Italy; use *AFC/CFP*, *tirocinio*, *scuola professionale*)
   - no US/UK concepts like GPA, college application, internship in the sense of a paid student job
7. **Swiss Standard German orthography:** use **"ss" instead of "ß"** (e.g. *grüssen*, *Strasse*), and Swiss vocabulary such as *Lehrstelle*, *Lernende*, *Schnupperlehre*, *Znüni*, *Grüezi*. In French and Italian, use the Swiss terms from the table (CFC/AFP; AFC/CFP).
8. **Ages and paths vary.** Include some personas who are 16–18, who come from a bridge offer or Vorlehre, who are changing apprenticeship, or who arrived recently (INVOL). Their interview questions differ ("What did you learn in your 10th year?").
9. **Keep the stakes realistic but reassuring.** Most young people find a solution. In the 2026 barometer, 73% of those interested in an apprenticeship already had a signed contract or an oral commitment by spring (SBFI, June 2026). The coach should frame practice as preparation, never as a threat ("you will never get an apprenticeship"), and should point to real support persons (BIZ counsellor, teacher, parents) when a candidate is very insecure (FHGR feedback guidelines).

---

## Sources

- SBFI/SEFRI (2025): *Die Berufsbildung in der Schweiz kurz erklärt* — https://www.sbfi.admin.ch/dam/de/sd-web/PkLymKJM-WMt/BBCH_2025_DE_WEB.pdf
- SBFI (11 June 2026): *Nahtstellenbarometer 2026: Berufliche Grundbildung bleibt erste Wahl* — https://www.sbfi.admin.ch/de/newnsb/Mul-QIZzSY-3ZqXV6Nb-k
- SBFI (28 Oct 2025): *Nahtstellenbarometer 2025: Stabilität bei Jugendlichen und Betrieben* — https://www.sbfi.admin.ch/de/newnsb/vi01XsBatKjLWHJgZ6ns_
- SBFI: *Ergänzungsprüfung Passerelle* — https://www.sbfi.admin.ch/de/ergaenzungspruefung-passerelle
- EDK/CDIP: *Obligatorische Schule (HarmoS)* — https://edk.ch/de/themen/harmos
- EDK/CDIP: *Dauer der Stufen* — https://www.edk.ch/de/bildungssystem/kantonale-schulorganisation/kantonsumfrage/a-13-dauer-der-stufen
- EDK/CDIP: *Schulmodell(e) Sekundarstufe I* — https://www.cdip.ch/de/bildungssystem/kantonale-schulorganisation/kantonsumfrage/a-4-schulmodell-e-auf-der-sekundarstufe-i
- berufsberatung.ch: *Lehrberufe: EFZ und EBA* — https://www.berufsberatung.ch/dyn/show/1973
- berufsberatung.ch: *Berufsmaturität* — https://www.berufsberatung.ch/dyn/show/3309
- berufsberatung.ch: *Brückenangebote, Zwischenlösungen* — https://www.berufsberatung.ch/dyn/show/7377 and https://www.berufsberatung.ch/dyn/show/7430
- berufsberatung.ch: *Motivationssemester SEMO* — https://www.berufsberatung.ch/dyn/show/2886?id=43948
- berufsberatung.ch: *Berufsmöglichkeiten / 22 Berufsfelder* — https://www.berufsberatung.ch/dyn/show/2468 ; Kanton St. Gallen: *9 Interessenfelder / 22 Berufsfelder* — https://www.sg.ch/content/dam/sgch/bildung-sport/berufs-studien-laufbahnberatung/infop/bw/BW-0000.pdf
- orientation.ch: *Maturité professionnelle* — https://www.orientation.ch/dyn/show/3309
- orientamento.ch: *Professioni con AFC e CFP* — https://www.orientamento.ch/dyn/show/1973 ; *Soluzioni transitorie* — https://www.orientamento.ch/dyn/show/7377
- berufsbildung.ch (SDBB): *Lexikon: Lehrvertrag*, *Probezeit*, *Berufsfachschule* — https://www.berufsbildung.ch/de/lexikon/lehrvertrag , https://www.berufsbildung.ch/de/lexikon/probezeit , https://www.berufsbildung.ch/de/lexikon/berufsfachschule
- Berufsbildungsgesetz (BBG, SR 412.10), Art. 14 — https://www.fedlex.admin.ch/eli/cc/2003/674/de
- FHGR / Profolio didactic material (not included in this repository; see [feedback_guidelines.md](feedback_guidelines.md) and [`../questions/`](../questions/))
