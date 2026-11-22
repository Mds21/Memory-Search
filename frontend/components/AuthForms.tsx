"use client";
import { ArrowLeft, Eye, EyeOff, Mail, Phone } from "lucide-react";
import { useEffect, useState } from "react";
import { API } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { Spinner } from "./ui";

export type Mode = "in" | "up" | "forgot" | "reset";

async function post(path: string, body: object) {
  let res: Response;
  try { res = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch { throw new Error("Can't reach Memory Search right now. Check that it's running and try again."); }
  const d = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof d.detail === "string" ? d.detail : "Please check what you entered and try again.");
  return d;
}

export function PasswordInput({ id, value, onChange, autoComplete, label, hint }: { id: string; value: string; onChange: (v: string) => void; autoComplete: string; label: string; hint?: string }) {
  const [show, setShow] = useState(false);
  return (
    <div>
      <label className="mb-1 block text-sm font-medium" htmlFor={id}>{label}</label>
      <div className="relative">
        <input id={id} type={show ? "text" : "password"} required className="input pr-11" value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} />
        <button type="button" onClick={() => setShow((s) => !s)} className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-lg p-2 text-ink-mute hover:text-ink" aria-label={show ? "Hide password" : "Show password"}>
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button>
      </div>
      {hint && <p className="mt-1 text-xs text-ink-mute">{hint}</p>}
    </div>
  );
}

const Err = ({ msg }: { msg: string }) => (msg ? <p role="alert" className="rounded-xl bg-danger-soft px-3 py-2 text-sm text-danger">{msg}</p> : null);

/** Sign in · create account · forgot password · reset with code. Any of email / mobile / username works to sign in. */
export default function AuthForms({ mode, setMode, onDone }: { mode: Mode; setMode: (m: Mode) => void; onDone: () => void }) {
  const { t, lang } = useI18n();
  const { login, register, adopt } = useAuth();
  const [ident, setIdent] = useState(""); const [password, setPassword] = useState(""); const [name, setName] = useState("");
  const [email, setEmail] = useState(""); const [phone, setPhone] = useState(""); const [via, setVia] = useState<"email" | "phone">("email");
  const [code, setCode] = useState(""); const [sentTo, setSentTo] = useState<{ channel: string | null; destination: string | null } | null>(null);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [canReset, setCanReset] = useState(false);
  useEffect(() => { fetch(`${API}/auth/providers`).then((r) => r.json()).then((d) => setCanReset(!!d.password_reset)).catch(() => {}); }, []);
  const go = (m: Mode) => { setErr(""); setMode(m); };
  const run = async (fn: () => Promise<void>) => { setErr(""); setBusy(true); try { await fn(); } catch (x: any) { setErr(x.message); } finally { setBusy(false); } };

  if (mode === "forgot" || mode === "reset") return (
    <div className="space-y-4">
      <button type="button" onClick={() => go("in")} className="btn-ghost -ml-2 !py-1 text-sm"><ArrowLeft className="h-4 w-4" />{t("auth.back")}</button>
      <h1 className="text-3xl font-semibold tracking-tight">{mode === "forgot" ? t("auth.forgotTitle") : t("auth.resetTitle")}</h1>
      {mode === "forgot" ? (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(async () => { const d = await post("/auth/forgot", { identifier: ident }); setSentTo(d); setMode("reset"); }); }}>
          <p className="text-sm text-ink-soft">{t("auth.forgotBody")}</p>
          <div><label className="mb-1 block text-sm font-medium" htmlFor="fid">{t("auth.identifier")}</label>
            <input id="fid" required className="input" value={ident} onChange={(e) => setIdent(e.target.value)} autoCapitalize="none" autoComplete="username" /></div>
          <Err msg={err} />
          <button className="btn-primary w-full" disabled={busy || !ident.trim()}>{busy && <Spinner />}{t("auth.sendCode")}</button>
        </form>
      ) : (
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(async () => { adopt(await post("/auth/reset", { identifier: ident, code, password })); onDone(); }); }}>
          <p className="rounded-xl bg-paper-sunk px-3 py-2.5 text-sm text-ink-soft">
            {sentTo?.destination ? t("auth.codeSentTo", { to: sentTo.destination }) : t("auth.codeSent")}
            {sentTo?.channel === "log" && <span className="mt-1 block text-xs text-ink-mute">{t("auth.codeNoDelivery")}</span>}</p>
          <div><label className="mb-1 block text-sm font-medium" htmlFor="code">{t("auth.code")}</label>
            <input id="code" required className="input text-center text-lg tracking-[.5em]" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
              inputMode="numeric" autoComplete="one-time-code" placeholder="••••••" /></div>
          <PasswordInput id="npw" label={t("auth.newPassword")} value={password} onChange={setPassword} autoComplete="new-password" hint={t("auth.passwordHint")} />
          <Err msg={err} />
          <button className="btn-primary w-full" disabled={busy || code.length < 6 || password.length < 8}>{busy && <Spinner />}{t("auth.setPassword")}</button>
          <button type="button" className="btn-ghost w-full text-sm" disabled={busy} onClick={() => run(async () => { setSentTo(await post("/auth/forgot", { identifier: ident })); })}>{t("auth.resend")}</button>
        </form>
      )}
    </div>
  );

  return (
    <form className="space-y-4" onSubmit={(e) => {
      e.preventDefault();
      run(async () => {
        if (mode === "in") await login(ident, password);
        else await register({ display_name: name, email: via === "email" ? email : email || undefined, phone: via === "phone" ? phone : phone || undefined, password, language: lang });
        onDone();
      });
    }}>
      {mode === "up" && (<>
        <div><label className="mb-1 block text-sm font-medium" htmlFor="name">{t("auth.name")}</label><input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>
        <div>
          <div className="mb-1.5 grid grid-cols-2 gap-1 rounded-xl bg-paper-sunk p-1" role="tablist">
            {(["email", "phone"] as const).map((v) => (
              <button key={v} type="button" role="tab" aria-selected={via === v} onClick={() => setVia(v)}
                className={`tap flex items-center justify-center gap-1.5 rounded-lg py-1.5 text-xs font-medium ${via === v ? "bg-paper-card text-ink shadow-soft" : "text-ink-mute"}`}>
                {v === "email" ? <Mail className="h-3.5 w-3.5" /> : <Phone className="h-3.5 w-3.5" />}{t(v === "email" ? "auth.email" : "auth.phone")}</button>))}
          </div>
          {via === "email"
            ? <input id="email" type="email" inputMode="email" autoCapitalize="none" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com" />
            : <input id="phone" type="tel" inputMode="tel" required className="input" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="tel" placeholder="98765 43210" />}
          <p className="mt-1 text-xs text-ink-mute">{t("auth.linkHint")}</p>
        </div>
      </>)}
      {mode === "in" && (
        <div><label className="mb-1 block text-sm font-medium" htmlFor="ident">{t("auth.identifier")}</label>
          <input id="ident" required className="input" value={ident} onChange={(e) => setIdent(e.target.value)} autoCapitalize="none" autoComplete="username" placeholder={t("auth.identifierPh")} /></div>)}
      <PasswordInput id="pw" label={t("auth.password")} value={password} onChange={setPassword} autoComplete={mode === "in" ? "current-password" : "new-password"} hint={mode === "up" ? t("auth.passwordHint") : undefined} />
      {mode === "in" && canReset && <div className="-mt-2 text-right"><button type="button" onClick={() => go("forgot")} className="text-sm font-medium text-ink-soft hover:text-ink hover:underline">{t("auth.forgot")}</button></div>}
      <Err msg={err} />
      <button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />}{mode === "in" ? t("auth.signIn") : t("auth.create")}</button>
      <p className="pt-2 text-sm text-ink-mute">{mode === "in" ? t("auth.noAccount") : t("auth.haveAccount")}{" "}
        <button type="button" className="font-semibold text-ink hover:underline" onClick={() => go(mode === "in" ? "up" : "in")}>{mode === "in" ? t("auth.create") : t("auth.signIn")}</button></p>
    </form>
  );
}
