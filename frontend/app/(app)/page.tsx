"use client";
import { Bookmark, CalendarClock, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import AssetTile from "@/components/AssetTile";
import SearchBar from "@/components/SearchBar";
import { Empty, GridSkeleton } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
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
  const { user } = useAuth();
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

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-12">
      <header className="max-w-3xl">
        <h1 className="font-serif text-4xl font-medium leading-[1.1] tracking-[-0.02em] sm:text-5xl">{t("home.title")}</h1>
        <div className="mt-7"><SearchBar large value={q} onChange={setQ} onSubmit={go} placeholder={t("home.placeholder")} autoFocus /></div>
        <ul className="mt-5 divide-y divide-paper-line border-y border-paper-line text-[15px]" aria-label={t("home.try")}>
          {(EXAMPLES[lang] || EXAMPLES.en).map((e) => <li key={e}><button className="flex w-full items-baseline justify-between gap-4 py-2 text-left text-ink-soft hover:text-tide" onClick={() => go(e)}><span className="font-serif">“{e}”</span><span className="shrink-0 font-mono text-xs text-ink-faint">↵</span></button></li>)}
        </ul>
      </header>

      {recent && total === 0 ? (
        <div className="mt-14"><Empty icon={<Upload className="h-8 w-8" />} title={t("home.emptyTitle")} body={t("home.emptyBody")}
          action={<Link href="/uploads" className="btn-primary">{t("home.upload")}</Link>} /></div>
      ) : (<>
        {saved.length > 0 && (
          <section className="mt-12"><h2 className="mb-3 flex items-center gap-2 border-b border-paper-line pb-2 font-serif text-lg font-medium"><Bookmark className="h-4 w-4 text-ink-faint" />{t("home.saved")}</h2>
            <div className="flex flex-wrap gap-2">{saved.map((s) => <button key={s.id} className="chip hover:bg-tide-soft" onClick={() => go(s.query.query || s.name || "")}>{s.name || s.query.query}</button>)}</div></section>)}
        {otd.length > 0 && (
          <section className="mt-10"><h2 className="mb-3 flex items-center gap-2 border-b border-paper-line pb-2 font-serif text-lg font-medium"><CalendarClock className="h-4 w-4 text-ink-faint" />{t("home.onThisDay")}</h2>
            <div className="flex gap-3 overflow-x-auto pb-2">{otd.map((a) => (
              <div key={a.asset_id} className="w-44 shrink-0"><AssetTile asset={a} onOpen={viewer.open} /><p className="mt-1 text-xs text-ink-mute">{a.years_ago} {a.years_ago === 1 ? "year" : "years"} ago</p></div>))}</div></section>)}
        <section className="mt-10"><h2 className="mb-3 border-b border-paper-line pb-2 font-serif text-lg font-medium">{t("home.recent")}</h2>
          {!recent ? <GridSkeleton n={8} /> : <div className="masonry">{recent.map((a) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} />)}</div>}</section>
      </>)}
      {viewer.node}
    </div>
  );
}
