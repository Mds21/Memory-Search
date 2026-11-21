"use client";
import { Download, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { Spinner, fmtBytes } from "@/components/ui";
import { api, raw } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { User } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

export default function Settings() {
  const { t } = useI18n();
  const { user, setUser, logout } = useAuth();
  const { toast } = useUploads();
  const [name, setName] = useState(user?.display_name || "");
  const [tz, setTz] = useState(user?.timezone || "UTC");
  const [store, setStore] = useState<{ items: { kind: string; count: number; bytes: number }[]; adapters: Record<string, string> } | null>(null);
  useEffect(() => { api.get<typeof store>("/me/storage").then(setStore).catch(() => {}); }, []);
  useEffect(() => { if (user) { setName(user.display_name || ""); setTz(user.timezone); } }, [user]);

  const save = async () => { try { setUser(await api.patch<User>("/me", { display_name: name, timezone: tz })); toast(t("media.saved")); } catch (e: any) { toast(e.message, "error"); } };
  const exportData = async () => {
    const r = await raw("/me/export"); const b = await r.blob(); const u = URL.createObjectURL(b);
    const a = document.createElement("a"); a.href = u; a.download = "smriti-export.zip"; a.click(); URL.revokeObjectURL(u);
  };
  const reindex = async () => { try { const r = await api.post<{ queued: number }>("/admin/reindex", { only_failed: true }); toast(`${t("up.queued")}: ${r.queued}`); } catch (e: any) { toast(e.message, "error"); } };
  const del = async () => { if (confirm(t("set.deleteWarn"))) { await api.del("/me"); logout(); } };
  const bytes = store?.items.reduce((s, i) => s + i.bytes, 0) || 0;

  return (
    <div className="mx-auto max-w-2xl space-y-5 px-4 py-6 sm:px-6">
      <h1 className="h-page">{t("set.title")}</h1>
      <section className="card space-y-4 p-5"><h2 className="font-semibold">{t("set.profile")}</h2>
        <p className="text-sm text-ink-mute">{user?.email}</p>
        <label className="block text-sm font-medium">{t("set.name")}<input className="input mt-1 font-normal" value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label className="block text-sm font-medium">{t("set.timezone")}<input className="input mt-1 font-normal" value={tz} onChange={(e) => setTz(e.target.value)} /></label>
        <div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-medium">{t("set.language")} <LanguageSwitcher /></div><button className="btn-primary" onClick={save}>{t("common.save")}</button></div>
      </section>
      <section className="card p-5"><h2 className="mb-3 font-semibold">{t("set.storage")}</h2>
        {!store ? <Spinner /> : (<ul className="space-y-1 text-sm">{store.items.map((i) => <li key={i.kind} className="flex justify-between"><span className="capitalize">{i.kind}s</span><span className="text-ink-mute">{i.count} • {fmtBytes(i.bytes)}</span></li>)}
          <li className="flex justify-between border-t border-paper-line pt-1 font-medium"><span>Total</span><span>{fmtBytes(bytes)}</span></li></ul>)}</section>
      {store && <section className="card p-5"><h2 className="font-semibold">{t("set.models")}</h2><p className="mb-3 text-xs text-ink-mute">{t("set.modelsHint")}</p>
        <dl className="grid grid-cols-[8rem_1fr] gap-y-1 text-sm">{Object.entries(store.adapters).map(([k, v]) => <div key={k} className="contents"><dt className="text-ink-mute">{k}</dt><dd className="font-mono text-xs">{v}</dd></div>)}</dl></section>}
      <section className="flex flex-wrap gap-2">
        <button className="btn-outline" onClick={exportData}><Download className="h-4 w-4" />{t("set.export")}</button>
        {user?.is_admin && <button className="btn-outline" onClick={reindex}><RefreshCw className="h-4 w-4" />{t("set.reindex")}</button>}
        <button className="btn-outline !text-danger" onClick={del}><Trash2 className="h-4 w-4" />{t("set.delete")}</button>
      </section>
    </div>
  );
}
