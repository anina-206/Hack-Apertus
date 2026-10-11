/**
 * Quiet action shown as underlined text: the second choice next to a PrimaryButton
 * ("Neues Interview"), or a small action inside a sentence or form ("Anmelden", "Entfernen").
 *
 * - tone: "brand" (blue, default), "muted" (grey, e.g. "Konto löschen"), "inherit" (colour of the text around it)
 * - inline: inside a sentence. Keeps a 44 px tap area without making the line taller.
 */
export default function TextButton({
  onClick,
  children,
  tone = "brand",
  small = false,
  inline = false,
  className = "",
  ...aria
}: {
  onClick: () => void;
  children: React.ReactNode;
  tone?: "brand" | "muted" | "inherit";
  small?: boolean;
  inline?: boolean;
  className?: string;
  "aria-expanded"?: boolean;
}) {
  const colour = {
    brand: "font-bold text-brand-dark hover:text-brand",
    muted: "text-charcoal-soft hover:text-danger",
    inherit: "font-bold",
  }[tone];
  const box = inline ? "-my-3 inline-block py-3" : "min-h-11 px-2";
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${box} ${small ? "text-sm" : ""} ${colour} underline underline-offset-4 transition-colors ${className}`}
      {...aria}
    >
      {children}
    </button>
  );
}
