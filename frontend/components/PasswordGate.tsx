"use client";
import { KeyRound } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { PasswordInput } from "./AuthForms";
import Logo from "./Logo";
import { Spinner } from "./ui";

/** Shown instead of the app when someone signs in with a one-time password (the admin account, or a reset by an admin). */
export default function PasswordGate() {
  const { t } = useI18n();
  const { user, adopt, logout } = useAuth();
  const [pw, setPw] = useState(""); const [again, setAgain] = useState("");
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    if (pw !== again) return setErr(t("pw.mismatch"));
    setBusy(true);
    try { adopt(await api.post("/me/password", { new_password: pw })); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <main className="ambient flex min-h-[100dvh] items-center justify-center px-5 py-10">
      <div className="w-full max-w-sm animate-fade-up">
        <div className="mb-6 flex items-center gap-2"><Logo size={30} /><span className="text-lg font-semibold">Smriti</span></div>
        <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-ink text-paper"><KeyRound className="h-6 w-6" /></div>
        <h1 className="text-2xl font-semibold tracking-tight">{t("pw.chooseTitle")}</h1>
        <p className="mt-1.5 text-sm text-ink-soft">{t("pw.chooseBody", { name: user?.username || user?.display_name || "" })}</p>
        <form onSubmit={submit} className="mt-6 space-y-4">
          <PasswordInput id="np1" label={t("auth.newPassword")} value={pw} onChange={setPw} autoComplete="new-password" hint={t("auth.passwordHint")} />
          <PasswordInput id="np2" label={t("pw.again")} value={again} onChange={setAgain} autoComplete="new-password" />
          {err && <p role="alert" className="rounded-xl bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}
          <button className="btn-primary w-full" disabled={busy || pw.length < 8}>{busy && <Spinner />}{t("pw.save")}</button>
          <button type="button" className="btn-ghost w-full text-sm" onClick={logout}>{t("nav.signOut")}</button>
        </form>
      </div>
    </main>
  );
}
