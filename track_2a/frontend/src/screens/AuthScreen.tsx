import { useState } from "react";
import { api, ApiError, type LanguageCode, type User } from "../api";
import { saveLogin } from "../auth";
import { errorText } from "../errors";
import Alert from "../components/Alert";
import CardAccent from "../components/CardAccent";
import { ChevronLeft } from "../components/icons";
import { inputClass } from "../components/fieldStyles";
import PrimaryButton from "../components/PrimaryButton";
import { t } from "../i18n";

type Props = {
  language: LanguageCode;
  onLoggedIn: (user: User) => void;
  /** Back to the start screen. */
  onCancel: () => void;
  /** Open on "create account" instead of "log in" (e.g. from the guest hint after the feedback) */
  startCreating?: boolean;
};


export default function AuthScreen({ language, onLoggedIn, onCancel, startCreating = false }: Props) {
  const text = t(language);

  const [creating, setCreating] = useState(startCreating); // false = log in, true = create account
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
                : errorText(err, text),
      );
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-dvh flex-col bg-page">
      <header className="bg-brand px-4 pt-safe-5 pb-14 text-white">
        <div className="mx-auto max-w-lg">
        <div className="flex items-center gap-2">
          <button
            onClick={onCancel}
            aria-label={text.back}
            className="-ml-2 flex h-11 w-11 items-center justify-center rounded-full hover:bg-brand-dark"
          >
            <ChevronLeft />
          </button>
          <h1 className="text-3xl font-bold tracking-tight">
            {creating ? text.register : text.login}
            <span className="text-logo-yellow">.</span>
          </h1>
        </div>
        <p className="mt-3 text-base text-white">{text.loginIntro}</p>
        </div>
      </header>

      <main className="mx-auto -mt-7 w-full max-w-lg flex-1 px-4 pb-safe-6">
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

          {error && <Alert>{error}</Alert>}

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
