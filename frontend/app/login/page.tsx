"use client";
import { Eye, EyeOff, FileText, Image as ImageIcon, Search } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import GoogleButton from "@/components/GoogleButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import Logo from "@/components/Logo";
import { Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

const SAMPLES = [
  { q: "goa trip photos with dad last december", icon: ImageIcon, found: "38 photos", where: "Goa · Dec 2025" },
  { q: "what did the rental agreement say about the deposit?", icon: FileText, found: "Rental agreement", where: "page 3" },
  { q: "पिछले साल की बीच तस्वीरें", icon: ImageIcon, found: "112 photos", where: "2024", lang: "hi" },
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
    <main className="grid min-h-screen bg-paper lg:grid-cols-[1.15fr_1fr]">
      <section className="relative hidden overflow-hidden border-r border-white/[0.06] bg-[#111113] p-12 text-[#ededed] lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-2.5"><Logo size={26} inverse /><span className="font-serif text-xl font-medium">Smriti</span><span className="text-sm text-white/40" lang="hi">स्मृति</span></div>
        <div className="max-w-xl">
          <p className="font-serif text-[52px] font-medium leading-[1.05] tracking-[-0.025em]">{t("auth.tagline")}</p>
          <div className="mt-12 rounded-2xl border border-white/[0.08] bg-[#19191b] p-2 shadow-[0_24px_48px_-24px_rgba(0,0,0,.6)]">
            <div className="flex h-11 items-center gap-3 rounded-xl bg-[#232325] px-4 text-sm text-white/45"><Search className="h-4 w-4" strokeWidth={1.75} />{t("home.placeholder")}</div>
            <ul className="mt-1">
              {SAMPLES.map((s, i) => (
                <li key={s.q} className={`flex items-center gap-3 rounded-lg px-4 py-3 ${i === 0 ? "bg-white/[0.04]" : ""}`}>
                  <s.icon className="h-4 w-4 shrink-0 text-white/40" strokeWidth={1.75} />
                  <span className="min-w-0 flex-1 truncate text-[15px] text-white/85" lang={s.lang}>{s.q}</span>
                  <span className="shrink-0 text-right"><span className="block text-xs text-white/70">{s.found}</span><span className="block font-mono text-[11px] text-white/35">{s.where}</span></span>
                </li>))}
            </ul>
          </div>
        </div>
        <p className="text-sm text-white/45">Your files stay on your own server</p>
      </section>

      <section className="flex flex-col px-6 py-8 sm:px-12">
        <div className="flex items-center justify-between lg:justify-end">
          <div className="flex items-center gap-2 lg:hidden"><Logo size={24} /><span className="font-serif text-lg font-medium">Smriti</span></div>
          <LanguageSwitcher />
        </div>
        <div className="m-auto w-full max-w-sm py-12">
          <h1 className="font-serif text-[32px] font-medium tracking-[-0.01em]">{mode === "in" ? t("auth.signIn") : t("auth.create")}</h1>
          <div className="mt-8 animate-rise"><GoogleButton onCredential={(c) => attempt(() => google(c, lang))} /></div>
          <div className="my-6 flex items-center gap-3 text-xs text-ink-faint" aria-hidden><span className="h-px flex-1 bg-paper-line" />{t("auth.or")}<span className="h-px flex-1 bg-paper-line" /></div>
          <form onSubmit={submit} className="space-y-4">
            {mode === "up" && (<div><label className="mb-1.5 block text-sm font-medium" htmlFor="name">{t("auth.name")}</label><input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>)}
            <div><label className="mb-1.5 block text-sm font-medium" htmlFor="email">{t("auth.email")}</label><input id="email" type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
            <div><label className="mb-1.5 block text-sm font-medium" htmlFor="pw">{t("auth.password")}</label>
              <div className="relative"><input id="pw" type={show ? "text" : "password"} required minLength={mode === "up" ? 8 : 1} className="input pr-10" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "in" ? "current-password" : "new-password"} />
                <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1.5 text-ink-faint transition-colors hover:text-ink">{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>
              {mode === "up" && <p className="mt-1 text-xs text-ink-mute">{t("auth.passwordHint")}</p>}</div>
            {err && <p role="alert" className="rounded-md border border-danger/20 bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}
            <button className="btn-primary !h-10 w-full" disabled={busy}>{busy && <Spinner />}{mode === "in" ? t("auth.signIn") : t("auth.create")}</button>
          </form>
          <p className="mt-6 text-sm text-ink-mute">{mode === "in" ? t("auth.noAccount") : t("auth.haveAccount")}{" "}
            <button className="font-medium text-tide hover:underline" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(""); }}>{mode === "in" ? t("auth.create") : t("auth.signIn")}</button></p>
        </div>
      </section>
    </main>
  );
}
