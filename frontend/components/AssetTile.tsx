"use client";
import { Check, FileText, Play } from "lucide-react";
import { abs } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";
import { highlight } from "@/lib/util";
import { Spinner, fmtDuration } from "./ui";

interface Props { asset: Asset; onOpen: (a: Asset) => void; selectMode?: boolean; selected?: boolean; onSelect?: (a: Asset) => void; terms?: string[] }

export default function AssetTile({ asset: a, onOpen, selectMode, selected, onSelect, terms = [] }: Props) {
  const { t } = useI18n();
  const pending = a.status === "queued" || a.status === "processing";
  const click = () => (selectMode ? onSelect?.(a) : onOpen(a));
  const ratio = a.kind === "document" ? 3 / 4 : a.width && a.height ? a.width / a.height : 4 / 3;
  const label = a.caption_user || a.title;

  return (
    <button onClick={click} aria-label={label} aria-pressed={selectMode ? !!selected : undefined}
      className="group relative block w-full rounded-lg text-left">
      <div className={`relative w-full overflow-hidden rounded-lg bg-paper-sunk ${a.kind === "document" ? "border border-paper-line" : ""} ${selected ? "ring-2 ring-tide ring-offset-2 ring-offset-paper" : ""}`} style={{ aspectRatio: String(Math.min(Math.max(ratio, 0.6), 1.9)) }}>
        {a.thumb_url ? <img src={abs(a.preview_url || a.thumb_url)} alt={label} loading="lazy" className={`h-full w-full transition-opacity group-hover:opacity-90 ${a.kind === "document" ? "object-cover object-top" : "object-cover"}`} />
          : <div className="flex h-full items-center justify-center text-ink-faint">{pending ? <Spinner className="h-6 w-6" /> : <FileText className="h-8 w-8" />}</div>}
        {a.kind === "video" && (<>
          <span className="absolute inset-0 flex items-center justify-center"><span className="flex h-10 w-10 items-center justify-center rounded-full bg-night/55 text-white backdrop-blur"><Play className="h-4 w-4 translate-x-px" fill="currentColor" /></span></span>
          <span className="absolute bottom-2 right-2 rounded-sm bg-night/70 px-1.5 py-0.5 font-mono text-[11px] tabular-nums text-white">{fmtDuration(a.duration_ms)}</span></>)}
        {pending && <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-sm bg-paper-card/95 px-2 py-0.5 text-[11px] font-medium text-ink-soft shadow-soft"><Spinner className="h-3 w-3" />{t(`up.${a.status}`)}</span>}
        {a.status === "failed" && <span className="absolute left-2 top-2 rounded-sm bg-danger px-2 py-0.5 text-[11px] font-medium text-white">{t("up.failed")}</span>}
        {selectMode && <span className={`absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full border-2 ${selected ? "border-tide bg-tide text-paper" : "border-white bg-night/30"}`}>{selected && <Check className="h-3.5 w-3.5" />}</span>}
        {a.match?.page && <span className="absolute right-2 top-2 rounded-sm bg-paper-card/95 px-2 py-0.5 font-mono text-[11px] tabular-nums text-tide shadow-soft">{t("search.page")} {a.match.page}</span>}
      </div>
      {a.kind !== "document" && (
        <p className="mt-2 truncate text-xs text-ink-mute">{[a.place, a.taken_at ? new Date(a.taken_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : null].filter(Boolean).join(", ") || <span className="text-ink-faint">{label}</span>}</p>)}
      {(a.kind === "document" || (a.snippet && terms.length > 0 && a.match?.type === "transcript")) && (
        <div className="pt-2.5">
          <p className="truncate text-sm font-medium">{a.title}</p>
          {a.snippet && <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-ink-mute">{highlight(a.snippet, terms)}</p>}
        </div>)}
      {a.status === "failed" && a.status_detail && <p className="pt-1 text-xs text-danger">{a.status_detail}</p>}
    </button>
  );
}
