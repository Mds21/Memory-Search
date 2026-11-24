"use client";
import { Eye, EyeOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import GoogleButton from "@/components/GoogleButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import Logo from "@/components/Logo";
import { Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const SAMPLES = [
  { q: "goa trip photos with dad last december", kind: "Photos" },
  { q: "what did the rental agreement say about the deposit?", kind: "Document" },
  { q: "पिछले साल की बीच तस्वीरें", kind: "Photos", lang: "hi" },
];

export default function LoginPage() {
  const { t, lang } = useI18n();
  const { user, loading, login, register, google } = useAuth();
  const router = useRouter();
  const [mode, setMode] = useState<"in" | "up">("in");
  const [email, setEmail] = useState(""); const [password, setPassword] = useState(""); const [name, setName] = useState("");
  const [show, setShow] = useState(false);
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);

  useEffect(() => { if (!loading && user) router.replace("/"); }, [loading, user, router]);

  async function attempt(fn: () => Promise<void>) {
    setErr(""); setBusy(true);
    try { await fn(); router.replace("/"); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  }
  const submit = (e: React.FormEvent) => { e.preventDefault(); attempt(() => (mode === "in" ? login(email, password) : register(email, password, name, lang))); };

  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="hidden bg-ink p-12 text-paper lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3"><Logo size={28} /><span className="font-serif text-2xl font-medium">Smriti</span><span className="text-white/40" lang="hi">स्मृति</span></div>
        <div>
          <p className="max-w-lg font-serif text-5xl font-medium leading-[1.08] tracking-[-0.02em]">{t("auth.tagline")}</p>
          <ul className="mt-12 max-w-md divide-y divide-white/15 border-y border-white/15">
            {SAMPLES.map((s) => (
              <li key={s.q} className="flex items-baseline justify-between gap-6 py-3">
                <span className="font-serif text-lg text-white/85" lang={s.lang}>“{s.q}”</span>
                <span className="shrink-0 font-mono text-xs text-white/40">{s.kind}</span>
              </li>))}
          </ul>
        </div>
        <p className="text-sm text-white/50">Your files stay on your own server</p>
      </section>

      <section className="flex flex-col px-6 py-8 sm:px-12">
        <div className="flex items-center justify-between lg:justify-end">
          <div className="flex items-center gap-2 lg:hidden"><Logo size={24} /><span className="font-serif text-lg font-medium">Smriti</span></div>
          <LanguageSwitcher />
        </div>
        <div className="m-auto w-full max-w-sm py-12">
          <h1 className="font-serif text-3xl font-medium">{mode === "in" ? t("auth.signIn") : t("auth.create")}</h1>
          <div className="mt-8"><GoogleButton onCredential={(c) => attempt(() => google(c, lang))} /></div>
          <div className="my-6 flex items-center gap-3 text-xs text-ink-faint" aria-hidden><span className="h-px flex-1 bg-paper-line" />{t("auth.or")}<span className="h-px flex-1 bg-paper-line" /></div>
          <form onSubmit={submit} className="space-y-4">
            {mode === "up" && (<div><label className="mb-1 block text-sm font-medium" htmlFor="name">{t("auth.name")}</label><input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>)}
            <div><label className="mb-1 block text-sm font-medium" htmlFor="email">{t("auth.email")}</label><input id="email" type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
            <div><label className="mb-1 block text-sm font-medium" htmlFor="pw">{t("auth.password")}</label>
              <div className="relative"><input id="pw" type={show ? "text" : "password"} required minLength={mode === "up" ? 8 : 1} className="input pr-10" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "in" ? "current-password" : "new-password"} />
                <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-1 text-ink-faint transition-colors hover:text-ink">{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>
              {mode === "up" && <p className="mt-1 text-xs text-ink-mute">{t("auth.passwordHint")}</p>}</div>
            {err && <p role="alert" className="rounded border border-danger/20 bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}
            <button className="btn-primary h-10 w-full" disabled={busy}>{busy && <Spinner />}{mode === "in" ? t("auth.signIn") : t("auth.create")}</button>
          </form>
          <p className="mt-6 text-sm text-ink-mute">{mode === "in" ? t("auth.noAccount") : t("auth.haveAccount")}{" "}
            <button className="font-medium text-tide hover:underline" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(""); }}>{mode === "in" ? t("auth.create") : t("auth.signIn")}</button></p>
        </div>
      </section>
    </main>
  );
}
