"use client";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AssetTile from "@/components/AssetTile";
import { Empty, GridSkeleton, PageHeader } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { useI18n } from "@/lib/i18n";
import { prefetch, useApi } from "@/lib/swr";
import type { Asset } from "@/lib/types";
import { monthBounds, monthLabel } from "@/lib/util";

interface Bucket { period: string; count: number; photo: number; video: number; document: number }
const monthKey = (period: string) => { const { from, to } = monthBounds(period); return `/assets?date_from=${from}&date_to=${to}&limit=200`; };

function TimelineView() {
  const { t, lang } = useI18n();
  const buckets = useApi<{ items: Bucket[] }>("/timeline").data?.items;
  const params = useSearchParams();
  const [sel, setSel] = useState<string | null>(params.get("month"));  // links from a photo's date land on its month
  const items = useApi<{ items: Asset[] }>(sel ? monthKey(sel) : null).data?.items ?? null;
  const viewer = useViewer(items || []);
  const strip = useRef<HTMLDivElement>(null);

  useEffect(() => { if (buckets?.length && !sel) setSel(buckets[buckets.length - 1].period); }, [buckets, sel]);
  // Scroll the histogram to the newest month on first load.
  useEffect(() => {
    if (!buckets?.length || !strip.current) return;
    const on = strip.current.querySelector<HTMLElement>('[aria-selected="true"]');
    if (on) on.scrollIntoView({ inline: "center", block: "nearest" }); else strip.current.scrollTo({ left: strip.current.scrollWidth });
  }, [buckets?.length, sel]);
  const max = Math.max(1, ...(buckets || []).map((b) => b.count));

  return (
    <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 sm:py-8">
      <PageHeader title={t("tl.title")} sub={t("tl.pick")} />
      {!buckets ? <div className="skeleton h-48 rounded-2xl" /> : buckets.length === 0 ? <Empty title={t("lib.noItems")} /> : (<>
        <div ref={strip} className="card overflow-x-auto p-5">
          <div className="flex h-40 min-w-max items-end gap-1.5" role="listbox" aria-label={t("tl.title")}>
            {buckets.map((b) => {
              const on = sel === b.period;
              return (
                <button key={b.period} role="option" aria-selected={on} onClick={() => setSel(b.period)} onMouseEnter={() => prefetch(monthKey(b.period))}
                  title={`${monthLabel(b.period, lang)}: ${b.count}`} className="tap group flex h-full w-10 flex-col items-center justify-end gap-1">
                  <span className={`text-[10px] font-medium tabular-nums transition-opacity ${on ? "text-tide-dark opacity-100" : "text-ink-mute opacity-0 group-hover:opacity-100"}`}>{b.count}</span>
                  <span className={`w-full rounded-lg transition-all duration-200 ${on ? "bg-gradient-to-t from-tide to-iris shadow-glow" : "bg-tide/25 group-hover:bg-tide/50"}`} style={{ height: `${Math.max(6, (b.count / max) * 100)}%` }} />
                  <span className={`h-4 text-[10px] ${on ? "font-semibold text-ink" : "text-ink-mute"}`}>{monthLabel(b.period, lang).split(" ")[0]}</span>
                </button>);
            })}
          </div>
          <div className="mt-1 flex min-w-max gap-1.5">{buckets.map((b, i) => <span key={b.period} className="w-10 text-center text-[10px] font-semibold text-ink-soft">{i === 0 || b.period.endsWith("-01") ? b.period.slice(0, 4) : ""}</span>)}</div>
        </div>
        {sel && <h2 className="mb-4 mt-8 flex items-baseline gap-2 text-lg font-semibold">{monthLabel(sel, lang)} <span className="text-sm font-normal text-ink-mute">{items ? `${items.length} ${t("tl.items")}` : ""}</span></h2>}
        {items === null ? <GridSkeleton n={8} /> : <div key={sel} className="masonry animate-fade-in">{items.map((a, i) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} priority={i < 6} />)}</div>}
      </>)}
      {viewer.node}
    </div>
  );
}

export default function Timeline() { return <Suspense fallback={<div className="mx-auto max-w-7xl px-4 py-6"><div className="skeleton h-48 rounded-2xl" /></div>}><TimelineView /></Suspense>; }
