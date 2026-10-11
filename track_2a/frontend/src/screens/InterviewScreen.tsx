import { useEffect, useRef, useState } from "react";
import { api, PHASES, type CreateSessionResponse, type LanguageCode, type Phase } from "../api";
import CardAccent from "../components/CardAccent";
import { ArrowRight, Check, ChevronLeft, Headphones, Mic, Speaker, Stop } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import { t, type UiTexts } from "../i18n";
import { canListen, canSpeak, speak, startListening, stopSpeaking, type ListenError } from "../speech";

type Props = {
  session: CreateSessionResponse;
  language: LanguageCode;
  /** Line under the title, e.g. "Schreiner/in EFZ · Deutsch · Training" */
  summary: string;
  onRestart: () => void;
  /** Called when the interview is over and the candidate wants to see the feedback report. */
  onFinished: () => void;
};

/** One bubble in the chat. `tip` is the short feedback after an answer (training mode). */
type ChatMessage = {
  role: "interviewer" | "candidate";
  text: string;
  tip?: string;
};

export default function InterviewScreen({ session, language, summary, onRestart, onFinished }: Props) {
  const text = t(language);

  // The posting's interviewer (real backend) or the default persona from the UI texts (mock)
  const interviewer: Interviewer = session.interviewer
    ? { ...session.interviewer, initials: initialsOf(session.interviewer.name) }
    : { name: text.interviewerName, role: text.interviewerRole, initials: text.interviewerInitials };

  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "interviewer", text: session.question.text },
  ]);
  const [questionId, setQuestionId] = useState<string | null>(session.question.id);
  const [phase, setPhase] = useState<Phase>(session.phase);
  const [progress, setProgress] = useState(session.progress);
  const [done, setDone] = useState(false);

  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(false);
  const [listening, setListening] = useState(false);
  const [micError, setMicError] = useState<ListenError>(null);
  const stopListeningRef = useRef<(() => void) | null>(null);
  const draftRef = useRef(draft);
  draftRef.current = draft;

  // Voice mode: every new question is read aloud, then the microphone starts by itself.
  const [voiceMode, setVoiceMode] = useState(() => canSpeak && loadVoiceMode());
  // Index of the message that is being read aloud right now, or null
  const [speakingIndex, setSpeakingIndex] = useState<number | null>(null);
  // Counts readings. Stopping speech also calls its "finished" callback, so the callback only
  // acts if its reading is still the current one.
  const readingRef = useRef(0);

  // Always scroll to the newest message
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Stop voice features when leaving the screen
  useEffect(
    () => () => {
      readingRef.current++;
      stopListeningRef.current?.();
      stopSpeaking();
    },
    [],
  );

  // In voice mode, read each new interviewer message aloud (also the first question).
  const lastInterviewerIndex = messages.findLastIndex((m) => m.role === "interviewer");
  useEffect(() => {
    if (voiceMode && lastInterviewerIndex >= 0) readAloud(lastInterviewerIndex, !done);
    // Only when a new question arrives, not when voice mode is switched on
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastInterviewerIndex]);

  async function send() {
    const answer = draft.trim();
    if (!answer || !questionId || sending) return;

    stopListeningRef.current?.();
    stopReading();

    // Show the answer immediately, then wait for the interviewer
    setMessages((m) => [...m, { role: "candidate", text: answer }]);
    setDraft("");
    setSending(true);
    setError(false);

    try {
      const res = await api.sendAnswer(session.session_id, questionId, answer);

      setMessages((m) => {
        const updated = [...m];
        // Attach the tip to the answer the candidate just gave
        if (res.turn_feedback) {
          updated[updated.length - 1] = { ...updated[updated.length - 1], tip: res.turn_feedback.short_tip };
        }
        const next = res.done ? res.closing_message : res.question?.text;
        if (next) updated.push({ role: "interviewer", text: next });
        return updated;
      });
      setPhase(res.phase);
      setProgress(res.progress);
      setQuestionId(res.question?.id ?? null);
      setDone(res.done);
    } catch {
      // Put the answer back into the input field so nothing is lost
      setMessages((m) => m.slice(0, -1));
      setDraft(answer);
      setError(true);
    } finally {
      setSending(false);
    }
  }

  function startMic() {
    if (!canListen || stopListeningRef.current) return;
    stopReading();
    // Dictated text is added to what is already in the input field
    const base = draftRef.current.trim();
    setListening(true);
    setMicError(null);
    stopListeningRef.current = startListening(
      language,
      (spoken) => setDraft(base ? `${base} ${spoken}` : spoken),
      (problem) => {
        setListening(false);
        setMicError(problem);
        stopListeningRef.current = null;
      },
    );
  }

  function toggleMic() {
    if (listening) stopListeningRef.current?.();
    else startMic();
  }

  /** Reads message `index` aloud. With `thenListen`, the microphone starts when reading is done. */
  function readAloud(index: number, thenListen = false) {
    stopListeningRef.current?.();
    const reading = ++readingRef.current;
    setSpeakingIndex(index);
    speak(messages[index]?.text ?? "", language, () => {
      if (readingRef.current !== reading) return; // stopped or replaced by a newer reading
      setSpeakingIndex(null);
      if (thenListen) startMic();
    });
  }

  function stopReading() {
    readingRef.current++;
    setSpeakingIndex(null);
    stopSpeaking();
  }

  function toggleVoiceMode() {
    const on = !voiceMode;
    setVoiceMode(on);
    saveVoiceMode(on);
    if (on && lastInterviewerIndex >= 0 && !done) readAloud(lastInterviewerIndex, true);
    if (!on) {
      stopReading();
      stopListeningRef.current?.();
    }
  }

  function handleEnd() {
    if (window.confirm(text.endConfirm)) {
      stopListeningRef.current?.();
      stopReading();
      onRestart();
    }
  }

  const phaseIndex = PHASES.indexOf(phase);
  // The question count only moves in the four scored phases (see docs/api.md)
  const showQuestionCount = phaseIndex < 4 && progress.total > 0;

  return (
    <div className="mx-auto flex h-dvh w-full max-w-lg flex-col bg-page">
      {/* Blue header */}
      <header className="bg-brand px-4 pt-5 pb-12 text-white">
        <div className="flex items-center gap-2">
          <button
            onClick={handleEnd}
            aria-label={text.back}
            className="-ml-2 flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10"
          >
            <ChevronLeft />
          </button>
          <h1 className="min-w-0 flex-1 text-2xl font-bold tracking-tight whitespace-nowrap sm:text-3xl">
            {text.title}
            <span className="text-logo-yellow">.</span>
          </h1>
          {canSpeak && (
            <button
              onClick={toggleVoiceMode}
              aria-pressed={voiceMode}
              aria-label={text.voiceMode}
              title={text.voiceMode}
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition ${
                voiceMode ? "border-logo-yellow bg-logo-yellow text-charcoal" : "border-white/80 hover:bg-white/10"
              }`}
            >
              <Headphones />
            </button>
          )}
          <button
            onClick={handleEnd}
            className="rounded-full border-2 border-white/80 px-4 py-1.5 text-sm font-bold hover:bg-white/10"
          >
            {text.end}
          </button>
        </div>
        <p className="mt-2 text-base text-white/90">
          {session.company ? `${summary} · ${session.company.name}` : summary}
        </p>
      </header>

      {/* Phase card: number, name and a segment per phase */}
      <div className="relative z-10 -mt-8 overflow-hidden rounded-2xl bg-white px-4 pt-5 pb-4 shadow-card mx-4">
        <CardAccent />
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 -rotate-6 items-center justify-center rounded-lg bg-logo-yellow font-bold">
            {phaseIndex + 1}
          </span>
          <span className="flex-1 text-xl font-bold">{text.phases[phase]}</span>
          <span className="text-sm text-charcoal-soft">
            {showQuestionCount
              ? `${text.question} ${progress.current} ${text.of} ${progress.total}`
              : `${text.phase} ${phaseIndex + 1} ${text.of} ${PHASES.length}`}
          </span>
        </div>
        <div className="mt-3 flex gap-1.5" aria-hidden="true">
          {PHASES.map((p, i) => (
            <div
              key={p}
              className={`h-2 flex-1 rounded-full ${
                i < phaseIndex || done ? "bg-logo-teal" : i === phaseIndex ? "bg-brand" : "bg-line"
              }`}
            />
          ))}
        </div>
      </div>

      {/* Messages */}
      <main className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
        {messages.map((msg, i) => (
          <Message
            key={i}
            message={msg}
            text={text}
            interviewer={interviewer}
            showName={i === 0}
            showReadAloud={canSpeak && i === lastInterviewerIndex && !sending}
            speaking={speakingIndex === i}
            onReadAloud={() => (speakingIndex === i ? stopReading() : readAloud(i))}
          />
        ))}

        {sending && (
          <div className="ml-12 flex w-fit items-center gap-1.5 rounded-full bg-white px-4 py-3 shadow-card" aria-label={text.thinking}>
            <Dot color="bg-logo-red" delay="0ms" />
            <Dot color="bg-logo-yellow" delay="150ms" />
            <Dot color="bg-logo-blue" delay="300ms" />
          </div>
        )}

        {done && (
          <div className="rounded-2xl bg-white p-6 text-center shadow-card">
            <p className="mb-4 text-xl font-bold">{text.finished}</p>
            <PrimaryButton onClick={onFinished}>{text.showFeedback}</PrimaryButton>
            <button onClick={onRestart} className="mt-4 block w-full text-sm font-bold text-brand">
              {text.newInterview}
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* Input */}
      {!done && (
        <footer className="border-t border-line bg-white px-4 pt-3 pb-3">
          {error && <p className="mb-2 rounded-xl bg-danger-lighter px-3 py-2 text-sm text-danger">{text.error}</p>}
          {micError && (
            <p className="mb-2 rounded-xl bg-danger-lighter px-3 py-2 text-sm text-danger">
              {micError === "not-allowed" ? text.micDenied : text.micError}
            </p>
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
            className="flex items-end gap-2"
          >
            <textarea
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                // Enter sends, Shift+Enter makes a new line
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
              placeholder={text.answerPlaceholder}
              rows={1}
              className="field-sizing-content max-h-32 min-h-12 flex-1 resize-none rounded-3xl border-2 border-line bg-white px-5 py-2.5 text-base placeholder:text-charcoal/40 focus:border-brand focus:outline-none"
            />
            {canListen && (
              <button
                type="button"
                onClick={toggleMic}
                aria-label={text.voiceInput}
                aria-pressed={listening}
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 transition ${
                  listening ? "animate-pulse border-logo-red bg-logo-red text-white" : "border-line bg-white text-charcoal"
                }`}
              >
                <Mic />
              </button>
            )}
            <button
              type="submit"
              disabled={!draft.trim() || sending}
              aria-label={text.send}
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand text-white shadow-button transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:bg-line disabled:shadow-none"
            >
              <ArrowRight />
            </button>
          </form>
          <p className="mt-2 text-center text-xs text-charcoal-soft">
            {listening ? (language === "gsw" ? text.mundartListening : text.listeningHint) : voiceMode ? text.voiceModeHint : text.inputHint}
          </p>
        </footer>
      )}
    </div>
  );
}

function Dot({ color, delay }: { color: string; delay: string }) {
  return <span className={`h-2 w-2 animate-bounce rounded-full ${color}`} style={{ animationDelay: delay }} />;
}

/** The interviewer's avatar: a small tilted red square with initials. */
function Avatar({ initials }: { initials: string }) {
  return (
    <div
      className="flex h-9 w-9 shrink-0 -rotate-6 items-center justify-center rounded-lg bg-logo-red text-sm font-bold text-white"
      aria-hidden="true"
    >
      {initials}
    </div>
  );
}

type Interviewer = { name: string; role: string; initials: string };

/** "Stefan Keller" -> "SK" */
function initialsOf(name: string) {
  return name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function Message({
  message,
  text,
  interviewer,
  showName,
  showReadAloud,
  speaking,
  onReadAloud,
}: {
  message: ChatMessage;
  text: UiTexts;
  interviewer: Interviewer;
  showName: boolean;
  showReadAloud: boolean;
  speaking: boolean;
  onReadAloud: () => void;
}) {
  if (message.role === "candidate") {
    return (
      <div className="space-y-3">
        <div className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-br-md bg-brand px-4 py-3 text-lg leading-snug whitespace-pre-wrap text-white">
          {message.text}
        </div>
        {message.tip && (
          <div className="ml-8 rounded-xl bg-mint-lighter px-4 py-3 text-sm text-mint-dark">
            <p className="mb-1 flex items-center gap-2 font-bold">
              <span className="flex h-5 w-5 items-center justify-center rounded-md bg-logo-teal text-white">
                <Check className="h-3.5 w-3.5" />
              </span>
              {text.feedbackTitle}
            </p>
            <p>
              <span className="font-bold">{text.tip}:</span> {message.tip}
            </p>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex items-start gap-3">
      <Avatar initials={interviewer.initials} />
      <div className="min-w-0 max-w-[78%]">
        {showName && (
          <p className="mb-1 text-xs text-charcoal-soft">
            {interviewer.name} · {interviewer.role}
          </p>
        )}
        <div className="rounded-2xl rounded-tl-md border border-line bg-white px-4 py-3 text-lg leading-snug whitespace-pre-wrap shadow-sm">
          {message.text}
        </div>
        {(showReadAloud || speaking) && (
          <button
            onClick={onReadAloud}
            className="mt-3 inline-flex items-center gap-1.5 rounded-full border-2 border-line bg-white px-3 py-1.5 text-sm font-bold text-brand hover:border-brand-light"
          >
            {speaking ? <Stop /> : <Speaker />}
            {speaking ? text.stopReading : text.readAloud}
          </button>
        )}
      </div>
    </div>
  );
}

// The voice-mode switch is remembered in this browser. Storage can be blocked, so both are guarded.
const VOICE_MODE_KEY = "coach.voiceMode";

function loadVoiceMode() {
  try {
    return localStorage.getItem(VOICE_MODE_KEY) === "on";
  } catch {
    return false;
  }
}

function saveVoiceMode(on: boolean) {
  try {
    localStorage.setItem(VOICE_MODE_KEY, on ? "on" : "off");
  } catch {
    // not saved, the switch still works for this interview
  }
}
