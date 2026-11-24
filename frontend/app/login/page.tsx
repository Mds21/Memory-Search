"use client";
import { Eye, EyeOff, FileText, Image as ImageIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import GoogleButton from "@/components/GoogleButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import { Wordmark } from "@/components/Logo";
import PhotoWall from "@/components/PhotoWall";
import ThemeButton from "@/components/ThemeButton";
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
      <section className="relative isolate hidden overflow-hidden bg-[#0e0e0e] p-12 text-[#e8e6e3] lg:flex lg:flex-col lg:justify-between">
        <PhotoWall count={30} rows="auto-rows-[140px]" cols="grid-cols-5" />
        <div aria-hidden className="absolute inset-0 -z-10 bg-[#0e0e0e]/70" />
        <Wordmark size={34} className="text-[#e8e6e3]" />
        <div className="max-w-xl rounded border border-white/[0.08] bg-[#0e0e0e]/80 p-10 backdrop-blur-md">
          <p className="h-display text-[34px] leading-[1.25]">{t("auth.tagline")}</p>
          <ul className="mt-10 divide-y divide-white/[0.08] border-y border-white/[0.08]">
            {SAMPLES.map((s) => (
              <li key={s.q} className="flex items-center gap-4 py-3.5">
                <s.icon className="h-4 w-4 shrink-0 text-white/35" strokeWidth={1.5} />
                <span className="min-w-0 flex-1 truncate text-[13px] text-white/80" lang={s.lang}>{s.q}</span>
                <span className="shrink-0 text-right text-[10px] uppercase tracking-label"><span className="block text-[#bf9c3a]">{s.found}</span><span className="block text-white/35">{s.where}</span></span>
              </li>))}
          </ul>
        </div>
        <p className="text-[11px] uppercase tracking-label text-white/40">© Smriti <span className="px-1.5 text-white/20">/</span> your files stay on your own server</p>
      </section>

      <section className="flex flex-col px-6 py-8 sm:px-12">
        <div className="flex items-center justify-between lg:justify-end">
          <Wordmark size={26} className="lg:invisible" />
          <div className="flex items-center gap-2"><LanguageSwitcher /><ThemeButton /></div>
        </div>
        <div className="m-auto w-full max-w-sm py-12">
          <h1 className="h-page">{mode === "in" ? t("auth.signIn") : t("auth.create")}</h1>
          <div className="mt-8 animate-rise"><GoogleButton onCredential={(c) => attempt(() => google(c, lang))} /></div>
          <div className="my-6 flex items-center gap-3 text-[11px] uppercase tracking-label text-ink-faint" aria-hidden><span className="h-px flex-1 bg-paper-line" />{t("auth.or")}<span className="h-px flex-1 bg-paper-line" /></div>
          <form onSubmit={submit} className="space-y-4">
            {mode === "up" && (<div><label className="label mb-2 block" htmlFor="name">{t("auth.name")}</label><input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" /></div>)}
            <div><label className="label mb-2 block" htmlFor="email">{t("auth.email")}</label><input id="email" type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" /></div>
            <div><label className="label mb-2 block" htmlFor="pw">{t("auth.password")}</label>
              <div className="relative"><input id="pw" type={show ? "text" : "password"} required minLength={mode === "up" ? 8 : 1} className="input pr-10" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "in" ? "current-password" : "new-password"} />
                <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? "Hide password" : "Show password"} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1.5 text-ink-faint transition-colors hover:text-ink">{show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></div>
              {mode === "up" && <p className="mt-1.5 pl-4 text-xs text-ink-mute">{t("auth.passwordHint")}</p>}</div>
            {err && <p role="alert" className="rounded border border-danger/25 bg-danger-soft px-4 py-2.5 text-[13px] text-danger">{err}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />}{mode === "in" ? t("auth.signIn") : t("auth.create")}</button>
          </form>
          <p className="mt-6 text-[13px] text-ink-mute">{mode === "in" ? t("auth.noAccount") : t("auth.haveAccount")}{" "}
            <button className="font-medium text-tide underline-offset-4 hover:underline" onClick={() => { setMode(mode === "in" ? "up" : "in"); setErr(""); }}>{mode === "in" ? t("auth.create") : t("auth.signIn")}</button></p>
        </div>
      </section>
    </main>
  );
}
