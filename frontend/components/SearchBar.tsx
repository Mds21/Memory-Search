"use client";
import { Mic, Search as SearchIcon, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

interface Sug { text: string; type: string }
interface Props { value: string; onChange: (v: string) => void; onSubmit: (v: string) => void; placeholder?: string; autoFocus?: boolean; large?: boolean; busy?: boolean; dropUp?: boolean }

export default function SearchBar({ value, onChange, onSubmit, placeholder, autoFocus, large, busy, dropUp }: Props) {
  const { t } = useI18n();
  const ref = useRef<HTMLInputElement>(null);
  const [sugs, setSugs] = useState<Sug[]>([]);
  const [open, setOpen] = useState(false);
  const [hi, setHi] = useState(-1);

  useEffect(() => {
    const f = () => ref.current?.focus();
    window.addEventListener("smriti:focus-search", f);
    if (autoFocus) ref.current?.focus();
    return () => window.removeEventListener("smriti:focus-search", f);
  }, [autoFocus]);

  useEffect(() => {
    if (!open) return;
    const id = setTimeout(() => { api.get<{ items: Sug[] }>(`/suggest?q=${encodeURIComponent(value.slice(-40))}`).then((r) => { setSugs(r.items); setHi(-1); }).catch(() => setSugs([])); }, 150);
    return () => clearTimeout(id);
  }, [value, open]);

  const submit = (v: string) => { if (!v.trim()) return; setOpen(false); onSubmit(v.trim()); };
  return (
    <div className="relative">
      <form onSubmit={(e) => { e.preventDefault(); submit(hi >= 0 ? sugs[hi].text : value); }}
        className={`flex items-center gap-2 rounded-xl border border-paper-line bg-paper-card shadow-soft transition-[border-color,box-shadow] focus-within:border-tide/60 focus-within:ring-4 focus-within:ring-tide/10 ${large ? "h-14 pl-4 pr-2" : "h-11 pl-3 pr-1.5"}`}>
        <SearchIcon className={`${large ? "h-5 w-5" : "h-4 w-4"} shrink-0 text-ink-mute`} strokeWidth={1.75} aria-hidden />
        <input ref={ref} value={value} onChange={(e) => { onChange(e.target.value); setOpen(true); }} onFocus={() => value && setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 120)}
          onKeyDown={(e) => { if (e.key === "ArrowDown") { e.preventDefault(); setHi((h) => Math.min(h + 1, sugs.length - 1)); } else if (e.key === "ArrowUp") { e.preventDefault(); setHi((h) => Math.max(h - 1, -1)); } else if (e.key === "Escape") setOpen(false); }}
          placeholder={placeholder || t("search.placeholder")} aria-label={t("nav.search")} role="combobox" aria-expanded={open && sugs.length > 0} aria-autocomplete="list"
          style={{ outline: "none", boxShadow: "none" }} className={`min-w-0 flex-1 bg-transparent placeholder:text-ink-faint ${large ? "text-base" : "text-sm"}`} />
        <button type="button" disabled title={t("search.voice")} aria-label={t("search.voice")} className="btn-ghost !h-9 !w-9 !p-0 opacity-50"><Mic className="h-4 w-4" strokeWidth={1.75} /></button>
        <button className={`btn-primary !p-0 ${large ? "!h-10 !w-10" : "!h-8 !w-8"}`} disabled={!value.trim() || busy} aria-label={t("search.send")}><Send className="h-4 w-4" strokeWidth={1.75} /></button>
      </form>
      {open && sugs.length > 0 && (
        <ul role="listbox" className={`absolute inset-x-0 z-20 overflow-hidden ${dropUp ? "bottom-full mb-2" : "top-full mt-2"} rounded-xl border border-paper-line bg-paper-card p-1 shadow-lift`}>
          {sugs.map((s, i) => (
            <li key={s.type + s.text} role="option" aria-selected={i === hi}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => submit(s.type === "recent" || s.type === "document" ? s.text : value ? `${value.split(" ").slice(0, -1).join(" ")} ${s.text}`.trim() : s.text)}
                className={`flex h-9 w-full items-center justify-between gap-3 rounded-md px-3 text-left text-sm ${i === hi ? "bg-paper-sunk" : "hover:bg-paper-sunk"}`}>
                <span className="truncate">{s.text}</span><span className="font-mono text-[11px] text-ink-faint">{s.type}</span>
              </button>
            </li>))}
        </ul>)}
    </div>
  );
}
