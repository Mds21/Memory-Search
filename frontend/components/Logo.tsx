/** The Smriti mark: an index card with a gold corner. `inverse` for placement on an always-dark panel. */
export default function Logo({ size = 28, inverse }: { size?: number; inverse?: boolean }) {
  const tile = inverse ? "#e8e6e3" : "rgb(var(--ink))";
  const line = inverse ? "#0e0e0e" : "rgb(var(--paper))";
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill={tile} />
      <rect x="8" y="8" width="16" height="16" rx="2" fill="none" stroke={line} strokeWidth="2" />
      <rect x="15" y="15" width="9" height="9" rx="1.5" fill="#BF9C3A" />
    </svg>
  );
}

/** Script wordmark with a small spaced caption underneath, studio-sign style. */
export function Wordmark({ size = 28, caption = "Memory search", className = "" }: { size?: number; caption?: string; className?: string }) {
  return (
    <span className={`inline-flex flex-col items-start leading-none ${className}`}>
      <span className="script" style={{ fontSize: size, lineHeight: 1 }}>Smriti</span>
      {caption && <span className="ml-[2px] mt-1 text-[8px] font-medium uppercase tracking-[0.28em] opacity-70">{caption}</span>}
    </span>
  );
}
