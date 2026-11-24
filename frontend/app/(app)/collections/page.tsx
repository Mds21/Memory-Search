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
    <div className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 className="h-page">{t("col.title")}</h1>
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); create(); }}>
          <input className="input !w-56" placeholder={t("col.name")} value={name} onChange={(e) => setName(e.target.value)} />
          <button className="btn-primary" disabled={!name.trim()}><Plus className="h-4 w-4" />{t("col.new")}</button>
        </form>
      </div>
      {!items ? <Spinner /> : items.length === 0 ? <Empty icon={<FolderOpen className="h-8 w-8" />} title={t("col.empty")} /> : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {items.map((c) => (
            <Link key={c.id} href={`/collections/${c.id}`} className="card overflow-hidden transition-shadow hover:shadow-lift">
              <div className="grid h-36 grid-cols-3 gap-0.5 bg-paper-sunk">
                {[0, 1, 2].map((i) => c.covers[i]?.thumb_url ? <img key={i} src={abs(c.covers[i].thumb_url)} alt="" className="h-full w-full object-cover" /> : <div key={i} />)}
              </div>
              <div className="p-3"><p className="truncate font-medium">{c.name}</p><p className="text-xs text-ink-mute">{c.count} {t("col.items")}</p></div>
            </Link>))}
        </div>)}
    </div>
  );
}
