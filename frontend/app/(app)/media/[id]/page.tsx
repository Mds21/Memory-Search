"use client";
import { RefreshCw, Trash2, X } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import DownloadMenu from "@/components/DownloadMenu";
import AssetTile from "@/components/AssetTile";
import { Spinner, fmtBytes, fmtDuration } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

interface Chunk { id: string; type: string; start_ms: number | null; content: string }

function MediaView() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const { t } = useI18n();
  const { toast, tick } = useUploads();
  const [a, setA] = useState<Asset | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [similar, setSimilar] = useState<Asset[]>([]);
  const [cap, setCap] = useState(""); const [place, setPlace] = useState(""); const [date, setDate] = useState(""); const [tags, setTags] = useState<string[]>([]); const [tagIn, setTagIn] = useState("");
  const [saving, setSaving] = useState(false);
  const vid = useRef<HTMLVideoElement>(null);
  const viewer = useViewer(similar);

  const fill = (x: Asset) => { setA(x); setCap(x.caption_user || ""); setPlace(x.place || ""); setDate(x.taken_at ? x.taken_at.slice(0, 10) : ""); setTags(x.tags); };
  useEffect(() => {
    api.get<Asset>(`/assets/${id}`).then(fill).catch(() => router.replace("/library"));
    api.get<{ items: Chunk[] }>(`/assets/${id}/chunks`).then((r) => setChunks(r.items)).catch(() => {});
    api.get<{ items: Asset[] }>(`/assets/${id}/similar`).then((r) => setSimilar(r.items)).catch(() => {});
  }, [id, tick]); // eslint-disable-line react-hooks/exhaustive-deps
  const seek = (ms: number) => { if (vid.current) { vid.current.currentTime = ms / 1000; vid.current.play().catch(() => {}); } };
  useEffect(() => { const t0 = Number(sp.get("t")); if (a && t0) setTimeout(() => seek(t0), 300); }, [a?.asset_id]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!a) return <div className="p-8"><Spinner /></div>;

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
    <div className="mx-auto grid max-w-[1440px] gap-8 px-4 py-6 sm:px-8 sm:py-8 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div className="min-w-0 space-y-6">
        <div className="overflow-hidden rounded-xl bg-ink">
          {a.kind === "video" && a.video_url ? <video ref={vid} src={abs(a.video_url)} poster={abs(a.preview_url)} controls className="max-h-[70vh] w-full" />
            : <img src={abs(a.original_url || a.preview_url)} alt={a.caption_user || a.title} className="mx-auto max-h-[70vh] object-contain" />}
        </div>
        {a.kind === "video" && moments.length > 0 && (
          <section><h2 className="mb-2 text-sm font-medium text-ink-soft">{t("media.moments")}</h2>
            <ul className="divide-y divide-paper-line rounded-xl border border-paper-line bg-paper-card">{moments.map((m) => (
              <li key={m.id}><button onClick={() => seek(m.start_ms!)} className="flex w-full gap-3 px-3 py-2 text-left text-sm hover:bg-paper-sunk">
                <span className="w-12 shrink-0 font-mono text-xs text-tide">{fmtDuration(m.start_ms)}</span><span className="line-clamp-2">{m.type === "transcript" ? `“${m.content}”` : m.content}</span></button></li>))}</ul></section>)}
        {similar.length > 0 && <section><h2 className="mb-2 text-sm font-medium text-ink-soft">{t("media.similar")}</h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">{similar.slice(0, 8).map((s) => <AssetTile key={s.asset_id} asset={s} onOpen={(x) => (x.kind === "document" ? router.push(`/documents/${x.asset_id}`) : router.push(`/media/${x.asset_id}`))} />)}</div></section>}
      </div>

      <aside className="space-y-4">
        <div className="card space-y-4 p-4">
          <h1 className="truncate text-lg font-medium" title={a.title}>{a.title}</h1>
          <label className="block text-sm font-medium">{t("media.caption")}<textarea rows={3} className="input mt-1 font-normal" value={cap} onChange={(e) => setCap(e.target.value)} placeholder={t("media.captionPh")} /></label>
          <label className="block text-sm font-medium">{t("media.location")}<input className="input mt-1 font-normal" value={place} onChange={(e) => setPlace(e.target.value)} /></label>
          <label className="block text-sm font-medium">{t("media.taken")}<input type="date" className="input mt-1 font-normal" value={date} onChange={(e) => setDate(e.target.value)} /></label>
          <div><p className="mb-1 text-sm font-medium">{t("media.tags")}</p>
            <div className="mb-2 flex flex-wrap gap-1.5">{tags.map((x) => <span key={x} className="chip chip-on">{x}<button aria-label={`Remove ${x}`} onClick={() => setTags(tags.filter((y) => y !== x))}><X className="h-3 w-3" /></button></span>)}</div>
            <form onSubmit={(e) => { e.preventDefault(); addTag(); }}><input className="input" value={tagIn} onChange={(e) => setTagIn(e.target.value)} placeholder={t("media.addTag")} /></form></div>
          <button className="btn-primary w-full" onClick={save} disabled={saving}>{saving && <Spinner />}{t("media.save")}</button>
        </div>
        <div className="card space-y-1 p-4 text-sm text-ink-soft">
          <h2 className="mb-1 font-medium text-ink">{t("media.details")}</h2>
          {a.width && <p>{a.width} × {a.height}</p>}{a.duration_ms ? <p>{fmtDuration(a.duration_ms)}</p> : null}{a.size_bytes ? <p>{fmtBytes(a.size_bytes)}</p> : null}
          {a.status === "failed" && <p className="text-danger">{a.status_detail}</p>}
        </div>
        <div className="flex flex-wrap gap-2">
          <DownloadMenu asset={a} tone="outline" />
          <button className="btn-outline" onClick={reindex}><RefreshCw className="h-4 w-4" />{t("media.reindex")}</button>
          <button className="btn-outline !text-danger" onClick={del}><Trash2 className="h-4 w-4" />{t("media.delete")}</button>
        </div>
      </aside>
      {viewer.node}
    </div>
  );
}
export default function MediaPage() { return <Suspense fallback={<div className="p-8"><Spinner /></div>}><MediaView /></Suspense>; }
