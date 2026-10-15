# Frontend

React web app of the Schnupper Interview Coach (Vite, React, TypeScript, Tailwind CSS, recharts).
In Docker it is built and served by nginx on port 8080 (`make run` in `track_2a/`).

## Screens

| Screen | File | What it does |
|---|---|---|
| Login (optional) | `src/screens/AuthScreen.tsx` | Account to keep interviews; guests can use everything |
| Setup | `src/screens/SetupScreen.tsx` | Language (DE/FR/IT/Mundart and dialect), occupation, interviewer style, mode, optional application letter |
| Interview | `src/screens/InterviewScreen.tsx` | Chat with progress through the phases, or the hands-free call view (`components/CallView.tsx`) |
| Feedback | `src/screens/FeedbackScreen.tsx` | Strengths, tips with example answers, letter feedback, what to practise next; the overall score and the 11 criteria (chart and comments) folded away until opened |

Voice: `src/useVoice.ts` records the answer, sends it to `POST /transcribe` (Whisper on the server) and reads the
questions aloud with `POST /speech` (Piper). Without server voice it falls back to the browser's
`SpeechRecognition` and `speechSynthesis`. The send button sends a spoken answer at any time.

UI texts in DE/FR/IT are in `src/i18n.ts`. The API contract is [`../docs/api.md`](../docs/api.md); its TypeScript
types are in `src/api/types.ts` (snake_case keys as in the backend).

## Develop

```bash
npm ci
npm run dev        # http://localhost:5173, backend expected on http://localhost:8000
npm run build      # type check + production build
npm run lint
```

| Variable | Default | Meaning |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000/api/v1` | Backend base URL |
| `VITE_USE_MOCK` | `false` | `true` uses the mock service (same interface, no backend needed) |
