import { GridSkeleton } from "@/components/ui";

/** Shown instantly while a section's code loads, so navigation never feels stuck. */
export default function Loading() {
  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8" aria-busy>
      <div className="skeleton mb-6 h-8 w-48 rounded-lg" />
      <GridSkeleton n={10} />
    </div>
  );
}
