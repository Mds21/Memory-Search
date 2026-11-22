/** Settings placeholder: a stack of cards, matching the real page. */
export default function Loading() {
  return (
    <div className="mx-auto max-w-2xl space-y-5 px-4 py-6 sm:px-6 sm:py-8" aria-busy>
      <div className="skeleton hidden h-8 w-40 rounded-lg lg:block" />
      {[28, 40, 32].map((h, i) => <div key={i} className="skeleton rounded-2xl" style={{ height: `${h * 4}px` }} />)}
    </div>
  );
}
