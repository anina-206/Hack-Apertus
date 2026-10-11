// The hands-free "call" view: the interviewer in the middle, pulsing with their voice,
// the candidate's voice as a live waveform, and a ring that fills up before the answer is sent.
//
// The animation reads the loudness from audio.ts (meter) in its own animation loop, so React does
// not re-render 60 times a second. With the browser voice there is no loudness, so a gentle
// made-up pulse is shown instead.

import { useEffect, useRef } from "react";
import { meter } from "../audio";
import type { UiTexts } from "../i18n";
import { ChatBubble, Mic, Pause, Play } from "./icons";

export type CallStatus = "speaking" | "thinking" | "listening" | "transcribing" | "countdown" | "paused" | "idle";

type Props = {
  text: UiTexts;
  interviewer: { name: string; role: string; initials: string };
  status: CallStatus;
  /** The interviewer's current question */
  question: string;
  /** In training mode: the tip on the last answer */
  tip?: string;
  /** What the candidate said (shown while it is about to be sent) */
  answer: string;
  /** Countdown before sending, 0 … 1 */
  countdown: number | null;
  /** Real loudness is available (server voice) */
  realSpeaker: boolean;
  realMic: boolean;
  onSkip: () => void;
  onHold: () => void;
  onResume: () => void;
  onShowChat: () => void;
  /** A microphone problem to show (permission, nothing understood, …) */
  error?: string | null;
};

const reducedMotion = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

export default function CallView(props: Props) {
  const { text, interviewer, status, question, tip, answer, countdown } = props;
  const speaking = status === "speaking";
  const listening = status === "listening";

  return (
    <div className="flex flex-1 flex-col items-center overflow-y-auto px-5 pt-8 pb-4 text-center">
      <SpeakerAvatar initials={interviewer.initials} active={speaking} real={props.realSpeaker} />
      <p className="mt-6 text-lg font-bold">{interviewer.name}</p>
      <p className="text-sm text-charcoal-soft" role="status" aria-live="polite">
        {statusText(text, status, interviewer.name)}
      </p>

      {tip && (
        <p className="mt-5 max-w-sm rounded-xl bg-mint-lighter px-4 py-2 text-sm text-mint-dark">
          <span className="font-bold">{text.tip}:</span> {tip}
        </p>
      )}
      <p className="mt-4 max-w-sm text-xl leading-snug font-medium">{question}</p>
      {props.error && (
        <p role="alert" className="mt-4 max-w-sm rounded-xl bg-danger-lighter px-4 py-2 text-sm text-danger">
          {props.error}
        </p>
      )}

      {/* The candidate's side */}
      <div className="mt-auto flex w-full max-w-sm flex-col items-center pt-8">
        {(status === "countdown" || status === "transcribing") && answer && (
          <p className="mb-4 w-full rounded-2xl rounded-br-md bg-brand px-4 py-3 text-left text-base text-white">{answer}</p>
        )}
        {status === "transcribing" && <ThinkingDots label={text.transcribing} />}
        {(listening || status === "countdown") && (
          <Waveform active={listening} real={props.realMic} label={text.listenNow} />
        )}
        {status === "countdown" && countdown !== null && <CountdownRing value={countdown} label={text.sendingSoon} />}
      </div>

      <div className="mt-6 flex w-full max-w-sm gap-3">
        <RoundButton onClick={props.onShowChat} label={text.showChat}>
          <ChatBubble />
        </RoundButton>
        {speaking ? (
          <RoundButton onClick={props.onSkip} label={text.skip} primary>
            <Mic />
          </RoundButton>
        ) : status === "paused" || status === "idle" ? (
          <RoundButton onClick={props.onResume} label={text.resume} primary>
            <Play />
          </RoundButton>
        ) : (
          <RoundButton onClick={props.onHold} label={status === "countdown" ? text.wait : text.pause} primary>
            <Pause />
          </RoundButton>
        )}
      </div>
    </div>
  );
}

function statusText(text: UiTexts, status: CallStatus, name: string) {
  switch (status) {
    case "speaking":
      return `${name} ${text.speakingNow}`;
    case "thinking":
      return `${name} ${text.thinkingNow}`;
    case "listening":
      return text.listenNow;
    case "transcribing":
      return text.transcribing;
    case "countdown":
      return text.understood;
    case "paused":
      return text.handsFreePaused;
    default:
      return "";
  }
}

/** Tilted avatar with three rings that grow with the loudness of the voice. */
function SpeakerAvatar({ initials, active, real }: { initials: string; active: boolean; real: boolean }) {
  const rings = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    let frame = 0;
    let smooth = 0;
    const animate = (time: number) => {
      // Real loudness from the audio, or a made-up pulse for the browser voice
      const target = !active ? 0 : real ? meter.speaker : 0.35 + 0.25 * Math.sin(time / 180) * Math.sin(time / 470);
      smooth += (target - smooth) * 0.25;
      rings.current.forEach((ring, i) => {
        if (!ring) return;
        // Each ring is a little bigger and fainter than the one inside it, like ripples
        const grow = reducedMotion ? 0.1 * i : 0.12 * i + smooth * (0.25 + i * 0.2);
        ring.style.transform = `scale(${1 + grow})`;
        ring.style.opacity = String(active ? Math.max(0, 0.7 - i * 0.2 + smooth * 0.3) : 0);
      });
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [active, real]);

  return (
    <div className="relative flex h-40 w-40 items-center justify-center" aria-hidden="true">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          ref={(el) => {
            rings.current[i] = el;
          }}
          className={`absolute inset-5 rounded-full border-logo-red transition-opacity duration-300 ${
            i === 0 ? "border-4 bg-logo-red/15" : "border-2"
          }`}
          style={{ opacity: 0 }}
        />
      ))}
      <div className="relative flex h-24 w-24 -rotate-6 items-center justify-center rounded-3xl bg-logo-red text-3xl font-bold text-white shadow-card">
        {initials}
      </div>
    </div>
  );
}

/** The candidate's voice as bars that scroll from right to left. */
function Waveform({ active, real, label }: { active: boolean; real: boolean; label: string }) {
  const canvas = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const el = canvas.current;
    const ctx = el?.getContext("2d");
    if (!el || !ctx) return;
    const ratio = window.devicePixelRatio || 1;
    el.width = el.clientWidth * ratio;
    el.height = el.clientHeight * ratio;
    const color = getComputedStyle(document.documentElement).getPropertyValue("--color-brand").trim() || "#0f6fe7";
    const bars = new Array(36).fill(0);
    let frame = 0;
    let tick = 0;

    const draw = (time: number) => {
      // Two new values per frame pair, so it scrolls at a calm speed
      if (tick++ % 2 === 0) {
        const level = !active ? 0 : real ? meter.mic : 0.15 + 0.35 * Math.abs(Math.sin(time / 210) * Math.sin(time / 90));
        bars.shift();
        bars.push(level);
      }
      ctx.clearRect(0, 0, el.width, el.height);
      const gap = el.width / bars.length;
      const width = gap * 0.55;
      bars.forEach((level, i) => {
        const height = Math.max(width, level * el.height * 0.95);
        ctx.fillStyle = color;
        ctx.globalAlpha = active ? 0.35 + 0.65 * (i / bars.length) : 0.25;
        ctx.beginPath();
        ctx.roundRect(i * gap + (gap - width) / 2, (el.height - height) / 2, width, height, width / 2);
        ctx.fill();
      });
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [active, real]);

  return <canvas ref={canvas} className="h-14 w-full" role="img" aria-label={label} />;
}

/** Ring that fills up until the answer is sent. */
function CountdownRing({ value, label }: { value: number; label: string }) {
  const r = 18;
  const length = 2 * Math.PI * r;
  return (
    <div className="mt-3 flex items-center gap-2 text-sm font-bold text-brand">
      <svg viewBox="0 0 44 44" className="h-8 w-8 -rotate-90" aria-hidden="true">
        <circle cx="22" cy="22" r={r} fill="none" stroke="currentColor" strokeOpacity="0.2" strokeWidth="5" />
        <circle
          cx="22"
          cy="22"
          r={r}
          fill="none"
          stroke="currentColor"
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={length}
          strokeDashoffset={length * (1 - value)}
        />
      </svg>
      {label}
    </div>
  );
}

function ThinkingDots({ label }: { label: string }) {
  return (
    <div className="mb-2 flex items-center gap-1.5" role="status">
      <span className="sr-only">{label}</span>
      {["bg-logo-red", "bg-logo-yellow", "bg-logo-blue"].map((color, i) => (
        <span
          key={color}
          className={`h-2.5 w-2.5 animate-dot rounded-full motion-reduce:animate-none ${color}`}
          style={{ animationDelay: `${i * 150}ms` }}
        />
      ))}
    </div>
  );
}

function RoundButton({
  onClick,
  label,
  primary,
  children,
}: {
  onClick: () => void;
  label: string;
  primary?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex flex-1 items-center justify-center gap-2 rounded-full border-2 px-4 py-3 text-base font-bold transition ${
        primary
          ? "border-brand bg-brand text-white shadow-button hover:bg-brand-dark"
          : "border-line bg-white text-charcoal hover:border-brand-light"
      }`}
    >
      {children}
      {label}
    </button>
  );
}

