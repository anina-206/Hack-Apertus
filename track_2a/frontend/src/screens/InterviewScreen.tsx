import { useEffect, useRef, useState } from "react";
import { api, PHASES, type Phase } from "../api";
import CardAccent from "../components/CardAccent";
import { ArrowRight, Check, ChevronLeft, Mic, Speaker } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import type { ChatMessage, SavedInterview } from "../history";
import { t, type UiTexts } from "../i18n";
import { canListen, canSpeak, speak, startListening, stopSpeaking } from "../speech";

type Props = {
  /** The interview to show: a new one, or a saved one that is continued or only read. */
  entry: SavedInterview;
  onRestart: () => void;
  /** Called when the interview is over and the candidate wants to see the feedback report. */
  onFinished: () => void;
};

export default function InterviewScreen({ entry, onRestart, onFinished }: Props) {
  const { language, summary } = entry;
  const text = t(language);

  const [messages, setMessages] = useState<ChatMessage[]>(entry.messages);
  const [questionId, setQuestionId] = useState<string | null>(entry.question_id);
  const [phase, setPhase] = useState<Phase>(entry.phase);
  const [done, setDone] = useState(entry.done);

  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(false);
  const [listening, setListening] = useState(false);
  const stopListeningRef = useRef<(() => void) | null>(null);

  // Always scroll to the newest message
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Stop voice features when leaving the screen
  useEffect(
    () => () => {
      stopListeningRef.current?.();
      stopSpeaking();
    },
    [],
  );

  async function send() {
    const answer = draft.trim();
    if (!answer || !questionId || sending) return;

    stopListeningRef.current?.();
    stopSpeaking();

    // Show the answer immediately, then wait for the interviewer
    setMessages((m) => [...m, { role: "candidate", text: answer }]);
    setDraft("");
    setSending(true);
    setError(false);

    try {
      const res = await api.sendAnswer(entry.session_id, questionId, answer);

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

  function toggleMic() {
    if (listening) {
      stopListeningRef.current?.();
      return;
    }
    const base = draft.trim();
    setListening(true);
    stopListeningRef.current = startListening(
      language,
      (spoken) => setDraft(base ? `${base} ${spoken}` : spoken),
      () => {
        setListening(false);
        stopListeningRef.current = null;
      },
    );
  }

  function handleEnd() {
    if (window.confirm(text.endConfirm)) {
      stopListeningRef.current?.();
      stopSpeaking();
      onRestart();
    }
  }

  const phaseIndex = PHASES.indexOf(phase);
  const lastInterviewerIndex = messages.findLastIndex((m) => m.role === "interviewer");

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
          <h1 className="flex-1 text-3xl font-bold tracking-tight">
            {text.title}
            <span className="text-logo-yellow">.</span>
          </h1>
          <button
            onClick={handleEnd}
            className="rounded-full border-2 border-white/80 px-4 py-1.5 text-sm font-bold hover:bg-white/10"
          >
            {text.end}
          </button>
        </div>
        <p className="mt-2 text-base text-white/90">{summary}</p>
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
            {text.phase} {phaseIndex + 1} {text.of} {PHASES.length}
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
            showName={i === 0}
            showReadAloud={canSpeak && i === lastInterviewerIndex && !sending}
            onReadAloud={() => speak(msg.text, language)}
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
          <p className="mt-2 text-center text-xs text-charcoal-soft">{text.inputHint}</p>
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

function Message({
  message,
  text,
  showName,
  showReadAloud,
  onReadAloud,
}: {
  message: ChatMessage;
  text: UiTexts;
  showName: boolean;
  showReadAloud: boolean;
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
      <Avatar initials={text.interviewerInitials} />
      <div className="min-w-0 max-w-[78%]">
        {showName && (
          <p className="mb-1 text-xs text-charcoal-soft">
            {text.interviewerName} · {text.interviewerRole}
          </p>
        )}
        <div className="rounded-2xl rounded-tl-md border border-line bg-white px-4 py-3 text-lg leading-snug whitespace-pre-wrap shadow-sm">
          {message.text}
        </div>
        {showReadAloud && (
          <button
            onClick={onReadAloud}
            className="mt-3 inline-flex items-center gap-1.5 rounded-full border-2 border-line bg-white px-3 py-1.5 text-sm font-bold text-brand hover:border-brand-light"
          >
            <Speaker />
            {text.readAloud}
          </button>
        )}
      </div>
    </div>
  );
}
