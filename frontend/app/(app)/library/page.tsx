"use client";
import { FolderPlus, LayoutGrid, Rows3, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import CollectionPicker from "@/components/CollectionPicker";
import { Empty, GridSkeleton, Spinner } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api, emptyUnlessOffline } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

const PAGE = 60;
export default function Library() {
  const { t } = useI18n();
  const { tick, toast } = useUploads();
  const [kind, setKind] = useState("");
  const [from, setFrom] = useState(""); const [to, setTo] = useState(""); const [tag, setTag] = useState("");
  const [items, setItems] = useState<Asset[] | null>(null);
  const [total, setTotal] = useState(0);
  const [more, setMore] = useState(false);
  const [grid, setGrid] = useState(false);
  const [sel, setSel] = useState<Set<string> | null>(null);
  const [pick, setPick] = useState<string[] | null>(null);
  const viewer = useViewer(items || []);

  const qs = useCallback((offset: number) => {
    const p = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    if (kind) p.set("kind", kind); if (from) p.set("date_from", from); if (to) p.set("date_to", to); if (tag.trim()) p.set("tag", tag.trim().toLowerCase());
    return p.toString();
  }, [kind, from, to, tag]);
  const load = useCallback(() => { api.get<{ items: Asset[]; total: number }>(`/assets?${qs(0)}`).then((r) => { setItems(r.items); setTotal(r.total); }).catch(emptyUnlessOffline(setItems)); }, [qs]);
  useEffect(() => { setItems(null); const id = setTimeout(load, 200); return () => clearTimeout(id); }, [load]);
  useEffect(() => { if (items) load(); }, [tick]); // eslint-disable-line react-hooks/exhaustive-deps
  const loadMore = async () => { setMore(true); try { const r = await api.get<{ items: Asset[] }>(`/assets?${qs(items!.length)}`); setItems((x) => [...(x || []), ...r.items]); } finally { setMore(false); } };

  const toggle = (a: Asset) => setSel((s) => { const n = new Set(s); n.has(a.asset_id) ? n.delete(a.asset_id) : n.add(a.asset_id); return n; });
  const del = async () => {
    if (!sel || !confirm(t("lib.deleteConfirm"))) return;
    await Promise.all([...sel].map((id) => api.del(`/assets/${id}`).catch(() => {})));
    toast(t("common.delete")); setSel(null); load();
  };
  const kinds = [["", "lib.all"], ["photo", "search.photos"], ["video", "search.videos"], ["document", "search.documents"]];

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-10 sm:px-8 sm:py-14">
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="h-page">{t("lib.title")} <span className="ml-2 text-[14px] tabular-nums tracking-normal text-ink-faint">{total}</span></h1></div>
        <div className="flex items-center gap-2">
          <button className="btn-ghost !h-10 !w-10 !p-0" onClick={() => setGrid((g) => !g)} aria-label="Toggle layout">{grid ? <Rows3 className="h-4 w-4" strokeWidth={1.5} /> : <LayoutGrid className="h-4 w-4" strokeWidth={1.5} />}</button>
          <button className={sel ? "btn-outline" : "btn-primary"} onClick={() => setSel(sel ? null : new Set())}>{sel ? t("lib.cancel") : t("lib.select")}</button>
        </div>
      </div>
      <p className="label mb-3">{t("lib.filters")}</p>
      <div className="mb-8 flex flex-wrap items-end gap-x-8 gap-y-4 border-b border-paper-line pb-4">
        <div className="flex gap-6" role="tablist">{kinds.map(([k, l]) => <button key={k} role="tab" aria-selected={kind === k} className={`tab ${kind === k ? "tab-on" : ""}`} onClick={() => setKind(k)}>{t(l)}</button>)}</div>
        <span className="flex-1" />
        <input type="date" className="input !w-auto" value={from} onChange={(e) => setFrom(e.target.value)} aria-label={t("search.from")} />
        <input type="date" className="input !w-auto" value={to} onChange={(e) => setTo(e.target.value)} aria-label={t("search.to")} />
        <input className="input !w-40" placeholder={t("lib.tag")} value={tag} onChange={(e) => setTag(e.target.value)} />
      </div>
      {items === null ? <GridSkeleton /> : items.length === 0 ? <Empty title={t("lib.noItems")} /> : (<>
        <div className={grid ? "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5 [&_img]:aspect-square" : "masonry"}>
          {items.map((a) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} selectMode={!!sel} selected={sel?.has(a.asset_id)} onSelect={toggle} />)}
        </div>
        {items.length < total && <div className="mt-6 text-center"><button className="btn-outline" onClick={loadMore} disabled={more}>{more ? <Spinner /> : null}{t("lib.loadMore")}</button></div>}
      </>)}
      {sel && sel.size > 0 && (
        <div className="fixed inset-x-0 bottom-16 z-30 mx-auto flex w-fit items-center gap-2 animate-rise rounded-full bg-night px-5 py-2 text-[12px] uppercase tracking-label text-white shadow-lift lg:bottom-6">
          <span>{sel.size} {t("lib.selected")}</span>
          <button className="btn-ghost !text-white hover:!bg-white/10" onClick={() => setPick([...sel])}><FolderPlus className="h-4 w-4" />{t("lib.addTo")}</button>
          <button className="btn-ghost !text-white hover:!bg-white/10" onClick={del}><Trash2 className="h-4 w-4" />{t("lib.delete")}</button>
        </div>)}
      <CollectionPicker ids={pick} onClose={() => setPick(null)} onDone={() => setSel(null)} />
      {viewer.node}
    </div>
  );
}
