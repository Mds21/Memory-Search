/**
 * Decorative photo wall behind the home hero and the sign-in panel. Uses bundled stock photos (public/stock, see
 * CREDITS.md there), never the person's own files, so nothing private shows up as decoration.
 */
const PHOTOS = Array.from({ length: 20 }, (_, i) => `/stock/memory-${String(i + 1).padStart(2, "0")}.jpg`);
const WIDE = new Set([0, 3, 7, 10, 14, 18, 21]); // tiles that span 2x2, for a gallery rhythm

export default function PhotoWall({ count = 24, className = "", rows = "auto-rows-[120px] sm:auto-rows-[150px]", cols = "grid-cols-4 sm:grid-cols-6 lg:grid-cols-8" }:
  { count?: number; className?: string; rows?: string; cols?: string }) {
  return (
    <div aria-hidden className={`pointer-events-none absolute inset-0 -z-10 grid grid-flow-dense gap-1 ${rows} ${cols} ${className}`}>
      {Array.from({ length: count }, (_, i) => (
        <div key={i} className={`overflow-hidden bg-paper-sunk ${WIDE.has(i) ? "col-span-2 row-span-2" : ""}`}>
          <img src={PHOTOS[(i * 7) % PHOTOS.length]} alt="" decoding="async" className="h-full w-full object-cover" />
        </div>))}
    </div>
  );
}
