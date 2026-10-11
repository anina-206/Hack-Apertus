import { useEffect, useState } from "react";
import { api, type CriterionId, type LanguageCode, type Report } from "../api";
import { Check, ChevronLeft } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import { t } from "../i18n";
import { useFocusHeading } from "../useFocusHeading";

type Props = {
  sessionId: string;
  language: LanguageCode;
  /** Report saved earlier: shown right away, no new request. */
  savedReport?: Report;
  /** Called once a freshly loaded report is there, so it can be saved. */
  onReportLoaded: (report: Report) => void;
  onRestart: () => void;
  /** Start a new interview with the same settings that practises these criteria (not available for opened old ones) */
  onPracticeAgain?: (focus: CriterionId[]) => Promise<void>;
};

/**
 * Order of the screen (coach first, numbers second):
 * 1. closing sentence + strengths, 2. overall level, 3. each criterion with its comment,
 * 4. tips, 5. what to practise next.
 */
export default function FeedbackScreen({
  sessionId,
  language,
  savedReport,
  onReportLoaded,
  onRestart,
  onPracticeAgain,
}: Props) {
  const text = t(language);
  const headingRef = useFocusHeading<HTMLHeadingElement>();
  const [starting, setStarting] = useState(false);

  async function practiceAgain(focus: CriterionId[]) {
    setStarting(true);
    try {
      await onPracticeAgain?.(focus);
    } catch {
      setStarting(false);
      setError(true);
    }
  }

  const [report, setReport] = useState<Report | null>(savedReport ?? null);
  const [error, setError] = useState(false);

  // Bumping this number loads the report again (retry button)
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (report) return;
    let cancelled = false;
    api
      .getReport(sessionId)
      .then((r) => {
        if (cancelled) return;
        setReport(r);
        onReportLoaded(r);
      })
      .catch(() => !cancelled && setError(true));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, attempt]);

  function retry() {
    setError(false);
    setAttempt((n) => n + 1);
  }

  // Only observed criteria get a row; the others (score null) are listed below.
  // Criterion names come from our own texts, so they match the UI language.
  const observed = report?.criteria.filter((c) => c.score !== null) ?? [];
  const notObserved = report?.criteria.filter((c) => c.score === null) ?? [];
  const scaleMax = report?.scale?.max ?? 4;
  // The overall score is an average (e.g. 2.8); a teenager reads the nearest level better than a decimal
  const overall = report?.overall_score != null ? Math.round(report.overall_score) : null;

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-lg flex-col bg-page">
      <header className="bg-brand px-4 pt-5 pb-12 text-white">
        <div className="flex items-center gap-2">
          <button
            onClick={onRestart}
            aria-label={text.back}
            className="-ml-2 flex h-11 w-11 items-center justify-center rounded-full hover:bg-white/10"
          >
            <ChevronLeft />
          </button>
          <h1 ref={headingRef} tabIndex={-1} className="flex-1 text-3xl font-bold tracking-tight outline-none">
            {text.feedbackScreenTitle}
            <span className="text-logo-yellow">.</span>
          </h1>
        </div>
      </header>

      <main className="relative z-10 -mt-8 space-y-4 px-4 pb-10">
        {!report && !error && (
          <Card>
            <div role="status" className="flex flex-col items-center py-6 text-center">
              <LogoCards />
              <p className="mt-6 text-lg font-bold">{text.loadingReport}</p>
              <p className="mt-1 text-charcoal-soft">{text.loadingReportHint}</p>
            </div>
            {/* Shape of what is coming, so the page does not feel empty */}
            <div className="mt-2 space-y-3" aria-hidden="true">
              {[80, 64, 72].map((w) => (
                <div key={w} className="h-3 animate-pulse rounded-full bg-page motion-reduce:animate-none" style={{ width: `${w}%` }} />
              ))}
            </div>
          </Card>
        )}

        {error && (
          <Card>
            <p role="alert" className="mb-4 rounded-xl bg-danger-lighter px-3 py-2 text-sm text-danger">
              {text.error}
            </p>
            <PrimaryButton onClick={retry} wide>
              {text.retry}
            </PrimaryButton>
          </Card>
        )}

        {report && (
          <>
            {/* Where to get help (FHGR rule L3), only when the interview showed distress */}
            {report.support_note && (
              <Card>
                <h2 className="mb-2 text-xl font-bold">{text.supportTitle}</h2>
                <p>{report.support_note}</p>
              </Card>
            )}

            {/* 1 + 2: the coach speaks first, the overall level comes after the strengths */}
            <Card>
              {report.closing && <p className="text-xl leading-snug font-bold text-balance">{report.closing}</p>}

              {report.strengths.length > 0 && (
                <>
                  <h2 className={`${report.closing ? "mt-6" : ""} mb-3 text-lg font-bold`}>{text.strengthsTitle}</h2>
                  <ul className="space-y-2.5">
                    {report.strengths.map((s) => (
                      <li key={s} className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 -rotate-6 items-center justify-center rounded-md bg-mint-dark text-white">
                          <Check className="h-4 w-4" />
                        </span>
                        {s}
                      </li>
                    ))}
                  </ul>
                </>
              )}

              {overall !== null && (
                <div className="mt-6 flex items-center justify-between gap-4 border-t border-line pt-4">
                  <span className="text-charcoal-soft">{text.overall}</span>
                  <span className="flex items-center gap-3">
                    <LevelMeter score={overall} max={scaleMax} />
                    <span>
                      <span className="font-bold">{text.levels[overall - 1]}</span>
                      <span className="text-charcoal-soft"> · {overall} {text.outOf}</span>
                    </span>
                  </span>
                </div>
              )}
            </Card>

            {/* 3: each criterion with its level, comment and the quote it is based on */}
            {observed.length > 0 && (
              <Card>
                <h2 className="text-xl font-bold">{text.scoresTitle}</h2>
                <p className="mt-1 text-sm text-charcoal-soft">
                  {text.scale}: {text.levels.map((l, i) => `${i + 1} ${l}`).join(" · ")}
                </p>
                <ul className="mt-4 divide-y divide-line">
                  {observed.map((c) => (
                    <li key={c.id} className="py-4 first:pt-0 last:pb-0">
                      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                        <h3 className="font-bold">{text.criteria[c.id] ?? c.label}</h3>
                        <span className="flex items-center gap-2 text-sm">
                          <LevelMeter score={c.score ?? 0} max={scaleMax} />
                          <span className="font-bold">{text.levels[(c.score ?? 1) - 1]}</span>
                          <span className="sr-only">
                            ({c.score} {text.outOf})
                          </span>
                        </span>
                      </div>
                      {/* The backend can leave a comment empty; then only the level is shown */}
                      {c.comment?.trim() && <p className="mt-1.5 text-sm">{c.comment}</p>}
                      {/* The quote the score is based on (FHGR rule K1), only real quotes come from the backend */}
                      {c.evidence && (
                        <p className="mt-2 rounded-lg bg-page px-3 py-2 text-sm text-charcoal-soft">
                          <span className="font-bold">{text.youSaid}:</span> «{c.evidence}»
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
                {notObserved.length > 0 && (
                  <div className="mt-4 rounded-xl bg-page px-4 py-3 text-sm">
                    <p>
                      <span className="font-bold">{text.notObserved}:</span>{" "}
                      {notObserved.map((c) => text.criteria[c.id] ?? c.label).join(", ")}
                    </p>
                    <p className="mt-1 text-charcoal-soft">{text.notObservedHint}</p>
                  </div>
                )}
              </Card>
            )}

            {/* 4: tips */}
            {report.improvements.length > 0 && (
              <Card>
                <h2 className="mb-3 text-xl font-bold">{text.improvementsTitle}</h2>
                <ul className="space-y-3">
                  {report.improvements.map((item) => (
                    <li key={item.tip} className="rounded-xl bg-mint-lighter px-4 py-3 text-mint-dark">
                      <p className="font-bold">{item.tip}</p>
                      {item.example_answer && (
                        <p className="mt-1 text-sm">
                          <span className="font-bold">{text.exampleAnswer}:</span> {item.example_answer}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            {/* 5: next practice */}
            {report.next_practice.length > 0 && (
              <Card>
                <h2 className="mb-3 text-xl font-bold">{text.nextPracticeTitle}</h2>
                <div className="flex flex-wrap gap-2">
                  {report.next_practice.map((id) => (
                    <span key={id} className="rounded-full bg-brand-lighter px-3 py-1.5 text-sm font-bold text-brand-dark">
                      {text.criteria[id]}
                    </span>
                  ))}
                </div>
                {onPracticeAgain && (
                  <div className="mt-4">
                    <PrimaryButton onClick={() => practiceAgain(report.next_practice)} disabled={starting} wide>
                      {starting ? text.starting : text.practiceThis}
                    </PrimaryButton>
                  </div>
                )}
              </Card>
            )}

            {/* With "practise this" there is already a main button; then a new interview is the quieter choice */}
            <div className="text-center">
              {onPracticeAgain && report.next_practice.length > 0 ? (
                <button
                  onClick={onRestart}
                  className="min-h-11 rounded-full px-5 font-bold text-brand-dark underline underline-offset-4 hover:text-brand"
                >
                  {text.newInterview}
                </button>
              ) : (
                <PrimaryButton onClick={onRestart}>{text.newInterview}</PrimaryButton>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <section className="rounded-2xl bg-white p-5 shadow-card">{children}</section>;
}

/** Four small segments, one per level, filled up to the score. Decorative: the level word next to it says the same. */
function LevelMeter({ score, max }: { score: number; max: number }) {
  return (
    <span className="flex gap-1" aria-hidden="true">
      {Array.from({ length: max }, (_, i) => (
        <span key={i} className={`h-2.5 w-4 rounded-sm ${i < score ? "bg-brand" : "bg-line"}`} />
      ))}
    </span>
  );
}

/** The four Profolio logo cards, lifting one after the other: "someone is writing". */
function LogoCards() {
  const cards = [
    { color: "bg-logo-yellow", tilt: "-8deg" },
    { color: "bg-logo-red", tilt: "6deg" },
    { color: "bg-logo-blue", tilt: "-4deg" },
    { color: "bg-logo-teal", tilt: "8deg" },
  ];
  return (
    <div className="flex gap-2" aria-hidden="true">
      {cards.map((c, i) => (
        <span
          key={c.color}
          className={`h-10 w-8 rounded-md ${c.color} animate-card-lift shadow-card motion-reduce:animate-none`}
          style={{ "--tilt": c.tilt, transform: `rotate(${c.tilt})`, animationDelay: `${i * 0.15}s` } as React.CSSProperties}
        />
      ))}
    </div>
  );
}
