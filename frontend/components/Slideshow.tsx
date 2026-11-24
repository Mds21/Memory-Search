"use client";
import { FileText, Film, Pause, Play, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { abs } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { nameOf, type Asset } from "@/lib/types";
import { fmtDate } from "./ui";

const STEP_MS = 4500;

/** Full-screen story-style slideshow of a moment: progress bars on top, tap left/right, Space pauses, Esc closes. */
export default function Slideshow({ items, title, start = 0, onClose }: { items: Asset[]; title: string; start?: number; onClose: () => void }) {
  const { t, lang } = useI18n();
  const [i, setI] = useState(start);
  const [playing, setPlaying] = useState(true);
  const [tick, setTick] = useState(0);  // restarts the progress animation on every slide
  const go = useCallback((d: number) => { setI((x) => (x + d + items.length) % items.length); setTick((n) => n + 1); }, [items.length]);

  useEffect(() => {
    if (!playing) return;
    const id = setTimeout(() => (i === items.length - 1 ? setPlaying(false) : go(1)), STEP_MS);
    return () => clearTimeout(id);
  }, [i, playing, go, items.length, tick]);

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose(); else if (e.key === "ArrowRight") go(1); else if (e.key === "ArrowLeft") go(-1);
      else if (e.key === " ") { e.preventDefault(); setPlaying((p) => !p); }
    };
    window.addEventListener("keydown", key);
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", key); document.body.style.overflow = ""; };
  }, [go, onClose]);

  useEffect(() => {  // warm the next image so it fades in without a gap
    const n = items[(i + 1) % items.length];
    const src = n?.preview_url || n?.thumb_url;
    if (src) { const im = new Image(); im.src = abs(src); }
  }, [i, items]);

  const a = items[i];
  if (!a) return null;
  const src = abs(a.preview_url || a.thumb_url);
  const meta = [fmtDate(a.taken_at, lang), a.place].filter(Boolean).join(" · ");
  const bars = items.slice(0, 40);

  return (
    <div className="fixed inset-0 z-[70] flex flex-col bg-night text-white" role="dialog" aria-modal aria-label={title}>
      <div className="absolute inset-x-0 top-0 z-20 flex gap-1 px-4 pt-3">
        {bars.map((_, k) => (
          <span key={k} className="h-0.5 flex-1 overflow-hidden rounded-full bg-white/25">
            <span key={k === i ? `${tick}-${i}` : k} className={`block h-full origin-left bg-white ${k < i ? "" : k > i ? "scale-x-0" : ""}`}
              style={k === i ? { animation: `slide-progress ${STEP_MS}ms linear forwards`, animationPlayState: playing ? "running" : "paused" } : undefined} />
          </span>))}
      </div>
      <div className="absolute inset-x-0 top-5 z-20 flex items-center justify-between px-4 pt-2">
        <p className="truncate text-[12px] font-medium uppercase tracking-label text-white/85">{title} <span className="ml-2 tabular-nums text-white/50">{i + 1} / {items.length}</span></p>
        <div className="flex items-center gap-1">
          <button onClick={() => setPlaying((p) => !p)} className="btn-ghost !h-9 !w-9 !p-0 !text-white hover:!bg-white/10" aria-label={playing ? t("mo.pause") : t("mo.play")}>
            {playing ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}</button>
          <button onClick={onClose} className="btn-ghost !h-9 !w-9 !p-0 !text-white hover:!bg-white/10" aria-label={t("common.close")}><X className="h-5 w-5" /></button>
        </div>
      </div>

      <div className="relative flex min-h-0 flex-1 items-center justify-center">
        {src ? <img key={a.asset_id} src={src} alt={a.caption_user || a.title} className="max-h-full max-w-full animate-[slide-in_600ms_ease-out] object-contain" />
          : <span className="flex flex-col items-center gap-3 text-white/60">{a.kind === "document" ? <FileText className="h-12 w-12" strokeWidth={1} /> : <Film className="h-12 w-12" strokeWidth={1} />}{a.title}</span>}
        <button aria-label="Previous" onClick={() => go(-1)} className="absolute inset-y-0 left-0 w-1/3 cursor-w-resize" />
        <button aria-label="Next" onClick={() => go(1)} className="absolute inset-y-0 right-0 w-2/3 cursor-e-resize" />
      </div>

      <div className="pointer-events-none px-6 pb-6 pt-3">
        <p className="truncate text-[13px] text-white/90">{nameOf(a)}</p>
        {meta && <p className="mt-0.5 text-[11px] uppercase tracking-label text-white/50">{meta}</p>}
      </div>
      <style>{`@keyframes slide-progress { from { transform: scaleX(0) } to { transform: scaleX(1) } }
        @keyframes slide-in { from { opacity: 0; transform: scale(1.015) } to { opacity: 1; transform: none } }
        @media (prefers-reduced-motion: reduce) { [style*="slide-progress"] { animation: none !important; transform: none } }`}</style>
    </div>
  );
}
