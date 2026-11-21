"use client";
import { Archive, CheckCircle2, CircleAlert, FileUp, RotateCw } from "lucide-react";
import Link from "next/link";
import { useRef } from "react";
import { Empty, Spinner } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { useUploads } from "@/lib/uploads";

export default function Uploads() {
  const { t } = useI18n();
  const { items, addFiles, importZip, retry } = useUploads();
  const fileRef = useRef<HTMLInputElement>(null); const zipRef = useRef<HTMLInputElement>(null);
  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      <h1 className="h-page mb-5">{t("up.title")}</h1>
      <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); addFiles([...e.dataTransfer.files]); }}
        className="flex flex-col items-center gap-3 rounded-2xl border-2 border-dashed border-tide-ring bg-tide-soft/50 px-6 py-12 text-center">
        <FileUp className="h-8 w-8 text-tide" />
        <p className="font-medium">{t("up.drop")}</p>
        <div className="flex flex-wrap justify-center gap-2">
          <button className="btn-primary" onClick={() => fileRef.current?.click()}>{t("up.browse")}</button>
          <button className="btn-outline" onClick={() => zipRef.current?.click()}><Archive className="h-4 w-4" />{t("up.zip")}</button>
        </div>
        <p className="text-xs text-ink-mute">{t("up.supported")}</p>
        <input ref={fileRef} type="file" multiple hidden onChange={(e) => { addFiles([...(e.target.files || [])]); e.target.value = ""; }} />
        <input ref={zipRef} type="file" accept=".zip" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) importZip(f); e.target.value = ""; }} />
      </div>
      <ul className="mt-6 space-y-2">
        {items.length === 0 && <Empty title={t("up.empty")} />}
        {items.map((i) => (
          <li key={i.key} className="card flex items-center gap-3 px-4 py-3">
            {i.status === "ready" || i.status === "duplicate" ? <CheckCircle2 className="h-5 w-5 shrink-0 text-tide" /> : i.status === "failed" || i.status === "rejected" ? <CircleAlert className="h-5 w-5 shrink-0 text-danger" /> : <Spinner className="h-5 w-5 shrink-0" />}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{i.assetId && i.status === "ready" ? <Link className="hover:underline" href={`/media/${i.assetId}`}>{i.name}</Link> : i.name}</p>
              <p className="text-xs text-ink-mute">{t(`up.${i.status}`)}{i.detail ? ` • ${i.detail}` : ""}</p>
              {i.status === "uploading" && <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-paper-sunk"><div className="h-full bg-tide transition-all" style={{ width: `${i.progress}%` }} /></div>}
            </div>
            {i.status === "failed" && i.assetId && <button className="btn-outline" onClick={() => retry(i.assetId!)}><RotateCw className="h-4 w-4" />{t("up.retry")}</button>}
          </li>))}
      </ul>
    </div>
  );
}
