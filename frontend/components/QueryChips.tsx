"use client";
import { Calendar, FileText, Image as ImageIcon, MapPin, Plus, Tag, Video, X } from "lucide-react";
import { useState } from "react";
import { useI18n } from "@/lib/i18n";
import type { Kind, Parsed } from "@/lib/types";
import { dateChipLabel } from "@/lib/util";

const KIND_ICON = { photo: ImageIcon, video: Video, document: FileText } as const;
const KIND_KEY = { photo: "search.photos", video: "search.videos", document: "search.documents" } as const;

/** Editable filter chips (F6). Editing re-runs the search with the structured filters, no LLM call. */
export default function QueryChips({ parsed, onChange }: { parsed: Parsed; onChange: (p: Parsed) => void }) {
  const { t, lang } = useI18n();
  const [open, setOpen] = useState(false);
  const [from, setFrom] = useState(""); const [to, setTo] = useState(""); const [place, setPlace] = useState("");
  const f = parsed.filters;
  const set = (patch: Partial<typeof f>) => onChange({ ...parsed, filters: { ...f, ...patch } });
  const date = dateChipLabel(f, lang);
  const Chip = ({ icon: I, label, onRemove }: { icon: any; label: string; onRemove: () => void }) => (
    <span className="chip chip-on"><I className="h-3.5 w-3.5" />{label}<button onClick={onRemove} className="-mr-1 rounded-full p-0.5 hover:bg-tide/10" aria-label={`Remove ${label}`}><X className="h-3 w-3" /></button></span>
  );
  const toggle = (k: Kind) => set({ kinds: f.kinds.includes(k) ? f.kinds.filter((x) => x !== k) : [...f.kinds, k] });

  return (
    <div className="relative flex flex-wrap items-center gap-2" aria-label="Filters">
      {parsed.semantic_query && <span className="chip"><span className="text-ink-faint">“</span>{parsed.semantic_query}<span className="text-ink-faint">”</span></span>}
      {f.kinds.map((k) => <Chip key={k} icon={KIND_ICON[k]} label={t(KIND_KEY[k])} onRemove={() => toggle(k)} />)}
      {date && <Chip icon={Calendar} label={date} onRemove={() => set({ date_from: null, date_to: null })} />}
      {f.place && <Chip icon={MapPin} label={f.place} onRemove={() => set({ place: null })} />}
      {f.tags.map((tg) => <Chip key={tg} icon={Tag} label={tg} onRemove={() => set({ tags: f.tags.filter((x) => x !== tg) })} />)}
      <button className="chip hover:bg-paper-sunk" onClick={() => setOpen((o) => !o)} aria-expanded={open}><Plus className="h-3.5 w-3.5" />{t("search.addFilter")}</button>
      {open && (
        <div className="absolute left-0 top-full z-20 mt-2 w-72 space-y-3 rounded-xl border border-paper-line bg-white p-3 shadow-lift">
          <div className="flex gap-1.5">{(["photo", "video", "document"] as Kind[]).map((k) => { const I = KIND_ICON[k]; return (
            <button key={k} onClick={() => toggle(k)} className={`chip ${f.kinds.includes(k) ? "chip-on" : ""}`}><I className="h-3.5 w-3.5" />{t(KIND_KEY[k])}</button>); })}</div>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-xs text-ink-mute">{t("search.from")}<input type="date" className="input mt-1" value={from} onChange={(e) => setFrom(e.target.value)} /></label>
            <label className="text-xs text-ink-mute">{t("search.to")}<input type="date" className="input mt-1" value={to} onChange={(e) => setTo(e.target.value)} /></label>
          </div>
          <label className="block text-xs text-ink-mute">{t("search.place")}<input className="input mt-1" value={place} onChange={(e) => setPlace(e.target.value)} placeholder="Goa" /></label>
          <button className="btn-primary w-full" onClick={() => { set({ date_from: from || f.date_from, date_to: to || f.date_to, place: place.trim() || f.place }); setOpen(false); setFrom(""); setTo(""); setPlace(""); }}>{t("search.apply")}</button>
        </div>)}
    </div>
  );
}
