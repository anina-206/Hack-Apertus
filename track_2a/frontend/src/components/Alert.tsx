/**
 * Red box for something that went wrong. Screen readers announce it right away (role="alert").
 * Spacing around it (mb-3, mt-4 …) comes from the place that uses it.
 */
export default function Alert({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div role="alert" className={`rounded-xl bg-danger-lighter px-4 py-3 text-sm text-danger ${className}`}>
      {children}
    </div>
  );
}
