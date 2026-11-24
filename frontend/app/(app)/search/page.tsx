"use client";
import { Bookmark, MessageSquarePlus, MessagesSquare } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import AssetTile from "@/components/AssetTile";
import FeedbackButtons from "@/components/FeedbackButtons";
import QueryChips from "@/components/QueryChips";
import SearchBar from "@/components/SearchBar";
import { Empty, GridSkeleton, Spinner } from "@/components/ui";
import { assetHref, useViewer } from "@/components/useViewer";
import { api, chatStream } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset, Citation, Parsed } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { termsOf } from "@/lib/util";

interface Msg { id: string; role: "user" | "assistant"; text: string; citations?: Citation[]; messageId?: string; streaming?: boolean; error?: boolean }

function SearchView() {
  const { t } = useI18n();
  const { toast } = useUploads();
  const params = useSearchParams();
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [results, setResults] = useState<Asset[] | null>(null);
  const [meta, setMeta] = useState<{ total: number; took: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cid, setCid] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const lastQuery = useRef("");
  const terms = termsOf(parsed?.semantic_query || q);
  const viewer = useViewer(results || [], parsed?.semantic_query);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || busy) return;
    lastQuery.current = text;
    const aid = `a${Date.now()}`;
    setMsgs((m) => [...m, { id: `u${Date.now()}`, role: "user", text }, { id: aid, role: "assistant", text: "", streaming: true }]);
    setQ(""); setBusy(true); setResults((r) => r ?? null);
    const upd = (p: Partial<Msg> | ((m: Msg) => Partial<Msg>)) => setMsgs((ms) => ms.map((m) => (m.id === aid ? { ...m, ...(typeof p === "function" ? p(m) : p) } : m)));
    abort.current = new AbortController();
    try {
      await chatStream({ message: text, conversation_id: cid, ui_language: document.documentElement.lang || "en" }, {
        parsed: (d) => { setParsed(d.parsed); setCid(d.conversation_id); },
        results: (d) => { setResults(d.results); setMeta({ total: d.total, took: d.took_ms }); },
        token: (s) => upd((m) => ({ text: m.text + s })),
        done: (d) => upd({ streaming: false, citations: d.citations, messageId: d.message_id }),
        error: (e) => upd({ streaming: false, error: true, text: e }),
      }, abort.current.signal);
    } catch (e: any) { if (e.name !== "AbortError") upd({ streaming: false, error: true, text: e.message || t("common.error") }); }
    upd({ streaming: false });
    setBusy(false);
  }, [busy, cid, t]);

  useEffect(() => { const s = params.get("q"); if (s && !started.current) { started.current = true; send(s); } }, [params, send]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);
  useEffect(() => () => abort.current?.abort(), []);

  /** Edited chips re-run retrieval with the structured filters, skipping query parsing. */
  const applyChips = async (p: Parsed) => {
    setParsed(p); setResults(null);
    try { const r = await api.post<{ results: Asset[]; total: number; took_ms: number; parsed: Parsed }>("/search", { parsed: p }); setResults(r.results); setMeta({ total: r.total, took: r.took_ms }); }
    catch (e: any) { toast(e.message, "error"); setResults([]); }
  };
  const save = async () => { try { await api.post("/saved-searches", { name: lastQuery.current.slice(0, 60), query: { query: lastQuery.current, parsed } }); toast(t("search.saved")); } catch (e: any) { toast(e.message, "error"); } };
  const reset = () => { abort.current?.abort(); setMsgs([]); setParsed(null); setResults(null); setMeta(null); setCid(null); setBusy(false); };
  const cite = (c: Citation) => (c.start_ms != null ? `/media/${c.asset_id}?t=${c.start_ms}` : `/documents/${c.asset_id}${c.page ? `?page=${c.page}` : ""}`);

  const renderText = (m: Msg) => m.text.split(/(\[S\d+\])/g).map((part, i) => {
    const c = m.citations?.find((x) => `[${x.label}]` === part || x.label === part.replace(/[\[\]]/g, ""));
    if (!c) return <span key={i}>{part}</span>;
    const res = results?.find((r) => r.asset_id === c.asset_id);
    const href = res ? assetHref({ ...res, match: res.match ? { ...res.match, page: c.page ?? res.match.page } : ({ page: c.page } as any) }) : cite(c);
    return <Link key={i} href={href} title={c.title} className="mx-0.5 rounded-sm bg-tide-soft px-1 font-mono text-[11px] font-medium text-tide transition-colors hover:bg-tide-ring/40">{part.replace(/[\[\]]/g, "")}</Link>;
  });

  return (
    <div className="mx-auto grid max-w-[1440px] gap-8 px-4 py-6 sm:px-8 sm:py-8 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
      <section className="flex min-h-[40vh] flex-col lg:sticky lg:top-8 lg:h-[calc(100vh-4rem)]" aria-label="Chat">
        <div className="mb-4 flex items-center justify-between"><h1 className="h-page">{t("nav.search")}</h1>
          {msgs.length > 0 && <button className="btn-ghost" onClick={reset}><MessageSquarePlus className="h-4 w-4" strokeWidth={1.75} />{t("search.new")}</button>}</div>
        <div className="flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
          {msgs.length === 0 && <Empty icon={<MessagesSquare className="h-6 w-6" strokeWidth={1.5} />} title={t("search.empty")} body={t("home.placeholder")} />}
          {msgs.filter((m) => m.role === "user" || m.streaming || m.text || m.error).map((m) => m.role === "user" ? (
            <div key={m.id} className="ml-auto w-fit max-w-[85%] rounded-xl bg-paper-sunk px-4 py-2.5 text-sm text-ink">{m.text}</div>
          ) : (
            <div key={m.id} className={`mr-2 rounded-xl border px-4 py-3 text-sm leading-relaxed shadow-soft ${m.error ? "border-danger/30 bg-danger-soft text-danger" : "border-paper-line bg-paper-card"}`}>
              {m.streaming && !m.text ? <span className="inline-flex items-center gap-2 text-ink-mute"><Spinner />{t("search.thinking")}</span> : <p className="whitespace-pre-wrap">{renderText(m)}</p>}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-paper-line pt-3"><span className="label mr-1">{t("search.sources")}</span>
                  {m.citations.map((c) => <Link key={c.chunk_id} href={cite(c)} className="chip hover:bg-paper-sunk hover:text-ink"><span className="font-mono text-[11px] text-tide">{c.label.replace(/[\[\]]/g, "")}</span><span className="max-w-[10rem] truncate">{c.title}{c.page ? ` · ${t("search.page")} ${c.page}` : ""}</span></Link>)}</div>)}
              {m.messageId && <div className="mt-1 flex justify-end"><FeedbackButtons messageId={m.messageId} /></div>}
            </div>))}
          <div ref={endRef} />
        </div>
        <div className="mt-3"><SearchBar dropUp value={q} onChange={setQ} onSubmit={send} busy={busy} autoFocus /></div>
      </section>

      <section aria-label={t("search.results")} className="min-w-0">
        {parsed && (
          <div className="mb-6 space-y-3">
            <QueryChips parsed={parsed} onChange={applyChips} />
            <div className="flex items-center justify-between font-mono text-xs tabular-nums text-ink-mute">
              <span>{results ? `${meta?.total ?? results.length} ${(meta?.total ?? results.length) === 1 ? t("search.matches").replace(/^matches$/, "match") : t("search.matches")}${meta ? ` · ${meta.took} ms` : ""}` : t("search.thinking")}</span>
              <button className="btn-ghost font-sans" onClick={save}><Bookmark className="h-4 w-4" strokeWidth={1.75} />{t("search.save")}</button>
            </div>
          </div>)}
        {results === null ? (parsed || busy ? <GridSkeleton n={8} /> : null)
          : results.length === 0 ? <Empty title={t("search.none")} />
          : <div className="masonry">{results.map((a) => <AssetTile key={a.asset_id} asset={a} terms={terms} onOpen={viewer.open} />)}</div>}
      </section>
      {viewer.node}
    </div>
  );
}

export default function SearchPage() { return <Suspense fallback={<div className="p-8"><Spinner /></div>}><SearchView /></Suspense>; }
