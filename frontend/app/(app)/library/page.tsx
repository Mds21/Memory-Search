"use client";
import { CheckSquare, FolderPlus, LayoutGrid, Rows3, SlidersHorizontal, Trash2, X } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import AssetTile from "@/components/AssetTile";
import CollectionPicker from "@/components/CollectionPicker";
import { Empty, GridSkeleton, PageHeader, Sheet, Spinner } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { invalidate, useApi } from "@/lib/swr";
import type { Asset } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

const PAGE = 60;
type Page = { items: Asset[]; total: number };
const KINDS = [["", "lib.all"], ["photo", "search.photos"], ["video", "search.videos"], ["document", "search.documents"]];

function LibraryView() {
  const { t } = useI18n();
  const { tick, toast } = useUploads();
  const params = useSearchParams();
  const router = useRouter();
  const [kind, setKindState] = useState(params.get("kind") || "");
  const [from, setFrom] = useState(""); const [to, setTo] = useState(""); const [tag, setTag] = useState(params.get("tag") || "");
  const [debTag, setDebTag] = useState(tag.trim().toLowerCase());
  const [extra, setExtra] = useState<Asset[]>([]);
  const [more, setMore] = useState(false);
  const [grid, setGrid] = useState(false);
  const [sel, setSel] = useState<Set<string> | null>(null);
  const [pick, setPick] = useState<string[] | null>(null);
  const [filters, setFilters] = useState(false);
  const sentinel = useRef<HTMLDivElement>(null);

  // the selected type lives in the URL, so Home tiles and the back button land on the same view
  const setKind = (k: string) => { setKindState(k); router.replace(k ? `/library?kind=${k}` : "/library", { scroll: false }); };
  useEffect(() => { setKindState(params.get("kind") || ""); }, [params]);
  useEffect(() => { const id = setTimeout(() => setDebTag(tag.trim().toLowerCase()), 250); return () => clearTimeout(id); }, [tag]);

  const qs = useCallback((offset: number) => {
    const p = new URLSearchParams({ limit: String(PAGE), offset: String(offset) });
    if (kind) p.set("kind", kind); if (from) p.set("date_from", from); if (to) p.set("date_to", to); if (debTag) p.set("tag", debTag);
    return p.toString();
  }, [kind, from, to, debTag]);

  const first = useApi<Page>(`/assets?${qs(0)}`, tick);
  useEffect(() => { setExtra([]); }, [qs, tick]);
  const items = useMemo(() => (first.data ? [...first.data.items, ...extra] : null), [first.data, extra]);
  const total = first.data?.total ?? 0;
  const viewer = useViewer(items || []);

  const loadMore = useCallback(async () => {
    if (more || !items || items.length >= total) return;
    setMore(true);
    try { const r = await api.get<Page>(`/assets?${qs(items.length)}`); setExtra((x) => [...x, ...r.items]); } finally { setMore(false); }
  }, [more, items, total, qs]);

  useEffect(() => {
    const el = sentinel.current;
    if (!el) return;
    const io = new IntersectionObserver((es) => es[0].isIntersecting && loadMore(), { rootMargin: "1200px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [loadMore]);

  const toggle = useCallback((a: Asset) => setSel((s) => { const n = new Set(s); n.has(a.asset_id) ? n.delete(a.asset_id) : n.add(a.asset_id); return n; }), []);
  const startSelect = useCallback((a: Asset) => setSel((s) => (s ? s : new Set([a.asset_id]))), []);
  const del = async () => {
    if (!sel || !confirm(t("lib.deleteConfirm"))) return;
    await Promise.all([...sel].map((id) => api.del(`/assets/${id}`).catch(() => {})));
    toast(t("lib.deleted")); setSel(null); invalidate("/assets", "/timeline", "/collections", "/on-this-day", "/me/storage"); first.reload(); setExtra([]);
  };
  const nFilters = [from, to, tag].filter(Boolean).length;
  const clear = () => { setFrom(""); setTo(""); setTag(""); };

  const dateFields = (<>
    <label className="block text-xs font-medium text-ink-mute">{t("search.from")}<input type="date" className="input mt-1" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
    <label className="block text-xs font-medium text-ink-mute">{t("search.to")}<input type="date" className="input mt-1" value={to} onChange={(e) => setTo(e.target.value)} /></label>
    <label className="block text-xs font-medium text-ink-mute">{t("lib.tag")}<input className="input mt-1" placeholder={t("lib.tagPh")} value={tag} onChange={(e) => setTag(e.target.value)} enterKeyHint="done" /></label>
  </>);

  return (
    <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 sm:py-8">
      <PageHeader title={t("lib.title")} count={first.data ? total : null} actions={<>
        <div className="flex rounded-xl border border-paper-line bg-paper-card p-0.5 shadow-soft">
          <button className={`tap rounded-lg p-2 transition-colors ${!grid ? "bg-paper-sunk text-ink" : "text-ink-mute hover:text-ink"}`} onClick={() => setGrid(false)} aria-label="Masonry layout" aria-pressed={!grid}><Rows3 className="h-4 w-4" /></button>
          <button className={`tap rounded-lg p-2 transition-colors ${grid ? "bg-paper-sunk text-ink" : "text-ink-mute hover:text-ink"}`} onClick={() => setGrid(true)} aria-label="Grid layout" aria-pressed={grid}><LayoutGrid className="h-4 w-4" /></button>
        </div>
        <button className={`tap ${sel ? "btn-outline" : "btn-primary"}`} onClick={() => setSel(sel ? null : new Set())}>{sel ? <X className="h-4 w-4" /> : <CheckSquare className="h-4 w-4" />}{sel ? t("lib.cancel") : t("lib.select")}</button>
      </>} />

      <div className="glass sticky top-14 z-20 -mx-4 mb-5 flex items-center gap-2 border-b border-paper-line/60 px-4 py-2.5 sm:mx-0 sm:rounded-2xl sm:border lg:top-3">
        <div className="flex min-w-0 flex-1 gap-1 overflow-x-auto rounded-xl bg-paper-sunk p-1 no-scrollbar sm:flex-none" role="tablist">{KINDS.map(([k, l]) => (
          <button key={k} role="tab" aria-selected={kind === k} onClick={() => setKind(k)}
            className={`tap shrink-0 rounded-lg px-3.5 py-1.5 text-[13px] font-medium transition-all ${kind === k ? "bg-paper-card text-ink shadow-soft" : "text-ink-mute hover:text-ink"}`}>{t(l)}</button>))}</div>
        <div className="hidden flex-wrap items-center gap-2 lg:flex [&_label]:flex [&_label]:items-center [&_label]:gap-2 [&_input]:!mt-0 [&_input]:!w-auto [&_input]:!py-1.5 [&_input]:text-xs">{dateFields}</div>
        <button onClick={() => setFilters(true)} className="tap btn-outline relative shrink-0 !px-3 !py-2 lg:hidden" aria-label={t("lib.filters")}>
          <SlidersHorizontal className="h-4 w-4" />{nFilters > 0 && <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-tide px-1 text-[10px] font-bold text-paper">{nFilters}</span>}</button>
        {nFilters > 0 && <button className="btn-ghost tap hidden !px-2 !py-1 text-xs lg:inline-flex" onClick={clear}><X className="h-3.5 w-3.5" />{t("lib.clear")}</button>}
      </div>
      {sel && sel.size === 0 && <p className="mb-3 animate-fade-in text-center text-sm text-ink-mute">{t("lib.tapToSelect")}</p>}

      {items === null ? <GridSkeleton /> : items.length === 0 ? (
        <Empty title={t("lib.noItems")} action={nFilters > 0 || kind ? <button className="btn-outline" onClick={() => { clear(); setKind(""); }}>{t("lib.clear")}</button> : undefined} />
      ) : (<>
        <div className={grid ? "grid grid-cols-3 gap-1.5 sm:grid-cols-4 sm:gap-3 lg:grid-cols-6 [&_img]:aspect-square" : "masonry"}>
          {items.map((a, i) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} selectMode={!!sel} selected={sel?.has(a.asset_id)} onSelect={toggle} onLongPress={startSelect} priority={i < 8} />)}
        </div>
        <div ref={sentinel} className="h-px" />
        {items.length < total && <div className="mt-6 flex justify-center"><button className="btn-outline" onClick={loadMore} disabled={more}>{more && <Spinner />}{t("lib.loadMore")}</button></div>}
      </>)}

      {sel && sel.size > 0 && (
        <div className="fixed inset-x-3 bottom-[calc(6.5rem+env(safe-area-inset-bottom))] z-40 mx-auto flex max-w-md animate-fade-up items-center gap-1 rounded-2xl bg-night px-2 py-2 text-sm text-white shadow-lift ring-1 ring-white/10 lg:bottom-6">
          <button className="tap rounded-xl p-2 hover:bg-white/10" onClick={() => setSel(null)} aria-label={t("lib.cancel")}><X className="h-4 w-4" /></button>
          <span className="flex-1 px-1 font-medium tabular-nums">{sel.size} {t("lib.selected")}</span>
          <button className="btn-ghost tap !text-white hover:!bg-white/10" onClick={() => setPick([...sel])}><FolderPlus className="h-4 w-4" /><span className="max-sm:hidden">{t("lib.addTo")}</span></button>
          <button className="btn-ghost tap !text-red-300 hover:!bg-white/10" onClick={del}><Trash2 className="h-4 w-4" /><span className="max-sm:hidden">{t("lib.delete")}</span></button>
        </div>)}

      <Sheet open={filters} onClose={() => setFilters(false)} title={t("lib.filters")}>
        <div className="space-y-3 pb-2">{dateFields}
          <div className="flex gap-2 pt-2"><button className="btn-outline flex-1" onClick={clear}>{t("lib.clear")}</button><button className="btn-primary flex-1" onClick={() => setFilters(false)}>{t("lib.show", { n: total })}</button></div>
        </div>
      </Sheet>
      <CollectionPicker ids={pick} onClose={() => setPick(null)} onDone={() => { setSel(null); invalidate("/collections"); }} />
      {viewer.node}
    </div>
  );
}

export default function Library() { return <Suspense fallback={<div className="mx-auto max-w-7xl px-4 py-6 sm:px-6"><GridSkeleton /></div>}><LibraryView /></Suspense>; }
