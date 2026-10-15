import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError, PHASES, type Interviewer, type Phase } from "../api";
import Alert from "../components/Alert";
import Card from "../components/Card";
import CallView, { type CallStatus } from "../components/CallView";
import CardAccent from "../components/CardAccent";
import Face from "../components/Face";
import { ArrowRight, Check, Headphones, Lightbulb, Mic, Speaker, Stop } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import TextButton from "../components/TextButton";
import type { ChatMessage, SavedInterview } from "../history";
import { t, type UiTexts } from "../i18n";
import { errorText, isSessionGone } from "../errors";
import { canListen, canSpeak } from "../speech";
import { useFocusHeading } from "../useFocusHeading";
import { useVoice } from "../useVoice";

/** The backend takes answers up to 4000 characters (docs/api.md). */
const MAX_ANSWER = 4000;
/** From here on, a counter under the input shows how much is left. */
const SHOW_COUNT_FROM = 3000;

type Props = {
  /** The interview to show: a new one, or a saved one that is continued or only read. */
  entry: SavedInterview;
  onRestart: () => void;
  /** Called when the interview is over and the candidate wants to see the feedback report. */
  onFinished: () => void;
  /** No account: nothing is saved, so "Pausieren" becomes an honest "Beenden" */
  guest?: boolean;
};

export default function InterviewScreen({ entry, onRestart, onFinished, guest = false }: Props) {
  const { language, summary } = entry;
  const text = t(language);
  const headingRef = useFocusHeading<HTMLHeadingElement>();

  // The posting's interviewer (real backend) or the default persona from the UI texts (mock)
  const interviewer: Interviewer = entry.interviewer ?? { name: text.interviewerName, role: text.interviewerRole };

  const [messages, setMessages] = useState<ChatMessage[]>(entry.messages);
  // Messages that were already there when the screen opened appear at once; only new ones slide in
  const [firstNew] = useState(entry.messages.length > 1 ? entry.messages.length : 0);
  const [questionId, setQuestionId] = useState<string | null>(entry.question_id);
  const [phase, setPhase] = useState<Phase>(entry.phase);
  // Saved interviews do not keep the question count; it shows again after the next answer
  const [progress, setProgress] = useState(entry.progress ?? { current: 0, total: 0 });
  const [done, setDone] = useState(entry.done);

  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  // Guards against a double send (two quick Enters) before `sending` is rendered
  const sendingRef = useRef(false);
  /** Why the last answer could not be sent, or null */
  const [error, setError] = useState<string | null>(null);
  /** The server forgot this interview (e.g. after a restart): only a new interview helps */
  const [gone, setGone] = useState(false);
  // First interview ever: a short "how it works" card above the first question, shown once
  const [showIntro, setShowIntro] = useState(() => entry.messages.length <= 1 && !entry.done && !introSeen());
  function dismissIntro() {
    setShowIntro(false);
    markIntroSeen();
  }

  const voice = useVoice({
    language,
    sessionId: entry.session_id,
    voice: entry.interviewer?.voice ?? "female",
    draft,
    setDraft,
    onSend: (answer) => send(answer),
    // Only hands-free listens again after reading; in text mode the candidate taps the microphone
    onRepeat: () => voice.say(lastInterviewerIndex, messages[lastInterviewerIndex].text, voice.handsFree),
  });

  // Always scroll to the newest message
  const bottomRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Hands-free: read each new interviewer message aloud, then listen for the answer.
  // The tip is only shown, not read: it interrupted the conversation.
  const lastInterviewerIndex = messages.findLastIndex((m) => m.role === "interviewer");
  useEffect(() => {
    if (voice.handsFree && lastInterviewerIndex >= 0) voice.say(lastInterviewerIndex, messages[lastInterviewerIndex].text, !done);
    // Only when a new message arrives, not on every render
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lastInterviewerIndex]);

  async function send(answerText = draft) {
    const answer = answerText.trim().slice(0, MAX_ANSWER);
    if (!answer || !questionId || sendingRef.current) return;
    sendingRef.current = true;

    voice.stopAll();
    if (showIntro) dismissIntro(); // the first answer shows it was understood

    // Show the answer immediately, then wait for the interviewer
    setMessages((m) => [...m, { role: "candidate", text: answer }]);
    setDraft("");
    setSending(true);
    setError(null);

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
      setProgress(res.progress);
      setQuestionId(res.question?.id ?? null);
      setDone(res.done);
    } catch (err) {
      // The answer did arrive earlier (e.g. the first try timed out, but the server got it):
      // load the interview as the server has it and go on from there
      if (err instanceof ApiError && (err.code === "WRONG_QUESTION" || err.code === "INTERVIEW_FINISHED")) {
        if (await catchUp()) return;
      }
      // Put the answer back into the input field so nothing is lost
      setMessages((m) => m.slice(0, -1));
      setDraft(answer);
      setError(errorText(err, text));
      setGone(isSessionGone(err));
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  // While the microphone listens or Whisper writes, "Senden" sends the spoken answer right away
  const voiceBusy = voice.listening || voice.transcribing || voice.countdown !== null;

  function submit() {
    if (voiceBusy) voice.sendNow();
    else send();
  }

  /** Takes over the server's state of this interview. Tips already shown are kept. Returns false if it fails. */
  async function catchUp() {
    try {
      const state = await api.getSession(entry.session_id);
      setMessages((old) =>
        state.history.map((h, i) =>
          h.role === "candidate"
            ? { role: "candidate", text: h.text, tip: old[i]?.text === h.text ? old[i].tip : undefined }
            : { role: "interviewer", text: h.text },
        ),
      );
      setPhase(state.phase);
      setProgress(state.progress);
      setQuestionId(state.current_question_id);
      setDone(state.done);
      return true;
    } catch {
      return false;
    }
  }

  // In hands-free mode the call view is shown; "Chat" switches back to the messages.
  const [showCall, setShowCall] = useState(true);
  const callOpen = voice.handsFree && showCall && !done;

  function toggleHandsFree() {
    setShowCall(true);
    if (voice.toggleHandsFree() && !done) voice.say(lastInterviewerIndex, messages[lastInterviewerIndex].text, true);
  }

  /** From the intro card: switch to hands-free and close the card */
  function startHandsFree() {
    dismissIntro();
    if (!voice.handsFree) toggleHandsFree();
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

  // "Pausieren" asks first, in a small sheet at the bottom (thumb reach) instead of window.confirm
  const [confirmEnd, setConfirmEnd] = useState(false);

  function handleEnd() {
    voice.hold();
    setConfirmEnd(true);
  }

  const closeEndSheet = useCallback(() => setConfirmEnd(false), []);

  function endNow() {
    voice.stopAll();
    onRestart();
  }

  // The microphone message for the current problem, shown in the chat and in the call view
  const micMessage =
    voice.micError === "not-allowed"
      ? text.micDenied
      : voice.micError === "nothing"
        ? text.micNothing
        : voice.micError
          ? text.micError
          : null;

  const phaseIndex = PHASES.indexOf(phase);
  // The question count only moves in the four scored phases (see docs/api.md)
  const showQuestionCount = phaseIndex < 4 && progress.total > 0;

  return (
    <div className="flex h-dvh flex-col bg-page">
      {/* Blue header, across the whole width */}
      <header className="bg-brand px-4 pt-safe-5 pb-12 text-white short:pt-3 short:pb-10">
        <div className="mx-auto max-w-lg lg:max-w-5xl lg:px-2">
        {/* No back arrow here: leaving the interview is one clear button, "Beenden" */}
        <div className="flex items-center gap-2">
          <h1
            ref={headingRef}
            tabIndex={-1}
            className="min-w-0 flex-1 truncate text-2xl font-bold tracking-tight outline-none sm:text-3xl"
          >
            {text.title}
            <span className="text-logo-yellow">.</span>
          </h1>
          {/* After the last question there is nothing to pause or hear: the "Geschafft!" card leads on */}
          {canSpeak && !done && (
            <button
              onClick={toggleHandsFree}
              aria-pressed={voice.handsFree}
              aria-label={text.voiceMode}
              title={text.voiceMode}
              // Phones: icon only (the intro card offers it with words). Wider screens: icon and word.
              className={`flex h-11 min-w-11 shrink-0 items-center justify-center gap-2 rounded-full border-2 text-sm font-bold transition sm:px-4 ${
                voice.handsFree ? "border-logo-yellow bg-logo-yellow text-charcoal" : "border-white/80 hover:bg-brand-dark"
              }`}
            >
              <Headphones />
              <span className="hidden sm:inline" aria-hidden="true">{text.handsFreeShort}</span>
            </button>
          )}
          {!done && (
            <button
              onClick={handleEnd}
              className="min-h-11 shrink-0 rounded-full border-2 border-white/80 px-4 text-sm font-bold hover:bg-brand-dark"
            >
              {guest ? text.endGuest : text.end}
            </button>
          )}
        </div>
        <p className="mt-2 text-base text-white short:hidden">
          {entry.company ? `${summary} · ${entry.company.name}` : summary}
        </p>
        </div>
      </header>

      {/* Phones: phase card on top, chat below. Wide screens: phase list on the left, chat on the right. */}
      <div className="mx-auto flex min-h-0 w-full max-w-lg flex-1 flex-col lg:grid lg:max-w-5xl lg:grid-cols-[15rem_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] lg:gap-8 lg:px-6">

      {/* Phase card: number, name and a segment per phase */}
      <section aria-label={text.phase} className="relative z-10 mx-4 -mt-8 overflow-hidden rounded-2xl bg-white px-4 pt-5 pb-4 shadow-card short:pt-3 short:pb-3 lg:hidden">
        <CardAccent />
        <div className="flex items-center gap-3">
          {/* key: a new phase mounts a new card, which lands like a stamp */}
          <span
            key={phaseIndex}
            className="flex h-8 w-8 -rotate-6 animate-stamp items-center justify-center rounded-lg bg-logo-yellow font-bold"
          >
            {phaseIndex + 1}
          </span>
          <span className="flex-1 text-xl font-bold">{text.phases[phase]}</span>
          <span className="text-sm text-charcoal-soft tabular-nums">
            {showQuestionCount
              ? `${text.question} ${progress.current} ${text.of} ${progress.total}`
              : `${text.phase} ${phaseIndex + 1} ${text.of} ${PHASES.length}`}
          </span>
        </div>
        <div className="mt-3 flex gap-1.5 short:hidden" aria-hidden="true">
          {PHASES.map((p, i) => (
            <div
              key={p}
              className={`h-2 flex-1 rounded-full transition-colors duration-500 ${
                i < phaseIndex || done ? "bg-logo-teal" : i === phaseIndex ? "bg-brand" : "bg-line"
              }`}
            />
          ))}
        </div>
      </section>

      <PhaseRail text={text} phaseIndex={phaseIndex} done={done} />

      {/* Screen readers hear when a new phase starts (the cards above only show it) */}
      <p className="sr-only" aria-live="polite">
        {`${text.phase} ${phaseIndex + 1} ${text.of} ${PHASES.length}: ${text.phases[phase]}`}
      </p>

      {/* The chat (or call view) with its input: the page's main content */}
      <main className="flex min-h-0 flex-1 flex-col">
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
          error={error ?? micMessage}
          onSkip={voice.skipReading}
          onHold={voice.hold}
          onResume={voice.resume}
          onShowChat={() => setShowCall(false)}
          onSend={voice.sendNow}
        />
      ) : (
        // role="log": a screen reader announces each new message
        <div className="flex-1 space-y-4 overflow-y-auto px-4 py-5" role="log" aria-live="polite" aria-relevant="additions">
          {voice.handsFree && !done && (
            <div className="flex flex-wrap justify-center gap-2">
              <button
                onClick={() => setShowCall(true)}
                className="flex min-h-10 items-center gap-2 rounded-full bg-brand-lighter px-4 py-2 text-sm font-bold text-brand"
              >
                <Headphones className="h-4 w-4" />
                {text.showCall}
              </button>
              {/* Leaves the voice mode: stops reading and listening, the chat stays */}
              <button
                onClick={toggleHandsFree}
                className="min-h-10 rounded-full border-2 border-line bg-white px-4 py-2 text-sm font-bold text-charcoal hover:border-brand-light"
              >
                {text.voiceModeOff}
              </button>
            </div>
          )}
          {entry.application_summary && (
            <details className="rounded-2xl bg-white px-4 py-3 text-sm shadow-card">
              <summary className="cursor-pointer font-bold text-brand">{text.applicationCardTitle}</summary>
              <p className="mt-2 whitespace-pre-wrap text-charcoal-soft">{entry.application_summary}</p>
            </details>
          )}
          {entry.application_failed && (
            <Alert>{text.applicationFailed}</Alert>
          )}

          {showIntro && (
            <Card step={0} labelledBy="intro-title">
              <h2 id="intro-title" className="text-lg font-bold">{text.introTitle}</h2>
              <ol className="mt-3 space-y-2.5">
                {text.introPoints.map((point, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="flex h-6 w-6 shrink-0 -rotate-6 items-center justify-center rounded-md bg-logo-yellow text-sm font-bold">
                      {i + 1}
                    </span>
                    {point.replace("{name}", interviewer.name)}
                  </li>
                ))}
              </ol>
              {/* Hands-free is the closest to a real interview: offer it here in words, not only as a header icon */}
              {canSpeak && !voice.handsFree && (
                <p className="mt-4 rounded-xl bg-page px-4 py-3 text-sm">
                  {text.handsFreeOffer.replace("{name}", interviewer.name)}
                </p>
              )}
              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  onClick={dismissIntro}
                  className="min-h-11 rounded-full bg-brand-lighter px-5 font-bold text-brand-dark transition hover:bg-brand-light active:scale-[0.97]"
                >
                  {text.introOk}
                </button>
                {canSpeak && !voice.handsFree && (
                  <button
                    onClick={startHandsFree}
                    className="flex min-h-11 items-center gap-2 rounded-full border-2 border-brand px-5 font-bold text-brand-dark transition hover:bg-brand-lighter active:scale-[0.97]"
                  >
                    <Headphones className="h-5 w-5" />
                    {text.handsFreeStart}
                  </button>
                )}
              </div>
            </Card>
          )}

          {messages.map((msg, i) => (
            <Message
              key={i}
              message={msg}
              animate={i >= firstNew}
              text={text}
              interviewer={interviewer}
              showReadAloud={canSpeak && i === lastInterviewerIndex && !sending}
              speaking={voice.speakingKey === i}
              onReadAloud={() => (voice.speakingKey === i ? voice.stopReading() : voice.say(i, msg.text))}
            />
          ))}

          {sending && (
            <div className="ml-13 flex w-fit animate-msg-left items-center gap-1.5 rounded-full bg-white px-4 py-3 shadow-card" role="status">
              <span className="sr-only">{text.thinking.replace("{name}", interviewer.name)}</span>
              <Dot color="bg-logo-red" delay="0ms" />
              <Dot color="bg-logo-yellow" delay="150ms" />
              <Dot color="bg-logo-blue" delay="300ms" />
            </div>
          )}

          {done && (
            <div className="animate-rise-in rounded-2xl bg-white p-6 text-center shadow-card">
              {/* The four Profolio cards land one after the other: the interview is done */}
              <LogoFan />
              <p className="mt-5 text-2xl font-bold">{text.finished}</p>
              <p className="mx-auto mt-1 mb-5 max-w-xs text-charcoal-soft">
                {text.finishedCount.replace("{count}", String(messages.filter((m) => m.role === "candidate").length))}
              </p>
              <PrimaryButton onClick={onFinished}>{text.showFeedback}</PrimaryButton>
              <TextButton onClick={onRestart} className="mx-auto mt-3 block">
                {text.newInterview}
              </TextButton>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      )}

      {/* Input (in the call view the candidate speaks; "Chat" shows the input again) */}
      {!done && !callOpen && (
        <footer className="border-t border-line bg-white px-4 pt-3 pb-safe-3 lg:rounded-t-2xl lg:border-x">
          {error && (
            <Alert className="mb-2">
              <p>{error}</p>
              {gone && (
                <TextButton onClick={onRestart} tone="inherit" className="mt-1 -ml-2">
                  {text.newInterview}
                </TextButton>
              )}
            </Alert>
          )}
          {micMessage && (
            <Alert className="mb-2" onClose={voice.dismissMicError} closeLabel={text.close}>
              {micMessage}
            </Alert>
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
              onSend={voice.sendNow}
            />
          )}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
            className="flex items-end gap-2"
          >
            <textarea
              value={draft}
              onChange={(e) => {
                setDraft(e.target.value);
                if (voice.micError) voice.dismissMicError(); // typing instead: the microphone message goes away
              }}
              // Typing in hands-free mode stops listening and auto-sending
              onFocus={voice.hold}
              onKeyDown={(e) => {
                // Enter sends, Shift+Enter makes a new line
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
              placeholder={text.answerPlaceholder}
              aria-label={text.answerPlaceholder}
              maxLength={MAX_ANSWER}
              rows={1}
              className="field-sizing-content max-h-32 min-h-12 flex-1 resize-none rounded-3xl border-2 border-line bg-white px-5 py-2.5 text-base placeholder:text-charcoal/40 focus:border-brand focus:ring-4 focus:ring-brand/20 focus:outline-none"
            />
            {canListen && (
              <button
                type="button"
                onClick={voice.toggleMic}
                aria-label={text.voiceInput}
                aria-pressed={voice.listening}
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full border-2 transition active:scale-90 ${
                  voice.listening ? "animate-pulse border-logo-red bg-logo-red text-white" : "border-line bg-white text-charcoal"
                }`}
              >
                <Mic />
              </button>
            )}
            <button
              type="submit"
              disabled={!(draft.trim() || voiceBusy) || sending}
              aria-label={text.send}
              className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand text-white shadow-button transition hover:bg-brand-dark active:scale-90 disabled:active:scale-100 disabled:cursor-not-allowed disabled:bg-line disabled:shadow-none"
            >
              <ArrowRight />
            </button>
          </form>
          <p className="mt-2 text-center text-sm text-charcoal-soft tabular-nums">
            {draft.length >= SHOW_COUNT_FROM
              ? text.answerLimit.replace("{count}", String(draft.length)).replace("{max}", String(MAX_ANSWER))
              : voice.listening && language === "gsw"
                ? text.mundartListening
                : voice.handsFree
                  ? text.voiceModeHint
                  : voice.listening
                    ? text.listeningHint
                    : text.inputHint}
          </p>
        </footer>
      )}
      </main>
      </div>

      {confirmEnd && <EndSheet text={text} guest={guest} onStay={closeEndSheet} onEnd={endNow} />}
    </div>
  );
}

/**
 * Bottom sheet: pause the interview (it stays saved) or keep practising. Esc or a tap outside keeps practising.
 * Guests have no saved interviews: for them it says plainly that ending loses this interview.
 */
function EndSheet({ text, guest, onStay, onEnd }: { text: UiTexts; guest: boolean; onStay: () => void; onEnd: () => void }) {
  const stayRef = useRef<HTMLButtonElement>(null);
  const endRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    stayRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onStay();
      // The sheet is modal: Tab and Shift+Tab go back and forth between its two buttons
      if (e.key === "Tab") {
        e.preventDefault();
        (document.activeElement === stayRef.current ? endRef : stayRef).current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onStay]);

  return (
    <div className="fixed inset-0 z-40 flex animate-fade-in items-end justify-center bg-charcoal/40" onClick={onStay}>
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="end-sheet-text"
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-lg animate-sheet-up rounded-t-3xl bg-white px-5 pt-6 pb-safe-6 shadow-card"
      >
        <p id="end-sheet-text" className="text-lg leading-snug">
          {guest ? text.endGuestConfirm : text.endConfirm}
        </p>
        <div className="mt-5 flex flex-col gap-3">
          <button
            ref={stayRef}
            onClick={onStay}
            className="min-h-12 rounded-full bg-brand px-5 text-lg font-bold text-white shadow-button transition hover:bg-brand-dark active:scale-[0.97]"
          >
            {text.endConfirmNo}
          </button>
          <button
            ref={endRef}
            onClick={onEnd}
            className="min-h-12 rounded-full border-2 border-line px-5 font-bold text-charcoal transition hover:border-brand-light active:scale-[0.97]"
          >
            {guest ? text.endGuest : text.endConfirmYes}
          </button>
        </div>
      </div>
    </div>
  );
}

/** Wide screens: all six phases as a list, the current one highlighted. Sits on the header like the phone's phase card. */
function PhaseRail({ text, phaseIndex, done }: { text: UiTexts; phaseIndex: number; done: boolean }) {
  return (
    <nav aria-label={text.phase} className="relative z-10 -mt-8 hidden self-start rounded-2xl bg-white p-4 shadow-card lg:block">
      <ol className="space-y-1">
        {PHASES.map((p, i) => {
          const past = i < phaseIndex || done;
          const current = i === phaseIndex && !done;
          return (
            <li
              key={p}
              aria-current={current ? "step" : undefined}
              className={`flex items-center gap-3 rounded-xl px-2 py-2 transition-colors duration-500 ${current ? "bg-brand-lighter font-bold" : ""}`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-sm font-bold transition-colors duration-500 ${
                  past ? "bg-logo-teal text-charcoal" : current ? "-rotate-6 bg-logo-yellow text-charcoal" : "bg-line text-charcoal-soft"
                }`}
              >
                {past ? <Check className="h-4 w-4" /> : i + 1}
              </span>
              <span className={past || current ? "" : "text-charcoal-soft"}>{text.phases[p]}</span>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

/** The four Profolio logo cards, fanned out and stamped in one after the other. */
function LogoFan() {
  const cards = ["bg-logo-yellow -rotate-12", "bg-logo-red -rotate-3", "bg-logo-blue rotate-6", "bg-logo-teal rotate-12"];
  return (
    <div className="flex justify-center -space-x-1.5" aria-hidden="true">
      {cards.map((card, i) => (
        <span
          key={card}
          className={`h-12 w-9 animate-stamp rounded-lg shadow-card ${card}`}
          style={{ animationDelay: `${200 + i * 110}ms` }}
        />
      ))}
    </div>
  );
}

function Dot({ color, delay }: { color: string; delay: string }) {
  return (
    <span
      className={`h-2 w-2 animate-dot rounded-full motion-reduce:animate-none ${color}`}
      style={{ animationDelay: delay }}
    />
  );
}

/** The interviewer's avatar: the same face as in the call view, on a small tilted red square. */
function Avatar({ interviewer }: { interviewer: Interviewer }) {
  return (
    <div className="h-10 w-10 shrink-0 -rotate-6 overflow-hidden rounded-lg bg-logo-red" aria-hidden="true">
      <Face seed={interviewer.name} voice={interviewer.voice} className="h-full w-full" />
    </div>
  );
}

function Message({
  message,
  animate,
  text,
  interviewer,
  showReadAloud,
  speaking,
  onReadAloud,
}: {
  message: ChatMessage;
  /** New message: slides in from the side of the one who speaks */
  animate: boolean;
  text: UiTexts;
  interviewer: Interviewer;
  showReadAloud: boolean;
  speaking: boolean;
  onReadAloud: () => void;
}) {
  if (message.role === "candidate") {
    return (
      <div className="space-y-3">
        <div className={`ml-auto w-fit max-w-[80%] hyphens-auto lg:max-w-xl ${animate ? "animate-msg-right" : ""} wrap-anywhere rounded-2xl rounded-br-md bg-brand px-4 py-3 text-lg leading-snug whitespace-pre-wrap text-white`}>
          {/* The interviewer's turns have a visible name; screen readers also hear who said this one */}
          <span className="sr-only">{text.you}: </span>
          {message.text}
        </div>
        {message.tip && (
          // The coach's tip follows a moment after the answer
          <div
            className={`ml-8 rounded-xl bg-mint-lighter px-4 py-3 text-base text-mint-dark wrap-anywhere hyphens-auto lg:max-w-xl ${animate ? "animate-rise-in" : ""}`}
            style={animate ? { animationDelay: "200ms" } : undefined}
          >
            <p className="mb-1 flex items-center gap-2 font-bold">
              <Lightbulb className="h-4 w-4" />
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
    <div className={`flex items-start gap-3 ${animate ? "animate-msg-left" : ""}`}>
      <Avatar interviewer={interviewer} />
      <div className="min-w-0 max-w-[78%] lg:max-w-xl">
        <p className="mb-1 text-sm text-charcoal-soft">
          {interviewer.name}
          {interviewer.role && ` · ${interviewer.role}`}
        </p>
        <div className="rounded-2xl rounded-tl-md border border-line bg-white px-4 py-3 text-lg leading-snug whitespace-pre-wrap wrap-anywhere hyphens-auto shadow-sm">
          {message.text}
        </div>
        {(showReadAloud || speaking) && (
          <button
            onClick={onReadAloud}
            className="mt-3 inline-flex min-h-11 items-center gap-1.5 rounded-full border-2 border-line bg-white px-4 text-sm font-bold text-brand-dark hover:border-brand-light"
          >
            {speaking ? <Stop /> : <Speaker />}
            {speaking ? text.stopReading : text.readAloud}
          </button>
        )}
      </div>
    </div>
  );
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
  onSend,
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
  onSend: () => void;
}) {
  const box = "mb-2 flex items-center gap-3 rounded-xl px-3 py-2 text-sm";
  const action = "min-h-11 shrink-0 rounded-full border-2 px-4 text-sm font-bold transition active:scale-[0.97]";
  // Sends the spoken answer now, without waiting for the pause or the countdown
  const sendButton = (extra = "") => (
    <button
      type="button"
      onClick={onSend}
      className={`${action} ${extra} flex items-center justify-center gap-1.5 border-brand bg-brand text-white shadow-button hover:bg-brand-dark`}
    >
      {text.sendNow}
      <ArrowRight className="h-4 w-4" />
    </button>
  );

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
    // Two rows so both buttons get room on a phone: the filling bar on top, "Warten" and a wide "Jetzt senden" below
    return (
      <div className="mb-2 rounded-xl bg-mint-lighter p-2 text-sm text-mint-dark">
        <div className="relative overflow-hidden rounded-lg px-2 py-1.5" role="status">
          {/* Fills up during the pause; when full, the answer is sent */}
          <div className="absolute inset-y-0 left-0 bg-logo-teal/25" style={{ width: `${Math.round(countdown * 100)}%` }} />
          <span className="relative">{text.sendingSoon}</span>
        </div>
        <div className="mt-2 flex gap-2">
          <button type="button" onClick={onHold} className={`${action} border-mint-dark bg-white`}>
            {text.wait}
          </button>
          {sendButton("flex-1")}
        </div>
      </div>
    );
  }
  if (listening) {
    return (
      <div className={`${box} bg-danger-lighter text-logo-red`} role="status">
        <span className="h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-logo-red" />
        <span className="flex-1 text-charcoal">{text.listenNow}</span>
        {sendButton()}
      </div>
    );
  }
  if (transcribing) {
    return (
      <div className={`${box} bg-brand-lighter text-brand`} role="status">
        <span className="h-2.5 w-2.5 shrink-0 animate-dot rounded-full bg-brand motion-reduce:animate-none" />
        <span className="flex-1">{text.transcribing}</span>
        {sendButton()}
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

// The "how it works" card is shown once per browser. Storage can be blocked, so both are guarded.
const INTRO_KEY = "coach.introSeen";

function introSeen() {
  try {
    return localStorage.getItem(INTRO_KEY) === "yes";
  } catch {
    return false;
  }
}

function markIntroSeen() {
  try {
    localStorage.setItem(INTRO_KEY, "yes");
  } catch {
    // not remembered, the card can show again next time
  }
}
