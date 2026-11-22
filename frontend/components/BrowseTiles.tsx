"use client";
import { BadgeCheck, CalendarDays, FileText, FolderHeart, HeartPulse, Image as ImageIcon, MapPin, Video } from "lucide-react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { prefetch, useApi } from "@/lib/swr";
import { searchHref } from "@/lib/share";
import { CountUp, Spotlight } from "./motion";

/** "Browse" row on Home: one tap into every part of the library, with live counts. */
export default function BrowseTiles() {
  const { t } = useI18n();
  const store = useApi<{ items: { kind: string; count: number }[] }>("/me/storage").data;
  const n = (k: string) => store?.items.find((i) => i.kind === k)?.count;
  const tiles = [
    { href: "/library?kind=photo", label: t("search.photos"), icon: ImageIcon, count: n("photo"), data: "/assets?limit=60&offset=0&kind=photo" },
    { href: "/library?kind=video", label: t("search.videos"), icon: Video, count: n("video"), data: "/assets?limit=60&offset=0&kind=video" },
    { href: "/library?kind=document", label: t("search.documents"), icon: FileText, count: n("document"), data: "/assets?limit=60&offset=0&kind=document" },
    { href: searchHref(t("browse.idQuery")), label: t("browse.ids"), icon: BadgeCheck },
    { href: searchHref(t("browse.healthQuery")), label: t("browse.health"), icon: HeartPulse },
    { href: "/timeline", label: t("nav.timeline"), icon: CalendarDays, data: "/timeline" },
    { href: "/map", label: t("browse.places"), icon: MapPin },
    { href: "/collections", label: t("nav.collections"), icon: FolderHeart, data: "/collections" },
  ];
  return (
    <div className="-mx-4 flex snap-x gap-2.5 overflow-x-auto px-4 pb-1 no-scrollbar sm:mx-0 sm:grid sm:grid-cols-4 sm:overflow-visible sm:px-0 lg:grid-cols-8">
      {tiles.map(({ href, label, icon: Icon, count, data }) => (
        <Spotlight key={href} className="w-[6.5rem] shrink-0 snap-start rounded-2xl sm:w-auto">
        <Link href={href} onMouseEnter={() => data && prefetch(data)} onTouchStart={() => data && prefetch(data)}
          className="tap group flex h-full flex-col gap-2.5 rounded-2xl border border-paper-line bg-paper-card/70 p-3 shadow-soft transition-all hover:-translate-y-0.5 hover:border-iris/30 hover:shadow-lift">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-paper shadow-soft transition-all group-hover:scale-105 group-hover:text-iris-soft group-hover:bg-iris"><Icon className="h-[18px] w-[18px]" /></span>
          <span className="min-w-0">
            <span className="block truncate text-[13px] font-semibold leading-tight">{label}</span>
            <span className="block text-[11px] tabular-nums text-ink-mute">{count != null ? <CountUp to={count} /> : " "}</span>
          </span>
        </Link>
        </Spotlight>))}
    </div>
  );
}
