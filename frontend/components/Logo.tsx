export default function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <circle cx="16" cy="16" r="14" fill="#0E7C86" />
      <circle cx="16" cy="16" r="8" fill="none" stroke="#fff" strokeWidth="2.4" />
      <circle cx="16" cy="16" r="3" fill="#F6C453" />
    </svg>
  );
}
