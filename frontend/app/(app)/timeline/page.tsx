"use client";
import { useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import { Empty, GridSkeleton, Spinner } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";
import { monthBounds, monthLabel } from "@/lib/util";

interface Bucket { period: string; count: number; photo: number; video: number; document: number }

export default function Timeline() {
  const { t, lang } = useI18n();
  const [buckets, setBuckets] = useState<Bucket[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [items, setItems] = useState<Asset[] | null>(null);
  const viewer = useViewer(items || []);

  useEffect(() => { api.get<{ items: Bucket[] }>("/timeline").then((r) => { setBuckets(r.items); const last = r.items[r.items.length - 1]; if (last) setSel(last.period); }).catch(() => setBuckets([])); }, []);
  useEffect(() => {
    if (!sel) return;
    setItems(null);
    const { from, to } = monthBounds(sel);
    api.get<{ items: Asset[] }>(`/assets?date_from=${from}&date_to=${to}&limit=200`).then((r) => setItems(r.items)).catch(() => setItems([]));
  }, [sel]);
  const max = Math.max(1, ...(buckets || []).map((b) => b.count));

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-6 sm:px-8 sm:py-8">
      <h1 className="h-page mb-1">{t("tl.title")}</h1>
      <p className="mb-5 text-sm text-ink-mute">{t("tl.pick")}</p>
      {!buckets ? <Spinner /> : buckets.length === 0 ? <Empty title={t("lib.noItems")} /> : (<>
        <div className="card overflow-x-auto p-4">
          <div className="flex h-40 min-w-max items-end gap-1.5" role="listbox" aria-label={t("tl.title")}>
            {buckets.map((b) => (
              <button key={b.period} role="option" aria-selected={sel === b.period} onClick={() => setSel(b.period)} title={`${monthLabel(b.period, lang)}: ${b.count}`}
                className="group flex h-full w-9 flex-col items-center justify-end gap-1">
                <span className="text-[10px] text-ink-mute opacity-0 group-hover:opacity-100">{b.count}</span>
                <span className={`w-full rounded-t transition-colors ${sel === b.period ? "bg-tide" : "bg-tide-ring group-hover:bg-tide"}`} style={{ height: `${Math.max(6, (b.count / max) * 100)}%` }} />
                <span className="h-4 text-[10px] text-ink-mute">{monthLabel(b.period, lang).split(" ")[0]}</span>
              </button>))}
          </div>
          <div className="mt-1 flex min-w-max gap-1.5">{buckets.map((b, i) => <span key={b.period} className="w-9 text-center text-[10px] font-medium text-ink-soft">{i === 0 || b.period.endsWith("-01") ? b.period.slice(0, 4) : ""}</span>)}</div>
        </div>
        {sel && <h2 className="mb-3 mt-6 text-lg font-medium">{monthLabel(sel, lang)} <span className="text-sm font-normal text-ink-mute">{items ? `${items.length} ${t("tl.items")}` : ""}</span></h2>}
        {items === null ? <GridSkeleton n={8} /> : <div className="masonry">{items.map((a) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} />)}</div>}
      </>)}
      {viewer.node}
    </div>
  );
}
