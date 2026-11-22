"use client";
import { Archive, ArrowRight, Camera, CheckCircle2, ChevronRight, CircleAlert, FileUp, RotateCw } from "lucide-react";
import Link from "next/link";
import { useRef } from "react";
import { Empty, PageHeader, Spinner } from "@/components/ui";
import { useI18n } from "@/lib/i18n";
import { useUploads } from "@/lib/uploads";

export default function Uploads() {
  const { t } = useI18n();
  const { items, addFiles, importZip, retry, busy } = useUploads();
  const fileRef = useRef<HTMLInputElement>(null); const zipRef = useRef<HTMLInputElement>(null); const camRef = useRef<HTMLInputElement>(null);
  const done = items.filter((i) => i.status === "ready" || i.status === "duplicate").length;
  return (
    <div className="mx-auto max-w-3xl px-4 py-4 sm:px-6 sm:py-6">
      <PageHeader title={t("up.title")} />
      <div onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); addFiles([...e.dataTransfer.files]); }}
        className="group relative isolate flex flex-col items-center gap-3 overflow-hidden rounded-3xl border-2 border-dashed border-tide/40 bg-paper-card px-5 py-10 text-center shadow-soft transition-colors hover:border-tide sm:px-6 sm:py-14">
        <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br from-tide/10 via-transparent to-iris/10" />
        <button onClick={() => fileRef.current?.click()} className="tap relative flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-tide to-iris text-paper shadow-glow transition-transform group-hover:-translate-y-0.5" aria-label={t("add.files")}><FileUp className="h-8 w-8" /></button>
        <p className="font-semibold"><span className="hidden lg:inline">{t("up.drop")}</span><span className="lg:hidden">{t("up.tap")}</span></p>
        <div className="grid w-full max-w-sm grid-cols-2 gap-2 sm:flex sm:w-auto sm:max-w-none sm:justify-center">
          <button className="btn-primary tap" onClick={() => fileRef.current?.click()}><FileUp className="h-4 w-4" />{t("add.files")}</button>
          <button className="btn-outline tap lg:hidden" onClick={() => camRef.current?.click()}><Camera className="h-4 w-4" />{t("add.camera")}</button>
          <button className="btn-outline tap col-span-2 sm:col-span-1" onClick={() => zipRef.current?.click()}><Archive className="h-4 w-4" />{t("up.zip")}</button>
        </div>
        <p className="text-xs text-ink-mute">{t("up.supported")}</p>
        <input ref={fileRef} type="file" multiple hidden onChange={(e) => { addFiles([...(e.target.files || [])]); e.target.value = ""; }} />
        <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { addFiles([...(e.target.files || [])]); e.target.value = ""; }} />
        <input ref={zipRef} type="file" accept=".zip" hidden onChange={(e) => { const f = e.target.files?.[0]; if (f) importZip(f); e.target.value = ""; }} />
      </div>

      {done > 0 && busy === 0 && (
        <Link href="/library" className="tap mt-4 flex animate-fade-up items-center justify-between rounded-2xl bg-tide-soft px-4 py-3 text-sm font-medium text-tide-dark">
          {t("up.allDone", { n: done })}<ArrowRight className="h-4 w-4" /></Link>)}

      <ul className="mt-4 space-y-2">
        {items.length === 0 && <Empty title={t("up.empty")} />}
        {items.map((i) => {
          const ok = i.status === "ready" || i.status === "duplicate";
          const body = (<>
            {ok ? <CheckCircle2 className="h-5 w-5 shrink-0 text-iris" /> : i.status === "failed" || i.status === "rejected" ? <CircleAlert className="h-5 w-5 shrink-0 text-danger" /> : <Spinner className="h-5 w-5 shrink-0" />}
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{i.name}</p>
              <p className="text-xs text-ink-mute">{t(`up.${i.status}`)}{i.detail ? ` • ${i.detail}` : ""}</p>
              {i.status === "uploading" && <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-paper-sunk"><div className="h-full rounded-full bg-gradient-to-r from-tide to-iris transition-all" style={{ width: `${i.progress}%` }} /></div>}
            </div>
            {i.status === "failed" && i.assetId && <button className="btn-outline tap" onClick={(e) => { e.preventDefault(); retry(i.assetId!); }}><RotateCw className="h-4 w-4" />{t("up.retry")}</button>}
            {ok && i.assetId && <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint" />}
          </>);
          return (
            <li key={i.key} className="animate-fade-up">
              {ok && i.assetId
                ? <Link href={`/media/${i.assetId}`} className="card tap flex min-h-[3.5rem] items-center gap-3 px-4 py-3 hover:border-tide/40">{body}</Link>
                : <div className="card flex min-h-[3.5rem] items-center gap-3 px-4 py-3">{body}</div>}
            </li>);
        })}
      </ul>
    </div>
  );
}
