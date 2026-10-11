// The interviewer as a small flat illustration: head, hair, shoulders. The colours are picked
// from the name, so each interviewer always looks the same; the hair style follows the voice.
// Mouth, eyes and eyebrows can be moved from outside (see SpeakerAvatar in CallView) through `parts`.

import type { RefObject } from "react";

export type FaceParts = {
  mouth: SVGEllipseElement | null;
  eyes: SVGGElement | null;
  brows: SVGGElement | null;
};

const SKIN = ["#f3cfb0", "#e5b48e", "#c98f66", "#9a6342", "#6e4429"];
const HAIR = ["#2a1b12", "#4b2e1d", "#7a4a26", "#b7853f", "#1c1c1c"];

/** A small number from the name, the same every time. */
function hash(text: string) {
  let h = 0;
  for (const char of text) h = (h * 31 + char.charCodeAt(0)) >>> 0;
  return h;
}

export default function Face({
  seed,
  voice = "female",
  parts,
  className,
}: {
  seed: string;
  voice?: "female" | "male";
  parts?: RefObject<FaceParts>;
  className?: string;
}) {
  const h = hash(seed);
  const skin = SKIN[h % SKIN.length];
  const hair = HAIR[(h >> 4) % HAIR.length];
  const female = voice === "female";

  return (
    <svg viewBox="8 11 80 80" className={className} aria-hidden="true">
      {/* long hair goes behind the head */}
      {female && <path d="M27 46C25 22 37 15 48 15s23 7 21 31l2 22c-7 5-39 5-46 0z" fill={hair} />}
      {/* shoulders with a shirt and a white collar */}
      <path d="M12 96c0-19 16-28 36-28s36 9 36 28z" fill="#33475b" />
      <path d="M39 68l9 11 9-11z" fill="#fff" />
      <rect x="42" y="55" width="12" height="15" rx="5" fill={skin} />
      <rect x="42" y="55" width="12" height="15" rx="5" fill="#000" opacity="0.12" />
      {/* ears (hidden by long hair) and head */}
      {!female && <ellipse cx="31" cy="44" rx="3.5" ry="4.5" fill={skin} />}
      {!female && <ellipse cx="65" cy="44" rx="3.5" ry="4.5" fill={skin} />}
      <ellipse cx="48" cy="42" rx="17" ry="20" fill={skin} />
      {/* hair on top */}
      {female ? (
        <path d="M31 39c1-14 10-19 18-19 10 0 16 7 16 19-6-8-17-11-34 0z" fill={hair} />
      ) : (
        <path d="M31 42c-3-16 7-24 18-24 11 0 18 7 16 22-2-6-5-9-9-10-7 4-15 5-25 12z" fill={hair} />
      )}
      {/* cheeks */}
      <circle cx="38" cy="50" r="3.5" fill="#fb505d" opacity="0.18" />
      <circle cx="58" cy="50" r="3.5" fill="#fb505d" opacity="0.18" />
      <g
        ref={(el) => {
          if (parts) parts.current.brows = el;
        }}
        stroke={hair}
        strokeWidth="1.8"
        strokeLinecap="round"
        fill="none"
      >
        <path d="M37 37.5q4-2 7 0" />
        <path d="M52 37.5q3-2 7 0" />
      </g>
      <g
        ref={(el) => {
          if (parts) parts.current.eyes = el;
        }}
        fill="#2b2b2b"
        style={{ transformBox: "fill-box", transformOrigin: "center" }}
      >
        <ellipse cx="41" cy="43" rx="2.2" ry="2.6" />
        <ellipse cx="55" cy="43" rx="2.2" ry="2.6" />
      </g>
      {/* a smile at rest; the open mouth (ellipse) grows over it while speaking */}
      <path d="M44 52.5q4 3 8 0" stroke="#6b2328" strokeWidth="1.6" strokeLinecap="round" fill="none" />
      <ellipse
        ref={(el) => {
          if (parts) parts.current.mouth = el;
        }}
        cx="48"
        cy="53.5"
        rx="4"
        ry="0"
        fill="#6b2328"
      />
    </svg>
  );
}
