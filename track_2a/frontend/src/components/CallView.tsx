// The hands-free "call" view: the interviewer in the middle, pulsing with their voice,
// the candidate's voice as a live waveform, and a ring that fills up before the answer is sent.
//
// The animation reads the loudness from audio.ts (meter) in its own animation loop, so React does
// not re-render 60 times a second. With the browser voice there is no loudness, so a gentle
// made-up pulse is shown instead.

import { useEffect, useRef } from "react";
import { meter } from "../audio";
import type { UiTexts } from "../i18n";
import Face, { type FaceParts } from "./Face";
import { ChatBubble, Mic, Pause, Play } from "./icons";

export type CallStatus = "speaking" | "thinking" | "listening" | "transcribing" | "countdown" | "paused" | "idle";

type Props = {
  text: UiTexts;
  interviewer: { name: string; role: string; initials: string; voice?: "female" | "male" };
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
      <SpeakerAvatar
        name={interviewer.name}
        voice={interviewer.voice}
        active={speaking}
        writing={status === "transcribing"}
        real={props.realSpeaker}
      />
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

const WAVES = 4; // how many ripples can be on their way at the same time
const WAVE_MS = 1300; // how long one ripple takes to roll out and fade

/**
 * Tilted avatar that "talks":
 * - a soft glow behind it follows the loudness,
 * - on every syllable (the voice gets loud again after a dip) a ripple rolls outwards,
 * - the card itself bounces a little with the voice,
 * - the face opens its mouth with the voice, raises the eyebrows a little and blinks now and then,
 * - while the answer is transcribed ("Ich schreibe mit …") a notepad appears: a pen writes line by line
 *   and the face looks down at it.
 * The ripples have the same rounded, tilted shape as the card.
 */
function SpeakerAvatar({
  name,
  voice,
  active,
  writing,
  real,
}: {
  name: string;
  voice?: "female" | "male";
  active: boolean;
  writing: boolean;
  real: boolean;
}) {
  const pad = useRef<NotepadParts>({ lines: [], pen: null });
  const card = useRef<HTMLDivElement>(null);
  const face = useRef<FaceParts>({ mouth: null, eyes: null, brows: null });
  const glow = useRef<HTMLSpanElement>(null);
  const waves = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    let frame = 0;
    let level = 0; // smoothed loudness 0 … 1
    let peak = 0; // loudest point since the last dip
    let low = true; // the voice dipped since the last ripple
    let lastWave = -Infinity;
    let next = 0; // which ripple element is launched next
    const started = new Array<number>(WAVES).fill(-Infinity); // start time of each ripple
    const strength = new Array<number>(WAVES).fill(0); // how loud the syllable was
    const fake = { target: 0, until: 0 };
    let mouth = 0; // like level, but closes quickly between syllables
    let blinkAt = performance.now() + 1500;
    const writeStart = performance.now();

    const animate = (time: number) => {
      const target = !active ? 0 : real ? meter.speaker : fakeVoice(fake, time);
      // Rise fast, fall slowly: that is how a voice meter looks natural
      level += (target - level) * (target > level ? 0.45 : 0.08);

      // Launch a ripple when a new syllable starts (louder again after a small dip),
      // or every half second while the voice stays loud without a dip
      peak = Math.max(peak, level);
      if (level < peak * 0.85) {
        low = true;
        peak = level;
      }
      const sinceLast = time - lastWave;
      const syllable = low && target > level && sinceLast > 220;
      if (active && level > 0.3 && (syllable || sinceLast > 480)) {
        started[next] = time;
        strength[next] = level;
        next = (next + 1) % WAVES;
        lastWave = time;
        low = false;
      }

      if (card.current) {
        const bounce = reducedMotion ? 0 : level;
        const nod = writing && !reducedMotion ? -3 : 0; // head bowed over the notepad
        card.current.style.transform = `rotate(${-6 + nod + bounce * 3}deg) scale(${1 + bounce * 0.06})`;
      }
      if (glow.current) {
        glow.current.style.opacity = String(active ? 0.35 + level * 0.65 : 0);
        glow.current.style.transform = `rotate(-6deg) scale(${1 + (reducedMotion ? 0.08 : level * 0.18)})`;
      }
      // The face: mouth open with the voice, eyebrows up a little, a blink every few seconds
      mouth += (target - mouth) * 0.5;
      const { mouth: lips, eyes, brows } = face.current;
      lips?.setAttribute("ry", String(mouth * 3.6));
      lips?.setAttribute("rx", String(4 - mouth * 0.8));
      // While writing, eyes and eyebrows go down a little: the face looks at the notepad
      const down = writing ? 1.5 : 0;
      if (brows) brows.style.transform = `translateY(${down + (reducedMotion ? 0 : -level * 1.6)}px)`;
      if (time > blinkAt + 140) blinkAt = time + 2500 + Math.random() * 3500;
      const blink = !reducedMotion && time > blinkAt ? " scaleY(0.1)" : "";
      if (eyes) eyes.style.transform = `translateY(${down}px)${blink}`;
      if (writing) writeNotes(pad.current, time - writeStart);

      waves.current.forEach((wave, i) => {
        if (!wave) return;
        const p = (time - started[i]) / WAVE_MS; // 0 … 1 while the ripple is rolling
        if (reducedMotion || p < 0 || p > 1) {
          wave.style.opacity = "0";
          return;
        }
        const eased = 1 - (1 - p) ** 3; // starts fast, slows down at the end
        wave.style.transform = `rotate(${-6 + eased * 8}deg) scale(${1.05 + eased * 0.75})`;
        wave.style.opacity = String((1 - p) * (0.35 + strength[i] * 0.5));
      });
      frame = requestAnimationFrame(animate);
    };
    frame = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(frame);
  }, [active, writing, real]);

  return (
    <div className="relative flex h-40 w-40 items-center justify-center" aria-hidden="true">
      {Array.from({ length: WAVES }, (_, i) => (
        <span
          key={i}
          ref={(el) => {
            waves.current[i] = el;
          }}
          className="absolute h-28 w-28 rounded-3xl border-2 border-logo-red"
          style={{ opacity: 0 }}
        />
      ))}
      <span
        ref={glow}
        className="absolute h-28 w-28 rounded-3xl bg-logo-red/25 blur-md transition-opacity duration-300"
        style={{ opacity: 0 }}
      />
      <div
        ref={card}
        className="relative h-28 w-28 -rotate-6 overflow-hidden rounded-3xl bg-logo-red shadow-card"
      >
        <Face seed={name} voice={voice} parts={face} className="h-full w-full" />
      </div>
      <Notepad parts={pad} visible={writing} />
    </div>
  );
}

type NotepadParts = { lines: (SVGPathElement | null)[]; pen: SVGGElement | null };

const NOTE_LINES = [20, 29, 38]; // y of the written lines on the notepad
const LINE_MS = 800; // time to write one line
const PAGE_MS = NOTE_LINES.length * LINE_MS + 600; // all lines, then a short pause before a fresh page

/** Moves the pen and draws the lines for the moment `elapsed` ms after writing started. */
function writeNotes({ lines, pen }: NotepadParts, elapsed: number) {
  const t = reducedMotion ? PAGE_MS - 1 : elapsed % PAGE_MS; // reduced motion: a full page, the pen stands still
  const current = Math.min(NOTE_LINES.length - 1, Math.floor(t / LINE_MS));
  const progress = Math.min(1, (t - current * LINE_MS) / LINE_MS); // 0 … 1 along the current line
  lines.forEach((line, i) => {
    // pathLength is 1, so the dash offset is "how much is still missing"
    const drawn = i < current ? 1 : i === current ? progress : 0;
    line?.setAttribute("stroke-dashoffset", String(1 - drawn));
  });
  // The pen tip follows the line, with a little up and down like handwriting
  const x = 8 + 28 * progress;
  const y = NOTE_LINES[current] + Math.sin(progress * Math.PI * 14) * 1.2;
  pen?.setAttribute("transform", `translate(${x} ${y})`);
}

/** A small notepad with a pen, at the bottom right of the avatar. Animated by writeNotes(). */
function Notepad({ parts, visible }: { parts: React.RefObject<NotepadParts>; visible: boolean }) {
  return (
    <svg
      viewBox="0 0 44 52"
      className={`absolute right-0 bottom-1 h-16 w-14 rotate-6 overflow-visible drop-shadow-md transition duration-300 ${
        visible ? "scale-100 opacity-100" : "scale-75 opacity-0"
      }`}
    >
      <rect x="2" y="4" width="40" height="46" rx="4" fill="#fff" />
      <path d="M2 14V8a4 4 0 0 1 4-4h32a4 4 0 0 1 4 4v6z" fill="#efd02c" />
      {NOTE_LINES.map((y, i) => (
        <path
          key={y}
          ref={(el) => {
            parts.current.lines[i] = el;
          }}
          d={`M8 ${y}q2-3 4 0t4 0t4 0t4 0t4 0t4 0t4 0`}
          pathLength={1}
          strokeDasharray="1"
          strokeDashoffset="1"
          stroke="#0f6fe7"
          strokeWidth="1.6"
          strokeLinecap="round"
          fill="none"
        />
      ))}
      <g
        ref={(el) => {
          parts.current.pen = el;
        }}
      >
        {/* tip at 0,0, the pen goes up to the right */}
        <path d="M0 0l1-4 12-12 3 3-12 12z" fill="#33475b" />
        <path d="M0 0l1-4 3 3z" fill="#efd02c" />
      </g>
    </svg>
  );
}

/**
 * Made-up loudness for the browser voice (it gives us no audio to measure):
 * syllables of random length and loudness, with a short pause between words now and then.
 */
function fakeVoice(state: { target: number; until: number }, time: number) {
  if (time > state.until) {
    const pause = Math.random() < 0.18;
    state.target = pause ? 0 : 0.45 + Math.random() * 0.5;
    state.until = time + (pause ? 180 + Math.random() * 220 : 110 + Math.random() * 150);
  }
  return state.target;
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

