import { useEffect, useState } from "react";
import {
  api,
  type AppConfig,
  type CreateSessionRequest,
  type CreateSessionResponse,
  type InterviewerStyle,
  type LanguageCode,
  type Mode,
} from "../api";
import CardAccent from "../components/CardAccent";
import { ArrowRight, Check, ChevronDown } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import { label, languageNames, t } from "../i18n";

type Props = {
  language: LanguageCode;
  onLanguageChange: (lang: LanguageCode) => void;
  /** `summary` is the line shown in the chat header, e.g. "Schreiner/in EFZ · Deutsch · Training". */
  onStarted: (session: CreateSessionResponse, request: CreateSessionRequest, summary: string) => void;
};

export default function SetupScreen({ language, onLanguageChange, onStarted }: Props) {
  const text = t(language);

  // Data from GET /config
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [loadError, setLoadError] = useState(false);

  // Form fields
  const [occupationId, setOccupationId] = useState("");
  const [style, setStyle] = useState<InterviewerStyle>("friendly");
  const [mode, setMode] = useState<Mode>("training");
  const [firstName, setFirstName] = useState("");
  const [schoolLevel, setSchoolLevel] = useState("");
  const [interests, setInterests] = useState("");

  // Start button
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState(false);

  function loadConfig() {
    api
      .getConfig()
      .then((c) => {
        setConfig(c);
        // Preselect the first occupation so the start button works right away
        setOccupationId((current) => current || c.occupations[0]?.id || "");
      })
      .catch(() => setLoadError(true));
  }

  function retryLoadConfig() {
    setLoadError(false);
    loadConfig();
  }

  useEffect(loadConfig, []);

  async function handleStart() {
    if (!config) return;
    const request: CreateSessionRequest = {
      language,
      occupation_id: occupationId,
      interviewer_style: style,
      mode,
      candidate: {
        first_name: firstName.trim() || undefined,
        school_level: schoolLevel.trim() || undefined,
        interests: interests.trim() || undefined,
      },
    };
    const occupation = config.occupations.find((o) => o.id === occupationId);
    const summary = [occupation ? label(occupation.label, language) : "", languageNames[language], text.modes[mode]]
      .filter(Boolean)
      .join(" · ");

    setStarting(true);
    setStartError(false);
    try {
      const session = await api.createSession(request);
      onStarted(session, request, summary);
    } catch {
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
          <h1 className="text-4xl font-bold tracking-tight">
            {text.title}
            <span className="text-logo-yellow">.</span>
          </h1>
          <p className="mt-2 text-lg leading-snug text-white/90">{text.subtitle}</p>
        </div>
      </header>

      <main className="mx-auto -mt-7 w-full max-w-lg flex-1 px-4">
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
          </Step>

          <Step number="2" chip="red" title={text.occupation}>
            <div className="relative">
              <select
                value={occupationId}
                onChange={(e) => setOccupationId(e.target.value)}
                className={`${inputClass} appearance-none pr-12`}
              >
                {config.occupations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {label(o.label, language)}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute top-1/2 right-5 h-5 w-5 -translate-y-1/2" />
            </div>
          </Step>

          <Step number="3" chip="blue" title={`${text.style} & ${text.mode}`}>
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
            number="4"
            chip="teal"
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
      </main>

      {/* Start bar: always visible at the bottom */}
      <footer className="sticky bottom-0 bg-gradient-to-t from-page via-page to-transparent px-4 pt-6 pb-4">
        <div className="mx-auto max-w-lg">
          {startError && <p className="mb-3 rounded-xl bg-danger-lighter px-4 py-3 text-danger">{text.error}</p>}
          <PrimaryButton onClick={handleStart} disabled={!occupationId || starting} wide>
            {starting ? text.starting : text.start}
            {!starting && <ArrowRight />}
          </PrimaryButton>
          <p className="mt-3 text-center text-xs text-charcoal-soft">{text.startHint}</p>
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
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="block">
      <span className="mb-2 block text-sm font-bold">{label}</span>
      <input value={value} onChange={(e) => onChange(e.target.value)} placeholder={placeholder} className={inputClass} />
    </label>
  );
}
