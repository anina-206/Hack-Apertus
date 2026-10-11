# Projekt: Hack Apertus – FHGR AI Job Interview Coach (Frontend)

## Kontext
Hackathon-Challenge (Track 2A, FHGR): Ein KI-Interview-Coach führt mit Jugendlichen
realistische Bewerbungsgespräche für Lehrstellen und gibt danach konstruktives Feedback.
Sprachen: Deutsch, Französisch, Italienisch (Schweizerdeutsch als Plus).
Deadline: Fr 16.10.2026, 12:00 CEST.

Das Backend (Python, LangGraph, deployt mit Aegra) baut mein Kollege.
Zur Laufzeit wird nur Apertus 1.5 8B verwendet. Claude wird nur für die Entwicklung genutzt.

**Meine Aufgabe: das Frontend.**

## Tech-Stack Frontend
- Vite + React + TypeScript
- Tailwind CSS
- recharts (Feedback-Scores)
- Backend-Anbindung: REST/JSON per `fetch` (siehe `track_2a/docs/api.md`)
- Backend-URL per Env-Variable: `VITE_API_URL`
- Ordner: `track_2a/frontend/`

## Screens
1. **Setup:** Sprache wählen (DE / FR / IT / Mundart), Kandidatenprofil und Lehrstelle wählen, Interview starten
2. **Interview (Chat):** Nachrichtenverlauf, Eingabefeld, Phasen-Fortschritt, Lade- bzw. Streaming-Anzeige
3. **Feedback:** Scores der 6 Kriterien als Chart, Stärken, konkrete Tipps (positiv, jugendgerecht)

Interview-Phasen: Einstieg → Motivation → Stärken/Schwächen → Situationsfragen → Kandidatenfragen → Abschluss (`closing`) → Feedback-Report

Die Original-Challenge (Bewertungskriterien, Deliverables, Gate) steht in **`track_2a/docs/challenge.md`**.

## Daten-Vertrag
Single source of truth: **`track_2a/docs/api.md`** (von Iago, Backend). Bei Änderungen zuerst dort anpassen.
Die TS-Typen dazu stehen in `track_2a/frontend/src/api/types.ts` (Keys in snake_case wie im Backend).

## Vorgehen
- Zuerst mit einem **Mock-Service** arbeiten (gleiches Interface wie der echte API-Client),
  später gegen das echte Backend austauschen. Umschalten per Env-Variable `VITE_USE_MOCK=true`.
- Mobilfreundlich (Schüler nutzen oft das Handy).
- UI-Texte mehrsprachig (DE/FR/IT).
- Optional (Innovation): Fragen vorlesen mit `speechSynthesis`, Spracheingabe mit `SpeechRecognition`.
- Docker: Produktions-Build per nginx, als Service in `docker-compose`; `make run` startet alles.

## Regeln
- Kleine, verständliche Schritte; Code soll ich im Finale erklären können.
- Keine Claude-/Anthropic-Aufrufe im Projektcode.
