"use client";

/** Monochrome mark: ink square with a paper ring, so it follows the light/dark theme. `onDark` forces the white version. */
export default function Logo({ size = 28, onDark }: { size?: number; onDark?: boolean }) {
  const fg = onDark ? "#FAFAFA" : "rgb(var(--ink))";
  const bg = onDark ? "#0A0A0A" : "rgb(var(--paper))";
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect x="1" y="1" width="30" height="30" rx="9" style={{ fill: fg }} />
      <circle cx="16" cy="16" r="7.5" fill="none" strokeWidth="2.4" style={{ stroke: bg }} />
      <circle cx="16" cy="16" r="2.8" style={{ fill: onDark ? "#A78BFA" : "rgb(var(--iris))" }} />
    </svg>
  );
}
