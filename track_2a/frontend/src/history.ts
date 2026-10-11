// Shape of an interview in the chat screen. Interviews are saved on the backend (logged-in users only).

import type { LanguageCode, Phase, Report, SavedInterviewDetail } from "./api";

/** One bubble in the chat. `tip` is the short feedback after an answer (training mode). */
export type ChatMessage = {
  role: "interviewer" | "candidate";
  text: string;
  tip?: string;
};

export type SavedInterview = {
  session_id: string;
  language: LanguageCode;
  /** Line under the title, e.g. "Schreiner/in EFZ · Deutsch · Training" */
  summary: string;
  started_at: string; // ISO 8601
  phase: Phase;
  question_id: string | null; // null when the interview is over
  done: boolean;
  messages: ChatMessage[];
  /** The FHGR posting's company and interviewer (null/missing in the mock) */
  company?: { name: string; place: string } | null;
  interviewer?: { name: string; role: string } | null;
  /** Bullet points from the uploaded application, shown on top of the chat */
  application_summary?: string | null;
  /** An application was uploaded, but the backend could not summarise it */
  application_failed?: boolean;
  report?: Report; // filled in once the feedback screen has loaded it
};

/** Turns an interview saved on the backend (GET /me/interviews/{id}) into the shape the chat screen uses. */
export function fromServer(d: SavedInterviewDetail, summary: string): SavedInterview {
  const messages: ChatMessage[] = d.history.map((h) =>
    h.role === "candidate"
      ? { role: "candidate", text: h.text, tip: h.turn_feedback?.short_tip }
      : { role: "interviewer", text: h.text },
  );
  return {
    session_id: d.session_id,
    language: d.language,
    summary,
    started_at: d.created_at,
    phase: d.phase,
    question_id: d.current_question_id,
    done: d.done,
    messages,
    company: d.company,
    interviewer: d.interviewer,
    report: d.report ?? undefined,
  };
}
