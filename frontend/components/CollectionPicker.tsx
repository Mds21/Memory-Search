"use client";
import { FolderPlus } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Collection } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { Modal, Spinner } from "./ui";

export default function CollectionPicker({ ids, onClose, onDone }: { ids: string[] | null; onClose: () => void; onDone?: () => void }) {
  const { t } = useI18n();
  const { toast } = useUploads();
  const [items, setItems] = useState<Collection[] | null>(null);
  const [name, setName] = useState("");
  useEffect(() => { if (ids) api.get<{ items: Collection[] }>("/collections").then((r) => setItems(r.items)).catch(() => setItems([])); }, [ids]);
  const add = async (cid: string) => { try { await api.post(`/collections/${cid}/items`, { asset_ids: ids }); toast(t("col.added")); onDone?.(); onClose(); } catch (e: any) { toast(e.message, "error"); } };
  const create = async () => { if (!name.trim()) return; const c = await api.post<Collection>("/collections", { name }); await add(c.id); };
  return (
    <Modal open={!!ids} onClose={onClose} title={t("col.choose")}>
      {!items ? <div className="py-6 text-center"><Spinner /></div> : (
        <div className="space-y-2">
          {items.map((c) => <button key={c.id} className="btn-outline w-full !justify-between" onClick={() => add(c.id)}><span className="truncate">{c.name}</span><span className="text-xs text-ink-mute">{c.count}</span></button>)}
          <form className="flex gap-2 pt-2" onSubmit={(e) => { e.preventDefault(); create(); }}>
            <input className="input" placeholder={t("col.name")} value={name} onChange={(e) => setName(e.target.value)} />
            <button className="btn-primary shrink-0" disabled={!name.trim()}><FolderPlus className="h-4 w-4" />{t("col.create")}</button>
          </form>
        </div>)}
    </Modal>
  );
}
