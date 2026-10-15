/**
 * Red box for something that went wrong. Screen readers announce it right away (role="alert").
 * Spacing around it (mb-3, mt-4 …) comes from the place that uses it.
 */
export default function Alert({
  children,
  className = "",
  onClose,
  closeLabel = "Schliessen",
}: {
  children: React.ReactNode;
  className?: string;
  /** Shows a × button that hides the message */
  onClose?: () => void;
  closeLabel?: string;
}) {
  return (
    <div role="alert" className={`flex items-start gap-2 rounded-xl bg-danger-lighter px-4 py-3 text-sm text-danger ${className}`}>
      <div className="flex-1">{children}</div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          aria-label={closeLabel}
          className="-my-1 -mr-2 flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-lg leading-none hover:bg-danger/10"
        >
          ×
        </button>
      )}
    </div>
  );
}
