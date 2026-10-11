import { useEffect, useState } from "react";
import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { api, type LanguageCode, type Report } from "../api";
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
};

/** Bar colour by score: low = red, middle = yellow, high = teal. */
function scoreColor(score: number) {
  if (score >= 4) return "var(--color-logo-teal)";
  if (score >= 3) return "var(--color-logo-yellow)";
  return "var(--color-logo-red)";
}

export default function FeedbackScreen({ sessionId, language, savedReport, onReportLoaded, onRestart }: Props) {
  const text = t(language);

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

  // Criterion names come from our own texts, so they match the UI language
  const chartData =
    report?.criteria.map((c) => ({ name: text.criteria[c.id] ?? c.label, score: c.score })) ?? [];

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
            {/* Overall score */}
            <Card>
              <p className="text-sm text-charcoal-soft">{text.overall}</p>
              <p className="text-5xl font-bold">
                {report.overall_score.toFixed(1)}
                <span className="ml-2 text-lg font-normal text-charcoal-soft">{text.outOf}</span>
              </p>
            </Card>

            {/* Scores chart */}
            <Card>
              <h2 className="mb-3 text-xl font-bold">{text.scoresTitle}</h2>
              <div className="h-64" role="img" aria-label={text.scoresTitle}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={chartData} layout="vertical" margin={{ top: 0, right: 24, bottom: 0, left: 0 }}>
                    <XAxis type="number" domain={[0, 5]} hide />
                    <YAxis
                      type="category"
                      dataKey="name"
                      width={110}
                      tickLine={false}
                      axisLine={false}
                      tick={{ fontSize: 13, fill: "var(--color-charcoal)" }}
                    />
                    <Bar dataKey="score" radius={6} barSize={18} background={{ fill: "var(--color-line)", radius: 6 }}>
                      {chartData.map((d) => (
                        <Cell key={d.name} fill={scoreColor(d.score)} />
                      ))}
                      <LabelList dataKey="score" position="right" fontSize={13} fontWeight={700} />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <ul className="mt-3 space-y-2 text-sm">
                {report.criteria.map((c) => (
                  <li key={c.id}>
                    <span className="font-bold">{text.criteria[c.id] ?? c.label}:</span> {c.comment}
                  </li>
                ))}
              </ul>
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
              </Card>
            )}

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
