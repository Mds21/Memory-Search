"use client";
import { ChevronDown, Pencil, RefreshCw, Sparkles, Trash2, X } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import AssetTile from "@/components/AssetTile";
import FileFacts from "@/components/FileFacts";
import { ShareActions } from "@/components/ShareCard";
import { Spinner, fmtDate, fmtDuration } from "@/components/ui";
import { assetHref, useViewer } from "@/components/useViewer";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

interface Chunk { id: string; type: string; start_ms: number | null; content: string }

function MediaView() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const { t, lang } = useI18n();
  const { toast, tick } = useUploads();
  const [edit, setEdit] = useState(false);
  const [a, setA] = useState<Asset | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [similar, setSimilar] = useState<Asset[]>([]);
  const [cap, setCap] = useState(""); const [place, setPlace] = useState(""); const [date, setDate] = useState(""); const [tags, setTags] = useState<string[]>([]); const [tagIn, setTagIn] = useState("");
  const [saving, setSaving] = useState(false);
  const vid = useRef<HTMLVideoElement>(null);
  const viewer = useViewer(a ? [a, ...similar] : similar);

  const fill = (x: Asset) => { setA(x); setCap(x.caption_user || ""); setPlace(x.place || ""); setDate(x.taken_at ? x.taken_at.slice(0, 10) : ""); setTags(x.tags); };
  useEffect(() => {
    api.get<Asset>(`/assets/${id}`).then(fill).catch(() => router.replace("/library"));
    api.get<{ items: Chunk[] }>(`/assets/${id}/chunks`).then((r) => setChunks(r.items)).catch(() => {});
    api.get<{ items: Asset[] }>(`/assets/${id}/similar`).then((r) => setSimilar(r.items)).catch(() => {});
  }, [id, tick]); // eslint-disable-line react-hooks/exhaustive-deps
  const seek = (ms: number) => { if (vid.current) { vid.current.currentTime = ms / 1000; vid.current.play().catch(() => {}); } };
  useEffect(() => { const t0 = Number(sp.get("t")); if (a && t0) setTimeout(() => seek(t0), 300); }, [a?.asset_id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!a) return <div className="mx-auto max-w-7xl space-y-4 sm:p-6"><div className="skeleton h-[50dvh] sm:rounded-2xl" /><div className="space-y-2 px-4"><div className="skeleton h-6 w-2/3 rounded-lg" /><div className="skeleton h-4 w-1/3 rounded-lg" /></div></div>;

  const save = async () => {
    setSaving(true);
    try { fill(await api.patch<Asset>(`/assets/${id}`, { caption_user: cap, place_name: place, taken_at: date || "", tags })); toast(t("media.saved")); } catch (e: any) { toast(e.message, "error"); }
    setSaving(false);
  };
  const addTag = () => { const v = tagIn.trim().toLowerCase(); if (v && !tags.includes(v)) setTags([...tags, v]); setTagIn(""); };
  const del = async () => { if (confirm(t("lib.deleteConfirm"))) { await api.del(`/assets/${id}`); router.replace("/library"); } };
  const reindex = async () => { await api.post(`/assets/${id}/reindex`); toast(t("up.queued")); };
  const moments = chunks.filter((c) => c.start_ms != null);

  return (
    <div className="mx-auto grid max-w-7xl gap-5 pb-6 sm:px-6 sm:py-6 lg:grid-cols-[minmax(0,1fr)_22rem] lg:gap-6">
      <div className="min-w-0 space-y-5">
        <div className="relative overflow-hidden bg-night sm:rounded-2xl">
          {a.kind === "video" && a.video_url ? <video ref={vid} src={abs(a.video_url)} poster={abs(a.preview_url)} controls playsInline className="max-h-[70dvh] w-full" />
            : <button onClick={() => viewer.open(a)} className="block w-full" aria-label={t("media.view")}>
                <img src={abs(a.original_url || a.preview_url)} alt={a.caption_user || a.title} className="mx-auto max-h-[70dvh] object-contain" /></button>}
        </div>
        <div className="space-y-3 px-4 sm:px-0">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold" title={a.title}>{a.display_title || a.title}</h1>
            <p className="truncate text-sm text-ink-mute">{[a.taken_at ? fmtDate(a.taken_at, lang) : null, a.place?.split(",")[0], a.people?.[0]].filter(Boolean).join(" • ") || a.title}</p>
            {!a.caption_user && a.auto_caption && <p className="mt-2 flex gap-1.5 rounded-xl bg-paper-sunk/70 px-3 py-2 text-sm text-ink-soft"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-iris" />{a.auto_caption}</p>}
          </div>
          <div className="flex flex-wrap gap-2"><ShareActions asset={a} size="md" /></div>
        </div>
        <div className="space-y-5 px-4 sm:px-0 lg:hidden"><FileFacts asset={a} /></div>
        {a.kind === "video" && moments.length > 0 && (
          <section className="px-4 sm:px-0"><h2 className="mb-2 text-sm font-semibold text-ink-soft">{t("media.moments")}</h2>
            <ul className="divide-y divide-paper-line rounded-2xl border border-paper-line bg-paper-card">{moments.map((m) => (
              <li key={m.id}><button onClick={() => seek(m.start_ms!)} className="tap flex min-h-[2.75rem] w-full items-center gap-3 px-3 py-2 text-left text-sm hover:bg-paper-sunk">
                <span className="w-12 shrink-0 font-mono text-xs text-tide-dark">{fmtDuration(m.start_ms)}</span><span className="line-clamp-2">{m.type === "transcript" ? `“${m.content}”` : m.content}</span></button></li>))}</ul></section>)}
        {similar.length > 0 && <section className="px-4 sm:px-0"><h2 className="mb-3 text-sm font-semibold text-ink-soft">{t("media.similar")}</h2>
          <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-1 no-scrollbar sm:mx-0 sm:grid sm:grid-cols-4 sm:px-0">{similar.slice(0, 8).map((s) => (
            <div key={s.asset_id} className="w-36 shrink-0 snap-start sm:w-auto"><AssetTile asset={s} onOpen={(x) => router.push(assetHref(x))} /></div>))}</div></section>}
      </div>

      <aside className="space-y-4 px-4 sm:px-0">
        <div className="hidden lg:block"><FileFacts asset={a} /></div>
        {a.status === "failed" && a.status_detail && <p className="rounded-xl bg-danger-soft px-3 py-2 text-sm text-danger">{a.status_detail}</p>}
        <div className="card overflow-hidden">
          <button onClick={() => setEdit((e) => !e)} className="tap flex w-full items-center justify-between px-4 py-3.5 text-sm font-semibold lg:pointer-events-none" aria-expanded={edit}>
            <span className="flex items-center gap-2"><Pencil className="h-4 w-4 text-ink-mute" />{t("media.edit")}</span><ChevronDown className={`h-4 w-4 text-ink-mute transition-transform lg:hidden ${edit ? "rotate-180" : ""}`} /></button>
          <div className={`space-y-4 border-t border-paper-line p-4 ${edit ? "" : "hidden lg:block"}`}>
            <label className="block text-sm font-medium">{t("media.caption")}<textarea rows={3} className="input mt-1 font-normal" value={cap} onChange={(e) => setCap(e.target.value)} placeholder={t("media.captionPh")} /></label>
            <label className="block text-sm font-medium">{t("media.location")}<input className="input mt-1 font-normal" value={place} onChange={(e) => setPlace(e.target.value)} /></label>
            <label className="block text-sm font-medium">{t("media.taken")}<input type="date" className="input mt-1 font-normal" value={date} onChange={(e) => setDate(e.target.value)} /></label>
            <div><p className="mb-1 text-sm font-medium">{t("media.tags")}</p>
              <div className="mb-2 flex flex-wrap gap-1.5">{tags.map((x) => <span key={x} className="chip chip-on">{x}<button className="-mr-1 rounded-full p-1" aria-label={`Remove ${x}`} onClick={() => setTags(tags.filter((y) => y !== x))}><X className="h-3 w-3" /></button></span>)}</div>
              <form onSubmit={(e) => { e.preventDefault(); addTag(); }}><input className="input" value={tagIn} onChange={(e) => setTagIn(e.target.value)} placeholder={t("media.addTag")} enterKeyHint="done" /></form></div>
            <button className="btn-primary w-full" onClick={save} disabled={saving}>{saving && <Spinner />}{t("media.save")}</button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button className="btn-outline tap" onClick={reindex}><RefreshCw className="h-4 w-4" />{t("media.reindex")}</button>
          <button className="btn-outline tap !text-danger" onClick={del}><Trash2 className="h-4 w-4" />{t("media.delete")}</button>
        </div>
      </aside>
      {viewer.node}
    </div>
  );
}

export default function MediaPage() { return <Suspense fallback={<div className="p-8"><Spinner /></div>}><MediaView /></Suspense>; }
