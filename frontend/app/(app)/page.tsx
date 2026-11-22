"use client";
import { ArrowRight, Bookmark, CalendarClock, Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import AssetTile from "@/components/AssetTile";
import BrowseTiles from "@/components/BrowseTiles";
import { Aurora, BlurText, RotatingText } from "@/components/motion";
import RecentChats from "@/components/RecentChats";
import SearchBar from "@/components/SearchBar";
import { Empty, GridSkeleton } from "@/components/ui";
import { useViewer } from "@/components/useViewer";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { useApi } from "@/lib/swr";
import type { Asset, SavedSearch } from "@/lib/types";
import { useUploads } from "@/lib/uploads";

const EXAMPLES: Record<string, string[]> = {
  en: ["share my PAN card", "what is my Aadhaar number?", "beach photos from last December", "the slide about pricing", "how many ID proofs do I have?"],
  hi: ["पिछले दिसंबर की फ़ोटो", "गोवा के वीडियो", "मेरे किराये के अनुबंध में जमा राशि के बारे में क्या लिखा है?"],
  mr: ["गेल्या डिसेंबरचे फोटो", "गोव्यातील व्हिडिओ"],
  ta: ["கடந்த டிசம்பர் புகைப்படங்கள்", "கோவா வீடியோக்கள்"],
  es: ["fotos de diciembre pasado", "vídeos de la playa en Goa", "¿qué dice mi contrato sobre la fianza?"],
};
const NONE: Asset[] = [];

function Section({ icon, title, action, children, delay = 0 }: { icon?: React.ReactNode; title: string; action?: React.ReactNode; children: React.ReactNode; delay?: number }) {
  return (
    <section className="reveal mt-12 animate-fade-up" style={{ animationDelay: `${delay}ms` }}>
      <div className="mb-4 flex items-center justify-between"><h2 className="flex items-center gap-2 text-[15px] font-semibold">{icon && <span className="text-iris">{icon}</span>}{title}</h2>{action}</div>
      {children}
    </section>
  );
}

export default function Home() {
  const { t, lang } = useI18n();
  const { user } = useAuth();
  const { tick } = useUploads();
  const router = useRouter();
  const [q, setQ] = useState("");
  // The three sections load in parallel and each renders as soon as its own data arrives.
  const recent = useApi<{ items: Asset[]; total: number }>("/assets?limit=12", tick);
  const otd = useApi<{ items: Asset[] }>("/on-this-day").data?.items ?? NONE;
  const saved = useApi<{ items: SavedSearch[] }>("/saved-searches").data?.items ?? [];
  const go = (v: string) => { window.dispatchEvent(new CustomEvent("ms:navstart", { detail: "/search" })); router.push(`/search?q=${encodeURIComponent(v)}`); };
  const items = recent.data?.items;
  const viewer = useViewer([...otd, ...(items || [])]);
  const first = user?.display_name?.split(" ")[0];

  return (
    <div className="relative isolate mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-14">
      <Aurora className="h-[30rem]" />
      <header className="mx-auto max-w-2xl animate-fade-up text-center">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-paper-line bg-paper-card/80 px-3 py-1 text-xs font-medium text-ink-soft shadow-soft backdrop-blur">
          <Sparkles className="h-3.5 w-3.5 text-iris" />{first || "Memory Search"}</span>
        <h1 className="mt-3 text-balance text-[1.7rem] font-semibold leading-tight tracking-tight sm:mt-4 sm:text-5xl sm:leading-[1.1]"><BlurText key={lang} text={t("home.title")} className="gradient-words" /></h1>
        <p className="mt-3 hidden text-sm text-ink-mute sm:block">{t("home.try")}: <RotatingText key={lang} items={EXAMPLES[lang] || EXAMPLES.en} className="font-medium text-ink" /></p>
        <div className="glow-ring mt-5 rounded-2xl text-left sm:mt-7"><SearchBar large value={q} onChange={setQ} onSubmit={go} placeholder={t("home.placeholder")} autoFocus /></div>
        <div className="-mx-4 mt-4 flex gap-2 overflow-x-auto px-4 no-scrollbar sm:mx-0 sm:flex-wrap sm:justify-center sm:px-0" aria-label={t("home.try")}>
          {(EXAMPLES[lang] || EXAMPLES.en).map((e) => <button key={e} className="chip tap shrink-0 !py-1.5 hover:border-tide/40 hover:bg-tide-soft hover:text-tide-dark" onClick={() => go(e)}>{e}</button>)}
        </div>
      </header>

      {!(recent.data && recent.data.total === 0) && (
        <section className="reveal mt-9 animate-fade-up sm:mt-12" style={{ animationDelay: "40ms" }}>
          <h2 className="mb-3 text-[15px] font-semibold">{t("browse.title")}</h2>
          <BrowseTiles />
        </section>)}
      <RecentChats />
      {recent.data && recent.data.total === 0 ? (
        <div className="mt-16"><Empty icon={<Upload className="h-7 w-7" />} title={t("home.emptyTitle")} body={t("home.emptyBody")}
          action={<Link href="/uploads" className="btn-primary">{t("home.upload")}</Link>} /></div>
      ) : (<>
        {saved.length > 0 && (
          <Section icon={<Bookmark className="h-4 w-4" />} title={t("home.saved")}>
            <div className="-mx-4 flex gap-2 overflow-x-auto px-4 no-scrollbar sm:mx-0 sm:flex-wrap sm:px-0">{saved.map((s) => <button key={s.id} className="chip tap shrink-0 !py-1.5 hover:border-tide/40 hover:bg-tide-soft hover:text-tide-dark" onClick={() => go(s.query.query || s.name || "")}>{s.name || s.query.query}</button>)}</div>
          </Section>)}
        {otd.length > 0 && (
          <Section icon={<CalendarClock className="h-4 w-4" />} title={t("home.onThisDay")} delay={60}>
            <div className="-mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 no-scrollbar sm:mx-0 sm:px-0">{otd.map((a) => (
              <div key={a.asset_id} className="w-44 shrink-0 snap-start"><AssetTile asset={a} onOpen={viewer.open} />
                <p className="mt-1.5 text-xs font-medium text-ink-mute">{a.years_ago} {a.years_ago === 1 ? "year" : "years"} ago</p></div>))}</div>
          </Section>)}
        <Section title={t("home.recent")} delay={120} action={<Link href="/library" className="btn-ghost !py-1 text-xs">{t("nav.library")}<ArrowRight className="h-3.5 w-3.5" /></Link>}>
          {!items ? <GridSkeleton n={8} /> : <div className="masonry">{items.map((a, i) => <AssetTile key={a.asset_id} asset={a} onOpen={viewer.open} priority={i < 4} />)}</div>}
        </Section>
      </>)}
      {viewer.node}
    </div>
  );
}
