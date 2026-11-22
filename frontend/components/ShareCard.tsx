"use client";
import { Download, ExternalLink, FileText, Share2, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { abs } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { downloadAsset, shareAsset } from "@/lib/share";
import type { Asset } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { Spinner } from "./ui";
import { assetHref } from "./useViewer";

/** Share / Download buttons for one file; used in chat replies, on the photo page and in the viewer. */
export function ShareActions({ asset: a, size = "sm", dark }: { asset: Asset; size?: "sm" | "md"; dark?: boolean }) {
  const { t } = useI18n();
  const { toast } = useUploads();
  const [busy, setBusy] = useState<"share" | "download" | null>(null);
  const run = async (kind: "share" | "download") => {
    setBusy(kind);
    try {
      if (kind === "download") await downloadAsset(a);
      else if ((await shareAsset(a)) === "copied") toast(t("share.copied"));
    } catch { toast(t("share.failed"), "error"); } finally { setBusy(null); }
  };
  const pad = size === "md" ? "!px-4 !py-2.5" : "!px-2.5 !py-1 text-xs";
  const ic = size === "md" ? "h-4 w-4" : "h-3.5 w-3.5";
  return (<>
    <button className={`btn-primary tap ${pad}`} onClick={() => run("share")} disabled={!!busy}>{busy === "share" ? <Spinner className={ic} /> : <Share2 className={ic} />}{t("share.share")}</button>
    <button className={`${dark ? "btn-ghost !text-white hover:!bg-white/10" : "btn-outline"} tap ${pad}`} onClick={() => run("download")} disabled={!!busy}>{busy === "download" ? <Spinner className={ic} /> : <Download className={ic} />}{t("share.download")}</button>
  </>);
}

/** The file the user asked for ("share my pan card"), with one-tap Share / Download / Open. */
export default function ShareCard({ asset: a }: { asset: Asset }) {
  const { t } = useI18n();
  return (
    <div className="mt-3 flex animate-scale-in gap-3 rounded-2xl border border-paper-line bg-paper-sunk/60 p-2.5">
      <Link href={assetHref(a)} className="tap relative h-20 w-20 shrink-0 overflow-hidden rounded-xl bg-paper-card">
        {a.thumb_url ? <img src={abs(a.thumb_url)} alt={a.title} className="h-full w-full object-cover" />
          : <span className="flex h-full items-center justify-center text-ink-faint"><FileText className="h-6 w-6" /></span>}
      </Link>
      <div className="flex min-w-0 flex-1 flex-col justify-between gap-1.5">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-ink">{a.display_title || a.doc_label || a.title}</p>
          <p className="flex items-center gap-1 truncate text-xs text-ink-mute">
            {a.people?.[0] ? <><UserRound className="h-3 w-3 shrink-0" />{a.people[0]}</> : a.title}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <ShareActions asset={a} />
          <Link href={assetHref(a)} className="btn-ghost tap !px-2 !py-1 text-xs"><ExternalLink className="h-3.5 w-3.5" />{t("share.open")}</Link>
        </div>
      </div>
    </div>
  );
}
