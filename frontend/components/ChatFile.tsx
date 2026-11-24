"use client";
import { Eye, FileText, Film, Image as ImageIcon } from "lucide-react";
import { abs } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";
import DownloadMenu from "./DownloadMenu";
import { fmtDate } from "./ui";

/** A file the assistant shared in a reply: preview, what it is, and View / Download right there in the chat. */
export default function ChatFile({ asset: a, label, onView }: { asset: Asset; label?: string; onView: (a: Asset) => void }) {
  const { t, lang } = useI18n();
  const Kind = a.kind === "video" ? Film : a.kind === "document" ? FileText : ImageIcon;
  const meta = [a.match?.page ? `${t("search.page")} ${a.match.page}` : null, fmtDate(a.taken_at, lang) || null, a.place].filter(Boolean).join(" · ");

  return (
    <div className="group flex items-center gap-3 rounded border border-paper-line bg-paper p-2 pr-3 transition-colors hover:border-ink-faint/60">
      <button type="button" onClick={() => onView(a)} aria-label={`${t("chat.view")} ${a.title}`}
        className="relative h-14 w-14 shrink-0 overflow-hidden rounded-sm bg-paper-sunk">
        {a.thumb_url ? <img src={abs(a.thumb_url)} alt="" className={`h-full w-full object-cover ${a.kind === "document" ? "object-top" : ""}`} />
          : <span className="flex h-full items-center justify-center text-ink-faint"><Kind className="h-5 w-5" strokeWidth={1.5} /></span>}
        {label && <span className="absolute left-1 top-1 rounded-sm bg-night/75 px-1 font-mono text-[10px] text-[#d8b65a]">{label}</span>}
      </button>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1.5 truncate text-[13px] font-medium"><Kind className="h-3.5 w-3.5 shrink-0 text-ink-mute" strokeWidth={1.5} /><span className="truncate">{a.caption_user || a.title}</span></p>
        {meta && <p className="mt-0.5 truncate text-[11px] uppercase tracking-[0.06em] text-ink-mute">{meta}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button type="button" onClick={() => onView(a)} className="btn-ghost !h-8 !px-3 text-[12px]" title={t("chat.view")}><Eye className="h-4 w-4" strokeWidth={1.5} /><span className="hidden sm:inline">{t("chat.view")}</span></button>
        <DownloadMenu asset={a} compact />
      </div>
    </div>
  );
}
