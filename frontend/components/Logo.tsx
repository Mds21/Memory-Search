export default function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="3" fill="#17181A" />
      <rect x="7" y="7" width="18" height="18" fill="none" stroke="#F3F4F1" strokeWidth="2" />
      <rect x="15" y="15" width="10" height="10" fill="#F2B632" />
    </svg>
  );
}
