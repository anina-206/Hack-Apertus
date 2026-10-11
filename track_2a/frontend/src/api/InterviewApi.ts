import type {
  AnswerResponse,
  AppConfig,
  AuthResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  InterviewListItem,
  Report,
  SavedInterviewDetail,
  SessionState,
  User,
} from "./types";

/**
 * The one interface the UI talks to.
 * Both the mock and the real HTTP client implement it,
 * so the screens never know which one is active.
 */
export interface InterviewApi {
  getConfig(): Promise<AppConfig>;
  createSession(req: CreateSessionRequest): Promise<CreateSessionResponse>;
  sendAnswer(sessionId: string, questionId: string, text: string): Promise<AnswerResponse>;
  getSession(sessionId: string): Promise<SessionState>;
  getReport(sessionId: string): Promise<Report>;
  // Accounts: with a login the interviews are saved on the backend
  register(username: string, password: string): Promise<AuthResponse>;
  login(username: string, password: string): Promise<AuthResponse>;
  logout(): Promise<void>;
  me(): Promise<User>;
  listInterviews(): Promise<InterviewListItem[]>;
  getSavedInterview(sessionId: string): Promise<SavedInterviewDetail>;
}
