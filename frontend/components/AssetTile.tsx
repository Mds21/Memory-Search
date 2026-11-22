"use client";
import { Check, Download, FileText, Play } from "lucide-react";
import { memo, useRef, useState } from "react";
import { abs } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { downloadAsset } from "@/lib/share";
import type { Asset } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { highlight } from "@/lib/util";
import { Spinner, fmtBytes, fmtDuration } from "./ui";

interface Props { asset: Asset; onOpen: (a: Asset) => void; selectMode?: boolean; selected?: boolean; onSelect?: (a: Asset) => void; terms?: string[]; priority?: boolean; onLongPress?: (a: Asset) => void }

/** Grid columns are ~180–320px wide; let the browser pick the 256px thumb or the 1000px preview by screen density. */
const SIZES = "(min-width: 1500px) 20vw, (min-width: 1100px) 25vw, (min-width: 640px) 33vw, 50vw";
const onLoad = (e: React.SyntheticEvent<HTMLImageElement>) => e.currentTarget.classList.add("loaded");

/** Coloured badge for a document format, the way file managers show them. */
export const TypeBadge = ({ type, className = "" }: { type?: string | null; className?: string }) =>
  type ? <span className={`inline-flex items-center rounded-md bg-ink px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-paper ${className}`}>{type}</span> : null;

function AssetTile({ asset: a, onOpen, selectMode, selected, onSelect, terms = [], priority, onLongPress }: Props) {
  // long-press (phones) starts selection, like a gallery app; the click that follows is swallowed
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const fired = useRef(false);
  const startPress = (e: React.PointerEvent) => {
    if (!onLongPress || e.pointerType === "mouse") return;
    fired.current = false;
    timer.current = setTimeout(() => { fired.current = true; navigator.vibrate?.(12); onLongPress(a); }, 450);
  };
  const endPress = () => { if (timer.current) clearTimeout(timer.current); timer.current = null; };
  const { t } = useI18n();
  const { toast } = useUploads();
  const [saving, setSaving] = useState(false);
  const pending = a.status === "queued" || a.status === "processing";
  const click = () => { if (fired.current) { fired.current = false; return; } selectMode ? onSelect?.(a) : onOpen(a); };
  const ratio = a.kind === "document" ? 3 / 4 : a.width && a.height ? a.width / a.height : 4 / 3;
  const label = a.display_title || a.caption_user || a.title;
  const thumb = abs(a.thumb_url), preview = abs(a.preview_url);
  const srcSet = thumb && preview ? `${thumb} 256w, ${preview} 1000w` : undefined;
  const isDoc = a.kind === "document";
  const download = async () => {
    setSaving(true);
    try { await downloadAsset(a); } catch { toast(t("share.failed"), "error"); } finally { setSaving(false); }
  };

  return (
    <div className={`tap group relative overflow-hidden rounded-2xl border bg-paper-card shadow-soft transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift ${selected ? "border-tide ring-2 ring-tide" : "border-paper-line/80"}`}>
      <button onClick={click} onPointerDown={startPress} onPointerUp={endPress} onPointerLeave={endPress} onPointerCancel={endPress}
        onContextMenu={(e) => onLongPress && e.preventDefault()} aria-label={label} aria-pressed={selectMode ? !!selected : undefined}
        className="block w-full text-left">
        <div className="relative w-full overflow-hidden bg-paper-sunk" style={{ aspectRatio: String(Math.min(Math.max(ratio, 0.6), 1.9)) }}>
          {a.thumb_url ? (
            <img src={preview || thumb} srcSet={srcSet} sizes={SIZES} alt={label} onLoad={onLoad}
              loading={priority ? "eager" : "lazy"} decoding="async" {...(priority ? { fetchpriority: "high" } : {})}
              className={`fade h-full w-full object-cover group-hover:scale-[1.03] ${isDoc ? "object-top" : ""}`} />
          ) : <div className="flex h-full items-center justify-center text-ink-faint">{pending ? <Spinner className="h-6 w-6" /> : <FileText className="h-8 w-8" />}</div>}
          <span className="pointer-events-none absolute inset-0 bg-gradient-to-t from-night/40 via-transparent to-transparent opacity-0 transition-opacity group-hover:opacity-100" />
          {a.kind === "video" && (<>
            <span className="absolute inset-0 flex items-center justify-center"><span className="flex h-11 w-11 items-center justify-center rounded-full bg-night/50 text-white ring-1 ring-white/30 backdrop-blur-md transition-transform group-hover:scale-110"><Play className="h-4 w-4 translate-x-px" fill="currentColor" /></span></span>
            <span className="absolute bottom-2 right-2 rounded-md bg-night/70 px-1.5 py-0.5 text-[11px] font-medium tabular-nums text-white backdrop-blur">{fmtDuration(a.duration_ms)}</span></>)}
          {pending && <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-night/60 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur"><Spinner className="h-3 w-3" />{t(`up.${a.status}`)}</span>}
          {a.status === "failed" && <span className="absolute left-2 top-2 rounded-full bg-danger px-2 py-0.5 text-[11px] font-medium text-white">{t("up.failed")}</span>}
          {selectMode && <span className={`absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full border-2 transition-colors ${selected ? "border-tide bg-tide text-paper" : "border-white bg-night/30"}`}>{selected && <Check className="h-3.5 w-3.5" />}</span>}
          {isDoc && !selectMode && <TypeBadge type={a.file_type} className="absolute left-2 top-2 shadow-soft" />}
          {!isDoc && a.doc_label && !selectMode && <span className="absolute bottom-2 left-2 max-w-[80%] truncate rounded-md bg-night/70 px-1.5 py-0.5 text-[11px] font-medium text-white backdrop-blur">{a.doc_label}</span>}
          {a.match?.page && <span className="absolute right-2 top-2 rounded-full bg-night/70 px-2 py-0.5 text-[11px] font-semibold text-white backdrop-blur">{t("search.page")} {a.match.page}</span>}
        </div>
        {(isDoc || (a.snippet && terms.length > 0 && a.match?.type === "transcript")) && (
          <div className="p-3 pr-12">
            <p className="line-clamp-2 text-sm font-medium leading-snug">{label}</p>
            <p className="mt-0.5 truncate text-[11px] text-ink-mute">
              {[a.doc_label && a.doc_label !== label ? a.doc_label : null, a.page_count ? `${a.page_count} ${t("doc.pages").toLowerCase()}` : null, a.size_bytes ? fmtBytes(a.size_bytes) : null].filter(Boolean).join(" · ")}</p>
            {a.snippet && <p className="mt-1.5 line-clamp-3 text-xs leading-relaxed text-ink-mute">{highlight(a.snippet, terms)}</p>}
          </div>)}
        {a.status === "failed" && a.status_detail && <p className="border-t border-paper-line p-2 text-xs text-danger">{a.status_detail}</p>}
      </button>
      {!selectMode && !pending && a.status !== "failed" && (
        <button onClick={download} disabled={saving} aria-label={`${t("share.download")} ${label}`} title={t("share.download")}
          className={`absolute flex h-9 w-9 items-center justify-center rounded-xl transition-all ${isDoc
            ? "bottom-2.5 right-2.5 bg-paper-sunk text-ink-soft hover:bg-tide hover:text-paper"
            : "right-2 top-2 bg-night/55 text-white opacity-0 backdrop-blur hover:bg-night/75 group-hover:opacity-100 [@media(pointer:coarse)]:hidden"}`}>
          {saving ? <Spinner className="h-4 w-4" /> : <Download className="h-4 w-4" />}</button>)}
    </div>
  );
}
export default memo(AssetTile);
