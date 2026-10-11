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
/** Dialect of the interviewer for language "gsw": Zürich, Bern, Basel, Graubünden, Wallis */
export type Dialect = "zh" | "be" | "bs" | "gr" | "vs";
export type InterviewerStyle = "friendly" | "strict";

/** A text in several languages, e.g. { de: "Freundlich", fr: "Bienveillant" } */
export type LocalizedLabel = Partial<Record<LanguageCode, string>>;

// ---------- GET /config ----------

export type AppConfig = {
  languages: { code: LanguageCode; label: string }[];
  occupations: { id: string; label: LocalizedLabel }[];
  interviewer_styles: { id: InterviewerStyle; label: LocalizedLabel }[];
  modes: { id: Mode; description: string }[];
  /** Server voice features (docs/api.md). Missing or off: the browser's own speech features are used. */
  voice?: { stt: boolean; tts: "piper" | "azure" | null };
  dialects?: { code: Dialect; label: LocalizedLabel }[];
};

export type Voice = "female" | "male";

// ---------- POST /transcribe ----------

export type TranscribeResponse = { text: string; language: LanguageCode; duration_ms: number; model: string };

// ---------- POST /sessions ----------

export type Candidate = {
  first_name?: string;
  school_level?: string;
  interests?: string;
};

export type CreateSessionRequest = {
  language: LanguageCode;
  /** One of GET /config. Either this or `occupation_name` is set. */
  occupation_id?: string;
  /** Any other apprenticeship by name, e.g. "Koch/Köchin EFZ" (no company) */
  occupation_name?: string;
  /** Only for language "gsw": the dialect the interviewer writes in (default zh) */
  dialect?: Dialect;
  interviewer_style: InterviewerStyle;
  mode: Mode;
  candidate?: Candidate;
  /** Text of the application letter (uploaded, from POST /application/extract, or pasted) */
  application_text?: string;
  posting_id?: string;
  /** Criteria the new round should practise, e.g. the last report's next_practice */
  focus?: CriterionId[];
};

/** POST /application/extract */
export type ApplicationExtract = { filename: string; text: string; chars: number; truncated: boolean };

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
  interviewer?: { name: string; role: string; voice?: Voice } | null;
  /** Bullet points from the uploaded application (null if none, or if it could not be read) */
  application_summary?: string | null;
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
  occupation_name?: string | null;
  mode: Mode;
  done: boolean;
  phase: Phase;
  progress: Progress;
  history: HistoryEntry[];
  current_question_id: string | null;
};

// ---------- GET /sessions/{id}/report ----------

/** Feedback on the uploaded application letter (null without a letter), part of the report */
export type LetterFeedback = {
  scale: { min: number; max: number };
  overall_score: number;
  criteria: { id: string; label: string; score: number | null; comment: string; evidence: string }[];
  strengths: string[];
  improvements: { tip: string; example_answer?: string }[];
};

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
  application_feedback?: LetterFeedback | null;
  closing?: string; // one encouraging sentence
  support_note?: string | null; // where to get help, only if the interview showed distress
};

// ---------- Accounts (docs/api.md section 3b) ----------

export type User = { id: string; username: string };
export type AuthResponse = { token: string; user: User };

/** One row of GET /me/interviews. */
export type InterviewListItem = {
  session_id: string;
  language: LanguageCode;
  occupation_id: string;
  occupation_name?: string | null;
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
  occupation_name?: string | null;
  interviewer_style: InterviewerStyle;
  mode: Mode;
  candidate?: Candidate | null;
  created_at: string;
  done: boolean;
  phase: Phase;
  progress: Progress;
  current_question_id: string | null;
  company?: { name: string; place: string } | null;
  interviewer?: { name: string; role: string } | null;
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
  | "TOO_MANY_REQUESTS"
  | "LLM_UNAVAILABLE"
  | "VOICE_UNAVAILABLE"
  | "NETWORK_ERROR"; // frontend only: backend not reachable

export class ApiError extends Error {
  code: ApiErrorCode;

  constructor(code: ApiErrorCode, message: string) {
    super(message);
    this.code = code;
  }
}
