"use client";
import {
  ArrowLeft, Camera, ChevronRight, Clock, FolderHeart, Home, Image as ImageIcon, LayoutGrid, LogOut, Map as MapIcon, Monitor, Moon, Plus,
  Search, Settings, Sun, UploadCloud,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { prefetch } from "@/lib/swr";
import { type ThemePref, useTheme } from "@/lib/theme";
import { useUploads } from "@/lib/uploads";
import LanguageSwitcher from "./LanguageSwitcher";
import Logo from "./Logo";
import PasswordGate from "./PasswordGate";
import { Sheet } from "./ui";

/** Each section's first API call, warmed on hover/touch so the page opens with data already cached. */
export const SECTION_DATA: Record<string, string[]> = {
  "/": ["/assets?limit=12", "/on-this-day", "/saved-searches", "/me/storage"],
  "/library": ["/assets?limit=60&offset=0"],
  "/timeline": ["/timeline"],
  "/collections": ["/collections"],
  "/settings": ["/me/storage"],
};

const NAV = [
  { href: "/", key: "nav.home", icon: Home }, { href: "/search", key: "nav.search", icon: Search }, { href: "/library", key: "nav.library", icon: ImageIcon },
  { href: "/timeline", key: "nav.timeline", icon: Clock }, { href: "/map", key: "nav.map", icon: MapIcon },
  { href: "/collections", key: "nav.collections", icon: FolderHeart }, { href: "/uploads", key: "nav.uploads", icon: UploadCloud },
];
const MORE = ["/timeline", "/map", "/collections", "/uploads"];
const TITLES: Record<string, string> = { "/search": "nav.search", "/library": "nav.library", "/timeline": "nav.timeline", "/map": "nav.map",
  "/collections": "nav.collections", "/uploads": "nav.uploads", "/settings": "nav.settings" };

function ThemeButton({ className = "" }: { className?: string }) {
  const { pref, cycle } = useTheme();
  const Icon = pref === "dark" ? Moon : pref === "light" ? Sun : Monitor;
  const label = `Theme: ${pref}`;
  return <button onClick={cycle} className={`btn-ghost !p-2 ${className}`} aria-label={label} title={label}><Icon className="h-4 w-4" /></button>;
}

function ThemeSegment() {
  const { t } = useI18n();
  const { pref, set } = useTheme();
  const opts: [ThemePref, typeof Sun, string][] = [["light", Sun, "theme.light"], ["dark", Moon, "theme.dark"], ["system", Monitor, "theme.auto"]];
  return (
    <div className="grid grid-cols-3 gap-1 rounded-2xl bg-paper-sunk p-1">
      {opts.map(([v, I, k]) => (
        <button key={v} onClick={() => set(v)} aria-pressed={pref === v}
          className={`tap flex items-center justify-center gap-1.5 rounded-xl py-2 text-xs font-medium transition-all ${pref === v ? "bg-paper-card text-ink shadow-soft" : "text-ink-mute"}`}>
          <I className="h-3.5 w-3.5" />{t(k)}</button>))}
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const { t } = useI18n();
  const { user, loading, logout } = useAuth();
  const { busy, addFiles, toasts } = useUploads();
  const path = usePathname();
  const router = useRouter();
  const [drag, setDrag] = useState(false);
  const [more, setMore] = useState(false);
  const [add, setAdd] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const camRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, user, router]);
  useEffect(() => { setMore(false); setAdd(false); }, [path]);

  // Warm every section's code once the browser is idle, so switching tabs is instant.
  useEffect(() => {
    if (!user) return;
    const idle = (window as any).requestIdleCallback || ((f: () => void) => setTimeout(f, 800));
    idle(() => { [...NAV.map((n) => n.href), "/settings"].forEach((h) => router.prefetch(h)); });
  }, [user, router]);

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

  if (loading || !user) return <ShellSkeleton />;
  if (user.must_change_password) return <PasswordGate />;
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
  const warm = (href: string) => () => SECTION_DATA[href]?.forEach(prefetch);
  const who = user.display_name || user.email || user.phone || user.username || "Me";
  const contact = user.email || user.phone || (user.username ? `@${user.username}` : "");
  const initials = who.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((s) => s[0]!.toUpperCase()).join("");
  const pick = (files: FileList | null) => { if (files?.length) { addFiles([...files]); router.push("/uploads"); } setAdd(false); };

  // phone header: detail pages get a back button, sections get their name, home gets the brand
  const detail = /^\/(media|documents|collections)\/[^/]+/.test(path);
  const section = Object.keys(TITLES).find((k) => path.startsWith(k));
  const detailTitle = path.startsWith("/media") ? t("nav.item") : path.startsWith("/documents") ? t("search.documents") : t("nav.collections");
  const back = () => (window.history.length > 1 ? router.back() : router.push(path.startsWith("/collections") ? "/collections" : "/library"));
  const moreActive = MORE.some((h) => path.startsWith(h)) || path.startsWith("/settings");

  return (
    <div className="ambient min-h-[100dvh] lg:grid lg:grid-cols-[248px_1fr]">
      <aside className="hidden border-r border-paper-line/70 bg-paper-card/60 backdrop-blur-xl lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <Link href="/" className="flex items-center gap-2.5 px-5 pb-4 pt-5"><Logo size={30} /><span className="text-[17px] font-semibold tracking-tight">Memory Search</span></Link>
        <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
          {NAV.map(({ href, key, icon: Icon }) => {
            const on = active(href);
            return (
              <Link key={href} href={href} aria-current={on ? "page" : undefined} onMouseEnter={warm(href)} onFocus={warm(href)}
                className={`group relative flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${on ? "bg-tide-soft text-tide-dark" : "text-ink-soft hover:bg-paper-sunk hover:text-ink"}`}>
                {on && <span className="absolute -left-3 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-iris" />}
                <Icon className={`h-[18px] w-[18px] transition-transform group-hover:scale-110 ${on ? "" : "text-ink-mute group-hover:text-ink-soft"}`} />{t(key)}
                {href === "/uploads" && busy > 0 && <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-tide px-1.5 text-[11px] font-semibold text-paper">{busy}</span>}
              </Link>);
          })}
        </nav>
        <div className="space-y-1 border-t border-paper-line/70 p-3">
          <Link href="/settings" onMouseEnter={warm("/settings")} className={`flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium transition-colors ${active("/settings") ? "bg-tide-soft text-tide-dark" : "text-ink-soft hover:bg-paper-sunk hover:text-ink"}`}><Settings className="h-[18px] w-[18px]" />{t("nav.settings")}</Link>
          <div className="flex items-center justify-between px-3 py-1"><LanguageSwitcher /><ThemeButton /></div>
          <div className="mt-1 flex items-center gap-3 rounded-xl bg-paper-sunk/70 px-3 py-2.5">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-tide to-iris text-xs font-semibold text-paper">{initials}</span>
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{who}</p><p className="truncate text-xs text-ink-mute">{contact}</p></div>
            <button onClick={logout} className="btn-ghost !p-1.5" aria-label={t("nav.signOut")} title={t("nav.signOut")}><LogOut className="h-4 w-4" /></button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col pb-[calc(5.5rem+env(safe-area-inset-bottom))] lg:pb-0">
        <header className="glass sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-paper-line/70 px-2 lg:hidden" style={{ paddingTop: "env(safe-area-inset-top)" }}>
          {detail ? (<>
            <button onClick={back} className="tap btn-ghost !p-2.5" aria-label={t("nav.back")}><ArrowLeft className="h-5 w-5" /></button>
            <span className="truncate text-[15px] font-semibold">{detailTitle}</span>
          </>) : section ? (
            <span className="px-2 text-lg font-semibold tracking-tight">{t(TITLES[section])}</span>
          ) : (
            <Link href="/" className="flex items-center gap-2 px-2"><Logo size={26} /><span className="font-semibold tracking-tight">Memory Search</span></Link>
          )}
          <div className="ml-auto flex items-center">
            {path !== "/search" && <Link href="/search" className="tap btn-ghost !p-2.5" aria-label={t("nav.search")}><Search className="h-5 w-5" /></Link>}
            <button onClick={() => setMore(true)} className="tap ml-0.5 flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-tide to-iris text-xs font-semibold text-paper" aria-label={t("nav.more")}>{initials}</button>
          </div>
        </header>
        <main key={path} className="min-w-0 flex-1 animate-fade-in">{children}</main>
      </div>

      {/* phone tab bar: the four places people go most, plus a big "add" in the middle */}
      <nav className="glass fixed inset-x-3 z-30 grid grid-cols-5 items-end rounded-[1.4rem] border border-paper-line/70 px-1 shadow-lift lg:hidden"
        style={{ bottom: "max(0.75rem, env(safe-area-inset-bottom))" }} aria-label="Main">
        <Tab href="/" icon={Home} label={t("nav.home")} on={active("/")} warm={warm("/")} />
        <Tab href="/search" icon={Search} label={t("nav.search")} on={active("/search")} />
        <div className="flex justify-center">
          <button onClick={() => setAdd(true)} aria-label={t("nav.add")}
            className="tap relative -top-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-tide to-iris text-paper shadow-glow ring-4 ring-paper">
            <Plus className="h-7 w-7" />
            {busy > 0 && <span className="absolute -right-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-night px-1 text-[10px] font-bold text-white ring-2 ring-paper">{busy}</span>}
          </button>
        </div>
        <Tab href="/library" icon={ImageIcon} label={t("nav.library")} on={active("/library")} warm={warm("/library")} />
        <button onClick={() => setMore(true)} className={`tap flex flex-col items-center gap-0.5 py-2 text-[10.5px] font-medium ${moreActive ? "text-tide-dark" : "text-ink-mute"}`}>
          <span className={`flex h-7 w-12 items-center justify-center rounded-full ${moreActive ? "bg-tide-soft" : ""}`}><LayoutGrid className="h-[19px] w-[19px]" /></span>{t("nav.more")}
        </button>
      </nav>

      <Sheet open={more} onClose={() => setMore(false)}>
        <div className="mb-4 flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-tide to-iris text-sm font-semibold text-paper">{initials}</span>
          <div className="min-w-0 flex-1"><p className="truncate font-semibold">{who}</p><p className="truncate text-xs text-ink-mute">{contact}</p></div>
        </div>
        <div className="grid grid-cols-2 gap-2.5">
          {NAV.filter((n) => MORE.includes(n.href)).map(({ href, key, icon: Icon }) => (
            <Link key={href} href={href} onTouchStart={warm(href)} className={`tap relative flex flex-col gap-2 rounded-2xl border p-3.5 ${active(href) ? "border-tide/40 bg-tide-soft" : "border-paper-line bg-paper-sunk/50"}`}>
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-paper-card text-iris shadow-soft"><Icon className="h-[18px] w-[18px]" /></span>
              <span className="text-sm font-medium">{t(key)}</span>
              {href === "/uploads" && busy > 0 && <span className="absolute right-3 top-3 rounded-full bg-tide px-2 py-0.5 text-[11px] font-semibold text-paper">{busy}</span>}
            </Link>))}
        </div>
        <Link href="/settings" className="tap mt-3 flex items-center gap-3 rounded-2xl border border-paper-line px-4 py-3 text-sm font-medium">
          <Settings className="h-[18px] w-[18px] text-ink-mute" />{t("nav.settings")}<ChevronRight className="ml-auto h-4 w-4 text-ink-faint" /></Link>
        <p className="eyebrow mb-2 mt-5">{t("theme.title")}</p>
        <ThemeSegment />
        <div className="mt-4 flex items-center justify-between"><LanguageSwitcher /><button onClick={logout} className="btn-ghost !text-danger"><LogOut className="h-4 w-4" />{t("nav.signOut")}</button></div>
      </Sheet>

      <Sheet open={add} onClose={() => setAdd(false)} title={t("nav.add")}>
        <div className="grid grid-cols-2 gap-2.5 pb-1">
          <button onClick={() => camRef.current?.click()} className="tap flex flex-col items-start gap-2 rounded-2xl bg-gradient-to-br from-tide to-iris p-4 text-left text-paper shadow-glow">
            <Camera className="h-6 w-6" /><span className="text-sm font-semibold">{t("add.camera")}</span><span className="text-xs text-white/80">{t("add.cameraHint")}</span></button>
          <button onClick={() => fileRef.current?.click()} className="tap flex flex-col items-start gap-2 rounded-2xl border border-paper-line bg-paper-sunk/60 p-4 text-left">
            <UploadCloud className="h-6 w-6 text-iris" /><span className="text-sm font-semibold">{t("add.files")}</span><span className="text-xs text-ink-mute">{t("add.filesHint")}</span></button>
        </div>
        <Link href="/uploads" className="mt-3 flex items-center justify-between rounded-2xl px-1 py-2 text-sm text-ink-soft">{t("add.manage")}<ChevronRight className="h-4 w-4" /></Link>
        <input ref={fileRef} type="file" multiple hidden onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
        <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => { pick(e.target.files); e.target.value = ""; }} />
      </Sheet>

      {drag && (
        <div className="pointer-events-none fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-night/70 p-6 backdrop-blur-sm">
          <div className="animate-scale-in rounded-3xl border-2 border-dashed border-paper/60 bg-gradient-to-br from-tide/90 to-iris/90 px-14 py-12 text-center text-paper shadow-lift">
            <UploadCloud className="mx-auto h-11 w-11" /><p className="mt-3 text-lg font-semibold">{t("up.drop")}</p>
          </div>
        </div>)}

      <div className="pointer-events-none fixed inset-x-3 bottom-[calc(6.5rem+env(safe-area-inset-bottom))] z-[60] flex flex-col items-center gap-2 sm:inset-x-auto sm:right-4 sm:items-end lg:bottom-6" aria-live="polite">
        {toasts.map((x) => (
          <div key={x.id} className={`pointer-events-auto max-w-sm animate-fade-up rounded-2xl px-4 py-2.5 text-sm font-medium shadow-lift ${x.kind === "error" ? "bg-danger text-white" : "bg-night text-white ring-1 ring-white/10"}`}>{x.msg}</div>))}
      </div>
    </div>
  );
}

function Tab({ href, icon: Icon, label, on, warm }: { href: string; icon: typeof Home; label: string; on: boolean; warm?: () => void }) {
  return (
    <Link href={href} onTouchStart={warm} aria-current={on ? "page" : undefined}
      className={`tap flex flex-col items-center gap-0.5 py-2 text-[10.5px] font-medium transition-colors ${on ? "text-tide-dark" : "text-ink-mute"}`}>
      <span className={`flex h-7 w-12 items-center justify-center rounded-full transition-colors ${on ? "bg-tide-soft" : ""}`}><Icon className="h-[19px] w-[19px]" /></span>{label}
    </Link>
  );
}

/** Same layout as the shell, so the first paint already looks like the app instead of a lone spinner. */
function ShellSkeleton() {
  return (
    <div className="ambient min-h-[100dvh] lg:grid lg:grid-cols-[248px_1fr]" aria-busy>
      <aside className="hidden border-r border-paper-line/70 bg-paper-card/60 p-5 lg:block">
        <div className="mb-6 flex items-center gap-2.5"><Logo size={30} /><span className="text-[17px] font-semibold tracking-tight">Memory Search</span></div>
        <div className="space-y-2">{Array.from({ length: 7 }, (_, i) => <div key={i} className="skeleton h-8 rounded-xl" />)}</div>
      </aside>
      <div className="mx-auto w-full max-w-5xl px-4 py-12 sm:px-6"><div className="skeleton mx-auto h-10 max-w-md rounded-xl" /><div className="skeleton mx-auto mt-6 h-14 max-w-2xl rounded-2xl" /></div>
    </div>
  );
}
