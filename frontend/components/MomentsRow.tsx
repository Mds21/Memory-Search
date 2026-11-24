"use client";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Moment } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import MomentCard from "./MomentCard";

/** "Moments for you" on Home: a swipeable row of story cards, best first. Hidden until there is at least one. */
export default function MomentsRow() {
  const { t } = useI18n();
  const { tick } = useUploads();
  const [items, setItems] = useState<Moment[] | null>(null);
  useEffect(() => { api.get<{ items: Moment[] }>("/moments").then((r) => setItems(r.items)).catch(() => setItems([])); }, [tick]);
  if (!items?.length) return null;

  return (
    <section className="mt-16">
      <div className="mb-6 flex items-end gap-4">
        <div><h2 className="text-[13px] font-medium uppercase tracking-label">{t("mo.for")}<span className="ml-3 tabular-nums text-ink-faint">{items.length}</span></h2><span className="bar mt-2.5" aria-hidden /></div>
        <span className="flex-1" />
        <Link href="/moments" className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-label text-ink-mute transition-colors hover:text-ink">{t("mo.all")}<ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} /></Link>
      </div>
      <div className="-mx-4 flex snap-x gap-4 overflow-x-auto px-4 pb-3 sm:-mx-8 sm:px-8">
        {items.slice(0, 10).map((m) => <MomentCard key={m.id} m={m} />)}
      </div>
    </section>
  );
}
