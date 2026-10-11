import type {
  AnswerResponse,
  AppConfig,
  CreateSessionRequest,
  CreateSessionResponse,
  Report,
  SessionState,
  TranscribeResponse,
  Voice,
  LanguageCode,
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
  /** Speech to text (Whisper). Only when config.voice.stt is true. */
  transcribe(audio: Blob, language: LanguageCode): Promise<TranscribeResponse>;
  /** Text to speech: the audio for one interviewer line. Only when config.voice.tts is set. */
  speech(text: string, language: LanguageCode, voice: Voice): Promise<Blob>;
}
