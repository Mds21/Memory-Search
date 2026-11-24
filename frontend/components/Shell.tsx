"use client";
import { Clock, FolderHeart, Home, Image as ImageIcon, LogOut, Map as MapIcon, Monitor, Moon, Search, Settings, Sun, UploadCloud } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useTheme } from "@/lib/theme";
import { useUploads } from "@/lib/uploads";
import LanguageSwitcher from "./LanguageSwitcher";
import Logo from "./Logo";
import { Spinner } from "./ui";

const NAV = [
  { href: "/", key: "nav.home", icon: Home }, { href: "/search", key: "nav.search", icon: Search, kbd: "/" }, { href: "/library", key: "nav.library", icon: ImageIcon },
  { href: "/timeline", key: "nav.timeline", icon: Clock }, { href: "/map", key: "nav.map", icon: MapIcon },
  { href: "/collections", key: "nav.collections", icon: FolderHeart }, { href: "/uploads", key: "nav.uploads", icon: UploadCloud },
];
const MOBILE = ["/", "/search", "/library", "/collections", "/uploads"];

function ThemeButton() {
  const { pref, cycle } = useTheme();
  const Icon = pref === "dark" ? Moon : pref === "light" ? Sun : Monitor;
  const label = `Theme: ${pref}`;
  return <button onClick={cycle} className="btn-ghost !h-8 !w-8 !p-0" aria-label={label} title={label}><Icon className="h-4 w-4" strokeWidth={1.75} /></button>;
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  const { user, loading, logout } = useAuth();
  const { busy, addFiles, toasts } = useUploads();
  const path = usePathname();
  const router = useRouter();
  const [drag, setDrag] = useState(false);

  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, user, router]);

  useEffect(() => {
    let depth = 0;
    const has = (e: DragEvent) => Array.from(e.dataTransfer?.types || []).includes("Files");
    const enter = (e: DragEvent) => { if (has(e)) { depth++; setDrag(true); } };
    const leave = (e: DragEvent) => { if (has(e) && --depth <= 0) { depth = 0; setDrag(false); } };
    const over = (e: DragEvent) => has(e) && e.preventDefault();
    const drop = (e: DragEvent) => { if (!has(e)) return; e.preventDefault(); depth = 0; setDrag(false); addFiles(Array.from(e.dataTransfer!.files)); router.push("/uploads"); };
    const key = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.key === "/" && !["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) && !el.isContentEditable) { e.preventDefault(); if (path !== "/search" && path !== "/") router.push("/search"); setTimeout(() => window.dispatchEvent(new Event("smriti:focus-search")), 50); }
    };
    window.addEventListener("dragenter", enter); window.addEventListener("dragleave", leave); window.addEventListener("dragover", over); window.addEventListener("drop", drop); window.addEventListener("keydown", key);
    return () => { window.removeEventListener("dragenter", enter); window.removeEventListener("dragleave", leave); window.removeEventListener("dragover", over); window.removeEventListener("drop", drop); window.removeEventListener("keydown", key); };
  }, [addFiles, router, path]);

  if (loading || !user) return <div className="flex h-screen items-center justify-center"><Spinner className="h-5 w-5 text-ink-mute" /></div>;
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[248px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-paper-line bg-paper-card px-3 pb-3 pt-4 lg:flex">
        <Link href="/" className="flex h-9 items-center gap-2.5 rounded-md px-2" aria-label="Smriti home">
          <Logo size={22} /><span className="font-serif text-[17px] font-medium">Smriti</span><span className="text-xs text-ink-faint" lang="hi">स्मृति</span>
        </Link>

        <nav className="mt-6 space-y-0.5" aria-label="Main">
          {NAV.map(({ href, key, icon: Icon, kbd }) => {
            const on = active(href);
            return (
              <Link key={href} href={href} aria-current={on ? "page" : undefined}
                className={`flex h-9 items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors ${on ? "bg-paper-sunk font-medium text-ink" : "text-ink-soft hover:bg-paper-sunk/60 hover:text-ink"}`}>
                <Icon className={`h-4 w-4 shrink-0 ${on ? "text-ink" : "text-ink-mute"}`} strokeWidth={1.75} />
                <span className="flex-1 truncate">{t(key)}</span>
                {href === "/uploads" && busy > 0 ? <span className="font-mono text-xs tabular-nums text-ink-mute">{busy}</span>
                  : on ? <span className="h-1.5 w-1.5 rounded-[1px] bg-glow" aria-hidden />
                  : kbd ? <span className="kbd">{kbd}</span> : null}
              </Link>);
          })}
        </nav>

        <div className="mt-auto border-t border-paper-line pt-3">
          <Link href="/settings" className={`flex items-center gap-2.5 rounded-md px-2.5 py-2 transition-colors ${active("/settings") ? "bg-paper-sunk" : "hover:bg-paper-sunk/60"}`} title={user.email}>
            <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-paper-sunk text-xs font-medium text-ink-soft">{(user.display_name || user.email).slice(0, 1).toUpperCase()}</span>
            <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{user.display_name || user.email}</span><span className="block truncate text-xs text-ink-mute">{t("nav.settings")}</span></span>
            <Settings className="h-4 w-4 shrink-0 text-ink-mute" strokeWidth={1.75} />
          </Link>
          <div className="mt-2 flex items-center gap-1 px-1">
            <LanguageSwitcher compact />
            <span className="flex-1" />
            <ThemeButton />
            <button onClick={logout} className="btn-ghost !h-8 !w-8 !p-0" aria-label={t("nav.signOut")} title={t("nav.signOut")}><LogOut className="h-4 w-4" strokeWidth={1.75} /></button>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-paper-line bg-paper/90 px-4 backdrop-blur lg:hidden">
          <Link href="/" className="flex items-center gap-2" aria-label="Smriti home"><Logo size={22} /><span className="font-serif text-[17px] font-medium">Smriti</span></Link>
          <span className="flex-1" />
          <ThemeButton />
          <Link href="/settings" className="btn-ghost !h-8 !w-8 !p-0" aria-label={t("nav.settings")}><Settings className="h-4 w-4" strokeWidth={1.75} /></Link>
        </header>
        <main className="pb-20 lg:pb-0">{children}</main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-paper-line bg-paper-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur lg:hidden" aria-label="Main">
        {NAV.filter((n) => MOBILE.includes(n.href)).map(({ href, key, icon: Icon }) => (
          <Link key={href} href={href} className={`relative flex flex-col items-center gap-1 py-2 text-[11px] font-medium ${active(href) ? "text-ink" : "text-ink-mute"}`}>
            <Icon className="h-5 w-5" strokeWidth={1.75} />{t(key)}
            {active(href) && <span className="absolute top-0 h-0.5 w-6 bg-glow" aria-hidden />}
            {href === "/uploads" && busy > 0 && <span className="absolute right-[30%] top-1.5 h-1.5 w-1.5 rounded-[1px] bg-glow" />}
          </Link>))}
      </nav>

      {drag && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-night/85 text-white">
          <div className="rounded-2xl border border-dashed border-white/40 px-12 py-10 text-center"><UploadCloud className="mx-auto h-8 w-8" strokeWidth={1.5} /><p className="mt-3 font-serif text-xl">{t("up.drop")}</p></div>
        </div>)}

      <div className="pointer-events-none fixed bottom-20 right-4 z-[60] flex flex-col gap-2 lg:bottom-6" aria-live="polite">
        {toasts.map((x) => (<div key={x.id} className={`pointer-events-auto max-w-sm animate-rise rounded-lg px-4 py-2.5 text-sm shadow-lift ${x.kind === "error" ? "bg-danger text-white" : "bg-night text-white"}`}>{x.msg}</div>))}
      </div>
    </div>
  );
}
