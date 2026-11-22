"use client";
import { ArrowLeft, ExternalLink, Sparkles } from "lucide-react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { TypeBadge } from "@/components/AssetTile";
import FileFacts from "@/components/FileFacts";
import { ShareActions } from "@/components/ShareCard";
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
    <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 sm:py-6">
      <button className="btn-ghost mb-3 -ml-2 max-lg:hidden" onClick={() => router.back()}><ArrowLeft className="h-4 w-4" />{t("common.close")}</button>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 flex items-center gap-2"><TypeBadge type={a.file_type} /><span className="truncate text-xs text-ink-mute">{a.title}</span></div>
          <h1 className="h-page line-clamp-2">{a.display_title || a.title}</h1>
          <p className="text-sm text-ink-mute">{[a.doc_label, a.page_count ? `${a.page_count} ${t("doc.pages").toLowerCase()}` : null, a.size_bytes ? fmtBytes(a.size_bytes) : null].filter(Boolean).join(" • ")}</p>
          {a.auto_caption && <p className="mt-2 flex max-w-2xl gap-1.5 text-sm text-ink-soft"><Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-iris" />{a.auto_caption}</p>}
        </div>
        <div className="flex flex-wrap gap-2"><ShareActions asset={a} size="md" />
          <a className="btn-ghost tap" href={abs(a.original_url)} target="_blank" rel="noreferrer"><ExternalLink className="h-4 w-4" />{t("doc.open")}</a></div>
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="card min-h-[60vh] overflow-hidden">
          {isPdf ? <iframe key={page} title={a.title} src={`${abs(a.original_url)}#page=${page}`} className="h-[60dvh] w-full lg:h-[75vh]" />
            : a.thumb_url ? <img src={abs(a.preview_url || a.thumb_url)} alt={a.title} className="w-full" /> : null}
        </div>
        <div className="space-y-4 lg:max-h-[75vh] lg:overflow-y-auto">
          <FileFacts asset={a} />
          {summary && <div className="card border-tide-ring bg-tide-soft p-4"><h2 className="mb-1 text-sm font-semibold text-tide-dark">{t("doc.summary")}</h2><p className="text-sm leading-relaxed">{summary.content}</p></div>}
          {pages.size === 0 && <p className="text-sm text-ink-mute">{t("doc.noText")}</p>}
          {[...pages.entries()].map(([p, texts]) => (
            <article key={p} ref={(n) => { refs.current[p] = n; }} className={`card p-4 ${p === page ? "border-tide ring-1 ring-tide" : ""}`}>
              <button className="mb-2 text-xs font-semibold text-tide-dark hover:underline" onClick={() => setPage(p)}>{t("doc.page")} {p}</button>
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{highlight(texts.join("\n\n"), terms)}</p>
            </article>))}
        </div>
      </div>
    </div>
  );
}
export default function DocPage() { return <Suspense fallback={<div className="p-8"><Spinner /></div>}><DocView /></Suspense>; }
