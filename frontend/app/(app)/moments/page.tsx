"use client";
import { Sparkles } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import MomentCard from "@/components/MomentCard";
import { Empty } from "@/components/ui";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Moment } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

const GROUPS: Record<string, string[]> = {
  "mo.groupTrips": ["trip", "event", "place"],
  "mo.groupTime": ["on_this_day", "month", "year", "archive", "recent"],
  "mo.groupThemes": ["theme", "videos"],
  "mo.groupDocs": ["documents"],
};

export default function MomentsPage() {
  const { t } = useI18n();
  const { tick } = useUploads();
  const [items, setItems] = useState<Moment[] | null>(null);
  const [group, setGroup] = useState("");
  useEffect(() => { api.get<{ items: Moment[] }>("/moments").then((r) => setItems(r.items)).catch(() => setItems([])); }, [tick]);

  const groups = Object.entries(GROUPS).filter(([, types]) => items?.some((m) => types.includes(m.type)));
  const shown = (items || []).filter((m) => !group || GROUPS[group].includes(m.type));
  const [feature, ...rest] = shown;

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-10 sm:px-8 sm:py-14">
      <div className="mb-8"><h1 className="h-page">{t("mo.title")} {items && <span className="ml-2 text-[14px] tabular-nums tracking-normal text-ink-faint">{items.length}</span>}</h1></div>
      {items && groups.length > 1 && (
        <div className="mb-8 flex flex-wrap gap-6 border-b border-paper-line pb-4" role="tablist">
          {[["", "lib.all"], ...groups.map(([k]) => [k, k])].map(([k, label]) => (
            <button key={k} role="tab" aria-selected={group === k} className={`tab ${group === k ? "tab-on" : ""}`} onClick={() => setGroup(k)}>{t(label)}</button>))}
        </div>)}
      {!items ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton aspect-[4/5] rounded-sm" />)}</div>
      ) : !items.length ? (
        <Empty icon={<Sparkles className="h-6 w-6" strokeWidth={1.25} />} title={t("mo.title")} body={t("mo.empty")}
          action={<Link href="/uploads" className="btn-primary">{t("home.upload")}</Link>} />
      ) : (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          {feature && <div className="sm:col-span-2"><MomentCard m={feature} size="wide" /></div>}
          {rest.map((m) => <MomentCard key={m.id} m={m} size="grid" />)}
        </div>)}
    </div>
  );
}
