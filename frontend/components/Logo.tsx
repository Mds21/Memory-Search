/** The Smriti mark: an index card with a marigold corner. `inverse` for placement on an always-dark panel. */
export default function Logo({ size = 28, inverse }: { size?: number; inverse?: boolean }) {
  const tile = inverse ? "#ededed" : "rgb(var(--ink))";
  const line = inverse ? "#141415" : "rgb(var(--paper))";
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill={tile} />
      <rect x="8" y="8" width="16" height="16" rx="2" fill="none" stroke={line} strokeWidth="2" />
      <rect x="15" y="15" width="9" height="9" rx="1.5" fill="#F2B632" />
    </svg>
  );
}
