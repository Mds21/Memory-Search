/** Chat-shaped placeholder: question box on the left, results on the right, like the real page. */
export default function Loading() {
  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 pt-4 sm:px-6 sm:py-8 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:gap-8" aria-busy>
      <div className="space-y-3"><div className="skeleton h-12 rounded-2xl" /><div className="skeleton h-24 rounded-2xl" /><div className="skeleton ml-auto h-10 w-2/3 rounded-2xl" /></div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton aspect-[4/3] rounded-2xl" />)}</div>
    </div>
  );
}
