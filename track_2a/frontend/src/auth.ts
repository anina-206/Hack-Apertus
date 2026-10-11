// Login state in this browser: the token the backend gave us, and the username for the header.

import type { User } from "./api";

const TOKEN_KEY = "interview-coach-token";
const USER_KEY = "interview-coach-user";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return getToken() && raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function saveLogin(token: string, user: User) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  } catch {
    // Storage blocked: the login only lasts until the page is reloaded
  }
}

export function clearLogin() {
  try {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  } catch {
    // nothing to clear
  }
}
