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
      className={`group relative block w-full overflow-hidden rounded-xl border bg-white text-left transition-shadow hover:shadow-lift ${selected ? "border-tide ring-2 ring-tide" : "border-paper-line"}`}>
      <div className="relative w-full bg-paper-sunk" style={{ aspectRatio: String(Math.min(Math.max(ratio, 0.6), 1.9)) }}>
        {a.thumb_url ? <img src={abs(a.preview_url || a.thumb_url)} alt={label} loading="lazy" className={`h-full w-full ${a.kind === "document" ? "object-cover object-top" : "object-cover"}`} />
          : <div className="flex h-full items-center justify-center text-ink-faint">{pending ? <Spinner className="h-6 w-6" /> : <FileText className="h-8 w-8" />}</div>}
        {a.kind === "video" && (<>
          <span className="absolute inset-0 flex items-center justify-center"><span className="flex h-10 w-10 items-center justify-center rounded-full bg-ink/60 text-white backdrop-blur"><Play className="h-4 w-4 translate-x-px" fill="currentColor" /></span></span>
          <span className="absolute bottom-2 right-2 rounded bg-ink/70 px-1.5 py-0.5 text-[11px] font-medium text-white">{fmtDuration(a.duration_ms)}</span></>)}
        {pending && <span className="absolute left-2 top-2 inline-flex items-center gap-1 rounded-full bg-white/90 px-2 py-0.5 text-[11px] font-medium text-ink-soft"><Spinner className="h-3 w-3" />{t(`up.${a.status}`)}</span>}
        {a.status === "failed" && <span className="absolute left-2 top-2 rounded-full bg-danger px-2 py-0.5 text-[11px] font-medium text-white">{t("up.failed")}</span>}
        {selectMode && <span className={`absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded-full border-2 ${selected ? "border-tide bg-tide text-white" : "border-white bg-ink/30"}`}>{selected && <Check className="h-3.5 w-3.5" />}</span>}
        {a.match?.page && <span className="absolute right-2 top-2 rounded-full bg-white/95 px-2 py-0.5 text-[11px] font-semibold text-tide-dark shadow">{t("search.page")} {a.match.page}</span>}
      </div>
      {(a.kind === "document" || (a.snippet && terms.length > 0 && a.match?.type === "transcript")) && (
        <div className="p-3">
          <p className="truncate text-sm font-medium">{a.title}</p>
          {a.snippet && <p className="mt-1 line-clamp-3 text-xs leading-relaxed text-ink-mute">{highlight(a.snippet, terms)}</p>}
        </div>)}
      {a.status === "failed" && a.status_detail && <p className="border-t border-paper-line p-2 text-xs text-danger">{a.status_detail}</p>}
    </button>
  );
}
