"use client";
import { FolderOpen, Plus } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Empty, Spinner } from "@/components/ui";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Collection } from "@/lib/types";

export default function Collections() {
  const { t } = useI18n();
  const [items, setItems] = useState<Collection[] | null>(null);
  const [name, setName] = useState("");
  const load = () => api.get<{ items: Collection[] }>("/collections").then((r) => setItems(r.items)).catch(() => setItems([]));
  useEffect(() => { load(); }, []);
  const create = async () => { if (!name.trim()) return; await api.post("/collections", { name }); setName(""); load(); };
  return (
    <div className="mx-auto max-w-[1440px] px-4 py-10 sm:px-8 sm:py-14">
      <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div><h1 className="h-page">{t("col.title")}</h1></div>
        <form className="flex w-full min-w-0 gap-2 sm:w-auto" onSubmit={(e) => { e.preventDefault(); create(); }}>
          <input className="input min-w-0 flex-1 sm:!w-60 sm:flex-none" placeholder={t("col.name")} value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn-primary" disabled={!name.trim()}><Plus className="h-4 w-4" strokeWidth={1.5} />{t("col.new")}</button>
        </form>
      </div>
      {!items ? <Spinner /> : items.length === 0 ? <Empty icon={<FolderOpen className="h-6 w-6" strokeWidth={1.25} />} title={t("col.empty")} /> : (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
          {items.map((c) => (
            <Link key={c.id} href={`/collections/${c.id}`} className="group relative block aspect-[4/3] overflow-hidden rounded-sm bg-paper-sunk shadow-lift">
              {c.covers[0]?.thumb_url
                ? <img src={abs(c.covers[0].thumb_url)} alt="" className="absolute inset-0 h-full w-full object-cover transition-[filter] duration-300 group-hover:brightness-110" />
                : <div className="absolute inset-0 flex items-center justify-center text-ink-faint"><FolderOpen className="h-8 w-8" strokeWidth={1} /></div>}
              <div aria-hidden className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/15 to-transparent" />
              <div className="absolute inset-x-0 bottom-0 p-6 text-white">
                <p className="truncate text-[15px] font-medium uppercase tracking-[0.1em]">{c.name}</p>
                
                <p className="mt-3 text-[11px] uppercase tracking-label text-white/70">{c.count} {t("col.items")}</p>
              </div>
            </Link>))}
        </div>)}
    </div>
  );
}
