// Types from the API contract: track_2a/docs/api.md
// Keys stay in snake_case, exactly as the backend sends them.

export type LanguageCode = "de" | "fr" | "it" | "gsw";

export type Phase =
  | "intro"
  | "motivation"
  | "strengths_weaknesses"
  | "situational"
  | "candidate_questions"
  | "closing";

/** The phases in interview order (used for "Phase 2 of 6"). */
export const PHASES: Phase[] = [
  "intro",
  "motivation",
  "strengths_weaknesses",
  "situational",
  "candidate_questions",
  "closing",
];

export type CriterionId =
  | "relevance"
  | "structure"
  | "examples"
  | "motivation"
  | "language"
  | "self_reflection";

export type Mode = "training" | "rehearsal";
export type InterviewerStyle = "friendly" | "strict";

/** A text in several languages, e.g. { de: "Freundlich", fr: "Bienveillant" } */
export type LocalizedLabel = Partial<Record<LanguageCode, string>>;

// ---------- GET /config ----------

export type AppConfig = {
  languages: { code: LanguageCode; label: string }[];
  occupations: { id: string; label: LocalizedLabel }[];
  interviewer_styles: { id: InterviewerStyle; label: LocalizedLabel }[];
  modes: { id: Mode; description: string }[];
};

// ---------- POST /sessions ----------

export type Candidate = {
  first_name?: string;
  school_level?: string;
  interests?: string;
};

export type CreateSessionRequest = {
  language: LanguageCode;
  occupation_id: string;
  interviewer_style: InterviewerStyle;
  mode: Mode;
  candidate?: Candidate;
};

export type Progress = { current: number; total: number };

export type Question = {
  id: string;
  text: string;
  is_follow_up?: boolean;
};

export type CreateSessionResponse = {
  session_id: string;
  phase: Phase;
  progress: Progress;
  question: Question;
};

// ---------- POST /sessions/{id}/answers ----------

export type Scores = Record<CriterionId, number>; // each 1-5

export type TurnFeedback = {
  short_tip: string;
  scores: Scores;
};

export type AnswerResponse = {
  done: boolean;
  phase: Phase;
  progress: Progress;
  question: Question | null;
  closing_message?: string;
  turn_feedback: TurnFeedback | null;
  meta?: { llm_calls: number; latency_ms: number };
};

// ---------- GET /sessions/{id} ----------

export type HistoryEntry = {
  role: "interviewer" | "candidate";
  question_id: string;
  text: string;
};

export type SessionState = {
  session_id: string;
  language: LanguageCode;
  occupation_id: string;
  mode: Mode;
  done: boolean;
  phase: Phase;
  progress: Progress;
  history: HistoryEntry[];
  current_question_id: string | null;
};

// ---------- GET /sessions/{id}/report ----------

export type Report = {
  session_id: string;
  language: LanguageCode;
  overall_score: number;
  criteria: {
    id: CriterionId;
    label: string;
    score: number;
    comment: string;
    evidence?: string;
  }[];
  strengths: string[];
  improvements: { tip: string; example_answer?: string }[];
  next_practice: CriterionId[];
};

// ---------- Accounts (docs/api.md section 3b) ----------

export type User = { id: string; username: string };
export type AuthResponse = { token: string; user: User };

/** One row of GET /me/interviews. */
export type InterviewListItem = {
  session_id: string;
  language: LanguageCode;
  occupation_id: string;
  interviewer_style: InterviewerStyle;
  mode: Mode;
  created_at: string;
  updated_at: string;
  done: boolean;
  overall_score: number | null;
};

/** GET /me/interviews/{id}: the whole saved conversation. */
export type SavedInterviewDetail = {
  session_id: string;
  language: LanguageCode;
  occupation_id: string;
  interviewer_style: InterviewerStyle;
  mode: Mode;
  candidate?: Candidate | null;
  created_at: string;
  done: boolean;
  phase: Phase;
  progress: Progress;
  current_question_id: string | null;
  history: (Omit<HistoryEntry, "question_id"> & {
    question_id: string | null;
    turn_feedback?: TurnFeedback | null;
  })[];
  report: Report | null;
};

// ---------- Errors ----------

export type ApiErrorCode =
  | "INVALID_REQUEST"
  | "SESSION_NOT_FOUND"
  | "WRONG_QUESTION"
  | "INTERVIEW_NOT_FINISHED"
  | "INTERVIEW_FINISHED"
  | "INTERNAL_ERROR"
  | "USERNAME_TAKEN"
  | "INVALID_CREDENTIALS"
  | "UNAUTHORIZED"
  | "INTERVIEW_NOT_FOUND"
  | "LLM_UNAVAILABLE"
  | "NETWORK_ERROR"; // frontend only: backend not reachable

export class ApiError extends Error {
  code: ApiErrorCode;

  constructor(code: ApiErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}
