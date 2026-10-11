// Real client: talks to the backend over HTTP (track_2a/docs/api.md).

import type { InterviewApi } from "./InterviewApi";
import { ApiError } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

/** Small fetch wrapper: sends JSON, parses JSON, turns error responses into ApiError. */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE_URL + path, {
      ...options,
      headers: { "Content-Type": "application/json", ...options.headers },
    });
  } catch {
    throw new ApiError("NETWORK_ERROR", "Backend not reachable.");
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(error?.code ?? "INVALID_REQUEST", error?.message ?? `HTTP ${response.status}`);
  }
  return body as T;
}

export const httpApi: InterviewApi = {
  getConfig: () => request("/config"),

  createSession: (req) => request("/sessions", { method: "POST", body: JSON.stringify(req) }),

  sendAnswer: (sessionId, questionId, text) =>
    request(`/sessions/${sessionId}/answers`, {
      method: "POST",
      body: JSON.stringify({ question_id: questionId, text }),
    }),

  getSession: (sessionId) => request(`/sessions/${sessionId}`),

  getReport: (sessionId) => request(`/sessions/${sessionId}/report`),

  async transcribe(audio, language) {
    // multipart/form-data: the browser sets the Content-Type (with the boundary) itself
    const form = new FormData();
    form.append("audio", audio, `answer.${audio.type.includes("mp4") ? "mp4" : "webm"}`);
    form.append("language", language);
    return checked(await send("/transcribe", { method: "POST", body: form })).json();
  },

  async speech(text, language, voice) {
    const response = await send("/speech", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language, voice }),
    });
    return checked(response).blob();
  },
};

/** fetch without the JSON defaults of request(), for audio uploads and downloads. */
async function send(path: string, options: RequestInit): Promise<Response> {
  try {
    return await fetch(BASE_URL + path, options);
  } catch {
    throw new ApiError("NETWORK_ERROR", "Backend not reachable.");
  }
}

function checked(response: Response): Response {
  if (!response.ok) throw new ApiError(response.status === 503 ? "VOICE_UNAVAILABLE" : "INVALID_REQUEST", `HTTP ${response.status}`);
  return response;
}
