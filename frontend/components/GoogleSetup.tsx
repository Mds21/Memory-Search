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
  const { data, reload } = useApi<{ client_id: string | null; source: "env" | "app" | null }>("/admin/settings/google");
  const [cid, setCid] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { setCid(data?.client_id || ""); }, [data?.client_id]);
  const on = !!data?.client_id;
  const origin = typeof window !== "undefined" ? window.location.origin : "";

  const save = async (value: string) => {
    setBusy(true);
    try { await api.put("/admin/settings/google", { client_id: value }); toast(value ? t("gs.saved") : t("gs.removed")); reload(); }
    catch (e: any) { toast(e.message, "error"); } finally { setBusy(false); }
  };

  return (
    <section className="card space-y-4 p-5">
      <div className="flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 font-semibold"><GoogleG />{t("gs.title")}</h2>
        {data && <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${on ? "bg-ink text-paper" : "bg-paper-sunk text-ink-mute"}`}>{on ? t("gs.on") : t("gs.off")}</span>}
      </div>
      <p className="text-sm text-ink-soft">{t("gs.intro")}</p>
      {on && (
        <details className="rounded-2xl border border-paper-line bg-paper-sunk/60 p-3 text-sm">
          <summary className="cursor-pointer font-medium">{t("gs.troubleTitle")}</summary>
          <p className="mt-2 text-ink-soft">{t("gs.troubleBody")}</p>
          <div className="mt-2 flex flex-wrap gap-1.5">{[origin, origin.replace(/:\d+$/, "")].filter((v, i, a) => a.indexOf(v) === i).map((o) => (
            <code key={o} className="rounded-lg bg-paper-card px-2 py-1 text-xs text-ink">{o}</code>))}</div>
          <p className="mt-2 text-xs text-ink-mute">{t("gs.troubleWait")}</p>
        </details>)}
      {data?.source === "env" ? <p className="text-sm text-ink-mute">{t("gs.fromConfig")}</p> : (<>
        <ol className="list-decimal space-y-1.5 pl-5 text-sm text-ink-soft marker:text-ink-faint">
          <li>{t("gs.step1")}</li>
          <li>{t("gs.step2")}</li>
          <li>{t("gs.step3")} <code className="rounded bg-paper-sunk px-1.5 py-0.5 text-xs text-ink">{origin}</code></li>
          <li>{t("gs.step4")}</li>
        </ol>
        <a href="https://console.cloud.google.com/apis/credentials" target="_blank" rel="noreferrer" className="btn-ghost -ml-2 !py-1 text-sm"><ExternalLink className="h-4 w-4" />{t("gs.open")}</a>
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); save(cid.trim()); }}>
          <input className="input min-w-0 flex-1" value={cid} onChange={(e) => setCid(e.target.value)} placeholder={t("gs.placeholder")} autoCapitalize="none" spellCheck={false} />
          <button className="btn-primary tap shrink-0" disabled={busy || !cid.trim() || cid.trim() === data?.client_id}>{busy && <Spinner />}{on ? t("gs.update") : t("gs.save")}</button>
          {on && <button type="button" className="btn-outline tap shrink-0" disabled={busy} onClick={() => save("")}>{t("gs.disable")}</button>}
        </form>
      </>)}
    </section>
  );
}
