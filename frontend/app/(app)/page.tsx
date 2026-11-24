"use client";
import { ArrowRight, Bookmark, CalendarClock, CornerDownRight, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import SearchBar from "@/components/SearchBar";
import { Empty, GridSkeleton } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api } from "@/lib/api";
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
  const [otd, setOtd] = useState<Asset[]>([]);
  const [saved, setSaved] = useState<SavedSearch[]>([]);
  const go = (v: string) => router.push(`/search?q=${encodeURIComponent(v)}`);

  useEffect(() => {
    api.get<{ items: Asset[]; total: number }>("/assets?limit=12").then((r) => { setRecent(r.items); setTotal(r.total); }).catch(() => setRecent([]));
  }, [tick]);
  useEffect(() => {
    api.get<{ items: Asset[] }>("/on-this-day").then((r) => setOtd(r.items)).catch(() => {});
    api.get<{ items: SavedSearch[] }>("/saved-searches").then((r) => setSaved(r.items)).catch(() => {});
  }, []);
  const all = [...otd, ...(recent || [])];
  const viewer = useViewer(all);

  const Section = ({ title, icon: I, meta, children, href }: { title: string; icon?: any; meta?: React.ReactNode; href?: string; children: React.ReactNode }) => (
    <section className="mt-12">
      <div className="mb-4 flex items-center gap-2">
        {I && <I className="h-4 w-4 text-ink-mute" strokeWidth={1.75} />}
        <h2 className="text-[15px] font-medium">{title}</h2>
        {meta && <span className="font-mono text-xs tabular-nums text-ink-faint">{meta}</span>}
        <span className="flex-1" />
        {href && <Link href={href} className="inline-flex items-center gap-1 text-sm text-ink-mute transition-colors hover:text-ink">{t("nav.library")}<ArrowRight className="h-3.5 w-3.5" strokeWidth={1.75} /></Link>}
      </div>
      {children}
    </section>
  );

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-8 sm:px-8 sm:py-14">
      <header className="max-w-3xl animate-rise">
        <h1 className="font-serif text-[40px] font-medium leading-[1.08] tracking-[-0.02em] sm:text-[52px]">{t("home.title")}</h1>
        <div className="mt-8"><SearchBar large value={q} onChange={setQ} onSubmit={go} placeholder={t("home.placeholder")} autoFocus /></div>
        <ul className="mt-3 flex flex-col" aria-label={t("home.try")}>
          {(EXAMPLES[lang] || EXAMPLES.en).map((e) => (
            <li key={e}><button className="group flex h-10 w-full items-center gap-3 rounded-md px-3 text-left text-sm text-ink-soft transition-colors hover:bg-paper-sunk hover:text-ink" onClick={() => go(e)}>
              <CornerDownRight className="h-4 w-4 shrink-0 text-ink-faint" strokeWidth={1.75} /><span className="flex-1 truncate">{e}</span>
              <span className="kbd opacity-0 transition-opacity group-hover:opacity-100">↵</span></button></li>))}
        </ul>
      </header>

      {recent && total === 0 ? (
        <div className="mt-16"><Empty icon={<Upload className="h-6 w-6" strokeWidth={1.5} />} title={t("home.emptyTitle")} body={t("home.emptyBody")}
          action={<Link href="/uploads" className="btn-primary">{t("home.upload")}</Link>} /></div>
      ) : (<>
        {saved.length > 0 && (
          <Section title={t("home.saved")} icon={Bookmark}>
            <div className="flex flex-wrap gap-2">{saved.map((s) => <button key={s.id} className="chip hover:bg-paper-sunk hover:text-ink" onClick={() => go(s.query.query || s.name || "")}>{s.name || s.query.query}</button>)}</div>
          </Section>)}
        {otd.length > 0 && (
          <Section title={t("home.onThisDay")} icon={CalendarClock}>
            <div className="-mx-1 flex gap-4 overflow-x-auto px-1 pb-2">{otd.map((a) => (
              <div key={a.asset_id} className="w-48 shrink-0"><AssetTile asset={a} onOpen={viewer.open} /><p className="mt-1 font-mono text-[11px] text-ink-faint">{a.years_ago} {a.years_ago === 1 ? "year" : "years"} ago</p></div>))}</div>
          </Section>)}
        <Section title={t("home.recent")} meta={recent ? total.toLocaleString() : undefined} href="/library">
          {!recent ? <GridSkeleton n={8} /> : <div className="masonry">{recent.map((a) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} />)}</div>}
        </Section>
      </>)}
      {viewer.node}
    </div>
  );
}
