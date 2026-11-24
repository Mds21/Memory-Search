"use client";
import { ArrowLeft, BookmarkPlus, Check, Play } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import { MOMENT_KIND } from "@/components/MomentCard";
import Slideshow from "@/components/Slideshow";
import { Empty, GridSkeleton, Spinner } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Moment } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

export default function MomentPage() {
  const { t } = useI18n();
  const { toast } = useUploads();
  const id = decodeURIComponent(String(useParams().id));
  const [m, setM] = useState<Moment | null | undefined>(undefined);
  const [show, setShow] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState<string | null>(null);
  const items = m?.items || [];
  const viewer = useViewer(items);

  useEffect(() => { api.get<Moment>(`/moments/${encodeURIComponent(id)}`).then(setM).catch(() => setM(null)); }, [id]);

  const save = async () => {
    setSaving(true);
    try { const r = await api.post<{ collection_id: string }>(`/moments/${encodeURIComponent(id)}/save`); setSaved(r.collection_id); toast(t("mo.saved")); }
    catch (e: any) { toast(e.message, "error"); } finally { setSaving(false); }
  };

  if (m === null) return <div className="mx-auto max-w-[1440px] px-4 py-14 sm:px-8"><Empty title={t("mo.gone")} action={<Link href="/moments" className="btn-outline">{t("mo.all")}</Link>} /></div>;
  const kind = m ? MOMENT_KIND[m.type] || MOMENT_KIND.theme : null;
  const Icon = kind?.icon;
  const cover = m?.cover?.preview_url || m?.cover?.thumb_url;

  return (
    <div>
      <section className="relative isolate overflow-hidden border-b border-paper-line/70 bg-night text-white">
        {cover && <img src={abs(cover)} alt="" aria-hidden className="absolute inset-0 -z-10 h-full w-full scale-110 object-cover opacity-60 blur-2xl" />}
        {cover && <img src={abs(cover)} alt="" aria-hidden className="absolute inset-y-0 right-0 -z-10 hidden h-full w-1/2 object-cover opacity-90 [mask-image:linear-gradient(to_left,black_55%,transparent)] lg:block" />}
        <div aria-hidden className="absolute inset-0 -z-10 bg-gradient-to-r from-black/85 via-black/60 to-black/20" />
        <div className="mx-auto flex min-h-[380px] max-w-[1440px] flex-col justify-end px-4 pb-12 pt-10 sm:px-8">
          <Link href="/moments" className="mb-auto inline-flex w-fit items-center gap-2 text-[11px] font-medium uppercase tracking-label text-white/70 transition-colors hover:text-white">
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={1.5} />{t("mo.all")}</Link>
          {!m ? <Spinner className="h-5 w-5 text-white/70" /> : (<div className="max-w-2xl animate-rise">
            <p className="flex items-center gap-2 text-[11px] font-medium uppercase tracking-label text-white/75">{Icon && <Icon className="h-4 w-4" strokeWidth={1.5} />}{t(kind!.key)}{m.when && <span className="text-white/50"> · {m.when}</span>}</p>
            <h1 className="h-display mt-4 text-[30px] leading-tight sm:text-[44px]">{m.title}</h1>
            <span className="bar mt-4" aria-hidden />
            <p className="mt-4 text-[13px] text-white/75">{m.subtitle}</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <button className="btn-primary" onClick={() => setShow(true)} disabled={!items.length}><Play className="h-4 w-4" strokeWidth={1.5} />{t("mo.play")}</button>
              {saved ? <Link href={`/collections/${saved}`} className="btn btn-pill bg-white/15 text-white hover:bg-white/25"><Check className="h-4 w-4" strokeWidth={1.5} />{t("mo.saved")}</Link>
                : <button className="btn btn-pill bg-white/15 text-white hover:bg-white/25" onClick={save} disabled={saving}>{saving ? <Spinner /> : <BookmarkPlus className="h-4 w-4" strokeWidth={1.5} />}{t("mo.save")}</button>}
            </div>
          </div>)}
        </div>
      </section>

      <div className="mx-auto max-w-[1440px] px-4 py-12 sm:px-8">
        <div className="mb-6"><h2 className="text-[13px] font-medium uppercase tracking-label">{t("mo.inside")}{m && <span className="ml-3 tabular-nums text-ink-faint">{m.count}</span>}</h2><span className="bar mt-2.5" aria-hidden /></div>
        {!m ? <GridSkeleton n={8} /> : <div className="masonry">{items.map((a) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} />)}</div>}
      </div>
      {viewer.node}
      {show && m && <Slideshow items={items} title={m.title} onClose={() => setShow(false)} />}
    </div>
  );
}
