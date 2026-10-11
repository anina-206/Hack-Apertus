import { useState } from "react";
import { api, type CreateSessionRequest, type CreateSessionResponse, type CriterionId, type LanguageCode } from "./api";
import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  type CreateSessionRequest,
  type CreateSessionResponse,
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
  const [session, setSession] = useState<CreateSessionResponse | null>(null);
  const [summary, setSummary] = useState("");
  const [lastRequest, setLastRequest] = useState<CreateSessionRequest | null>(null);
  // Logged-in user (null = guest). The token itself lives in auth.ts.
  const [user, setUser] = useState<User | null>(getStoredUser);
  // The interview that is open (new or saved)
  const [entry, setEntry] = useState<SavedInterview | null>(null);

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
    setSession(newSession);
    setSummary(newSummary);
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
    });
    setScreen("interview");
  }

  /** Opens a saved interview: finished ones start at the chat too, from there the report is one click away. */
  function handleOpen(saved: SavedInterview) {
    setLanguage(saved.language);
    setEntry(saved);
    setScreen("interview");
  }

  /** "Practise this": same settings as the last interview, focused on the weakest criteria */
  async function handlePracticeAgain(focus: CriterionId[]) {
    if (!lastRequest) return;
    const request = { ...lastRequest, focus };
    handleStarted(await api.createSession(request), request, summary);
  }

  function handleReportLoaded(report: Report) {
    if (!entry) return;
    setEntry({ ...entry, report });
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

      {screen === "feedback" && session && (
        <FeedbackScreen
          sessionId={session.session_id}
          language={language}
          onRestart={handleRestart}
          onPracticeAgain={handlePracticeAgain}
        />
      {screen === "feedback" && entry && (
        <FeedbackScreen
          sessionId={entry.session_id}
          language={entry.language}
          savedReport={entry.report}
          onReportLoaded={handleReportLoaded}
          onRestart={handleRestart}
        />
      )}
    </div>
  );
}
