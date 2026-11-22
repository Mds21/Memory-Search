"use client";
import { FolderOpen, Plus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { CardSkeleton, Empty, PageHeader } from "@/components/ui";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { prefetch, useApi } from "@/lib/swr";
import type { Collection } from "@/lib/types";

export default function Collections() {
  const { t } = useI18n();
  const { data, reload } = useApi<{ items: Collection[] }>("/collections");
  const items = data?.items;
  const [name, setName] = useState("");
  const create = async () => { if (!name.trim()) return; await api.post("/collections", { name }); setName(""); reload(); };
  return (
    <div className="mx-auto max-w-6xl px-4 py-4 sm:px-6 sm:py-8">
      <PageHeader wideActions title={t("col.title")} count={items?.length ?? null} actions={
        <form className="flex w-full gap-2 sm:w-auto" onSubmit={(e) => { e.preventDefault(); create(); }}>
          <input className="input min-w-0 flex-1 sm:!w-56 sm:flex-none" placeholder={t("col.name")} value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn-primary tap shrink-0" disabled={!name.trim()}><Plus className="h-4 w-4" />{t("col.new")}</button>
        </form>} />
      {!items ? <CardSkeleton h={212} /> : items.length === 0 ? <Empty icon={<FolderOpen className="h-7 w-7" />} title={t("col.empty")} /> : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((c, i) => (
            <Link key={c.id} href={`/collections/${c.id}`} onMouseEnter={() => prefetch(`/collections/${c.id}`)} style={{ animationDelay: `${Math.min(i, 8) * 40}ms` }}
              className="card group animate-fade-up overflow-hidden transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lift">
              <div className="grid h-40 grid-cols-[2fr_1fr] grid-rows-2 gap-0.5 overflow-hidden bg-paper-sunk">
                {[0, 1, 2].map((k) => (
                  <div key={k} className={`overflow-hidden ${k === 0 ? "row-span-2" : ""}`}>
                    {c.covers[k]?.thumb_url && <img src={abs(c.covers[k].thumb_url)} alt="" loading="lazy" decoding="async" onLoad={(e) => e.currentTarget.classList.add("loaded")} className="fade h-full w-full object-cover group-hover:scale-105" />}
                  </div>))}
              </div>
              <div className="flex items-center justify-between p-4"><p className="truncate font-medium">{c.name}</p><span className="shrink-0 rounded-full bg-paper-sunk px-2 py-0.5 text-xs tabular-nums text-ink-mute">{c.count} {t("col.items")}</span></div>
            </Link>))}
        </div>)}
    </div>
  );
}
