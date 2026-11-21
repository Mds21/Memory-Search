"use client";
import { Clock, FolderHeart, Home, Image as ImageIcon, LogOut, Map as MapIcon, Search, Settings, UploadCloud } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useUploads } from "@/lib/uploads";
import LanguageSwitcher from "./LanguageSwitcher";
import Logo from "./Logo";
import { Spinner } from "./ui";

const NAV = [
  { href: "/", key: "nav.home", icon: Home }, { href: "/search", key: "nav.search", icon: Search }, { href: "/library", key: "nav.library", icon: ImageIcon },
  { href: "/timeline", key: "nav.timeline", icon: Clock }, { href: "/map", key: "nav.map", icon: MapIcon },
  { href: "/collections", key: "nav.collections", icon: FolderHeart }, { href: "/uploads", key: "nav.uploads", icon: UploadCloud },
];
const MOBILE = ["/", "/search", "/library", "/collections", "/uploads"];

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

  if (loading || !user) return <div className="flex h-screen items-center justify-center"><Spinner className="h-6 w-6 text-tide" /></div>;
  const active = (href: string) => (href === "/" ? path === "/" : path.startsWith(href));

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[232px_1fr]">
      <aside className="hidden border-r border-paper-line bg-white lg:sticky lg:top-0 lg:flex lg:h-screen lg:flex-col">
        <div className="flex items-center gap-2.5 px-5 py-5"><Logo /><span className="text-lg font-semibold tracking-tight">Smriti</span></div>
        <nav className="flex-1 space-y-0.5 px-3" aria-label="Main">
          {NAV.map(({ href, key, icon: Icon }) => (
            <Link key={href} href={href} aria-current={active(href) ? "page" : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${active(href) ? "bg-tide-soft text-tide-dark" : "text-ink-soft hover:bg-paper-sunk"}`}>
              <Icon className="h-[18px] w-[18px]" />{t(key)}
              {href === "/uploads" && busy > 0 && <span className="ml-auto inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-tide px-1.5 text-[11px] text-white">{busy}</span>}
            </Link>))}
        </nav>
        <div className="space-y-2 border-t border-paper-line p-3">
          <Link href="/settings" className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium ${active("/settings") ? "bg-tide-soft text-tide-dark" : "text-ink-soft hover:bg-paper-sunk"}`}><Settings className="h-[18px] w-[18px]" />{t("nav.settings")}</Link>
          <div className="px-3"><LanguageSwitcher /></div>
          <div className="flex items-center justify-between gap-2 px-3 py-1">
            <div className="min-w-0"><p className="truncate text-sm font-medium">{user.display_name}</p><p className="truncate text-xs text-ink-mute">{user.email}</p></div>
            <button onClick={logout} className="btn-ghost !p-2" aria-label={t("nav.signOut")} title={t("nav.signOut")}><LogOut className="h-4 w-4" /></button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col pb-16 lg:pb-0">
        <header className="flex items-center justify-between border-b border-paper-line bg-white px-4 py-3 lg:hidden">
          <div className="flex items-center gap-2"><Logo size={24} /><span className="font-semibold">Smriti</span></div>
          <div className="flex items-center gap-1"><LanguageSwitcher compact /><Link href="/settings" className="btn-ghost !p-2" aria-label={t("nav.settings")}><Settings className="h-5 w-5" /></Link></div>
        </header>
        <main className="min-w-0 flex-1">{children}</main>
      </div>

      <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-paper-line bg-white lg:hidden" aria-label="Main">
        {NAV.filter((n) => MOBILE.includes(n.href)).map(({ href, key, icon: Icon }) => (
          <Link key={href} href={href} className={`relative flex flex-col items-center gap-0.5 py-2 text-[11px] font-medium ${active(href) ? "text-tide" : "text-ink-mute"}`}>
            <Icon className="h-5 w-5" />{t(key)}{href === "/uploads" && busy > 0 && <span className="absolute right-[28%] top-1 h-2 w-2 rounded-full bg-tide" />}
          </Link>))}
      </nav>

      {drag && (<div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center bg-tide/90 text-white"><div className="rounded-2xl border-2 border-dashed border-white/70 px-12 py-10 text-center"><UploadCloud className="mx-auto h-10 w-10" /><p className="mt-3 text-lg font-semibold">{t("up.drop")}</p></div></div>)}

      <div className="pointer-events-none fixed bottom-20 right-4 z-[60] flex flex-col gap-2 lg:bottom-6" aria-live="polite">
        {toasts.map((x) => (<div key={x.id} className={`pointer-events-auto max-w-sm rounded-lg px-4 py-2.5 text-sm shadow-lift ${x.kind === "error" ? "bg-danger text-white" : "bg-ink text-white"}`}>{x.msg}</div>))}
      </div>
    </div>
  );
}
