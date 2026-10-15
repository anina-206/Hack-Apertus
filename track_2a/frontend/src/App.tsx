import { lazy, Suspense, useEffect, useState } from "react";
import {
  api,
  ApiError,
  type CreateSessionRequest,
  type CreateSessionResponse,
  type CriterionId,
  type LanguageCode,
  type Report,
  type User,
} from "./api";
import { clearLogin, getStoredUser } from "./auth";
import { locale } from "./i18n";
import type { SavedInterview } from "./history";
import AuthScreen from "./screens/AuthScreen";
import InterviewScreen from "./screens/InterviewScreen";
import SetupScreen from "./screens/SetupScreen";

// The feedback screen brings the chart library (recharts), about half of the app's code.
// It loads separately, so the first screen appears sooner; the interview fetches it in the background.
// Once fetched, the screen is used directly: a React.lazy component would still pause ~300 ms on first show.
let LoadedFeedback: typeof import("./screens/FeedbackScreen").default | null = null;
const loadFeedback = () =>
  import("./screens/FeedbackScreen").then((m) => {
    LoadedFeedback = m.default;
    return m;
  });
const LazyFeedback = lazy(loadFeedback);

type Screen = "setup" | "auth" | "interview" | "feedback";

export default function App() {
  const [screen, setScreen] = useState<Screen>("setup");
  const [language, setLanguage] = useState<LanguageCode>("de");
  // Logged-in user (null = not logged in). The token itself lives in auth.ts.
  const [user, setUser] = useState<User | null>(getStoredUser);
  // The interview that is open (new or saved)
  const [entry, setEntry] = useState<SavedInterview | null>(null);
  // Settings of the interview that was just started, for "practise this" (not known for opened old ones)
  const [lastRequest, setLastRequest] = useState<CreateSessionRequest | null>(null);
  // The report before "practise this", so the new feedback can show what got better
  const [previousReport, setPreviousReport] = useState<Report | null>(null);
  // The account screen opens on "create account" when a guest comes from the feedback
  const [authCreating, setAuthCreating] = useState(false);

  // Screen readers pronounce the page in this language (Mundart: Swiss German)
  useEffect(() => {
    document.documentElement.lang = locale(language);
  }, [language]);

  // While the candidate answers, get the feedback screen ready, so it opens without waiting
  useEffect(() => {
    if (screen === "interview") loadFeedback().catch(() => {});
  }, [screen]);

  // A stored login can be expired: ask the backend once and forget it if it says no
  useEffect(() => {
    if (!user) return;
    api.me().catch((err) => {
      if (err instanceof ApiError && err.code === "UNAUTHORIZED") {
        clearLogin();
        setUser(null);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleLogout() {
    try {
      await api.logout();
    } catch {
      // The token is dropped here in any case
    }
    clearLogin();
    setUser(null);
  }

  function handleStarted(session: CreateSessionResponse, request: CreateSessionRequest, summary: string) {
    setLanguage(request.language);
    setLastRequest(request);
    setEntry({
      session_id: session.session_id,
      language: request.language,
      summary,
      started_at: new Date().toISOString(),
      phase: session.phase,
      question_id: session.question.id,
      done: false,
      messages: [{ role: "interviewer", text: session.question.text }],
      company: session.company,
      interviewer: session.interviewer,
      progress: session.progress,
      application_summary: session.application_summary,
      application_failed: Boolean(request.application_text) && !session.application_summary,
    });
    setScreen("interview");
  }

  /** Opens a saved interview: finished ones start at the chat too, from there the report is one click away. */
  function handleOpen(saved: SavedInterview) {
    setLanguage(saved.language);
    setLastRequest(null);
    setPreviousReport(null);
    setEntry(saved);
    setScreen("interview");
  }

  /** "Practise this": same settings as the last interview, focused on the weakest criteria */
  async function handlePracticeAgain(focus: CriterionId[]) {
    if (!entry || !lastRequest) return;
    const request = { ...lastRequest, focus };  // same settings, including company and application
    const before = entry.report ?? null;
    handleStarted(await api.createSession(request), request, entry.summary);
    setPreviousReport(before);
  }

  function handleReportLoaded(report: Report) {
    setEntry((current) => (current ? { ...current, report } : current));
  }

  function handleRestart() {
    setEntry(null);
    setPreviousReport(null);
    setScreen("setup");
  }

  const FeedbackView = LoadedFeedback ?? LazyFeedback;

  return (
    <div className="min-h-dvh">
      {screen === "setup" && (
        <SetupScreen
          language={language}
          onLanguageChange={setLanguage}
          onStarted={handleStarted}
          onOpenSaved={handleOpen}
          user={user}
          onLoginClick={() => {
            setAuthCreating(false);
            setScreen("auth");
          }}
          onLogout={handleLogout}
        />
      )}

      {screen === "auth" && (
        <AuthScreen
          language={language}
          startCreating={authCreating}
          onLoggedIn={(u) => {
            setUser(u);
            setScreen("setup");
          }}
          onCancel={() => setScreen("setup")}
        />
      )}

      {screen === "interview" && entry && (
        <InterviewScreen
          key={entry.session_id}
          entry={entry}
          onRestart={handleRestart}
          onFinished={() => setScreen("feedback")}
        />
      )}

      {screen === "feedback" && entry && (
        <Suspense fallback={<div className="min-h-dvh bg-page" />}>
        <FeedbackView
          key={entry.session_id}
          sessionId={entry.session_id}
          language={entry.language}
          savedReport={entry.report}
          onReportLoaded={handleReportLoaded}
          onRestart={handleRestart}
          onPracticeAgain={lastRequest ? handlePracticeAgain : undefined}
          previousReport={previousReport ?? undefined}
          onCreateAccount={
            user
              ? undefined
              : () => {
                  setAuthCreating(true);
                  setScreen("auth");
                }
          }
        />
        </Suspense>
      )}
    </div>
  );
}
