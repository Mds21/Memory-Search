import { GridSkeleton } from "@/components/ui";

/** Shown instantly while a section's code loads, so navigation never feels stuck. */
export default function Loading() {
  return (
    <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-8 sm:py-8" aria-busy>
      <div className="skeleton mb-6 h-9 w-48 rounded-md" />
      <GridSkeleton n={10} />
    </div>
  );
}
