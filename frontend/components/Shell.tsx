"use client";
import { LogOut, Menu, Search, Settings, UploadCloud, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useUploads } from "@/lib/uploads";
import LanguageSwitcher from "./LanguageSwitcher";
import { Wordmark } from "./Logo";
import ThemeButton from "./ThemeButton";
import { Spinner } from "./ui";

const NAV = [
  { href: "/", key: "nav.home" }, { href: "/search", key: "nav.search" }, { href: "/library", key: "nav.library" },
  { href: "/timeline", key: "nav.timeline" }, { href: "/map", key: "nav.map" },
  { href: "/collections", key: "nav.collections" }, { href: "/uploads", key: "nav.uploads" },
];

export default function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  const { user, loading, logout } = useAuth();
  const { busy, addFiles, toasts } = useUploads();
  const path = usePathname();
  const router = useRouter();
  const [drag, setDrag] = useState(false);
  const [menu, setMenu] = useState(false);

  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, user, router]);
  useEffect(() => { setMenu(false); }, [path]);

  useEffect(() => {
    let depth = 0;
    const has = (e: DragEvent) => Array.from(e.dataTransfer?.types || []).includes("Files");
    const enter = (e: DragEvent) => { if (has(e)) { depth++; setDrag(true); } };
    const leave = (e: DragEvent) => { if (has(e) && --depth <= 0) { depth = 0; setDrag(false); } };
    const over = (e: DragEvent) => has(e) && e.preventDefault();
    const drop = (e: DragEvent) => { if (!has(e)) return; e.preventDefault(); depth = 0; setDrag(false); addFiles(Array.from(e.dataTransfer!.files)); router.push("/uploads"); };
    const key = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.key === "Escape") setMenu(false);
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) && !el.isContentEditable) { e.preventDefault(); if (path !== "/search" && path !== "/") router.push("/search"); setTimeout(() => window.dispatchEvent(new Event("smriti:focus-search")), 50); }
    };
    window.addEventListener("dragenter", enter); window.addEventListener("dragleave", leave); window.addEventListener("dragover", over); window.addEventListener("drop", drop); window.addEventListener("keydown", key);
    return () => { window.removeEventListener("dragenter", enter); window.removeEventListener("dragleave", leave); window.removeEventListener("dragover", over); window.removeEventListener("drop", drop); window.removeEventListener("keydown", key); };
  }, [addFiles, router, path]);

  if (loading || !user) return <div className="flex h-screen items-center justify-center"><Spinner className="h-5 w-5 text-ink-mute" /></div>;
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b border-paper-line/70 bg-paper/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-6 px-4 sm:px-8">
          <Link href="/" aria-label="Smriti home" className="shrink-0 text-ink"><Wordmark size={26} /></Link>
          <nav className="ml-auto hidden items-center gap-7 lg:flex" aria-label="Main">
            {NAV.map(({ href, key }) => {
              const on = active(href);
              return (
                <Link key={href} href={href} aria-current={on ? "page" : undefined}
                  className={`relative py-2 text-[12px] font-medium uppercase tracking-label transition-colors ${on ? "text-ink" : "text-ink-mute hover:text-ink"}`}>
                  {t(key)}
                  {href === "/uploads" && busy > 0 && <span className="ml-1.5 tabular-nums text-tide">{busy}</span>}
                  {on && <span className="absolute -bottom-px left-0 h-0.5 w-4 bg-tide" aria-hidden />}
                </Link>);
            })}
          </nav>
          <div className="ml-auto flex items-center gap-1 lg:ml-2 lg:border-l lg:border-paper-line lg:pl-4">
            <Link href="/search" className="btn-ghost !h-9 !w-9 !p-0 lg:hidden" aria-label={t("nav.search")}><Search className="h-4 w-4" strokeWidth={1.5} /></Link>
            <ThemeButton />
            <Link href="/settings" className={`btn-ghost !h-9 !w-9 !p-0 ${active("/settings") ? "!text-ink" : ""}`} aria-label={t("nav.settings")} title={`${user.display_name || ""} · ${user.email}`}><Settings className="h-4 w-4" strokeWidth={1.5} /></Link>
            <button onClick={logout} className="btn-ghost hidden !h-9 !w-9 !p-0 lg:inline-flex" aria-label={t("nav.signOut")} title={t("nav.signOut")}><LogOut className="h-4 w-4" strokeWidth={1.5} /></button>
            <button onClick={() => setMenu(true)} className="btn-ghost !h-9 !w-9 !p-0 lg:hidden" aria-label="Menu" aria-expanded={menu}><Menu className="h-5 w-5" strokeWidth={1.5} /></button>
          </div>
        </div>
      </header>

      {menu && (
        <div className="fixed inset-0 z-50 flex flex-col bg-paper px-6 py-5 lg:hidden" role="dialog" aria-modal aria-label="Menu">
          <div className="flex items-center justify-between"><Wordmark size={26} /><button onClick={() => setMenu(false)} className="btn-ghost !h-9 !w-9 !p-0" aria-label="Close menu"><X className="h-5 w-5" strokeWidth={1.5} /></button></div>
          <nav className="mt-12 flex flex-col gap-1" aria-label="Main">
            {[...NAV, { href: "/settings", key: "nav.settings" }].map(({ href, key }, i) => (
              <Link key={href} href={href} style={{ animationDelay: `${i * 40}ms` }}
                className={`flex animate-rise items-center gap-4 py-3 text-[22px] font-light uppercase tracking-display ${active(href) ? "text-ink" : "text-ink-mute"}`}>
                {active(href) && <span className="bar" aria-hidden />}{t(key)}
              </Link>))}
          </nav>
          <div className="mt-auto flex items-center justify-between border-t border-paper-line pt-4">
            <LanguageSwitcher />
            <button onClick={logout} className="btn-ghost"><LogOut className="h-4 w-4" strokeWidth={1.5} />{t("nav.signOut")}</button>
          </div>
        </div>)}

      <main className="flex-1">{children}</main>

      <footer className="border-t border-paper-line/70">
        <div className="mx-auto flex max-w-[1440px] flex-wrap items-center justify-between gap-3 px-4 py-5 sm:px-8">
          <p className="text-[11px] uppercase tracking-label text-ink-mute">© Smriti <span className="px-1.5 text-ink-faint">/</span> your files stay on your own server</p>
          <LanguageSwitcher />
        </div>
      </footer>

      {drag && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-night/85 text-white">
          <div className="rounded border border-dashed border-white/40 px-14 py-12 text-center"><UploadCloud className="mx-auto h-8 w-8" strokeWidth={1.25} /><p className="mt-4 text-lg font-light uppercase tracking-display">{t("up.drop")}</p></div>
        </div>)}

      <div className="pointer-events-none fixed bottom-6 right-4 z-[60] flex flex-col gap-2" aria-live="polite">
        {toasts.map((x) => (<div key={x.id} className={`pointer-events-auto max-w-sm animate-rise rounded px-4 py-3 text-[13px] shadow-lift ${x.kind === "error" ? "bg-danger text-white" : "bg-night text-white"}`}>{x.msg}</div>))}
      </div>
    </div>
  );
}
