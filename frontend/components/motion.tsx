"use client";
/**
 * Small motion primitives in the spirit of React Bits (reactbits.dev): blur-in text, rotating phrases, count-up
 * numbers, a cursor spotlight and a soft aurora backdrop. CSS + a few lines of React, no animation library, and all
 * of them settle instantly when the person prefers reduced motion.
 */
import { useEffect, useRef, useState } from "react";

const reduced = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Words fade up from a blur one after another. */
export function BlurText({ text, className = "", step = 70 }: { text: string; className?: string; step?: number }) {
  return (
    <span className={className} aria-label={text}>
      {text.split(" ").map((w, i) => (
        <span key={`${w}-${i}`} aria-hidden className="blur-word" style={{ animationDelay: `${i * step}ms` }}>{w}{" "}</span>
      ))}
    </span>
  );
}

/** Cycles through phrases with a vertical flip. */
export function RotatingText({ items, interval = 2600, className = "" }: { items: string[]; interval?: number; className?: string }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (items.length < 2 || reduced()) return;
    const id = setInterval(() => setI((x) => (x + 1) % items.length), interval);
    return () => clearInterval(id);
  }, [items.length, interval]);
  const word = items[i % Math.max(items.length, 1)] || "";
  return (
    <span className={`relative inline-flex overflow-hidden align-bottom ${className}`} aria-live="polite">
      <span key={word} className="rotate-in inline-block whitespace-nowrap">{word}</span>
    </span>
  );
}

/** Animated number that counts up to `to` when it first scrolls into view. */
export function CountUp({ to, duration = 900, className = "" }: { to: number; duration?: number; className?: string }) {
  const [v, setV] = useState(0);
  const el = useRef<HTMLSpanElement>(null);
  const from = useRef(0);
  useEffect(() => {
    if (reduced()) { setV(to); return; }
    let raf = 0;
    const start = from.current;
    const run = () => {
      const t0 = performance.now();
      const tick = (now: number) => {
        const p = Math.min(1, (now - t0) / duration);
        const val = Math.round(start + (to - start) * (1 - Math.pow(1 - p, 3)));
        setV(val);
        from.current = val;
        if (p < 1) raf = requestAnimationFrame(tick);
      };
      raf = requestAnimationFrame(tick);
    };
    const node = el.current;
    if (!node || !("IntersectionObserver" in window)) { run(); return () => cancelAnimationFrame(raf); }
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) { run(); io.disconnect(); } });
    io.observe(node);
    return () => { io.disconnect(); cancelAnimationFrame(raf); };
  }, [to, duration]);
  return <span ref={el} className={`tabular-nums ${className}`}>{v.toLocaleString()}</span>;
}

/** Wrapper that paints a soft violet glow under the pointer (desktop only; touch devices just see the card). */
export function Spotlight({ children, className = "", as: Tag = "div" }: { children: React.ReactNode; className?: string; as?: any }) {
  const ref = useRef<HTMLElement>(null);
  const move = (e: React.PointerEvent) => {
    const n = ref.current;
    if (!n || e.pointerType !== "mouse") return;
    const r = n.getBoundingClientRect();
    n.style.setProperty("--mx", `${e.clientX - r.left}px`);
    n.style.setProperty("--my", `${e.clientY - r.top}px`);
  };
  return <Tag ref={ref} onPointerMove={move} className={`spotlight ${className}`}>{children}</Tag>;
}

/** Slow-drifting aurora blobs + a faint dot grid. Purely decorative. */
export function Aurora({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden className={`pointer-events-none absolute inset-0 -z-10 overflow-hidden ${className}`}>
      <div className="aurora-blob aurora-a" />
      <div className="aurora-blob aurora-b" />
      <div className="dot-grid absolute inset-0" />
    </div>
  );
}
