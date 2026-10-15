import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { api, type CriterionId, type LanguageCode, type Report } from "../api";
import Alert from "../components/Alert";
import Card from "../components/Card";
import { ArrowRight, Chart, Check, ChevronLeft, Lightbulb } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import TextButton from "../components/TextButton";
import { locale, t, type UiTexts } from "../i18n";
import { errorText, isSessionGone } from "../errors";
import { useFocusHeading } from "../useFocusHeading";
import { usePrefersReducedMotion } from "../usePrefersReducedMotion";

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
  /** The report before "practise this": criteria that got better are celebrated */
  previousReport?: Report;
  /** Guests only: this interview was not saved, offer an account for the next ones */
  onCreateAccount?: () => void;
};

/** Bar colour by FHGR level (1-4): 3-4 Gut/Sehr gut = teal, 2 Ausbaufähig = yellow, 1 Ungenügend = red. */
function scoreColor(score: number) {
  if (score >= 3) return "var(--color-logo-teal)";
  if (score >= 2) return "var(--color-logo-yellow)";
  return "var(--color-logo-red)";
}

/** A score as a whole FHGR level 1-4 (the levels have names, so 2.6 or 7 cannot be shown as they are). */
function toLevel(score: number, max: number) {
  return Math.min(Math.max(1, Math.round(score)), Math.min(max, 4));
}

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
  previousReport,
  onCreateAccount,
}: Props) {
  const text = t(language);
  const headingRef = useFocusHeading<HTMLHeadingElement>();
  const [starting, setStarting] = useState(false);

  async function practiceAgain(focus: CriterionId[]) {
    setStarting(true);
    try {
      await onPracticeAgain?.(focus);
    } catch (err) {
      setStarting(false);
      setError(errorText(err, text));
    }
  }

  const [report, setReport] = useState<Report | null>(savedReport ?? null);
  /** Why the report could not be loaded, or null */
  const [error, setError] = useState<string | null>(null);
  /** The server forgot this interview: trying again cannot help */
  const [gone, setGone] = useState(false);

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
      .catch((err) => {
        if (cancelled) return;
        setError(errorText(err, text));
        setGone(isSessionGone(err));
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, attempt]);

  function retry() {
    setError(null);
    setAttempt((n) => n + 1);
  }

  // Only observed criteria get a row; the others (score null) are listed below.
  // Criterion names come from our own texts, so they match the UI language.
  // Scores are cleaned up first: the model could send 0, 5 or 2.5, the screen only knows the levels 1-4
  const observed = (report?.criteria ?? [])
    .filter((c) => c.score !== null)
    .map((c) => ({ ...c, score: toLevel(c.score ?? 1, report?.scale?.max ?? 4) }));
  const notObserved = report?.criteria.filter((c) => c.score === null) ?? [];
  const scaleMax = report?.scale?.max ?? 4;
  // The overall score is an average (e.g. 2.8): the level pill shows the nearest level, the number stays exact
  // (otherwise 2.4 reads as "2 von 4" although most criteria are "Gut")
  const overall = report?.overall_score != null ? toLevel(report.overall_score, scaleMax) : null;
  const reducedMotion = usePrefersReducedMotion();
  // Level per criterion last time; only real improvements are shown (no "worse than before")
  const before = new Map(
    (previousReport?.criteria ?? [])
      .filter((c) => c.score !== null)
      .map((c) => [c.id, toLevel(c.score ?? 1, previousReport?.scale?.max ?? 4)]),
  );
  const improved = observed.filter((c) => before.has(c.id) && c.score > (before.get(c.id) ?? 4));
  const chartData = observed.map((c) => ({ name: text.criteria[c.id] ?? c.label, score: c.score }));

  return (
    <div className="flex min-h-dvh flex-col bg-page">
      <header className="bg-brand px-4 pt-safe-5 pb-12 text-white">
        <div className="mx-auto flex max-w-lg items-center gap-2 lg:max-w-5xl">
          <button
            onClick={onRestart}
            aria-label={text.back}
            className="-ml-2 flex h-11 w-11 items-center justify-center rounded-full hover:bg-brand-dark"
          >
            <ChevronLeft />
          </button>
          <h1 ref={headingRef} tabIndex={-1} className="flex-1 text-3xl font-bold tracking-tight outline-none">
            {text.feedbackScreenTitle}
            <span className="text-logo-yellow">.</span>
          </h1>
        </div>
      </header>

      <main className="relative z-10 mx-auto -mt-8 flex w-full max-w-lg flex-col gap-4 px-4 pb-safe-10 lg:grid lg:max-w-5xl lg:grid-cols-2 lg:items-start lg:gap-6">
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
            <Alert className="mb-4">
              {error}
            </Alert>
            {gone ? (
              <PrimaryButton onClick={onRestart} wide>
                {text.newInterview}
              </PrimaryButton>
            ) : (
              <PrimaryButton onClick={retry} wide>
                {text.retry}
              </PrimaryButton>
            )}
          </Card>
        )}

        {report && (
          <>
            {/* Left on wide screens: the coach. On phones these wrappers vanish (contents) and `order` sorts the cards. */}
            <div className="contents lg:flex lg:flex-col lg:gap-4">
              {/* Where to get help (FHGR rule L3), only when the interview showed distress */}
              {report.support_note && (
                <Card step={0}>
                  <h2 className="mb-2 text-xl font-bold">{text.supportTitle}</h2>
                  <p>{report.support_note}</p>
                </Card>
              )}

              {/* Nothing to show yet (very short interview): say so instead of an empty page */}
              {observed.length === 0 && report.strengths.length === 0 && (
                <Card step={0}>
                  <p className="text-lg">{text.emptyReport}</p>
                </Card>
              )}

              {/* 1 + 2: the coach speaks first, the overall level comes after the strengths */}
              {(report.closing || report.strengths.length > 0 || overall !== null) && (
                <Card step={0}>
                  {report.closing && <p className="text-xl leading-snug font-bold text-balance">{report.closing}</p>}

                  {/* Practised and got better: the first thing after the coach's sentence */}
                  {improved.length > 0 && (
                    <div className={`${report.closing ? "mt-5" : ""} rounded-xl bg-mint-lighter px-4 py-3 text-mint-dark`}>
                      <h2 className="mb-2 font-bold">{text.improvedTitle}</h2>
                      <ul className="space-y-2">
                        {improved.map((c, i) => (
                          <li key={c.id} className="flex flex-wrap items-center gap-x-2 gap-y-1">
                            <span className="font-bold">{text.criteria[c.id] ?? c.label}</span>
                            <span className="flex items-center gap-1.5 text-sm">
                              {text.levels[(before.get(c.id) ?? 1) - 1]}
                              <ArrowRight className="h-4 w-4" />
                              <span className="sr-only">→</span>
                              <span
                                className="inline-block -rotate-3 animate-stamp rounded-md bg-mint-dark px-2 py-0.5 font-bold text-white"
                                style={{ animationDelay: `${250 + i * 160}ms` }}
                              >
                                {text.levels[c.score - 1]}
                              </span>
                            </span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {report.strengths.length > 0 && (
                    <>
                      <SectionTitle chip="teal" icon={<Check className="h-4 w-4" />} className={report.closing || improved.length > 0 ? "mt-6 mb-3" : "mb-3"}>
                        {text.strengthsTitle}
                      </SectionTitle>
                      <ul className="space-y-2.5">
                        {report.strengths.map((s, i) => (
                          <li key={i} className="flex items-start gap-3 wrap-anywhere">
                            {/* The checks land one after the other, like stamps */}
                            <span
                              className="mt-0.5 flex h-6 w-6 shrink-0 -rotate-6 animate-stamp items-center justify-center rounded-md bg-mint-dark text-white"
                              style={{ animationDelay: `${300 + i * 140}ms` }}
                            >
                              <Check className="h-4 w-4" />
                            </span>
                            {s}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}

                  {overall !== null && (
                    <div className="mt-6 flex flex-wrap items-center justify-between gap-x-4 gap-y-2 border-t border-line pt-4">
                      <span className="text-charcoal-soft">{text.overall}</span>
                      <span className="flex items-center gap-3">
                        <LevelMeter score={overall} max={scaleMax} />
                        <span className="whitespace-nowrap">
                          <LevelPill score={overall} text={text} />
                          <span className="text-charcoal-soft">
                            {" "}
                            · {report.overall_score?.toLocaleString(locale(language))} {text.outOf}
                          </span>
                        </span>
                      </span>
                    </div>
                  )}
                </Card>
              )}

              {/* 4: tips */}
              {report.improvements.length > 0 && (
                <Card step={2} className="order-2">
                  <SectionTitle chip="yellow" icon={<Lightbulb className="h-4 w-4" />}>
                    {text.improvementsTitle}
                  </SectionTitle>
                  <ul className="space-y-3">
                    {report.improvements.map((item, i) => (
                      <li key={i} className="rounded-xl bg-logo-yellow-lighter px-4 py-3 text-logo-yellow-dark wrap-anywhere">
                        <p className="font-bold">{item.tip}</p>
                        {item.example_answer && (
                          <p className="mt-1">
                            <span className="font-bold">{text.exampleAnswer}:</span> {item.example_answer}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {/* Feedback on the uploaded application letter */}
              {report.application_feedback && (
                <Card step={3} className="order-2">
                  <SectionTitle chip="teal" icon={<Check className="h-4 w-4" />}>
                    {text.letterFeedbackTitle}
                  </SectionTitle>
                  <p className="mb-3 text-sm text-charcoal-soft">{text.letterFeedbackIntro}</p>
                  <ul className="space-y-4">
                    {report.application_feedback.criteria.map((c) => (
                      <li key={c.id} className="wrap-anywhere">
                        <div className="mb-1 flex items-center justify-between gap-3">
                          <span className="font-bold">{c.label}</span>
                          {c.score !== null && <LevelPill score={c.score} text={text} />}
                        </div>
                        {c.score !== null && <LevelMeter score={c.score} max={report.application_feedback?.scale.max ?? 4} />}
                        {c.comment && <p className="mt-1 text-sm">{c.comment}</p>}
                        {c.evidence && (
                          <p className="mt-1 border-l-2 border-line pl-2 text-sm text-charcoal-soft italic">«{c.evidence}»</p>
                        )}
                      </li>
                    ))}
                  </ul>

                  {report.application_feedback.strengths.length > 0 && (
                    <>
                      <h3 className="mt-5 mb-2 font-bold">{text.strengthsTitle}</h3>
                      <ul className="space-y-2">
                        {report.application_feedback.strengths.map((s) => (
                          <li key={s} className="flex items-start gap-3 wrap-anywhere">
                            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-mint-dark text-white">
                              <Check className="h-4 w-4" />
                            </span>
                            {s}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}

                  {report.application_feedback.improvements.length > 0 && (
                    <>
                      <h3 className="mt-5 mb-2 font-bold">{text.improvementsTitle}</h3>
                      <ul className="space-y-3">
                        {report.application_feedback.improvements.map((item) => (
                          <li key={item.tip} className="rounded-xl bg-logo-yellow-lighter px-4 py-3 text-logo-yellow-dark wrap-anywhere">
                            <p className="font-bold">{item.tip}</p>
                            {item.example_answer && (
                              <p className="mt-1">
                                <span className="font-bold">{text.exampleAnswer}:</span> {item.example_answer}
                              </p>
                            )}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </Card>
              )}

              {/* 5: next practice */}
              {report.next_practice.length > 0 && (
                <Card step={3} className="order-2">
                  <SectionTitle chip="red" icon={<ArrowRight className="h-4 w-4" />}>
                    {text.nextPracticeTitle}
                  </SectionTitle>
                  <div className="flex flex-wrap gap-2">
                    {report.next_practice.filter((id) => text.criteria[id]).map((id) => (
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

              {/* Guests: honest about saving, and one tap to an account */}
              {onCreateAccount && (
                <Card step={4} className="order-2">
                  <h2 className="text-lg font-bold">{text.guestSaveTitle}</h2>
                  <p className="mt-1 text-charcoal-soft">{text.guestSaveText}</p>
                  <button
                    onClick={onCreateAccount}
                    className="mt-4 min-h-11 rounded-full border-2 border-brand px-5 font-bold text-brand-dark transition hover:bg-brand-lighter active:scale-[0.97]"
                  >
                    {text.register}
                  </button>
                </Card>
              )}

              {/* With "practise this" there is already a main button; then a new interview is the quieter choice */}
              <div className="order-2 animate-rise-in text-center" style={{ animationDelay: "320ms" }}>
                {onPracticeAgain && report.next_practice.length > 0 ? (
                  <TextButton onClick={onRestart}>{text.newInterview}</TextButton>
                ) : (
                  <PrimaryButton onClick={onRestart}>{text.newInterview}</PrimaryButton>
                )}
              </div>
            </div>

            {/* Right on wide screens: the values */}
            <div className="contents lg:block">
              {/* 3: each criterion with its level, comment and the quote it is based on */}
              {observed.length > 0 && (
                <Card step={1} className="order-1">
                  <SectionTitle chip="blue" icon={<Chart className="h-4 w-4" />} className="">
                    {text.scoresTitle}
                  </SectionTitle>
                  <p className="mt-1 text-sm text-charcoal-soft">
                    {text.scale}: {text.levels.map((l, i) => `${i + 1} ${l}`).join(" · ")}
                  </p>
                  {/* Overview: one coloured bar per criterion. Screen readers get the same in the list below. */}
                  <div className="mt-4" style={{ height: chartData.length * 34 + 16 }} aria-hidden="true">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={chartData}
                        layout="vertical"
                        margin={{ top: 0, right: 24, bottom: 0, left: 0 }}
                        accessibilityLayer={false} // decorative: no tab stop, the list below says the same
                      >
                        <XAxis type="number" domain={[0, scaleMax]} hide />
                        <YAxis
                          type="category"
                          dataKey="name"
                          width={165}
                          tickLine={false}
                          axisLine={false}
                          tick={{ fontSize: 12, fill: "var(--color-charcoal)" }}
                        />
                        {/* The bars grow once the card has arrived */}
                        <Bar
                          dataKey="score"
                          radius={6}
                          barSize={18}
                          background={{ fill: "var(--color-line)", radius: 6 }}
                          isAnimationActive={!reducedMotion}
                          animationBegin={350}
                          animationDuration={900}
                          animationEasing="ease-out"
                        >
                          {chartData.map((d) => (
                            <Cell key={d.name} fill={scoreColor(d.score)} />
                          ))}
                          <LabelList dataKey="score" position="right" fontSize={13} fontWeight={700} fill="var(--color-charcoal)" />
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                  <ul className="mt-5 divide-y divide-line border-t border-line">
                    {observed.map((c) => (
                      <li key={c.id} className="py-4 wrap-anywhere last:pb-0">
                        <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                          <h3 className="font-bold">{text.criteria[c.id] ?? c.label}</h3>
                          <span className="flex items-center gap-2 text-sm">
                            <LevelPill score={c.score} text={text} />
                            <span className="sr-only">
                              ({c.score} {text.outOf})
                            </span>
                            {improved.includes(c) && (
                              <span className="text-charcoal-soft">
                                ({text.improvedFrom}: {text.levels[(before.get(c.id) ?? 1) - 1]})
                              </span>
                            )}
                          </span>
                        </div>
                        {/* The backend can leave a comment empty; then only the level is shown */}
                        {c.comment?.trim() && <p className="mt-1.5 hyphens-auto">{c.comment}</p>}
                        {/* The quote the score is based on (FHGR rule K1), only real quotes come from the backend */}
                        {c.evidence && (
                          <p className="mt-2 rounded-lg bg-brand-lighter px-3 py-2 text-sm text-charcoal">
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

            </div>
          </>
        )}
      </main>
    </div>
  );
}

/** Four small segments, one per level, filled up to the score in the level colour. Decorative: the level word next to it says the same. */
function LevelMeter({ score, max }: { score: number; max: number }) {
  return (
    <span className="flex gap-1" aria-hidden="true">
      {Array.from({ length: max }, (_, i) => (
        // Track in grey, the filled part grows in from the left, segment by segment
        <span key={i} className="h-2.5 w-4 overflow-hidden rounded-sm bg-line">
          {i < score && (
            <span
              className="block h-full w-full origin-left animate-fill"
              style={{ background: scoreColor(score), animationDelay: `${450 + i * 90}ms` }}
            />
          )}
        </span>
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

// The four Profolio logo colours lead through the report, like the numbered steps on the setup screen
const chipColour = {
  teal: "bg-logo-teal text-charcoal",
  blue: "bg-logo-blue text-white",
  yellow: "bg-logo-yellow text-charcoal",
  red: "bg-logo-red text-white",
};

/** Section heading with a small tilted logo card holding an icon. */
function SectionTitle({
  chip,
  icon,
  children,
  className = "mb-3",
}: {
  chip: keyof typeof chipColour;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <span className={`flex h-8 w-8 shrink-0 -rotate-6 items-center justify-center rounded-lg ${chipColour[chip]}`} aria-hidden="true">
        {icon}
      </span>
      <h2 className="text-xl font-bold">{children}</h2>
    </div>
  );
}

/** The level as a word on its colour: good levels green, "Ausbaufähig" yellow, "Ungenügend" red. */
function LevelPill({ score, text }: { score: number; text: UiTexts }) {
  const tint =
    score >= 3
      ? "bg-mint-lighter text-mint-dark"
      : score >= 2
        ? "bg-logo-yellow-lighter text-logo-yellow-dark"
        : "bg-danger-lighter text-danger";
  return <span className={`rounded-full px-2.5 py-0.5 text-sm font-bold ${tint}`}>{text.levels[score - 1]}</span>;
}
