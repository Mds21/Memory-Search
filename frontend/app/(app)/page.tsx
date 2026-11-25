"use client";
import { ArrowRight, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import PhotoWall from "@/components/PhotoWall";
import MomentsRow from "@/components/MomentsRow";
import RecentChats from "@/components/RecentChats";
import SearchBar from "@/components/SearchBar";
import { Empty, GridSkeleton } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api, emptyUnlessOffline } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset, SavedSearch } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

const EXAMPLES: Record<string, string[]> = {
  en: ["photos from last December", "beach videos in Goa", "what does my rental agreement say about the deposit?"],
  hi: ["पिछले दिसंबर की फ़ोटो", "गोवा के वीडियो", "मेरे किराये के अनुबंध में जमा राशि के बारे में क्या लिखा है?"],
  mr: ["गेल्या डिसेंबरचे फोटो", "गोव्यातील व्हिडिओ"],
  ta: ["கடந்த டிசம்பர் புகைப்படங்கள்", "கோவா வீடியோக்கள்"],
  es: ["fotos de diciembre pasado", "vídeos de la playa en Goa", "¿qué dice mi contrato sobre la fianza?"],
};

export default function Home() {
  const { t, lang } = useI18n();
  const { tick } = useUploads();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [recent, setRecent] = useState<Asset[] | null>(null);
  const [total, setTotal] = useState(0);
  const [saved, setSaved] = useState<SavedSearch[]>([]);
  const go = (v: string) => router.push(`/search?q=${encodeURIComponent(v)}`);

  useEffect(() => {
    api.get<{ items: Asset[]; total: number }>("/assets?limit=12").then((r) => { setRecent(r.items); setTotal(r.total); }).catch(emptyUnlessOffline(setRecent));
  }, [tick]);
  useEffect(() => {
    api.get<{ items: SavedSearch[] }>("/saved-searches").then((r) => setSaved(r.items)).catch(() => {});
  }, []);
  const viewer = useViewer(recent || []);  // "On this day" now lives in Moments above

  const Section = ({ title, meta, children, href }: { title: string; meta?: React.ReactNode; href?: string; children: React.ReactNode }) => (
    <section className="mt-16">
      <div className="mb-6 flex items-end gap-4">
        <div>
          <h2 className="text-[13px] font-medium uppercase tracking-label">{title}{meta != null && <span className="ml-3 tabular-nums text-ink-faint">{meta}</span>}</h2>
          <span className="bar mt-2.5" aria-hidden />
        </div>
        <span className="flex-1" />
        {href && <Link href={href} className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-label text-ink-mute transition-colors hover:text-ink">{t("nav.library")}<ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} /></Link>}
      </div>
      {children}
    </section>
  );

  return (
    <div>
      <section className="relative isolate overflow-hidden border-b border-paper-line/70">
        <PhotoWall />
        <div aria-hidden className="absolute inset-0 -z-10 bg-paper/65" />
        <div className="mx-auto flex min-h-[560px] max-w-[1440px] items-center px-4 py-16 sm:min-h-[620px] sm:px-8">
          <div className="w-full max-w-3xl animate-rise rounded border border-paper-line/60 bg-paper/80 p-7 shadow-lift backdrop-blur-md sm:p-12">
            <h1 className="h-display text-[28px] leading-tight sm:text-[42px]">{t("home.title")}</h1>
            <p className="mt-4 max-w-xl text-[14px] leading-relaxed text-ink-soft">{t("auth.tagline")}. {t("home.emptyBody")}</p>
            <div className="mt-8"><SearchBar large value={q} onChange={setQ} onSubmit={go} placeholder={t("home.placeholder")} autoFocus /></div>
            <div className="mt-4 flex flex-wrap gap-x-5 gap-y-2" aria-label={t("home.try")}>
              {(EXAMPLES[lang] || EXAMPLES.en).map((e) => (
                <button key={e} onClick={() => go(e)} className="text-left text-[12px] text-ink-mute underline decoration-paper-line underline-offset-4 transition-colors hover:text-ink hover:decoration-tide">{e}</button>))}
            </div>
            <div className="mt-10 flex flex-wrap gap-3">
              <Link href="/library" className="btn-outline">{t("nav.library")}</Link>
              <Link href="/uploads" className="btn-primary">{t("home.upload")}</Link>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-[1440px] px-4 pb-20 sm:px-8">
        <MomentsRow />
        <RecentChats />
        {recent && total === 0 ? (
          <div className="mt-16"><Empty icon={<Upload className="h-6 w-6" strokeWidth={1.25} />} title={t("home.emptyTitle")} body={t("home.emptyBody")}
            action={<Link href="/uploads" className="btn-primary">{t("home.upload")}</Link>} /></div>
        ) : (<>
          {saved.length > 0 && (
            <Section title={t("home.saved")}>
              <div className="flex flex-wrap gap-2">{saved.map((s) => <button key={s.id} className="chip hover:border-tide/50 hover:text-ink" onClick={() => go(s.query.query || s.name || "")}>{s.name || s.query.query}</button>)}</div>
            </Section>)}
          <Section title={t("home.recent")} meta={recent ? total.toLocaleString() : undefined} href="/library">
            {!recent ? <GridSkeleton n={8} /> : <div className="masonry">{recent.map((a) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} />)}</div>}
          </Section>
        </>)}
      </div>
      {viewer.node}
    </div>
  );
}
