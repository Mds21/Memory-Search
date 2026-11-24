/** Map placeholder: one large panel. */
export default function Loading() {
  return <div className="h-[calc(100dvh-8rem)] p-3 sm:p-6 lg:h-screen" aria-busy><div className="skeleton h-full rounded-2xl" /></div>;
}
