"use client";
import { ChevronLeft, ChevronRight, ExternalLink, X, ZoomIn } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { nameOf, type Asset } from "@/lib/types";
import DownloadMenu from "./DownloadMenu";
import { fmtDate } from "./ui";

/** Full-screen viewer for photos and videos: arrows/swipe to navigate, click or +/- to zoom, Esc to close. */
export default function Lightbox({ items, index, onIndex, onClose }: { items: Asset[]; index: number; onIndex: (i: number) => void; onClose: () => void }) {
  const { t, lang } = useI18n();
  const cur = items[index];
  const [full, setFull] = useState<Asset | null>(null);
  const [zoom, setZoom] = useState(false);
  const touch = useRef<number | null>(null);

  useEffect(() => {
    setZoom(false); setFull(null);
    if (cur) api.get<Asset>(`/assets/${cur.asset_id}`).then(setFull).catch(() => {});
  }, [cur?.asset_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const go = useCallback((d: number) => { const n = index + d; if (n >= 0 && n < items.length) onIndex(n); }, [index, items.length, onIndex]);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose(); else if (e.key === "ArrowRight") go(1); else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === "+" || e.key === "=") setZoom(true); else if (e.key === "-") setZoom(false);
    };
    window.addEventListener("keydown", h);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", h); document.body.style.overflow = ""; };
  }, [go, onClose]);
  if (!cur) return null;
  const a = full || cur;
  const src = abs(a.kind === "photo" ? a.original_url || a.preview_url || a.thumb_url : a.preview_url);

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-night text-white" role="dialog" aria-modal aria-label={a.title}
      onTouchStart={(e) => (touch.current = e.touches[0].clientX)}
      onTouchEnd={(e) => { if (touch.current == null || zoom) return; const dx = e.changedTouches[0].clientX - touch.current; if (Math.abs(dx) > 60) go(dx < 0 ? 1 : -1); touch.current = null; }}>
      <div className="flex items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0"><p className="truncate text-sm font-medium" title={a.title}>{nameOf(a)}</p>
          <p className="truncate text-xs text-white/60">{[fmtDate(a.taken_at, lang), a.place].filter(Boolean).join(" • ")}</p></div>
        <div className="flex items-center gap-1">
          {a.kind === "photo" && <button className="btn-ghost !text-white hover:!bg-white/10" onClick={() => setZoom((z) => !z)} aria-label="Zoom"><ZoomIn className="h-4 w-4" /></button>}
          <DownloadMenu asset={full || a} tone="dark" />
          <Link href={`/media/${a.asset_id}`} className="btn-ghost !text-white hover:!bg-white/10" onClick={onClose}><ExternalLink className="h-4 w-4" /><span className="hidden sm:inline">{t("media.details")}</span></Link>
          <button className="btn-ghost !text-white hover:!bg-white/10" onClick={onClose} aria-label={t("common.close")}><X className="h-5 w-5" /></button>
        </div>
      </div>
      <div className="relative flex min-h-0 flex-1 items-center justify-center" onClick={(e) => e.target === e.currentTarget && onClose()}>
        {index > 0 && <button onClick={() => go(-1)} aria-label="Previous" className="absolute left-2 z-10 rounded-[3px] bg-paper-card/10 p-2 hover:bg-paper-card/20"><ChevronLeft className="h-6 w-6" /></button>}
        {a.kind === "video" && full?.video_url
          ? <video key={a.asset_id} src={abs(full.video_url)} poster={abs(a.preview_url)} controls autoPlay className="max-h-full max-w-full" />
          : <div className={`h-full w-full ${zoom ? "overflow-auto" : "flex items-center justify-center"}`}>
              <img key={a.asset_id} src={src} alt={a.caption_user || a.title} onClick={() => setZoom((z) => !z)}
                className={zoom ? "max-w-none cursor-zoom-out" : "max-h-full max-w-full cursor-zoom-in object-contain"} style={zoom ? { width: "180%" } : undefined} /></div>}
        {index < items.length - 1 && <button onClick={() => go(1)} aria-label="Next" className="absolute right-2 z-10 rounded-[3px] bg-paper-card/10 p-2 hover:bg-paper-card/20"><ChevronRight className="h-6 w-6" /></button>}
      </div>
      {a.tags.length > 0 && <div className="flex flex-wrap gap-1.5 px-4 py-3">{a.tags.slice(0, 10).map((x) => <span key={x} className="rounded-[3px] bg-paper-card/10 px-2.5 py-0.5 text-xs">{x}</span>)}</div>}
    </div>
  );
}
