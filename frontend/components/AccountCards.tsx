"use client";
import { Copy, KeyRound, Mail, Phone, Shield, ShieldOff, UserRound } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useApi } from "@/lib/swr";
import type { User } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { PasswordInput } from "./AuthForms";
import { LineSkeleton, Spinner } from "./ui";

/** How you sign in: email, mobile, username (all lead to this one account) and your password. */
export function SignInCard() {
  const { t } = useI18n();
  const { user, setUser, adopt } = useAuth();
  const { toast } = useUploads();
  const [email, setEmail] = useState(""); const [phone, setPhone] = useState(""); const [username, setUsername] = useState("");
  const [cur, setCur] = useState(""); const [next, setNext] = useState(""); const [pwCur, setPwCur] = useState("");
  const [busy, setBusy] = useState<"contact" | "pw" | null>(null);
  useEffect(() => { setEmail(user?.email || ""); setPhone(user?.phone || ""); setUsername(user?.username || ""); }, [user]);
  if (!user) return null;
  const changed = email !== (user.email || "") || phone !== (user.phone || "") || username !== (user.username || "");
  const needsPw = user.has_password !== false;

  const saveContact = async () => {
    setBusy("contact");
    try {
      const u = await api.patch<User>("/me/contact", { email, phone, username, current_password: cur || undefined });
      setUser(u); setCur(""); toast(t("acct.saved"));
    } catch (e: any) { toast(e.message, "error"); } finally { setBusy(null); }
  };
  const savePw = async () => {
    setBusy("pw");
    try { adopt(await api.post("/me/password", { current_password: pwCur || undefined, new_password: next })); setPwCur(""); setNext(""); toast(t("acct.pwSaved")); }
    catch (e: any) { toast(e.message, "error"); } finally { setBusy(null); }
  };

  return (
    <section className="card space-y-5 p-5">
      <div>
        <h2 className="font-semibold">{t("acct.title")}</h2>
        <p className="mt-0.5 text-sm text-ink-mute">{t("acct.body")}</p>
      </div>
      <div className="space-y-3">
        <Field icon={Mail} label={t("auth.email")}><input className="input" type="email" inputMode="email" autoCapitalize="none" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></Field>
        <Field icon={Phone} label={t("auth.phone")}><input className="input" type="tel" inputMode="tel" value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="98765 43210" /></Field>
        <Field icon={UserRound} label={t("acct.username")}><input className="input" autoCapitalize="none" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="e.g. ravi" /></Field>
        {changed && (<>
          {needsPw && <PasswordInput id="cpw" label={t("acct.currentPw")} value={cur} onChange={setCur} autoComplete="current-password" />}
          <button className="btn-primary" onClick={saveContact} disabled={busy !== null || (needsPw && !cur)}>{busy === "contact" && <Spinner />}{t("common.save")}</button>
        </>)}
      </div>
      <div className="space-y-3 border-t border-paper-line pt-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold"><KeyRound className="h-4 w-4 text-ink-mute" />{needsPw ? t("acct.changePw") : t("acct.setPw")}</h3>
        {!needsPw && <p className="text-xs text-ink-mute">{t("acct.setPwHint")}</p>}
        {needsPw && <PasswordInput id="opw" label={t("acct.currentPw")} value={pwCur} onChange={setPwCur} autoComplete="current-password" />}
        <PasswordInput id="npw" label={t("auth.newPassword")} value={next} onChange={setNext} autoComplete="new-password" hint={t("acct.pwHint")} />
        <button className="btn-outline" onClick={savePw} disabled={busy !== null || next.length < 8 || (needsPw && !pwCur)}>{busy === "pw" && <Spinner />}{needsPw ? t("acct.changePw") : t("acct.setPw")}</button>
      </div>
    </section>
  );
}

function Field({ icon: I, label, children }: { icon: typeof Mail; label: string; children: React.ReactNode }) {
  return <label className="block"><span className="mb-1 flex items-center gap-1.5 text-sm font-medium"><I className="h-3.5 w-3.5 text-ink-mute" />{label}</span>{children}</label>;
}

/** Owner tools: everyone with an account; give a temporary password; make or remove administrators. */
export function PeopleCard() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useUploads();
  const { data, reload } = useApi<{ items: (User & { created_at: string })[] }>("/admin/users");
  const [temp, setTemp] = useState<{ who: string; pw: string } | null>(null);

  const reset = async (u: User) => {
    if (!confirm(t("people.resetConfirm", { who: label(u) }))) return;
    try { const r = await api.post<{ temporary_password: string }>(`/admin/users/${u.id}/reset-password`); setTemp({ who: label(u), pw: r.temporary_password }); reload(); }
    catch (e: any) { toast(e.message, "error"); }
  };
  const toggleAdmin = async (u: User) => {
    try { await api.patch(`/admin/users/${u.id}`, { is_admin: !u.is_admin }); reload(); } catch (e: any) { toast(e.message, "error"); }
  };
  const label = (u: User) => u.display_name || u.email || u.phone || u.username || "—";

  return (
    <section className="card space-y-4 p-5">
      <div><h2 className="font-semibold">{t("people.title")}</h2><p className="mt-0.5 text-sm text-ink-mute">{t("people.body")}</p></div>
      {temp && (
        <div className="animate-fade-in rounded-2xl border border-paper-line bg-paper-sunk p-3 text-sm">
          <p>{t("people.tempFor", { who: temp.who })}</p>
          <div className="mt-2 flex items-center gap-2"><code className="flex-1 rounded-lg bg-paper-card px-3 py-2 font-mono text-base">{temp.pw}</code>
            <button className="btn-outline !p-2.5" onClick={() => navigator.clipboard?.writeText(temp.pw).then(() => toast(t("share.copiedText")))} aria-label="Copy"><Copy className="h-4 w-4" /></button></div>
          <p className="mt-2 text-xs text-ink-mute">{t("people.tempHint")}</p>
        </div>)}
      {!data ? <LineSkeleton n={3} /> : (
        <ul className="divide-y divide-paper-line">
          {data.items.map((u) => (
            <li key={u.id} className="flex items-center gap-3 py-2.5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-paper-sunk text-xs font-semibold">{label(u).slice(0, 2).toUpperCase()}</span>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 truncate text-sm font-medium">{label(u)}{u.is_admin && <span className="rounded-full bg-ink px-1.5 py-0.5 text-[10px] font-semibold text-paper">{t("people.admin")}</span>}</p>
                <p className="truncate text-xs text-ink-mute">{[u.username && `@${u.username}`, u.email, u.phone, u.google && "Google"].filter(Boolean).join(" · ")}</p>
              </div>
              <button className="btn-ghost tap !p-2" onClick={() => reset(u)} title={t("people.reset")} aria-label={t("people.reset")}><KeyRound className="h-4 w-4" /></button>
              {u.id !== user?.id && <button className="btn-ghost tap !p-2" onClick={() => toggleAdmin(u)} title={u.is_admin ? t("people.removeAdmin") : t("people.makeAdmin")}
                aria-label={u.is_admin ? t("people.removeAdmin") : t("people.makeAdmin")}>{u.is_admin ? <ShieldOff className="h-4 w-4" /> : <Shield className="h-4 w-4" />}</button>}
            </li>))}
        </ul>)}
    </section>
  );
}
