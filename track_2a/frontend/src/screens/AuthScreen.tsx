import { useState } from "react";
import { api, ApiError, type LanguageCode, type User } from "../api";
import { saveLogin } from "../auth";
import CardAccent from "../components/CardAccent";
import { ChevronLeft } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import { t } from "../i18n";

type Props = {
  language: LanguageCode;
  onLoggedIn: (user: User) => void;
  /** Back to the start screen. */
  onCancel: () => void;
};

const inputClass =
  "w-full rounded-full border-2 border-line bg-white px-5 py-3.5 text-base text-charcoal placeholder:text-charcoal/40 focus:border-brand focus:ring-4 focus:ring-brand/20 focus:outline-none";

export default function AuthScreen({ language, onLoggedIn, onCancel }: Props) {
  const text = t(language);

  const [creating, setCreating] = useState(false); // false = log in, true = create account
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const { token, user } = creating
        ? await api.register(username.trim(), password)
        : await api.login(username.trim(), password);
      saveLogin(token, user);
      onLoggedIn(user);
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "";
      setError(
        code === "INVALID_CREDENTIALS"
          ? text.loginFailed
          : code === "USERNAME_TAKEN"
            ? text.usernameTaken
            : code === "TOO_MANY_REQUESTS"
              ? text.tooManyRequests
              : code === "INVALID_REQUEST"
                ? text.invalidInput
                : text.error,
      );
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-lg flex-col bg-page">
      <header className="bg-brand px-4 pt-5 pb-14 text-white">
        <div className="flex items-center gap-2">
          <button
            onClick={onCancel}
            aria-label={text.back}
            className="-ml-2 flex h-11 w-11 items-center justify-center rounded-full hover:bg-white/10"
          >
            <ChevronLeft />
          </button>
          <h1 className="text-3xl font-bold tracking-tight">
            {creating ? text.register : text.login}
            <span className="text-logo-yellow">.</span>
          </h1>
        </div>
        <p className="mt-3 text-base text-white/90">{text.loginIntro}</p>
      </header>

      <main className="-mt-7 flex-1 px-4">
        <form onSubmit={submit} className="relative space-y-5 overflow-hidden rounded-3xl bg-white p-5 shadow-card">
          <CardAccent />

          <label className="block">
            <span className="mb-2 block text-sm font-bold">{text.username}</span>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              autoCapitalize="none"
              required
              className={inputClass}
            />
          </label>

          <label className="block">
            <span className="mb-2 block text-sm font-bold">{text.password}</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={creating ? "new-password" : "current-password"}
              required
              className={inputClass}
            />
            {creating && <span className="mt-2 block text-sm text-charcoal-soft">{text.passwordHint}</span>}
          </label>

          {error && <p className="rounded-xl bg-danger-lighter px-4 py-3 text-danger">{error}</p>}

          <PrimaryButton type="submit" disabled={busy || !username.trim() || !password} wide>
            {busy ? text.pleaseWait : creating ? text.register : text.login}
          </PrimaryButton>

          <button
            type="button"
            onClick={() => {
              setCreating(!creating);
              setError(null);
            }}
            className="block min-h-11 w-full text-center text-sm font-bold text-brand-dark"
          >
            {creating ? text.haveAccount : text.noAccountYet}
          </button>
        </form>

        <button onClick={onCancel} className="mt-5 block w-full pb-6 text-center text-sm font-bold text-charcoal-soft">
          {text.back}
        </button>
      </main>
    </div>
  );
}
