import { useEffect, useRef, useState } from "react";
import { api, PHASES, type CreateSessionResponse, type LanguageCode, type Phase } from "../api";
import CallView, { type CallStatus } from "../components/CallView";
import CardAccent from "../components/CardAccent";
import { ArrowRight, Check, ChevronLeft, Headphones, Mic, Speaker, Stop } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import { t, type UiTexts } from "../i18n";
import { canListen, canSpeak } from "../speech";
import { useVoice } from "../useVoice";

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

  const voice = useVoice({
    language,
    voice: session.interviewer?.voice ?? "female",
    draft,
    setDraft,
    onSend: (answer) => send(answer),
    onRepeat: () => voice.say(lastInterviewerIndex, messages[lastInterviewerIndex].text, true),
  });

  // Always scroll to the newest message
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Hands-free: read each new interviewer message aloud (in training mode with the tip first),
  // then listen for the answer.
  const lastInterviewerIndex = messages.findLastIndex((m) => m.role === "interviewer");
  useEffect(() => {
    if (voice.handsFree && lastInterviewerIndex >= 0) voice.say(lastInterviewerIndex, spokenText(), !done);
    // Only when a new message arrives, not on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastInterviewerIndex]);

  /** The newest interviewer message as it is read aloud: the tip of the last answer, then the question. */
  function spokenText() {
    const question = messages[lastInterviewerIndex].text;
    const tip = messages[lastInterviewerIndex - 1]?.tip;
    return tip ? `${text.tip}: ${withFullStop(tip)} ${question}` : question;
  }

  async function send(answerText = draft) {
    const answer = answerText.trim();
    if (!answer || !questionId || sending) return;

    voice.stopAll();

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

  // In hands-free mode the call view is shown; "Chat" switches back to the messages.
  const [showCall, setShowCall] = useState(true);
  const callOpen = voice.handsFree && showCall && !done;

  function toggleHandsFree() {
    setShowCall(true);
    if (voice.toggleHandsFree() && !done) voice.say(lastInterviewerIndex, spokenText(), true);
  }

  const callStatus: CallStatus =
    voice.speakingKey !== null
      ? "speaking"
      : sending
        ? "thinking"
        : voice.countdown !== null
          ? "countdown"
          : voice.transcribing
            ? "transcribing"
            : voice.listening
              ? "listening"
              : voice.paused
                ? "paused"
                : "idle";

  function handleEnd() {
    if (window.confirm(text.endConfirm)) {
      voice.stopAll();
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
              onClick={toggleHandsFree}
              aria-pressed={voice.handsFree}
              aria-label={text.voiceMode}
              title={text.voiceMode}
              className={`flex h-10 w-10 items-center justify-center rounded-full border-2 transition ${
                voice.handsFree ? "border-logo-yellow bg-logo-yellow text-charcoal" : "border-white/80 hover:bg-white/10"
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

      {callOpen ? (
        <CallView
          text={text}
          interviewer={interviewer}
          status={callStatus}
          question={messages[lastInterviewerIndex]?.text ?? ""}
          tip={messages[lastInterviewerIndex - 1]?.tip}
          answer={draft}
          countdown={voice.countdown}
          realSpeaker={voice.server.tts}
          realMic={voice.server.stt}
          onSkip={voice.skipReading}
          onHold={voice.hold}
          onResume={voice.resume}
          onShowChat={() => setShowCall(false)}
        />
      ) : (
        <main className="flex-1 space-y-4 overflow-y-auto px-4 py-5">
          {voice.handsFree && !done && (
            <button
              onClick={() => setShowCall(true)}
              className="mx-auto flex items-center gap-2 rounded-full bg-brand-lighter px-4 py-2 text-sm font-bold text-brand"
            >
              <Headphones className="h-4 w-4" />
              {text.showCall}
            </button>
          )}
          {messages.map((msg, i) => (
            <Message
              key={i}
              message={msg}
              text={text}
              interviewer={interviewer}
              showName={i === 0}
              showReadAloud={canSpeak && i === lastInterviewerIndex && !sending}
              speaking={voice.speakingKey === i}
              onReadAloud={() => (voice.speakingKey === i ? voice.stopReading() : voice.say(i, msg.text))}
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
      )}

      {/* Input (in the call view the candidate speaks; "Chat" shows the input again) */}
      {!done && !callOpen && (
        <footer className="border-t border-line bg-white px-4 pt-3 pb-3">
          {error && <p className="mb-2 rounded-xl bg-danger-lighter px-3 py-2 text-sm text-danger">{text.error}</p>}
          {voice.micError && (
            <p className="mb-2 rounded-xl bg-danger-lighter px-3 py-2 text-sm text-danger">
              {voice.micError === "not-allowed" ? text.micDenied : text.micError}
            </p>
          )}
          {voice.handsFree && !sending && (
            <HandsFreeBar
              text={text}
              speaker={interviewer.name}
              speaking={voice.speakingKey !== null}
              listening={voice.listening}
              transcribing={voice.transcribing}
              countdown={voice.countdown}
              paused={voice.paused}
              onSkip={voice.skipReading}
              onHold={voice.hold}
            />
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
              // Typing in hands-free mode stops listening and auto-sending
              onFocus={voice.hold}
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
                onClick={voice.toggleMic}
                aria-label={text.voiceInput}
                aria-pressed={voice.listening}
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 transition ${
                  voice.listening ? "animate-pulse border-logo-red bg-logo-red text-white" : "border-line bg-white text-charcoal"
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
            {voice.listening && language === "gsw"
              ? text.mundartListening
              : voice.handsFree
                ? text.voiceModeHint
                : voice.listening
                  ? text.listeningHint
                  : text.inputHint}
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


/** "Gut gemacht" -> "Gut gemacht." so that reading aloud pauses before the question. */
function withFullStop(sentence: string) {
  return /[.!?…]$/.test(sentence.trim()) ? sentence.trim() : `${sentence.trim()}.`;
}

/** Hands-free status above the input: who speaks, listening, or the countdown before sending. */
function HandsFreeBar({
  text,
  speaker,
  speaking,
  listening,
  transcribing,
  countdown,
  paused,
  onSkip,
  onHold,
}: {
  text: UiTexts;
  speaker: string;
  speaking: boolean;
  listening: boolean;
  transcribing: boolean;
  countdown: number | null;
  paused: boolean;
  onSkip: () => void;
  onHold: () => void;
}) {
  const box = "mb-2 flex items-center gap-3 rounded-xl px-3 py-2 text-sm";
  const action = "shrink-0 rounded-full border-2 px-3 py-1 text-xs font-bold";

  if (speaking) {
    return (
      <div className={`${box} bg-brand-lighter text-brand`} role="status">
        <Speaker className="h-4 w-4 shrink-0" />
        <span className="flex-1">
          {speaker} {text.speakingNow}
        </span>
        <button type="button" onClick={onSkip} className={`${action} border-brand`}>
          {text.skip}
        </button>
      </div>
    );
  }
  if (countdown !== null) {
    return (
      <div className={`${box} relative overflow-hidden bg-mint-lighter text-mint-dark`} role="status">
        {/* Fills up during the pause; when full, the answer is sent */}
        <div className="absolute inset-y-0 left-0 bg-logo-teal/25" style={{ width: `${Math.round(countdown * 100)}%` }} />
        <ArrowRight className="relative h-4 w-4 shrink-0" />
        <span className="relative flex-1">{text.sendingSoon}</span>
        <button type="button" onClick={onHold} className={`${action} relative border-mint-dark`}>
          {text.wait}
        </button>
      </div>
    );
  }
  if (listening) {
    return (
      <div className={`${box} bg-danger-lighter text-logo-red`} role="status">
        <span className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-logo-red" />
        <span className="flex-1 text-charcoal">{text.listenNow}</span>
      </div>
    );
  }
  if (transcribing) {
    return (
      <div className={`${box} bg-brand-lighter text-brand`} role="status">
        <span className="h-2.5 w-2.5 shrink-0 animate-bounce rounded-full bg-brand" />
        <span className="flex-1">{text.transcribing}</span>
      </div>
    );
  }
  if (paused) {
    return (
      <div className={`${box} bg-page text-charcoal-soft`} role="status">
        <Mic className="h-4 w-4 shrink-0" />
        <span className="flex-1">{text.handsFreePaused}</span>
      </div>
    );
  }
  return null;
}
