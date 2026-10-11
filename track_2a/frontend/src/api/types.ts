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

/** The 11 FHGR criteria (datasets/rubric/criteria.json), in rubric order. */
export const CRITERIA = [
  "clarity",
  "relevance",
  "motivation",
  "self_reflection",
  "communication",
  "concrete_examples",
  "demeanor",
  "preparation",
  "goal_orientation",
  "difficult_questions",
  "initiative",
] as const;

export type CriterionId = (typeof CRITERIA)[number];

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
  posting_id?: string;
  /** Criteria the new round should practise, e.g. the last report's next_practice */
  focus?: CriterionId[];
};

export type Progress = { current: number; total: number };

export type Question = {
  id: string;
  text: string;
  is_follow_up?: boolean;
  /** Set when the guardrails answered instead of a normal question (see docs/api.md). */
  guard?: "crisis" | "support" | "redirect";
};

export type CreateSessionResponse = {
  session_id: string;
  phase: Phase;
  progress: Progress;
  question: Question;
  /** The FHGR posting's company and interviewer (null in the mock) */
  company?: { name: string; place: string } | null;
  interviewer?: { name: string; role: string } | null;
};

// ---------- POST /sessions/{id}/answers ----------

/** Each 1-4, or null when the answer showed nothing about this criterion. */
export type Scores = Partial<Record<CriterionId, number | null>>;

export type TurnFeedback = {
  short_tip: string;
  scores: Scores;
  problem_flags?: string[];
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
  scale: { min: number; max: number }; // 1-4
  overall_score: number | null; // null if no criterion was observed
  criteria: {
    id: CriterionId;
    label: string;
    score: number | null; // null = not observed in the interview

    comment: string;
    evidence?: string;
  }[];
  strengths: string[];
  improvements: { tip: string; example_answer?: string }[];
  next_practice: CriterionId[];
  closing?: string; // one encouraging sentence
  support_note?: string | null; // where to get help, only if the interview showed distress
};

// ---------- Errors ----------

export type ApiErrorCode =
  | "INVALID_REQUEST"
  | "SESSION_NOT_FOUND"
  | "WRONG_QUESTION"
  | "INTERVIEW_NOT_FINISHED"
  | "INTERVIEW_FINISHED"
  | "LLM_UNAVAILABLE"
  | "NETWORK_ERROR"; // frontend only: backend not reachable

export class ApiError extends Error {
  code: ApiErrorCode;

  constructor(code: ApiErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}
