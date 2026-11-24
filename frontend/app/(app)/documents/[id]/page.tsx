"use client";
import DownloadMenu from "@/components/DownloadMenu";
import { ArrowLeft, ExternalLink } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Spinner, fmtBytes } from "@/components/ui";
import { abs, api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset } from "@/lib/types";
import { highlight, termsOf } from "@/lib/util";

interface Chunk { id: string; type: string; page: number | null; content: string; is_summary: boolean }

function DocView() {
  const { id } = useParams<{ id: string }>();
  const sp = useSearchParams();
  const router = useRouter();
  const { t } = useI18n();
  const [a, setA] = useState<Asset | null>(null);
  const [chunks, setChunks] = useState<Chunk[]>([]);
  const [page, setPage] = useState(Number(sp.get("page")) || 1);
  const terms = termsOf(sp.get("q") || "");
  const refs = useRef<Record<number, HTMLElement | null>>({});

  useEffect(() => { api.get<Asset>(`/assets/${id}`).then(setA); api.get<{ items: Chunk[] }>(`/assets/${id}/chunks`).then((r) => setChunks(r.items)); }, [id]);
  useEffect(() => { refs.current[page]?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [page, chunks.length]);
  if (!a) return <div className="p-8"><Spinner /></div>;

  const isPdf = a.mime_type === "application/pdf";
  const summary = chunks.find((c) => c.is_summary);
  const body = chunks.filter((c) => !c.is_summary);
  const pages = new Map<number, string[]>();
  body.forEach((c) => { const p = c.page ?? 1; pages.set(p, [...(pages.get(p) || []), c.content]); });

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-10 sm:px-8 sm:py-14">
      <button className="btn-ghost mb-3 -ml-2" onClick={() => router.back()}><ArrowLeft className="h-4 w-4" />{t("common.close")}</button>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0"><h1 className="h-page truncate">{a.title}</h1><p className="text-sm text-ink-mute">{[a.page_count ? `${a.page_count} ${t("doc.pages").toLowerCase()}` : null, a.size_bytes ? fmtBytes(a.size_bytes) : null, a.language].filter(Boolean).join(" • ")}</p></div>
        <div className="flex gap-2"><a className="btn-outline" href={abs(a.original_url)} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />{t("doc.open")}</a><DownloadMenu asset={a} tone="outline" /></div>
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="card min-h-[60vh] overflow-hidden">
          {isPdf ? <iframe key={page} title={a.title} src={`${abs(a.original_url)}#page=${page}`} className="h-[75vh] w-full" />
            : a.thumb_url ? <img src={abs(a.preview_url || a.thumb_url)} alt={a.title} className="w-full" /> : null}
        </div>
        <div className="max-h-[75vh] space-y-4 overflow-y-auto">
          {summary && <div className="card border-tide-ring bg-tide-soft p-4"><h2 className="mb-1 text-sm font-medium text-tide">{t("doc.summary")}</h2><p className="text-sm leading-relaxed">{summary.content}</p></div>}
          {pages.size === 0 && <p className="text-sm text-ink-mute">{t("doc.noText")}</p>}
          {[...pages.entries()].map(([p, texts]) => (
            <article key={p} ref={(n) => { refs.current[p] = n; }} className={`card p-4 ${p === page ? "border-tide ring-1 ring-tide" : ""}`}>
              <button className="mb-2 font-mono text-xs text-tide hover:underline" onClick={() => setPage(p)}>{t("doc.page")} {p}</button>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{highlight(texts.join("\n\n"), terms)}</p>
            </article>))}
        </div>
      </div>
    </div>
  );
}
export default function DocPage() { return <Suspense fallback={<div className="p-8"><Spinner /></div>}><DocView /></Suspense>; }
