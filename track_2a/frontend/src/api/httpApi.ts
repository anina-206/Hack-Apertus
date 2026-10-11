// Real client: talks to the backend over HTTP (track_2a/docs/api.md).

import type { InterviewApi } from "./InterviewApi";
import { getToken } from "../auth";
import { ApiError, type InterviewListItem } from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

/** Small fetch wrapper: sends JSON, parses JSON, turns error responses into ApiError. */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(BASE_URL + path, {
      ...options,
      headers: {
        // A file upload (FormData) sets its own Content-Type with the boundary
        ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
        // Logged in: the backend saves the interviews for this user
        ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
        ...options.headers,
      },
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

  extractApplication: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/application/extract", { method: "POST", body: form });
  },

  createSession: (req) => request("/sessions", { method: "POST", body: JSON.stringify(req) }),

  sendAnswer: (sessionId, questionId, text) =>
    request(`/sessions/${sessionId}/answers`, {
      method: "POST",
      body: JSON.stringify({ question_id: questionId, text }),
    }),

  getSession: (sessionId) => request(`/sessions/${sessionId}`),

  getReport: (sessionId) => request(`/sessions/${sessionId}/report`),

  register: (username, password) =>
    request("/auth/register", { method: "POST", body: JSON.stringify({ username, password }) }),

  login: (username, password) =>
    request("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),

  logout: () => request("/auth/logout", { method: "POST" }),

  me: () => request("/auth/me"),

  deleteAccount: (password) => request("/auth/me", { method: "DELETE", body: JSON.stringify({ password }) }),

  listInterviews: async () => (await request<{ interviews: InterviewListItem[] }>("/me/interviews")).interviews,

  getSavedInterview: (sessionId) => request(`/me/interviews/${sessionId}`),

  deleteInterview: (sessionId) => request(`/me/interviews/${sessionId}`, { method: "DELETE" }),

  async transcribe(audio, language, sessionId) {
    // multipart/form-data: the browser sets the Content-Type (with the boundary) itself
    const form = new FormData();
    form.append("audio", audio, `answer.${audio.type.includes("mp4") ? "mp4" : "webm"}`);
    form.append("language", language);
    if (sessionId) form.append("session_id", sessionId);
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
