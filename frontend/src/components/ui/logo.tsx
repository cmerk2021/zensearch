import { cn } from "@/lib/utils";

/**
 * Zen brand mark: an ensō — the single-stroke Zen circle symbolising clarity
 * and focus. Uses ``currentColor`` so it inherits text colour, and round line
 * caps give it the tapered brush-stroke feel. Replaces the old placeholder
 * kanji glyph.
 */
export function ZenLogo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 32 32"
      role="img"
      aria-label="Zen"
      className={cn("h-7 w-7", className)}
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <circle
        cx="16"
        cy="16"
        r="11.5"
        stroke="currentColor"
        strokeWidth="3.4"
        strokeLinecap="round"
        strokeDasharray="60 100"
        transform="rotate(48 16 16)"
      />
    </svg>
  );
}
