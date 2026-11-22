"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AuthForms, { type Mode } from "@/components/AuthForms";
import GoogleButton from "@/components/GoogleButton";
import LanguageSwitcher from "@/components/LanguageSwitcher";
import Logo from "@/components/Logo";
import { BlurText } from "@/components/motion";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";

export default function LoginPage() {
  const { t, lang } = useI18n();
  const { user, loading, loginWithGoogle } = useAuth();
  const onGoogle = async (credential: string) => {
    setErr(""); setBusy(true);
    try { await loginWithGoogle(credential, lang); router.replace("/"); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("in");
  const [err, setErr] = useState(""); const [, setBusy] = useState(false);

  useEffect(() => { if (!loading && user) router.replace("/"); }, [loading, user, router]);


  return (
    <main className="grid min-h-screen lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden bg-night p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div className="aurora-blob aurora-a !opacity-40" style={{ background: "radial-gradient(closest-side, rgb(139 92 246 / .55), transparent)" }} />
        <div className="pointer-events-none absolute -left-32 -top-32 h-[28rem] w-[28rem] rounded-full bg-white/[.08] blur-3xl" />
        <div className="pointer-events-none absolute -bottom-40 right-[-6rem] h-[30rem] w-[30rem] rounded-full bg-white/[.06] blur-3xl" />
        <div className="pointer-events-none absolute inset-0 opacity-[.07]" style={{ backgroundImage: "radial-gradient(#fff 1px, transparent 1px)", backgroundSize: "22px 22px" }} />
        <div className="relative flex items-center gap-3"><Logo size={36} onDark /><span className="text-xl font-semibold tracking-tight">Smriti</span></div>
        <div className="relative">
          <p className="max-w-md text-balance text-[2.6rem] font-semibold leading-[1.1] tracking-tight"><BlurText key={t("auth.tagline")} text={t("auth.tagline")} step={60} /></p>
          <ul className="mt-10 max-w-md space-y-3">
            {["goa trip photos with dad last december", "what did the rental agreement say about the deposit?", "पिछले साल की बीच तस्वीरें"].map((q, i) => (
              <li key={q} className="animate-fade-up rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white/80 backdrop-blur" style={{ animationDelay: `${150 + i * 120}ms` }}>“{q}”</li>))}
          </ul>
        </div>
        <p className="relative text-sm text-white/50">Open source. Your files stay on your own server.</p>
      </section>
      <section className="ambient flex min-h-[100dvh] flex-col px-5 py-6 sm:px-12 sm:py-8" style={{ paddingTop: "max(1.5rem, env(safe-area-inset-top))" }}>
        <div className="flex items-center justify-between lg:justify-end">
          <div className="flex items-center gap-2 lg:hidden"><Logo /><span className="font-semibold">Smriti</span></div>
          <LanguageSwitcher />
        </div>
        <div className="m-auto w-full max-w-sm animate-fade-up">
          <div className="mb-8 lg:hidden">
            <div className="relative mb-5 overflow-hidden rounded-3xl bg-night p-5 text-white shadow-lift">
              <div className="pointer-events-none absolute -left-10 -top-10 h-40 w-40 rounded-full bg-white/15 blur-2xl" />
              <div className="pointer-events-none absolute -bottom-12 -right-8 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
              <p className="relative text-xl font-semibold leading-snug">{t("auth.tagline")}</p>
              <div className="relative mt-4 flex flex-col gap-2">
                {["share my PAN card", "beach photos from Goa", "पिछले साल की बीच तस्वीरें"].map((q, i) => (
                  <span key={q} className="w-fit animate-fade-up rounded-xl border border-white/10 bg-white/10 px-3 py-1.5 text-xs text-white/85 backdrop-blur" style={{ animationDelay: `${120 + i * 100}ms` }}>“{q}”</span>))}
              </div>
            </div>
          </div>
          {(mode === "in" || mode === "up") && (<>
            <h1 className="text-3xl font-semibold tracking-tight">{mode === "in" ? t("auth.signIn") : t("auth.create")}</h1>
            <div className="mb-4 mt-6 space-y-4">
              <GoogleButton onCredential={onGoogle} />
              <div className="flex items-center gap-3 text-xs text-ink-mute"><span className="h-px flex-1 bg-paper-line" />{t("auth.or")}<span className="h-px flex-1 bg-paper-line" /></div>
            </div>
            {err && <p role="alert" className="mb-4 rounded-xl bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}
          </>)}
          <AuthForms mode={mode} setMode={setMode} onDone={() => router.replace("/")} />
        </div>
      </section>
    </main>
  );
}
