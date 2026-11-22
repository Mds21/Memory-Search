"use client";
import { Download, FileText, Image as ImageIcon, RefreshCw, Trash2, Video } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { PeopleCard, SignInCard } from "@/components/AccountCards";
import GoogleSetup from "@/components/GoogleSetup";
import { GoogleG } from "@/components/GoogleButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { LineSkeleton, PageHeader, fmtBytes } from "@/components/ui";
import { api, raw } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useApi } from "@/lib/swr";
import { useI18n } from "@/lib/i18n";
import type { User } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

const KIND_ICON: Record<string, typeof ImageIcon> = { photo: ImageIcon, video: Video, document: FileText };
const KIND_KEY: Record<string, string> = { photo: "search.photos", video: "search.videos", document: "search.documents" };

/** "Asia/Kolkata" -> "Kolkata (GMT+5:30)": people pick a city, not an identifier. */
function zoneLabel(z: string) {
  let off = "";
  try { off = new Intl.DateTimeFormat("en", { timeZone: z, timeZoneName: "shortOffset" }).formatToParts().find((p) => p.type === "timeZoneName")?.value || ""; } catch { /* old browser */ }
  const city = z.split("/").pop()!.replace(/_/g, " ");
  return off ? `${city} (${off})` : city;
}

export default function Settings() {
  const { t } = useI18n();
  const { user, setUser, logout } = useAuth();
  const { toast } = useUploads();
  const [name, setName] = useState(user?.display_name || "");
  const [tz, setTz] = useState(user?.timezone || "UTC");
  const store = useApi<{ items: { kind: string; count: number; bytes: number }[] }>("/me/storage").data;
  useEffect(() => { if (user) { setName(user.display_name || ""); setTz(user.timezone); } }, [user]);
  const zones = useMemo(() => {
    let list: string[] = [];
    try { list = (Intl as any).supportedValuesOf("timeZone"); } catch { list = [] }
    if (!list.includes(tz)) list = [tz, ...list];
    return list.map((z) => ({ z, label: zoneLabel(z) })).sort((a, b) => a.label.localeCompare(b.label));
  }, [tz]);

  const save = async () => { try { setUser(await api.patch<User>("/me", { display_name: name, timezone: tz })); toast(t("media.saved")); } catch (e: any) { toast(e.message, "error"); } };
  const exportData = async () => {
    const r = await raw("/me/export"); const b = await r.blob(); const u = URL.createObjectURL(b);
    const a = document.createElement("a"); a.href = u; a.download = "memory-search-export.zip"; a.click(); URL.revokeObjectURL(u);
  };
  const refresh = async (all = false) => {
    try { const r = await api.post<{ queued: number }>("/admin/reindex", { only_failed: !all }); toast(t("set.refreshing", { n: r.queued })); }
    catch (e: any) { toast(e.message, "error"); }
  };
  const del = async () => { if (confirm(t("set.deleteWarn"))) { await api.del("/me"); logout(); } };
  const bytes = store?.items.reduce((s, i) => s + i.bytes, 0) || 0;

  return (
    <div className="mx-auto max-w-2xl space-y-5 px-4 py-6 sm:px-6 sm:py-8">
      <PageHeader title={t("set.title")} />
      <section className="card space-y-4 p-5"><h2 className="font-semibold">{t("set.profile")}</h2>
        <p className="flex flex-wrap items-center gap-2 text-sm text-ink-mute">{user?.email || user?.phone || (user?.username ? `@${user.username}` : "")}
          {user?.google && <span className="inline-flex items-center gap-1 rounded-full border border-paper-line px-2 py-0.5 text-xs font-medium text-ink-soft"><GoogleG size={12} />{t("set.signedInGoogle")}</span>}</p>
        <label className="block text-sm font-medium">{t("set.name")}<input className="input mt-1 font-normal" value={name} onChange={(e) => setName(e.target.value)} />
          <span className="mt-1 block text-xs font-normal text-ink-mute">{t("set.nameHint")}</span></label>
        <label className="block text-sm font-medium">{t("set.timezone")}
          <select className="input mt-1 font-normal" value={tz} onChange={(e) => setTz(e.target.value)}>{zones.map(({ z, label }) => <option key={z} value={z}>{label}</option>)}</select></label>
        <div className="flex items-center justify-between"><div className="flex items-center gap-2 text-sm font-medium">{t("set.language")} <LanguageSwitcher /></div><button className="btn-primary" onClick={save}>{t("common.save")}</button></div>
      </section>
      <section className="card p-5"><h2 className="mb-3 font-semibold">{t("set.storage")}</h2>
        {!store ? <LineSkeleton n={4} /> : (
          <ul className="space-y-2 text-sm">
            {store.items.map((i) => { const I = KIND_ICON[i.kind] || FileText; return (
              <li key={i.kind} className="flex items-center justify-between"><span className="flex items-center gap-2"><I className="h-4 w-4 text-ink-mute" />{t(KIND_KEY[i.kind] || i.kind)}</span>
                <span className="text-ink-mute">{i.count} • {fmtBytes(i.bytes)}</span></li>); })}
            <li className="flex justify-between border-t border-paper-line pt-2 font-medium"><span>{t("set.total")}</span><span>{fmtBytes(bytes)}</span></li>
          </ul>)}
      </section>
      <SignInCard />
      {user?.is_admin && <PeopleCard />}
      {user?.is_admin && <GoogleSetup />}
      <section className="flex flex-wrap gap-2">
        <button className="btn-outline" onClick={exportData}><Download className="h-4 w-4" />{t("set.export")}</button>
        {user?.is_admin && <button className="btn-outline" onClick={() => refresh()}><RefreshCw className="h-4 w-4" />{t("set.reindex")}</button>}
        {user?.is_admin && <button className="btn-outline" onClick={() => confirm(t("set.reindexAllWarn")) && refresh(true)}><RefreshCw className="h-4 w-4" />{t("set.reindexAll")}</button>}
        <button className="btn-outline !text-danger" onClick={del}><Trash2 className="h-4 w-4" />{t("set.delete")}</button>
      </section>
    </div>
  );
}
