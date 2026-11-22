"use client";
import { Loader2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

export const Spinner = ({ className = "" }: { className?: string }) => <Loader2 className={`h-4 w-4 animate-spin ${className}`} aria-label="Loading" />;

export function Empty({ icon, title, body, action }: { icon?: React.ReactNode; title: string; body?: string; action?: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-sm animate-fade-up flex-col items-center py-16 text-center">
      {icon && (
        <div className="relative mb-5">
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-tide to-iris opacity-25 blur-xl" />
          <div className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-paper-line bg-paper-card text-iris shadow-soft">{icon}</div>
        </div>)}
      <h3 className="text-base font-semibold">{title}</h3>
      {body && <p className="mt-1.5 text-sm leading-relaxed text-ink-mute">{body}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function GridSkeleton({ n = 12 }: { n?: number }) {
  const hs = [160, 220, 190, 250, 170, 210];
  return <div className="masonry" aria-hidden>{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton rounded-2xl" style={{ height: hs[i % hs.length] }} />)}</div>;
}
export function CardSkeleton({ n = 6, h = 200 }: { n?: number; h?: number }) {
  return <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" aria-hidden>{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton rounded-2xl" style={{ height: h }} />)}</div>;
}
export function LineSkeleton({ n = 3 }: { n?: number }) {
  return <div className="space-y-2" aria-hidden>{Array.from({ length: n }, (_, i) => <div key={i} className="skeleton h-4 rounded-md" style={{ width: `${90 - i * 15}%` }} />)}</div>;
}

/** Page title row used across sections. */
/** Page title row. On phones the top bar already names the section, so `inBar` pages show only count/sub/actions there. */
export function PageHeader({ title, count, sub, actions, inBar = true, wideActions }: { title: React.ReactNode; count?: number | null; sub?: React.ReactNode; actions?: React.ReactNode; inBar?: boolean; wideActions?: boolean }) {
  const badge = count != null && <span className="rounded-full bg-paper-sunk px-2.5 py-0.5 text-sm font-medium tabular-nums text-ink-mute">{count}</span>;
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 sm:mb-6 sm:items-end">
      <div className="min-w-0">
        <h1 className={`h-page items-baseline gap-2.5 ${inBar ? "hidden lg:flex" : "flex"}`}>{title}{badge}</h1>
        {inBar && count != null && <p className="text-sm text-ink-mute lg:hidden"><span className="font-semibold tabular-nums text-ink">{count}</span> {"·"} {typeof title === "string" ? title : ""}</p>}
        {sub && <p className="mt-1 text-sm text-ink-mute">{sub}</p>}
      </div>
      {actions && <div className={`flex flex-wrap items-center gap-2 ${wideActions ? "max-sm:basis-full" : ""}`}>{actions}</div>}
    </div>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: React.ReactNode; wide?: boolean }) {
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex animate-fade-in items-end justify-center bg-night/50 p-0 backdrop-blur-sm sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal aria-label={title}>
      <div className={`max-h-[85vh] w-full animate-scale-in overflow-auto rounded-t-3xl border border-paper-line bg-paper-card p-5 shadow-lift sm:rounded-3xl ${wide ? "sm:max-w-2xl" : "sm:max-w-md"}`}>
        <div className="mb-4 flex items-center justify-between"><h2 className="text-base font-semibold">{title}</h2>
          <button className="btn-ghost !p-1.5" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button></div>
        {children}
      </div>
    </div>
  );
}

/** Phone-style sheet that slides up from the bottom (centred dialog on wide screens). Swipe down or tap outside to close. */
export function Sheet({ open, onClose, title, children }: { open: boolean; onClose: () => void; title?: string; children: React.ReactNode }) {
  const [dy, setDy] = useState(0);
  const start = useRef<number | null>(null);
  useEffect(() => {
    if (!open) return;
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", h); document.body.style.overflow = prev; };
  }, [open, onClose]);
  useEffect(() => { if (!open) setDy(0); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[55] flex animate-fade-in items-end justify-center bg-night/50 backdrop-blur-[2px] sm:items-center sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()} role="dialog" aria-modal aria-label={title}>
      <div className="max-h-[88dvh] w-full overflow-y-auto overscroll-contain rounded-t-3xl border border-paper-line bg-paper-card pb-[max(1rem,env(safe-area-inset-bottom))] shadow-lift sm:max-w-md sm:rounded-3xl sm:pb-4"
        style={{ transform: dy ? `translateY(${dy}px)` : undefined, transition: start.current === null ? "transform .2s ease" : "none", animation: "sheet-up .28s cubic-bezier(.2,.8,.2,1) both" }}
        onTouchStart={(e) => { if ((e.currentTarget as HTMLElement).scrollTop <= 0) start.current = e.touches[0].clientY; }}
        onTouchMove={(e) => { if (start.current !== null) setDy(Math.max(0, e.touches[0].clientY - start.current)); }}
        onTouchEnd={() => { if (dy > 90) onClose(); else setDy(0); start.current = null; }}>
        <div className="sticky top-0 z-10 bg-paper-card/95 px-5 pb-2 pt-3 backdrop-blur">
          <div className="mx-auto mb-2 h-1.5 w-10 rounded-full bg-paper-line sm:hidden" aria-hidden />
          {title && <div className="flex items-center justify-between"><h2 className="text-base font-semibold">{title}</h2>
            <button className="btn-ghost !p-2" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></button></div>}
        </div>
        <div className="px-5">{children}</div>
      </div>
    </div>
  );
}

/** True on phones/tablets: used to avoid popping the keyboard open on page load. */
export const isTouch = () => typeof window !== "undefined" && window.matchMedia("(pointer: coarse)").matches;

export function fmtDate(iso?: string | null, lang = "en") {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(lang, { year: "numeric", month: "short", day: "numeric" });
}
export function fmtDuration(ms?: number | null) {
  if (!ms && ms !== 0) return "";
  const s = Math.round(ms / 1000);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}
export function fmtBytes(n: number) {
  if (n < 1024) return `${n} B`;
  const u = ["KB", "MB", "GB", "TB"]; let i = -1;
  do { n /= 1024; i++; } while (n >= 1024 && i < 3);
  return `${n.toFixed(n < 10 ? 1 : 0)} ${u[i]}`;
}
