/**
 * White card on the grey page. With `step`, it rises in after the cards before it
 * (step 0 first, each step 80 ms later), e.g. when the feedback report arrives.
 */
export default function Card({
  children,
  step,
  className = "",
  labelledBy,
}: {
  children: React.ReactNode;
  step?: number;
  className?: string;
  /** id of the card's heading, so screen readers name the section */
  labelledBy?: string;
}) {
  return (
    <section
      aria-labelledby={labelledBy}
      className={`rounded-2xl bg-white p-5 shadow-card ${step !== undefined ? "animate-rise-in" : ""} ${className}`}
      style={step !== undefined ? { animationDelay: `${step * 80}ms` } : undefined}
    >
      {children}
    </section>
  );
}
