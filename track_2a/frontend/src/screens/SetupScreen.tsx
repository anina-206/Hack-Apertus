import { useEffect, useState } from "react";
import {
  api,
  ApiError,
  type AppConfig,
  type Dialect,
  type CreateSessionRequest,
  type CreateSessionResponse,
  type InterviewerStyle,
  type InterviewListItem,
  type LanguageCode,
  type Mode,
  type User,
} from "../api";
import CardAccent from "../components/CardAccent";
import { ArrowRight, Check } from "../components/icons";
import OccupationPicker from "../components/OccupationPicker";
import type { Lehrberuf } from "../data/lehrberufe";
import PrimaryButton from "../components/PrimaryButton";
import { unlockAudio } from "../audio";
import { fromServer, type SavedInterview } from "../history";
import { label, languageNames, t } from "../i18n";
import { occupationLabel } from "../occupation";

type Props = {
  language: LanguageCode;
  onLanguageChange: (lang: LanguageCode) => void;
  /** `summary` is the line shown in the chat header, e.g. "Schreiner/in EFZ · Deutsch · Training". */
  onStarted: (session: CreateSessionResponse, request: CreateSessionRequest, summary: string) => void;
  /** A saved interview was clicked. */
  onOpenSaved: (entry: SavedInterview) => void;
  /** Logged-in user, or null for a guest. */
  user: User | null;
  onLoginClick: () => void;
  onLogout: () => void;
};

export default function SetupScreen({ language, onLanguageChange, onStarted, onOpenSaved, user, onLoginClick, onLogout }: Props) {
  const text = t(language);

  // Data from GET /config
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loadError, setLoadError] = useState(false);

  // Interviews of the logged-in user, saved on the backend
  const [remote, setRemote] = useState<InterviewListItem[]>([]);

  // "Delete account" panel
  const [deleting, setDeleting] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    api
      .listInterviews()
      .then((list) => !cancelled && setRemote(list))
      .catch(() => !cancelled && setRemote([]));
    return () => {
      cancelled = true;
    };
  }, [user]);

  // Form fields
  const [occupation, setOccupation] = useState<Lehrberuf | null>(null);
  const [style, setStyle] = useState<InterviewerStyle>("friendly");
  const [mode, setMode] = useState<Mode>("training");
  const [dialect, setDialect] = useState<Dialect>("zh");
  const [firstName, setFirstName] = useState("");
  const [schoolLevel, setSchoolLevel] = useState("");
  const [interests, setInterests] = useState("");

  // The uploaded application: its text (sent when the interview starts) and what to show
  const [application, setApplication] = useState<{ filename: string; text: string; truncated: boolean } | null>(null);
  const [applicationState, setApplicationState] = useState<"idle" | "reading" | "error">("idle");
  // ... or the letter pasted as text
  const [showPaste, setShowPaste] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const applicationText = application?.text ?? (pastedText.trim() || undefined);

  // Start button
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(false);

  function loadConfig() {
    api
      .getConfig()
      .then(setConfig)
      .catch(() => setLoadError(true));
  }

  function retryLoadConfig() {
    setLoadError(false);
    loadConfig();
  }

  useEffect(loadConfig, []);

  /** The apprenticeships the backend knows (with a company) match by name; all others are sent by name only. */
  function knownOccupation(o: Lehrberuf) {
    const wanted = occupationLabel(o).toLowerCase();
    return config?.occupations.find((k) => (k.label.de ?? "").toLowerCase() === wanted);
  }

  function summaryOf(occupationId: string, occupationName: string | null | undefined, lang: LanguageCode, m: Mode) {
    const known = config?.occupations.find((o) => o.id === occupationId);
    const name = occupationName || (known ? label(known.label, lang) : "");
    return [name, languageNames[lang], t(lang).modes[m]].filter(Boolean).join(" · ");
  }

  async function openRemote(item: InterviewListItem) {
    try {
      const detail = await api.getSavedInterview(item.session_id);
      onOpenSaved(fromServer(detail, summaryOf(item.occupation_id, item.occupation_name, item.language, item.mode)));
    } catch {
      setStartError(true);
    }
  }

  async function handleApplicationFile(file: File | undefined) {
    if (!file) return;
    setApplicationState("reading");
    try {
      const result = await api.extractApplication(file);
      setApplication({ filename: result.filename || file.name, text: result.text, truncated: result.truncated });
      setApplicationState("idle");
    } catch {
      setApplication(null);
      setApplicationState("error");
    }
  }

  async function handleDeleteInterview(sessionId: string) {
    if (!window.confirm(text.deleteInterviewConfirm)) return;
    try {
      await api.deleteInterview(sessionId);
      setRemote((list) => list.filter((item) => item.session_id !== sessionId));
    } catch {
      setStartError(true);
    }
  }

  async function handleDeleteAccount() {
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await api.deleteAccount(deletePassword);
      onLogout(); // the account is gone: forget the login in this browser too
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "";
      setDeleteError(
        code === "INVALID_CREDENTIALS"
          ? text.wrongPassword
          : code === "TOO_MANY_REQUESTS"
            ? text.tooManyRequests
            : text.error,
      );
      setDeleteBusy(false);
    }
  }

  async function handleStart() {
    if (!config || !user || !occupation) return;
    unlockAudio(); // a tap: lets the interviewer's voice play on phones later
    const known = knownOccupation(occupation);
    const request: CreateSessionRequest = {
      language,
      // The German name: the backend looks it up in its occupation data (tasks, duration, requirements)
      ...(known ? { occupation_id: known.id } : { occupation_name: occupationLabel(occupation) }),
      interviewer_style: style,
      mode,
      dialect: language === "gsw" ? dialect : undefined,
      candidate: {
        first_name: firstName.trim() || undefined,
        school_level: schoolLevel.trim() || undefined,
        interests: interests.trim() || undefined,
      },
      application_text: applicationText,
    };
    const summary = summaryOf(known?.id ?? "", known ? undefined : occupationLabel(occupation, language), language, mode);

    setStarting(true);
    setStartError(false);
    try {
      const session = await api.createSession(request);
      onStarted(session, request, summary);
    } catch (err) {
      if (err instanceof ApiError && err.code === "UNAUTHORIZED") {
        // The login expired: forget it and ask for a new one
        onLogout();
        onLoginClick();
        return;
      }
      setStartError(true);
      setStarting(false);
    }
  }

  if (loadError) {
    return (
      <Centered>
        <p className="mb-4 text-danger">{text.error}</p>
        <PrimaryButton onClick={retryLoadConfig}>{text.retry}</PrimaryButton>
      </Centered>
    );
  }

  if (!config) {
    return (
      <Centered>
        <div className="mb-3 h-8 w-8 animate-spin rounded-full border-4 border-brand-light border-t-brand" />
        <p className="text-charcoal-soft">{text.loading}</p>
      </Centered>
    );
  }

  return (
    <div className="flex min-h-dvh flex-col">
      {/* Blue header */}
      <header className="bg-brand px-5 pt-10 pb-14 text-white">
        <div className="mx-auto max-w-lg">
          <div className="mb-4 flex items-center justify-end gap-3 text-sm">
            {user && <span className="truncate text-white/90">{user.username}</span>}
            {user && (
              <button onClick={() => setDeleting(true)} className="font-bold text-white/80 underline hover:text-white">
                {text.deleteAccount}
              </button>
            )}
            <button
              onClick={user ? onLogout : onLoginClick}
              className="rounded-full border-2 border-white/80 px-4 py-1.5 font-bold hover:bg-white/10"
            >
              {user ? text.logout : text.login}
            </button>
          </div>
          <h1 className="text-4xl font-bold tracking-tight">
            {text.title}
            <span className="text-logo-yellow">.</span>
          </h1>
          <p className="mt-2 text-lg leading-snug text-white/90">{text.subtitle}</p>
        </div>
      </header>

      <main className="mx-auto -mt-7 w-full max-w-lg flex-1 px-4">
        {user && deleting && (
          <div className="relative z-10 mb-4 rounded-2xl bg-white p-4 shadow-card">
            <p className="mb-3 text-sm">{text.deleteAccountWhy}</p>
            <input
              type="password"
              value={deletePassword}
              onChange={(e) => setDeletePassword(e.target.value)}
              placeholder={text.password}
              autoComplete="current-password"
              className={inputClass}
            />
            {deleteError && <p className="mt-3 rounded-xl bg-danger-lighter px-4 py-2 text-sm text-danger">{deleteError}</p>}
            <div className="mt-3 flex gap-2">
              <button
                onClick={handleDeleteAccount}
                disabled={!deletePassword || deleteBusy}
                className="flex-1 rounded-full bg-danger px-4 py-2.5 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {deleteBusy ? text.pleaseWait : text.deleteAccountConfirm}
              </button>
              <button
                onClick={() => {
                  setDeleting(false);
                  setDeletePassword("");
                  setDeleteError(null);
                }}
                className="rounded-full border-2 border-line px-4 py-2.5 text-sm font-bold"
              >
                {text.cancel}
              </button>
            </div>
          </div>
        )}

        {!user && (
          <div className="relative z-10 mb-4 rounded-2xl border-2 border-logo-yellow bg-white p-4 shadow-card">
            <p className="font-bold">{text.loginRequired}</p>
            <p className="mt-1 text-sm text-charcoal-soft">{text.loginRequiredWhy}</p>
            <button
              onClick={onLoginClick}
              className="mt-3 rounded-full bg-brand px-5 py-2 text-sm font-bold text-white hover:bg-brand-dark"
            >
              {text.login} / {text.register}
            </button>
          </div>
        )}

        <div className="relative divide-y divide-line overflow-hidden rounded-3xl bg-white shadow-card">
          <CardAccent />

          <Step number="1" chip="yellow" title={text.language}>
            <div className="grid grid-cols-2 gap-3">
              {config.languages.map((l) => (
                <Choice key={l.code} selected={language === l.code} onClick={() => onLanguageChange(l.code)}>
                  {languageNames[l.code]}
                  {l.code === "gsw" && (
                    <span className="ml-2 rounded-full bg-beta-bg px-2 py-0.5 text-xs font-bold text-beta-text">
                      {text.beta}
                    </span>
                  )}
                </Choice>
              ))}
            </div>
            {language === "gsw" && config.dialects && (
              <div className="mt-4">
                <p className="mb-2 text-sm font-bold">{text.dialect}</p>
                <div className="grid grid-cols-2 gap-3">
                  {config.dialects.map((d) => (
                    <Choice key={d.code} selected={dialect === d.code} onClick={() => setDialect(d.code)}>
                      {label(d.label, language)}
                    </Choice>
                  ))}
                </div>
                <p className="mt-2 text-sm text-charcoal-soft">{text.dialectHint}</p>
              </div>
            )}
          </Step>

          <Step number="2" chip="red" title={text.occupation}>
            <OccupationPicker
              language={language}
              value={occupation}
              onChange={setOccupation}
              placeholder={text.occupationSearch}
              noResults={text.occupationNone}
              className={inputClass}
            />
            <p className="mt-2 text-sm text-charcoal-soft">{text.occupationHint}</p>
          </Step>

          <Step
            number="3"
            chip="blue"
            title={
              <>
                {text.application} <span className="font-normal text-charcoal-soft">{text.optional}</span>
              </>
            }
          >
            <p className="mb-3 -mt-2 text-sm text-charcoal-soft">{text.applicationHint}</p>
            {application ? (
              <div className="flex items-center gap-3 rounded-2xl bg-mint-lighter px-4 py-3 text-mint-dark">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-logo-teal text-white">
                  <Check className="h-4 w-4" />
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate font-bold">{application.filename}</p>
                  <p className="text-sm">
                    {application.text.length} {text.applicationChars} {text.applicationRead}
                    {application.truncated && ` · ${text.applicationTruncated}`}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setApplication(null)}
                  className="shrink-0 text-sm font-bold underline"
                >
                  {text.applicationRemove}
                </button>
              </div>
            ) : (
              <label
                className={`flex min-h-12 cursor-pointer items-center justify-center rounded-full border-2 border-dashed border-line bg-white px-5 py-3 text-base font-bold text-brand hover:border-brand-light ${
                  applicationState === "reading" ? "pointer-events-none opacity-60" : ""
                }`}
              >
                {applicationState === "reading" ? text.applicationReading : text.applicationChoose}
                <input
                  type="file"
                  accept=".pdf,.docx,.txt,.md"
                  className="sr-only"
                  onChange={(e) => {
                    handleApplicationFile(e.target.files?.[0]);
                    e.target.value = ""; // the same file can be chosen again after an error
                  }}
                />
              </label>
            )}
            {!application && (
              <div className="mt-3">
                <button
                  type="button"
                  onClick={() => setShowPaste(!showPaste)}
                  aria-expanded={showPaste}
                  className="text-sm font-bold text-brand"
                >
                  {showPaste ? text.applicationPasteHide : text.applicationPaste}
                </button>
                {showPaste && (
                  <div className="mt-3">
                    <TextArea
                      label=""
                      value={pastedText}
                      onChange={setPastedText}
                      placeholder={text.applicationPastePlaceholder}
                      maxLength={8000}
                      rows={8}
                    />
                  </div>
                )}
              </div>
            )}
            {applicationState === "error" && (
              <p className="mt-3 rounded-xl bg-danger-lighter px-4 py-2 text-sm text-danger">{text.applicationError}</p>
            )}
            <p className="mt-3 text-xs text-charcoal-soft">{text.applicationPrivacy}</p>
          </Step>

          <Step number="4" chip="teal" title={`${text.style} & ${text.mode}`}>
            <p className="mb-2 text-sm font-bold">{text.styleQuestion}</p>
            <div className="grid grid-cols-2 gap-3">
              {config.interviewer_styles.map((s) => (
                <Choice key={s.id} selected={style === s.id} onClick={() => setStyle(s.id)}>
                  {label(s.label, language)}
                </Choice>
              ))}
            </div>

            <p className="mt-4 mb-2 text-sm font-bold">{text.modeQuestion}</p>
            <div className="grid grid-cols-2 gap-3">
              {config.modes.map((m) => (
                <Choice key={m.id} selected={mode === m.id} onClick={() => setMode(m.id)}>
                  {text.modes[m.id]}
                </Choice>
              ))}
            </div>

            <div className="mt-4 flex items-center gap-3 rounded-xl bg-mint-lighter px-3 py-3 text-sm text-mint-dark">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-logo-teal text-white">
                <Check className="h-4 w-4" />
              </span>
              {text.modeHints[mode]}
            </div>
          </Step>

          <Step
            number="5"
            chip="yellow"
            title={
              <>
                {text.profile} <span className="font-normal text-charcoal-soft">{text.optional}</span>
              </>
            }
          >
            <p className="mb-4 -mt-2 text-sm text-charcoal-soft">{text.profileHint}</p>
            <div className="space-y-4">
              <TextField
                label={text.firstName}
                value={firstName}
                onChange={setFirstName}
                placeholder={text.firstNamePlaceholder}
              />
              <TextField
                label={text.schoolLevel}
                value={schoolLevel}
                onChange={setSchoolLevel}
                placeholder={text.schoolLevelPlaceholder}
              />
              <TextField
                label={text.interests}
                value={interests}
                onChange={setInterests}
                placeholder={text.interestsPlaceholder}
              />
            </div>
          </Step>
        </div>

        {user && remote.length > 0 && (
          <section className="mt-6 pb-4">
            <h2 className="mb-3 text-xl font-bold">{text.previousInterviews}</h2>
            <ul className="space-y-2">
              {remote.map((item) => (
                <li key={item.session_id} className="flex items-center gap-2 rounded-2xl bg-white shadow-card">
                  <button onClick={() => openRemote(item)} className="min-w-0 flex-1 px-4 py-3 text-left">
                    <p className="truncate font-bold">
                      {summaryOf(item.occupation_id, item.occupation_name, item.language, item.mode)}
                      {item.overall_score !== null && " · Ø " + item.overall_score}
                    </p>
                    <p className="text-sm text-charcoal-soft">
                      {new Date(item.created_at).toLocaleString(language === "gsw" ? "de-CH" : language)}
                      {!item.done && " · " + text.inProgress}
                    </p>
                  </button>
                  <button
                    onClick={() => handleDeleteInterview(item.session_id)}
                    className="mr-3 shrink-0 rounded-full px-3 py-1.5 text-sm font-bold text-danger hover:bg-danger-lighter"
                  >
                    {text.deleteInterview}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

      </main>

      {/* Start bar: always visible at the bottom */}
      <footer className="sticky bottom-0 bg-gradient-to-t from-page via-page to-transparent px-4 pt-6 pb-4">
        <div className="mx-auto max-w-lg">
          {startError && <p className="mb-3 rounded-xl bg-danger-lighter px-4 py-3 text-danger">{text.error}</p>}
          {user ? (
            <PrimaryButton onClick={handleStart} disabled={!occupation || starting} wide>
              {starting ? text.starting : text.start}
              {!starting && <ArrowRight />}
            </PrimaryButton>
          ) : (
            <PrimaryButton onClick={onLoginClick} wide>
              {text.loginToStart}
              <ArrowRight />
            </PrimaryButton>
          )}
          <p className="mt-3 text-center text-xs text-charcoal-soft">
            {user && !occupation ? text.fillRequired : text.startHint}
          </p>
        </div>
      </footer>
    </div>
  );
}

// ---------- small building blocks ----------

const inputClass =
  "w-full rounded-full border-2 border-line bg-white px-5 py-3.5 text-base text-charcoal placeholder:text-charcoal/40 focus:border-brand focus:outline-none";

// Number chips in the colours of the four Profolio logo cards. Full class names so Tailwind finds them.
const chipStyle = {
  yellow: "bg-logo-yellow text-charcoal",
  red: "bg-logo-red text-white",
  blue: "bg-logo-blue text-white",
  teal: "bg-logo-teal text-white",
};

function Centered({ children }: { children: React.ReactNode }) {
  return <main className="flex min-h-dvh flex-col items-center justify-center px-5 text-center">{children}</main>;
}

/** A numbered block of the form: a small tilted coloured square with the number, the title, then the content. */
function Step({
  number,
  chip,
  title,
  children,
}: {
  number: string;
  chip: keyof typeof chipStyle;
  title: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="px-5 py-6">
      <h2 className="mb-4 flex items-center gap-3 text-xl font-bold">
        <span className={`flex h-8 w-8 -rotate-6 items-center justify-center rounded-lg text-base font-bold ${chipStyle[chip]}`}>
          {number}
        </span>
        <span>{title}</span>
      </h2>
      {children}
    </section>
  );
}

/** Selectable pill. The selected one is filled blue. */
function Choice({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex min-h-12 items-center justify-center rounded-full border-2 px-3 py-2.5 text-base transition ${
        selected
          ? "border-brand bg-brand font-bold text-white"
          : "border-line bg-white font-medium text-charcoal hover:border-brand-light"
      }`}
    >
      {children}
    </button>
  );
}

function TextField({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength?: number;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-bold">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      <input
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        className={inputClass}
      />
    </label>
  );
}

/** Several lines of text, e.g. the pasted application letter. */
function TextArea({
  label,
  value,
  onChange,
  placeholder,
  maxLength,
  rows = 3,
  required,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  maxLength: number;
  rows?: number;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-bold">
        {label}
        {required && <span className="text-danger"> *</span>}
      </span>
      <textarea
        required={required}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        maxLength={maxLength}
        rows={rows}
        className="w-full resize-y rounded-3xl border-2 border-line bg-white px-5 py-3.5 text-base text-charcoal placeholder:text-charcoal/40 focus:border-brand focus:outline-none"
      />
      <span className="mt-1 block text-right text-xs text-charcoal-soft">
        {value.length}/{maxLength}
      </span>
    </label>
  );
}
