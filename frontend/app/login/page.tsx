"use client";
import { Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import Logo from "@/components/Logo";
import { Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const { t, lang } = useI18n();
  const { user, loading, login, register } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [name, setName] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);

  useEffect(() => { if (!loading && user) router.replace("/"); }, [loading, user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(""); setBusy(true);
    try { mode === "in" ? await login(email, password) : await register(email, password, name, lang); router.replace("/"); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="hidden bg-ink p-12 text-paper lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3"><Logo size={30} /><span className="font-serif text-2xl font-semibold tracking-tight">Smriti</span><span className="text-white/40" lang="hi">स्मृति</span></div>
        <div>
          <p className="max-w-lg font-serif text-5xl font-semibold leading-[1.08] tracking-tight">{t("auth.tagline")}</p>
          <ul className="mt-10 max-w-md divide-y divide-white/15 border-y border-white/15 font-serif text-lg italic text-white/75">
            <li className="py-3">“goa trip photos with dad last december”</li>
            <li className="py-3">“what did the rental agreement say about the deposit?”</li>
            <li className="py-3" lang="hi">“पिछले साल की बीच तस्वीरें”</li>
          </ul>
        </div>
        <p className="text-sm text-white/50">Your files stay on your own server.</p>
      </section>
      <section className="flex flex-col px-6 py-8 sm:px-12">
        <div className="flex items-center justify-between lg:justify-end">
          <div className="flex items-center gap-2 lg:hidden"><Logo /><span className="font-semibold">Smriti</span></div>
          <LanguageSwitcher />
        </div>
        <div className="m-auto w-full max-w-sm">
          <h1 className="font-serif text-3xl font-semibold tracking-tight">{mode === "in" ? t("auth.signIn") : t("auth.create")}</h1>
          <form onSubmit={submit} className="mt-6 space-y-4">
            {mode === "up" && (<div><label className="mb-1 block text-sm font-medium" htmlFor="name">{t("auth.name")}</label><input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>)}
            <div><label className="mb-1 block text-sm font-medium" htmlFor="email">{t("auth.email")}</label><input id="email" type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
            <div><label className="mb-1 block text-sm font-medium" htmlFor="pw">{t("auth.password")}</label>
              <div className="relative"><input id="pw" type={show ? "text" : "password"} required minLength={mode === "up" ? 8 : 1} className="input pr-10" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "in" ? "current-password" : "new-password"} />
                <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-ink-faint hover:text-ink">{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>
              {mode === "up" && <p className="mt-1 text-xs text-ink-mute">{t("auth.passwordHint")}</p>}</div>
            {err && <p role="alert" className="rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />}{mode === "in" ? t("auth.signIn") : t("auth.create")}</button>
          </form>
          <p className="mt-6 text-sm text-ink-mute">{mode === "in" ? t("auth.noAccount") : t("auth.haveAccount")}{" "}
            <button className="font-medium text-tide hover:underline" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(""); }}>{mode === "in" ? t("auth.create") : t("auth.signIn")}</button></p>
        </div>
      </section>
    </main>
  );
}
