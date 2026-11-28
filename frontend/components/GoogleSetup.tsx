"use client";
import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useApi } from "@/lib/swr";
import { useUploads } from "@/lib/uploads";
import { GoogleG } from "./GoogleButton";
import { Spinner } from "./ui";

/** Owner-only: switch "Continue with Google" on by pasting the app's Google Client ID once. */
export default function GoogleSetup() {
  const { t } = useI18n();
  const { toast } = useUploads();
  const { data, reload } = useApi<{ client_id: string | null; source: "env" | "app" | null; enabled: boolean }>("/admin/settings/google");
  const [cid, setCid] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setCid(data?.client_id || ""); }, [data?.client_id]);
  const configured = !!data?.client_id;
  const on = configured && data?.enabled !== false;
  const origin = typeof window !== "undefined" ? window.location.origin : "";

  const save = async (value: string) => {
    setBusy(true);
    try { await api.put("/admin/settings/google", { client_id: value }); toast(value ? t("gs.saved") : t("gs.removed")); reload(); }
    catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  const setEnabled = async (enabled: boolean) => {
    setBusy(true);
    try { await api.put("/admin/settings/google/enabled", { enabled }); toast(enabled ? t("gs.resumed") : t("gs.pausedToast")); reload(); }
    catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  return (
    <section className="card space-y-5 p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-[13px] font-medium uppercase tracking-label"><GoogleG size={16} />{t("gs.title")}</h2>
        {data && <span className={`flex items-center gap-1.5 text-xs ${on ? "text-ok" : "text-ink-mute"}`}><span className={`h-1.5 w-1.5 ${on ? "bg-ok" : "bg-ink-faint"}`} />{on ? t("gs.on") : configured ? t("gs.paused") : t("gs.off")}</span>}
      </div>
      {configured && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded border border-paper-line bg-paper-sunk/60 px-4 py-3">
          <p className="min-w-0 flex-1 text-sm text-ink-soft">{on ? t("gs.onNote") : t("gs.pausedNote")}</p>
          <button type="button" role="switch" aria-checked={on} disabled={busy} onClick={() => setEnabled(!on)} className={on ? "btn-outline shrink-0" : "btn-primary shrink-0"}>
            {busy && <Spinner />}{on ? t("gs.pause") : t("gs.resume")}</button>
        </div>)}
      <p className="text-sm text-ink-soft">{t("gs.intro")}</p>
      {on && (
        <details className="rounded border border-paper-line bg-paper-sunk/60 p-3 text-sm">
          <summary className="cursor-pointer font-medium">{t("gs.troubleTitle")}</summary>
          <p className="mt-2 text-ink-soft">{t("gs.troubleBody")}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">{[origin, origin.replace(/:\d+$/, "")].filter((v, i, a) => a.indexOf(v) === i).map((o) => (
            <code key={o} className="rounded-sm bg-paper-card px-2 py-1 font-mono text-xs text-ink">{o}</code>))}</div>
          <p className="mt-2 text-xs text-ink-mute">{t("gs.troubleWait")}</p>
        </details>)}
      {data?.source === "env" ? <p className="text-sm text-ink-mute">{t("gs.fromConfig")}</p> : (<>
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-ink-soft marker:text-ink-faint">
          <li>{t("gs.step1")}</li>
          <li>{t("gs.step2")}</li>
          <li>{t("gs.step3")} <code className="rounded-sm bg-paper-sunk px-1.5 py-0.5 font-mono text-xs text-ink">{origin}</code></li>
          <li>{t("gs.step4")}</li>
        </ol>
        <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer" className="btn-ghost -ml-2 !py-1 text-sm"><ExternalLink className="h-4 w-4" />{t("gs.open")}</a>
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); save(cid.trim()); }}>
          <input className="input min-w-0 flex-1" value={cid} onChange={(e) => setCid(e.target.value)} placeholder={t("gs.placeholder")} autoCapitalize="none" spellCheck={false} />
          <button className="btn-primary shrink-0" disabled={busy || !cid.trim() || cid.trim() === data?.client_id}>{busy && <Spinner />}{on ? t("gs.update") : t("gs.save")}</button>
          {on && <button type="button" className="btn-outline shrink-0" disabled={busy} onClick={() => save("")}>{t("gs.disable")}</button>}
        </form>
      </>)}
    </section>
  );
}
