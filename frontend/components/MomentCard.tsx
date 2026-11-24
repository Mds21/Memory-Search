"use client";
import { CalendarHeart, FileText, Film, Images, MapPin, Palette, Plane, Sparkles as Star, Clock } from "lucide-react";
import Link from "next/link";
import { abs } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Moment } from "@/lib/types";

export const MOMENT_KIND: Record<string, { icon: any; key: string }> = {
  on_this_day: { icon: CalendarHeart, key: "mo.onThisDay" },
  trip: { icon: Plane, key: "mo.trip" },
  event: { icon: Star, key: "mo.event" },
  month: { icon: Clock, key: "mo.month" },
  year: { icon: Clock, key: "mo.year" },
  place: { icon: MapPin, key: "mo.place" },
  theme: { icon: Palette, key: "mo.theme" },
  documents: { icon: FileText, key: "mo.documents" },
  videos: { icon: Film, key: "mo.videos" },
  recent: { icon: Images, key: "mo.recent" },
  archive: { icon: Images, key: "mo.archive" },
};

/** A moment as a story card: its cover photo, what kind of moment it is, the title and what's inside. */
export default function MomentCard({ m, size = "story" }: { m: Moment; size?: "story" | "wide" | "grid" }) {
  const { t } = useI18n();
  const kind = MOMENT_KIND[m.type] || MOMENT_KIND.theme;
  const Icon = kind.icon;
  const cover = m.cover?.preview_url || m.cover?.thumb_url;
  const box = size === "story" ? "w-56 shrink-0 aspect-[3/4] sm:w-60" : size === "wide" ? "aspect-[16/10] w-full" : "aspect-[4/5] w-full";

  return (
    <Link href={`/moments/${encodeURIComponent(m.id)}`} className={`group relative block snap-start overflow-hidden rounded-sm bg-paper-sunk shadow-lift ${box}`}>
      {cover ? <img src={abs(cover)} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover transition-[filter] duration-300 group-hover:brightness-110" />
        : <span className="absolute inset-0 flex items-center justify-center text-ink-faint"><Icon className="h-10 w-10" strokeWidth={1} /></span>}
      {m.type === "documents" && cover && <span aria-hidden className="absolute inset-0 bg-night/35" />}
      <span aria-hidden className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-black/10" />
      <span className="absolute left-4 right-4 top-4 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-label text-white/80">
        <Icon className="h-3.5 w-3.5" strokeWidth={1.5} />{t(kind.key)}{m.when ? <span className="truncate text-white/55"> · {m.when}</span> : null}
      </span>
      {m.preview.length > 0 && size !== "story" && (
        <span aria-hidden className="absolute right-4 top-10 hidden gap-1 sm:flex">
          {m.preview.slice(0, 3).map((p) => p.thumb_url && <img key={p.asset_id} src={abs(p.thumb_url)} alt="" className="h-9 w-9 rounded-sm border border-white/30 object-cover" />)}
        </span>)}
      <span className="absolute inset-x-0 bottom-0 p-5 text-white">
        <span className={`block font-medium uppercase leading-tight tracking-[0.1em] ${size === "wide" ? "text-[22px]" : "text-[15px]"}`}>{m.title}</span>
        <span className="bar mt-3" aria-hidden />
        <span className="mt-3 block truncate text-[11px] uppercase tracking-label text-white/70">{m.subtitle}</span>
      </span>
    </Link>
  );
}
