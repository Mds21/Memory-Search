"use client";
import { BadgeCheck, ChevronRight, Copy, Info } from "lucide-react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { monthHref, searchHref } from "@/lib/share";
import type { Asset, Fact } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { fmtBytes, fmtDate, fmtDuration } from "./ui";

type Row = Fact & { href?: string };

/** Plain-language summary of what was recognised in a file. Details link onward: same person, same place, same month. */
export default function FileFacts({ asset: a }: { asset: Asset }) {
  const { t, lang } = useI18n();
  const { toast } = useUploads();
  const facts: Row[] = (a.facts || []).filter((f) => f.key !== "holder")
    .map((f) => (f.key === "father_name" || f.key === "relative" ? { ...f, href: searchHref(f.value) } : f));
  const about: Row[] = [
    ...(a.details || []).map((d): Row => {
      if (d.key === "place") return { ...d, href: searchHref(`photos in ${d.value.split(",")[0]}`) };
      if (d.key === "taken_on" || d.key === "created") return { ...d, href: monthHref(a.taken_at) };
      if (d.key === "scene") return { ...d, href: searchHref(`${d.value.split(",")[0].toLowerCase()} photos`) };
      return d;
    }),
    ...(a.duration_ms ? [{ key: "length", label: "Length", value: fmtDuration(a.duration_ms) }] : []),
    ...(!a.details?.some((d) => d.key === "taken_on" || d.key === "created") && a.taken_at
      ? [{ key: "date", label: "Date", value: fmtDate(a.taken_at, lang), href: monthHref(a.taken_at) }] : []),
    ...(a.size_bytes ? [{ key: "size", label: "Size", value: fmtBytes(a.size_bytes) }] : []),
  ];
  const copy = (v: string) => navigator.clipboard?.writeText(v).then(() => toast(t("share.copiedText"))).catch(() => {});

  return (
    <div className="card space-y-4 p-4">
      {(a.doc_label || a.people?.length || facts.length > 0) && (
        <section>
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><BadgeCheck className="h-4 w-4 text-iris" />{t("about.title")}</h2>
          <dl className="divide-y divide-paper-line/70 text-sm">
            {a.doc_label && <Item label={t("about.type")} value={a.doc_label} href={searchHref(`all my ${a.doc_label}s`)} />}
            {a.people?.[0] && <Item label={t("about.belongs")} value={a.people[0]} href={searchHref(a.people[0].split(" ")[0])} />}
            {facts.map((f) => <Item key={f.key} label={f.label} value={f.value} href={f.href} onCopy={() => copy(f.value)} />)}
          </dl>
        </section>)}
      <section>
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold"><Info className="h-4 w-4 text-ink-mute" />{t("about.file")}</h2>
        {about.length ? <dl className="divide-y divide-paper-line/70 text-sm">{about.map((f) => <Item key={f.key} label={f.label} value={f.value} href={f.href} />)}</dl>
          : <p className="text-sm text-ink-mute">{t("about.none")}</p>}
      </section>
      {a.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-t border-paper-line/70 pt-3">
          {a.tags.slice(0, 12).map((tg) => <Link key={tg} href={searchHref(tg)} className="chip tap hover:border-tide/40 hover:bg-tide-soft hover:text-tide-dark">#{tg}</Link>)}
        </div>)}
    </div>
  );
}

function Item({ label, value, href, onCopy }: { label: string; value: string; href?: string; onCopy?: () => void }) {
  const body = (<>
    <dt className="text-ink-mute">{label}</dt>
    <dd className="flex min-w-0 items-center justify-between gap-1 break-words font-medium">
      <span className="min-w-0">{value}</span>
      {href ? <ChevronRight className="h-4 w-4 shrink-0 text-ink-faint" />
        : onCopy && <button onClick={onCopy} className="shrink-0 rounded-lg p-1.5 text-ink-faint hover:text-ink" aria-label={`Copy ${label}`}><Copy className="h-3.5 w-3.5" /></button>}
    </dd>
  </>);
  const cls = "grid min-h-[2.75rem] grid-cols-[7.5rem_1fr] items-center gap-2 py-1.5";
  return href ? <Link href={href} className={`${cls} tap -mx-2 rounded-xl px-2 hover:bg-paper-sunk`}>{body}</Link> : <div className={cls}>{body}</div>;
}
