"use client";
import { Pencil, Trash2, X } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import { Empty, GridSkeleton } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Collection } from "@/lib/types";

export default function CollectionPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const router = useRouter();
  const [c, setC] = useState<Collection | null>(null);
  const [edit, setEdit] = useState(false); const [name, setName] = useState("");
  const [rm, setRm] = useState(false);
  const load = () => api.get<Collection>(`/collections/${id}`).then(setC).catch(() => router.replace("/collections"));
  useEffect(() => { load(); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  const viewer = useViewer(c?.items || []);
  const rename = async () => { if (name.trim()) { await api.patch(`/collections/${id}`, { name }); setEdit(false); load(); } };
  const del = async () => { if (confirm(t("col.deleteConfirm"))) { await api.del(`/collections/${id}`); router.replace("/collections"); } };
  const remove = async (assetId: string) => { await api.del(`/collections/${id}/items/${assetId}`); load(); };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        {edit ? (
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); rename(); }}><input className="input" autoFocus value={name} onChange={(e) => setName(e.target.value)} /><button className="btn-primary">{t("common.save")}</button></form>
        ) : <h1 className="h-page">{c?.name} <span className="text-base font-normal text-ink-mute">{c?.count}</span></h1>}
        <div className="flex gap-2">
          <button className="btn-outline" onClick={() => { setName(c?.name || ""); setEdit(true); }}><Pencil className="h-4 w-4" />{t("col.rename")}</button>
          <button className={rm ? "btn-primary" : "btn-outline"} onClick={() => setRm((r) => !r)}><X className="h-4 w-4" />{t("col.remove")}</button>
          <button className="btn-outline !text-danger" onClick={del}><Trash2 className="h-4 w-4" />{t("common.delete")}</button>
        </div>
      </div>
      {!c ? <GridSkeleton /> : c.items!.length === 0 ? <Empty title={t("lib.noItems")} /> : (
        <div className="masonry">{c.items!.map((a) => <AssetTile key={a.asset_id} asset={a} selectMode={rm} onSelect={(x) => remove(x.asset_id)} onOpen={viewer.open} />)}</div>)}
      {viewer.node}
    </div>
  );
}
