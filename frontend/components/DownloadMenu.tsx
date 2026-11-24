"use client";
import { ChevronDown, Download } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, downloadHref } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";

const LABEL: Record<string, string> = {
  jpg: "JPG image", png: "PNG image", webp: "WebP image", gif: "GIF image", bmp: "BMP image", tif: "TIFF image",
  pdf: "PDF document", txt: "Text (.txt)", docx: "Word (.docx)", mp4: "MP4 video",
};
const ext = (name: string) => (name.split(".").pop() || "").toUpperCase();

/**
 * Download control. The main button saves the file exactly as it was uploaded (same format, same name); the arrow
 * opens "Download as" with the conversions the server offers for it. Links are signed and short-lived, so a fresh
 * one is fetched on every click.
 */
export default function DownloadMenu({ asset: a, tone = "ghost", compact = false }:
  { asset: Pick<Asset, "asset_id" | "title" | "download_formats">; tone?: "ghost" | "outline" | "dark"; compact?: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [formats, setFormats] = useState<string[] | undefined>(a.download_formats);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !box.current?.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("mousedown", close); window.addEventListener("keydown", close);
    return () => { window.removeEventListener("mousedown", close); window.removeEventListener("keydown", close); };
  }, [open]);

  const save = async (fmt?: string) => {
    setOpen(false);
    try {
      const d = await api.get<Asset>(`/assets/${a.asset_id}`);
      if (!formats) setFormats(d.download_formats);
      window.location.href = downloadHref(d.original_url, fmt);
    } catch { /* offline or deleted: nothing to save */ }
  };
  const toggle = async () => {
    if (!formats) { try { setFormats((await api.get<Asset>(`/assets/${a.asset_id}`)).download_formats || []); } catch { setFormats([]); } }
    setOpen((v) => !v);
  };

  const btn = tone === "dark" ? "btn-ghost !text-white hover:!bg-white/10" : tone === "outline" ? "btn-outline" : "btn-ghost";
  const menu = tone === "dark" ? "border-white/10 bg-[#1a1a1a] text-white" : "border-paper-line bg-paper-card text-ink";
  const hover = tone === "dark" ? "hover:bg-white/10" : "hover:bg-paper-sunk";
  const own = ext(a.title);

  return (
    <div ref={box} className="relative inline-flex">
      <button type="button" onClick={() => save()} className={`${btn} ${compact ? "!h-8 !w-8 !p-0" : "!rounded-r-none !pr-3"}`}
        title={`${t("media.download")} (${t("dl.original")}${own ? ` · ${own}` : ""})`} aria-label={`${t("media.download")} ${a.title}`}>
        <Download className="h-4 w-4" strokeWidth={1.5} />{!compact && <span>{t("media.download")}</span>}
      </button>
      <button type="button" onClick={toggle} aria-haspopup="menu" aria-expanded={open} aria-label={t("dl.as")} title={t("dl.as")}
        className={`${btn} ${compact ? "!h-8 !w-5 !p-0" : "!rounded-l-none !pl-1.5 !pr-2.5"}`}>
        <ChevronDown className="h-3.5 w-3.5" strokeWidth={1.5} />
      </button>
      {open && (
        <div role="menu" className={`absolute right-0 top-full z-40 mt-1 w-56 animate-rise rounded border p-1 shadow-lift ${menu}`}>
          <p className="px-3 pb-1 pt-2 text-[10px] font-medium uppercase tracking-label opacity-60">{t("dl.as")}</p>
          <button role="menuitem" type="button" onClick={() => save()} className={`flex w-full items-center justify-between rounded-sm px-3 py-2 text-left text-[13px] ${hover}`}>
            <span>{t("dl.original")}</span><span className="text-[11px] uppercase tracking-[0.06em] opacity-60">{own}</span>
          </button>
          {(formats || []).map((f) => (
            <button key={f} role="menuitem" type="button" onClick={() => save(f)} className={`flex w-full items-center justify-between rounded-sm px-3 py-2 text-left text-[13px] ${hover}`}>
              <span>{LABEL[f] || f.toUpperCase()}</span><span className="text-[11px] uppercase tracking-[0.06em] opacity-60">{f}</span>
            </button>))}
          {formats && formats.length === 0 && <p className="px-3 py-2 text-[12px] opacity-60">{t("dl.onlyOriginal")}</p>}
        </div>)}
    </div>
  );
}
