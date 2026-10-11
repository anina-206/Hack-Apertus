import { useEffect, useState } from "react";
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
import type { SavedInterview } from "./history";
import AuthScreen from "./screens/AuthScreen";
import FeedbackScreen from "./screens/FeedbackScreen";
import InterviewScreen from "./screens/InterviewScreen";
import SetupScreen from "./screens/SetupScreen";

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
    setEntry(saved);
    setScreen("interview");
  }

  /** "Practise this": same settings as the last interview, focused on the weakest criteria */
  async function handlePracticeAgain(focus: CriterionId[]) {
    if (!entry || !lastRequest) return;
    const request = { ...lastRequest, focus };  // same settings, including company and application
    handleStarted(await api.createSession(request), request, entry.summary);
  }

  function handleReportLoaded(report: Report) {
    setEntry((current) => (current ? { ...current, report } : current));
  }

  function handleRestart() {
    setEntry(null);
    setScreen("setup");
  }

  return (
    <div className="min-h-dvh">
      {screen === "setup" && (
        <SetupScreen
          language={language}
          onLanguageChange={setLanguage}
          onStarted={handleStarted}
          onOpenSaved={handleOpen}
          user={user}
          onLoginClick={() => setScreen("auth")}
          onLogout={handleLogout}
        />
      )}

      {screen === "auth" && (
        <AuthScreen
          language={language}
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
        <FeedbackScreen
          key={entry.session_id}
          sessionId={entry.session_id}
          language={entry.language}
          savedReport={entry.report}
          onReportLoaded={handleReportLoaded}
          onRestart={handleRestart}
          onPracticeAgain={lastRequest ? handlePracticeAgain : undefined}
        />
      )}
    </div>
  );
}
