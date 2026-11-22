"use client";
import { ArrowLeft, Pencil, Trash2, X } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import { Empty, GridSkeleton, PageHeader } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { invalidate, useApi } from "@/lib/swr";
import type { Collection } from "@/lib/types";

export default function CollectionPage() {
  const { id } = useParams<{ id: string }>();
  const { t } = useI18n();
  const router = useRouter();
  const { data: c, error, reload } = useApi<Collection>(`/collections/${id}`);
  const [edit, setEdit] = useState(false); const [name, setName] = useState("");
  const [rm, setRm] = useState(false);
  useEffect(() => { if (error) router.replace("/collections"); }, [error, router]);
  const viewer = useViewer(c?.items || []);
  const done = () => { invalidate("/collections"); return reload(); };
  const rename = async () => { if (name.trim()) { await api.patch(`/collections/${id}`, { name }); setEdit(false); done(); } };
  const del = async () => { if (confirm(t("col.deleteConfirm"))) { await api.del(`/collections/${id}`); invalidate("/collections"); router.replace("/collections"); } };
  const remove = async (assetId: string) => { await api.del(`/collections/${id}/items/${assetId}`); done(); };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
      <Link href="/collections" className="btn-ghost mb-2 -ml-2 !py-1 text-xs max-lg:hidden"><ArrowLeft className="h-3.5 w-3.5" />{t("col.title")}</Link>
      <PageHeader inBar={false}
        title={edit ? (
          <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); rename(); }}><input className="input text-base" autoFocus value={name} onChange={(e) => setName(e.target.value)} /><button className="btn-primary">{t("common.save")}</button></form>
        ) : (c?.name ?? <span className="skeleton inline-block h-8 w-48 rounded-lg" />)}
        count={edit ? null : c?.count ?? null}
        actions={<>
          <button className="btn-outline" onClick={() => { setName(c?.name || ""); setEdit(true); }}><Pencil className="h-4 w-4" />{t("col.rename")}</button>
          <button className={rm ? "btn-primary" : "btn-outline"} onClick={() => setRm((r) => !r)}><X className="h-4 w-4" />{t("col.remove")}</button>
          <button className="btn-outline !text-danger" onClick={del}><Trash2 className="h-4 w-4" />{t("common.delete")}</button>
        </>} />
      {!c ? <GridSkeleton /> : c.items!.length === 0 ? <Empty title={t("lib.noItems")} /> : (
        <div className="masonry">{c.items!.map((a, i) => <AssetTile key={a.asset_id} asset={a} selectMode={rm} onSelect={(x) => remove(x.asset_id)} onOpen={viewer.open} priority={i < 6} />)}</div>)}
      {viewer.node}
    </div>
  );
}
