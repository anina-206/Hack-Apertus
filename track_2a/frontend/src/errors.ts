// One place that turns an error into a sentence for the candidate: what happened and what to do now.
// Screens check their own special cases first (e.g. wrong password) and use this for the rest.

import { ApiError } from "./api";
import type { UiTexts } from "./i18n";

export function errorText(err: unknown, text: UiTexts): string {
  // The browser knows it is offline even before a request fails
  if (typeof navigator !== "undefined" && navigator.onLine === false) return text.errorOffline;
  const code = err instanceof ApiError ? err.code : null;
  switch (code) {
    case "NETWORK_ERROR":
      return text.errorOffline;
    case "TIMEOUT":
      return text.errorTimeout;
    case "LLM_UNAVAILABLE":
      return text.errorBusy;
    case "SESSION_NOT_FOUND":
    case "INTERVIEW_NOT_FOUND":
      return text.errorSessionGone;
    case "UNAUTHORIZED":
      return text.errorLoggedOut;
    case "TOO_MANY_REQUESTS":
      return text.tooManyRequests;
    default:
      return text.error;
  }
}

/** Errors where trying again cannot help: the interview is gone on the server. */
export function isSessionGone(err: unknown) {
  return err instanceof ApiError && (err.code === "SESSION_NOT_FOUND" || err.code === "INTERVIEW_NOT_FOUND");
}
