/** Uploads placeholder: drop area and a short list. */
export default function Loading() {
  return (
    <div className="mx-auto max-w-3xl space-y-3 px-4 py-4 sm:px-6 sm:py-6" aria-busy>
      <div className="skeleton h-40 rounded-3xl" />
      {Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton h-14 rounded-2xl" />)}
    </div>
  );
}
