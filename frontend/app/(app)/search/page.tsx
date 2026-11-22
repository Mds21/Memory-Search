"use client";
import { ArrowUpRight, Bookmark, History, MessageSquarePlus, Pin, PinOff, Sparkles } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import AssetTile from "@/components/AssetTile";
import ChatHistory from "@/components/ChatHistory";
import FeedbackButtons from "@/components/FeedbackButtons";
import QueryChips from "@/components/QueryChips";
import SearchBar from "@/components/SearchBar";
import ShareCard from "@/components/ShareCard";
import { Empty, GridSkeleton, Spinner } from "@/components/ui";
import { assetHref, useViewer } from "@/components/useViewer";
import { api, chatStream } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset, Citation, Parsed } from "@/lib/types";
import { invalidate } from "@/lib/swr";
import { useUploads } from "@/lib/uploads";
import { termsOf } from "@/lib/util";

const SUGGEST = ["share my PAN card", "what is my Aadhaar number?", "beach photos", "how many ID proofs do I have?"];

interface Msg { id: string; role: "user" | "assistant"; text: string; citations?: Citation[]; messageId?: string; streaming?: boolean; error?: boolean; primary?: Asset[] }

function SearchView() {
  const { t } = useI18n();
  const { toast } = useUploads();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") || "");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [results, setResults] = useState<Asset[] | null>(null);
  const [meta, setMeta] = useState<{ total: number; took: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cid, setCidState] = useState<string | null>(null);
  const cidRef = useRef<string | null>(null);
  const setCid = (v: string | null) => { cidRef.current = v; setCidState(v); };
  const [pinned, setPinned] = useState(false);
  const [history, setHistory] = useState(false);
  const [loadingChat, setLoadingChat] = useState(false);
  const router = useRouter();
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
    let latest: Asset[] = [];
    try {
      await chatStream({ message: text, conversation_id: cid, ui_language: document.documentElement.lang || "en" }, {
        parsed: (d) => {
          setParsed(d.parsed);
          if (cidRef.current !== d.conversation_id) {  // a new chat: give it its own link so it can be reopened later
            setCid(d.conversation_id); setPinned(false);
            router.replace(`/search?c=${d.conversation_id}`, { scroll: false });
          }
          invalidate("/conversations");
        },
        results: (d) => { latest = d.results; setResults(d.results); setMeta({ total: d.total, took: d.took_ms }); },
        token: (s) => upd((m) => ({ text: m.text + s })),
        done: (d) => upd({ streaming: false, citations: d.citations, messageId: d.message_id, primary: (d.primary || []).map((id) => latest.find((r) => r.asset_id === id)).filter(Boolean) as Asset[] }),
        error: (e) => upd({ streaming: false, error: true, text: e }),
      }, abort.current.signal);
    } catch (e: any) { if (e.name !== "AbortError") upd({ streaming: false, error: true, text: e.message || t("common.error") }); }
    upd({ streaming: false });
    setBusy(false);
  }, [busy, cid, t, router]);

  /** Reopen a saved chat exactly as it was: messages, the results it showed and the files it handed over. */
  const openChat = useCallback(async (id: string) => {
    abort.current?.abort();
    setLoadingChat(true);
    try {
      const c = await api.get<{ id: string; pinned: boolean; assets: Record<string, Asset>; messages: { id: string; role: "user" | "assistant"; content: string;
        parsed_query: Parsed | null; citations: Citation[] | null; result_asset_ids: string[]; primary_ids: string[] }[] }>(`/conversations/${id}`);
      const pick = (ids: string[]) => ids.map((i) => c.assets[i]).filter(Boolean);
      setMsgs(c.messages.map((m) => (m.role === "user" ? { id: m.id, role: "user", text: m.content }
        : { id: m.id, role: "assistant", text: m.content, citations: m.citations || [], messageId: m.id, primary: pick(m.primary_ids) })));
      const last = [...c.messages].reverse().find((m) => m.role === "assistant");
      setResults(last ? pick(last.result_asset_ids) : null);
      setParsed(last?.parsed_query || null);
      setMeta(last ? { total: last.result_asset_ids.length, took: 0 } : null);
      setCid(c.id); setPinned(c.pinned); setBusy(false);
      lastQuery.current = [...c.messages].reverse().find((m) => m.role === "user")?.content || "";
    } catch (e: any) {
      toast(e.message, "error"); router.replace("/search");
    } finally { setLoadingChat(false); }
  }, [router, toast]);

  useEffect(() => { const c = params.get("c"); if (c && c !== cidRef.current) openChat(c); }, [params, openChat]);
  const togglePin = async () => {
    if (!cid) return;
    const r = await api.patch<{ pinned: boolean }>(`/conversations/${cid}`, { pinned: !pinned });
    setPinned(r.pinned); invalidate("/conversations"); toast(r.pinned ? t("chat.pinned") : t("chat.unpinned"));
  };

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
  const reset = () => { abort.current?.abort(); setMsgs([]); setParsed(null); setResults(null); setMeta(null); setCid(null); setPinned(false); setBusy(false); router.replace("/search", { scroll: false }); };
  const cite = (c: Citation) => (c.start_ms != null ? `/media/${c.asset_id}?t=${c.start_ms}` : `/documents/${c.asset_id}${c.page ? `?page=${c.page}` : ""}`);

  const renderText = (m: Msg) => m.text.split(/(\[S\d+\])/g).map((part, i) => {
    const c = m.citations?.find((x) => `[${x.label}]` === part || x.label === part.replace(/[\[\]]/g, ""));
    if (!c) return <span key={i}>{part}</span>;
    const res = results?.find((r) => r.asset_id === c.asset_id);
    const href = res ? assetHref({ ...res, match: res.match ? { ...res.match, page: c.page ?? res.match.page } : ({ page: c.page } as any) }) : cite(c);
    return <Link key={i} href={href} title={c.title} className="mx-0.5 rounded bg-tide-soft px-1 text-xs font-semibold text-tide-dark hover:bg-tide-ring/50">{part.replace(/[\[\]]/g, "")}</Link>;
  });

  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 pb-28 pt-4 sm:px-6 sm:py-8 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:gap-8 lg:pb-8">
      <section className="flex flex-col lg:sticky lg:top-6 lg:h-[calc(100vh-3rem)]" aria-label="Chat">
        <div className="mb-3 flex items-center gap-1"><h1 className="h-page mr-auto max-lg:hidden">{t("nav.search")}</h1>
          <button className="btn-ghost tap max-lg:mr-auto" onClick={() => setHistory(true)}><History className="h-4 w-4" />{t("chat.history")}</button>
          {cid && <button className={`btn-ghost tap !px-2.5 ${pinned ? "!text-iris" : ""}`} onClick={togglePin} aria-label={pinned ? t("chat.unpin") : t("chat.pin")} title={pinned ? t("chat.unpin") : t("chat.pin")}>
            {pinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}</button>}
          {msgs.length > 0 && <button className="btn-ghost tap" onClick={reset}><MessageSquarePlus className="h-4 w-4" /><span className="max-sm:hidden">{t("search.new")}</span></button>}</div>
        {loadingChat && <div className="mb-3 space-y-2"><div className="skeleton ml-auto h-10 w-2/3 rounded-2xl" /><div className="skeleton h-16 w-5/6 rounded-2xl" /></div>}
        <div className="flex-1 space-y-4 pr-1 lg:overflow-y-auto" aria-live="polite">
          {msgs.length === 0 && !loadingChat && (
            <div className="animate-fade-up">
              <Empty icon={<Sparkles className="h-7 w-7" />} title={t("search.empty")} body={t("search.emptyBody")} />
              <div className="-mt-8 flex flex-col gap-2">{SUGGEST.map((s) => (
                <button key={s} onClick={() => send(s)} className="tap flex items-center justify-between rounded-2xl border border-paper-line bg-paper-card px-4 py-3 text-left text-sm shadow-soft hover:border-tide/40">
                  {s}<ArrowUpRight className="h-4 w-4 shrink-0 text-ink-faint" /></button>))}</div>
            </div>)}
          {msgs.map((m) => m.role === "user" ? (
            <div key={m.id} className="ml-8 animate-fade-up rounded-2xl rounded-br-md bg-gradient-to-br from-tide to-iris px-4 py-2.5 text-sm text-paper shadow-soft">{m.text}</div>
          ) : (
            <div key={m.id} className={`mr-4 animate-fade-up rounded-2xl rounded-bl-md border px-4 py-3 text-sm leading-relaxed shadow-soft ${m.error ? "border-danger/30 bg-danger-soft text-danger" : "border-paper-line bg-paper-card"}`}>
              {m.streaming && !m.text ? <span className="inline-flex items-center gap-2 text-ink-mute"><Spinner />{t("search.thinking")}</span> : <p className="whitespace-pre-wrap">{renderText(m)}</p>}
              {m.citations && m.citations.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5 border-t border-paper-line pt-2"><span className="text-xs text-ink-mute">{t("search.sources")}:</span>
                  {m.citations.map((c) => <Link key={c.chunk_id} href={cite(c)} className="chip hover:bg-tide-soft"><b>{c.label.replace(/[\[\]]/g, "")}</b><span className="max-w-[10rem] truncate">{c.title}{c.page ? ` • ${t("search.page")} ${c.page}` : ""}</span></Link>)}</div>)}
              {m.primary?.map((a) => <ShareCard key={a.asset_id} asset={a} />)}
              {m.messageId && <div className="mt-1 flex justify-end"><FeedbackButtons messageId={m.messageId} /></div>}
            </div>))}
          <div ref={endRef} />
        </div>
        <div className="fixed inset-x-3 bottom-[calc(5.9rem+env(safe-area-inset-bottom))] z-20 lg:static lg:mt-3"><SearchBar dropUp value={q} onChange={setQ} onSubmit={send} busy={busy} autoFocus /></div>
      </section>

      <section aria-label={t("search.results")} className="min-w-0">
        {parsed && (
          <div className="mb-4 space-y-3">
            <QueryChips parsed={parsed} onChange={applyChips} />
            <div className="flex items-center justify-between text-sm text-ink-mute">
              <span>{results ? `${meta?.total ?? results.length} ${t("search.matches")}` : t("search.thinking")}</span>
              <button className="btn-ghost" onClick={save}><Bookmark className="h-4 w-4" />{t("search.save")}</button>
            </div>
          </div>)}
        {results === null ? (parsed || busy ? <GridSkeleton n={8} /> : null)
          : results.length === 0 ? <Empty title={t("search.none")} />
          : <div className="masonry animate-fade-in">{results.map((a, i) => <AssetTile key={a.asset_id} asset={a} terms={terms} onOpen={viewer.open} priority={i < 6} />)}</div>}
      </section>
      <ChatHistory open={history} onClose={() => setHistory(false)} current={cid} onOpen={(id) => router.push(`/search?c=${id}`)}
        onDeleted={(id) => { if (id === cid) reset(); }} />
      {viewer.node}
    </div>
  );
}

export default function SearchPage() { return <Suspense fallback={<div className="p-8"><Spinner /></div>}><SearchView /></Suspense>; }
