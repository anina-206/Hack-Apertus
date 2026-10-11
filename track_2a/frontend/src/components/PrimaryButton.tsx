/** Blue pill button, the main call to action. */
export default function PrimaryButton({
  onClick,
  type = "button",
  disabled,
  wide,
  children,
}: {
  onClick?: () => void;
  type?: "button" | "submit";
  disabled?: boolean;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-full bg-brand px-7 py-4 text-lg font-bold text-white shadow-button transition hover:bg-brand-dark disabled:cursor-not-allowed disabled:bg-line disabled:text-charcoal-soft disabled:shadow-none ${
        wide ? "w-full" : ""
      }`}
    >
      {children}
    </button>
  );
}
