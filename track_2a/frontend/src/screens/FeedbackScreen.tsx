import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { api, type CriterionId, type LanguageCode, type Report } from "../api";
import CardAccent from "../components/CardAccent";
import { Check, ChevronLeft } from "../components/icons";
import PrimaryButton from "../components/PrimaryButton";
import { t } from "../i18n";

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

/** Bar colour by FHGR level (1-4): 3-4 Gut/Sehr gut = teal, 2 Ausbaufähig = yellow, 1 Ungenügend = red. */
function scoreColor(score: number) {
  if (score >= 3) return "var(--color-logo-teal)";
  if (score >= 2) return "var(--color-logo-yellow)";
  return "var(--color-logo-red)";
}

export default function FeedbackScreen({
  sessionId,
  language,
  savedReport,
  onReportLoaded,
  onRestart,
  onPracticeAgain,
}: Props) {
  const text = t(language);
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

  // Only observed criteria get a bar; the others (score null) are listed below the chart.
  // Criterion names come from our own texts, so they match the UI language.
  const observed = report?.criteria.filter((c) => c.score !== null) ?? [];
  const notObserved = report?.criteria.filter((c) => c.score === null) ?? [];
  const chartData = observed.map((c) => ({ name: text.criteria[c.id] ?? c.label, score: c.score }));
  const scaleMax = report?.scale?.max ?? 4;

  return (
    <div className="mx-auto flex min-h-dvh w-full max-w-lg flex-col bg-page">
      <header className="bg-brand px-4 pt-5 pb-12 text-white">
        <div className="flex items-center gap-2">
          <button
            onClick={onRestart}
            aria-label={text.back}
            className="-ml-2 flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10"
          >
            <ChevronLeft />
          </button>
          <h1 className="flex-1 text-3xl font-bold tracking-tight">
            {text.feedbackScreenTitle}
            <span className="text-logo-yellow">.</span>
          </h1>
        </div>
      </header>

      <main className="relative z-10 -mt-8 space-y-4 px-4 pb-8">
        {!report && !error && (
          <Card>
            <p className="text-center text-lg">{text.loadingReport}</p>
          </Card>
        )}

        {error && (
          <Card>
            <p className="mb-4 rounded-xl bg-danger-lighter px-3 py-2 text-sm text-danger">{text.error}</p>
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

            {/* Overall score */}
            <Card>
              <p className="text-sm text-charcoal-soft">{text.overall}</p>
              <p className="text-5xl font-bold">
                {report.overall_score?.toFixed(1) ?? "–"}
                <span className="ml-2 text-lg font-normal text-charcoal-soft">{text.outOf}</span>
              </p>
            </Card>

            {/* Scores chart */}
            <Card>
              <h2 className="mb-3 text-xl font-bold">{text.scoresTitle}</h2>
              <div style={{ height: chartData.length * 34 + 16 }} role="img" aria-label={text.scoresTitle}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }}>
                    <XAxis type="number" domain={[0, scaleMax]} hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={140}
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 12, fill: "var(--color-charcoal)" }}
                    />
                    <Bar dataKey="score" radius={6} barSize={18} background={{ fill: "var(--color-line)", radius: 6 }}>
                      {chartData.map((d) => (
                        <Cell key={d.name} fill={scoreColor(d.score ?? 0)} />
                      ))}
                      <LabelList dataKey="score" position="right" fontSize={13} fontWeight={700} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-3 space-y-2 text-sm">
                {observed.map((c) => (
                  <li key={c.id}>
                    <span className="font-bold">{text.criteria[c.id] ?? c.label}:</span> {c.comment}
                    {/* The quote the score is based on (FHGR rule K1), only real quotes come from the backend */}
                    {c.evidence && (
                      <span className="mt-1 block border-l-2 border-line pl-2 text-charcoal-soft italic">
                        {text.youSaid}: «{c.evidence}»
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              {notObserved.length > 0 && (
                <p className="mt-3 text-sm text-charcoal-soft">
                  {text.notObserved}: {notObserved.map((c) => text.criteria[c.id] ?? c.label).join(", ")}
                </p>
              )}
            </Card>

            {/* Strengths */}
            <Card>
              <h2 className="mb-3 text-xl font-bold">{text.strengthsTitle}</h2>
              <ul className="space-y-2">
                {report.strengths.map((s) => (
                  <li key={s} className="flex items-start gap-2">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-logo-teal text-white">
                      <Check className="h-3.5 w-3.5" />
                    </span>
                    {s}
                  </li>
                ))}
              </ul>
            </Card>

            {/* Tips */}
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

            {/* Feedback on the uploaded application letter */}
            {report.application_feedback && (
              <Card>
                <h2 className="mb-1 text-xl font-bold">{text.letterFeedbackTitle}</h2>
                <p className="mb-3 text-sm text-charcoal-soft">{text.letterFeedbackIntro}</p>
                <p className="mb-4 text-4xl font-bold">
                  {report.application_feedback.overall_score.toFixed(1)}
                  <span className="ml-2 text-lg font-normal text-charcoal-soft">
                    / {report.application_feedback.scale.max}
                  </span>
                </p>
                <ul className="space-y-4">
                  {report.application_feedback.criteria.map((c) => (
                    <li key={c.id}>
                      <div className="mb-1 flex items-baseline justify-between gap-3">
                        <span className="font-bold">{c.label}</span>
                        <span className="text-sm font-bold">
                          {c.score ?? "–"} / {report.application_feedback?.scale.max}
                        </span>
                      </div>
                      <div className="h-2 rounded-full bg-line" aria-hidden="true">
                        <div
                          className="h-2 rounded-full"
                          style={{
                            width: `${((c.score ?? 0) / (report.application_feedback?.scale.max ?? 4)) * 100}%`,
                            background: scoreColor(c.score ?? 0),
                          }}
                        />
                      </div>
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
                        <li key={s} className="flex items-start gap-2">
                          <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-logo-teal text-white">
                            <Check className="h-3.5 w-3.5" />
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
                  </>
                )}
              </Card>
            )}

            {/* Next practice */}
            {report.next_practice.length > 0 && (
              <Card>
                <h2 className="mb-3 text-xl font-bold">{text.nextPracticeTitle}</h2>
                <div className="flex flex-wrap gap-2">
                  {report.next_practice.map((id) => (
                    <span key={id} className="rounded-full bg-brand-lighter px-3 py-1.5 text-sm font-bold text-brand">
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

            {report.closing && <p className="px-2 text-center text-lg">{report.closing}</p>}

            <div className="pt-2 text-center">
              <PrimaryButton onClick={onRestart}>{text.newInterview}</PrimaryButton>
            </div>
          </>
        )}
      </main>
    </div>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <section className="relative overflow-hidden rounded-2xl bg-white p-5 shadow-card">
      <CardAccent />
      {children}
    </section>
  );
}
