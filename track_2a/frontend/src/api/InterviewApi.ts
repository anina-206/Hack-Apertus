import type {
  AnswerResponse,
  ApplicationExtract,
  AppConfig,
  AuthResponse,
  CreateSessionRequest,
  CreateSessionResponse,
  InterviewListItem,
  Report,
  SavedInterviewDetail,
  SessionState,
  TranscribeResponse,
  Voice,
  LanguageCode,
  User,
} from "./types";

/**
 * The one interface the UI talks to.
 * Both the mock and the real HTTP client implement it,
 * so the screens never know which one is active.
 */
export interface InterviewApi {
  getConfig(): Promise<AppConfig>;
  /** Reads an uploaded application (PDF, Word or text) and returns its text. Nothing is stored. */
  extractApplication(file: File): Promise<ApplicationExtract>;
  createSession(req: CreateSessionRequest): Promise<CreateSessionResponse>;
  sendAnswer(sessionId: string, questionId: string, text: string): Promise<AnswerResponse>;
  getSession(sessionId: string): Promise<SessionState>;
  getReport(sessionId: string): Promise<Report>;
  /** Speech to text (Whisper). Only when config.voice.stt is true. `sessionId` gives Whisper the occupation's words. */
  transcribe(audio: Blob, language: LanguageCode, sessionId?: string): Promise<TranscribeResponse>;
  /** Text to speech: the audio for one interviewer line. Only when config.voice.tts is set. */
  speech(text: string, language: LanguageCode, voice: Voice): Promise<Blob>;
  // Accounts: with a login the interviews are saved on the backend
  register(username: string, password: string): Promise<AuthResponse>;
  login(username: string, password: string): Promise<AuthResponse>;
  logout(): Promise<void>;
  me(): Promise<User>;
  /** Deletes the account with all saved interviews. Needs the password again. */
  deleteAccount(password: string): Promise<void>;
  listInterviews(): Promise<InterviewListItem[]>;
  getSavedInterview(sessionId: string): Promise<SavedInterviewDetail>;
  /** Deletes one saved interview of the logged-in user. */
  deleteInterview(sessionId: string): Promise<void>;
}
