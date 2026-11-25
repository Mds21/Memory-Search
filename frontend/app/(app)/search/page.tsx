"use client";
import { Bookmark, History, MessageSquarePlus, MessagesSquare, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import AssetTile from "@/components/AssetTile";
import ChatFile from "@/components/ChatFile";
import FeedbackButtons from "@/components/FeedbackButtons";
import QueryChips from "@/components/QueryChips";
import { RecentChatsList, useChats } from "@/components/RecentChats";
import SearchBar from "@/components/SearchBar";
import { Empty, GridSkeleton, Spinner } from "@/components/ui";
import { assetHref, useViewer } from "@/components/useViewer";
import { api, chatStream, emptyUnlessOffline } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import type { Asset, Citation, Parsed } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { termsOf } from "@/lib/util";

interface Msg { id: string; role: "user" | "assistant"; text: string; citations?: Citation[]; files?: Asset[]; messageId?: string; streaming?: boolean; error?: boolean }

function SearchView() {
  const { t } = useI18n();
  const { toast } = useUploads();
  const params = useSearchParams();
  const router = useRouter();
  const chats = useChats();
  const [showRecent, setShowRecent] = useState(false);
  const opened = useRef<string | null>(null);
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [results, setResults] = useState<Asset[] | null>(null);
  const [meta, setMeta] = useState<{ total: number; took: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cid, setCid] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const started = useRef<string | null>(null);
  const lastQuery = useRef("");
  const terms = termsOf(parsed?.semantic_query || q);
  // Everything that can open in the viewer: files shared in the chat plus the latest matches (deduplicated).
  const viewable = [...msgs.flatMap((m) => m.files || []), ...(results || [])].filter((a, i, all) => all.findIndex((b) => b.asset_id === a.asset_id) === i);
  const viewer = useViewer(viewable, parsed?.semantic_query);

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
        parsed: (d) => {
          if (d.parsed) setParsed(d.parsed);  // small talk keeps the last search
          setCid(d.conversation_id); opened.current = d.conversation_id;
          // The address now names the chat, so reloading or coming back reopens it instead of asking ?q= again.
          if (new URLSearchParams(window.location.search).get("c") !== d.conversation_id) router.replace(`/search?c=${d.conversation_id}`, { scroll: false });
        },
        results: (d) => { setResults(d.results); setMeta({ total: d.total, took: d.took_ms }); },
        token: (s) => upd((m) => ({ text: m.text + s })),
        done: (d) => upd({ streaming: false, citations: d.citations, files: d.files, messageId: d.message_id }),
        error: (e) => upd({ streaming: false, error: true, text: e }),
      }, abort.current.signal);
    } catch (e: any) { if (e.name !== "AbortError") upd({ streaming: false, error: true, text: e.message || t("common.error") }); }
    upd({ streaming: false });
    setBusy(false);
    chats.reload();  // the chat (and its new position) shows up in Recent chats
  }, [busy, cid, t, chats.reload, router]); // eslint-disable-line react-hooks/exhaustive-deps

  // A question typed on the home page arrives as ?q=. Start it from a timer so React's dev double-mount (which runs
  // the cleanup below and would abort the request) cancels the timer instead of the request; send each ?q= once.
  useEffect(() => {
    const s = params.get("q");
    if (!s || started.current === s) return;
    const id = setTimeout(() => { started.current = s; send(s); }, 0);
    return () => clearTimeout(id);
  }, [params, send]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);
  useEffect(() => () => abort.current?.abort(), []);

  /** Reopens a saved chat: every message with its files, and the last search's matches on the right. */
  const openChat = useCallback(async (id: string) => {
    abort.current?.abort(); setBusy(false); setShowRecent(false); opened.current = id;
    try {
      const c = await api.get<{ id: string; messages: { id: string; role: "user" | "assistant"; content: string; citations: Citation[] | null; files?: Asset[]; parsed_query: Parsed | null }[] }>(`/conversations/${id}`);
      setMsgs(c.messages.map((m) => ({ id: m.id, role: m.role, text: m.content, citations: m.citations || undefined, files: m.files,
                                        messageId: m.role === "assistant" ? m.id : undefined })));
      setCid(c.id);
      const last = [...c.messages].reverse().find((m) => m.parsed_query)?.parsed_query || null;
      setParsed(last); setResults(null); setMeta(null);
      if (last) api.post<{ results: Asset[]; total: number; took_ms: number }>("/search", { parsed: last })
        .then((r) => { setResults(r.results); setMeta({ total: r.total, took: r.took_ms }); }).catch(emptyUnlessOffline(setResults));
      if (params.get("c") !== id) router.replace(`/search?c=${id}`, { scroll: false });
    } catch (e: any) { toast(e.message, "error"); }
  }, [params, router, toast]);
  useEffect(() => { const c = params.get("c"); if (c && opened.current !== c && c !== cid) openChat(c); }, [params, cid, openChat]);

  /** Edited chips re-run retrieval with the structured filters, skipping query parsing. */
  const applyChips = async (p: Parsed) => {
    setParsed(p); setResults(null);
    try { const r = await api.post<{ results: Asset[]; total: number; took_ms: number; parsed: Parsed }>("/search", { parsed: p }); setResults(r.results); setMeta({ total: r.total, took: r.took_ms }); }
    catch (e: any) { toast(e.message, "error"); setResults([]); }
  };
  const save = async () => { try { await api.post("/saved-searches", { name: lastQuery.current.slice(0, 60), query: { query: lastQuery.current, parsed } }); toast(t("search.saved")); } catch (e: any) { toast(e.message, "error"); } };
  const reset = () => { abort.current?.abort(); setMsgs([]); setParsed(null); setResults(null); setMeta(null); setCid(null); setBusy(false); opened.current = null; setShowRecent(false); if (params.get("c") || params.get("q")) router.replace("/search", { scroll: false }); };
  const removeChat = async (id: string) => { await chats.remove(id); if (id === cid) reset(); };
  const cite = (c: Citation) => (c.start_ms != null ? `/media/${c.asset_id}?t=${c.start_ms}` : `/documents/${c.asset_id}${c.page ? `?page=${c.page}` : ""}`);

  // Citations look like [S1]; some models write [ S1 ] with (thin) spaces, so match loosely.
  const renderText = (m: Msg) => m.text.replace(/\s*\[(?:the\s+)?library[_ ]overview\]/gi, "").split(/(\[\s*S\s*\d+\s*\])/g).map((part, i) => {
    const label = /^\[\s*S\s*\d+\s*\]$/.test(part) ? part.replace(/[\[\]\s]/g, "") : null;
    const c = label ? m.citations?.find((x) => x.label === label) : undefined;
    if (!c) return <span key={i}>{part}</span>;
    const res = results?.find((r) => r.asset_id === c.asset_id);
    const href = res ? assetHref({ ...res, match: res.match ? { ...res.match, page: c.page ?? res.match.page } : ({ page: c.page } as any) }) : cite(c);
    return <Link key={i} href={href} title={c.title} className="mx-0.5 rounded-sm bg-tide-soft px-1 font-mono text-[11px] font-medium text-tide transition-colors hover:bg-tide-ring/40">{label}</Link>;
  });

  return (
    <div className="mx-auto grid max-w-[1440px] grid-cols-[minmax(0,1fr)] gap-10 px-4 py-10 sm:px-8 sm:py-12 lg:grid-cols-[minmax(0,38rem)_minmax(0,1fr)]">
      <section className="relative flex min-h-[40vh] min-w-0 flex-col lg:sticky lg:top-24 lg:h-[calc(100vh-8rem)]" aria-label="Chat">
        <div className="mb-6 flex flex-wrap items-start justify-between gap-3"><h1 className="h-page">{t("nav.search")}</h1>
          <div className="flex items-center gap-1">
            <button className={`btn-ghost ${showRecent ? "!bg-paper-sunk !text-ink" : ""}`} onClick={() => { setShowRecent((v) => !v); if (!showRecent) chats.reload(); }} aria-expanded={showRecent} aria-label={t("chat.recent")} title={t("chat.recent")}>
              <History className="h-4 w-4" strokeWidth={1.75} /><span className="hidden sm:inline">{t("chat.recent")}</span>{chats.items?.length ? <span className="tabular-nums text-ink-faint">{chats.items.length}</span> : null}</button>
            {msgs.length > 0 && <button className="btn-ghost" onClick={reset} aria-label={t("search.new")} title={t("search.new")}><MessageSquarePlus className="h-4 w-4" strokeWidth={1.75} /><span className="hidden sm:inline">{t("search.new")}</span></button>}
          </div></div>
        {showRecent && (
          <div className="absolute inset-x-0 top-14 z-20 animate-rise rounded border border-paper-line bg-paper-card p-2 shadow-lift" role="dialog" aria-label={t("chat.recent")}>
            <div className="mb-1 flex items-center justify-between px-3 pt-1"><p className="label">{t("chat.recent")}</p>
              <button className="btn-ghost !h-7 !w-7 !p-0" onClick={() => setShowRecent(false)} aria-label={t("common.close")}><X className="h-4 w-4" strokeWidth={1.5} /></button></div>
            <div className="max-h-[55vh] overflow-y-auto"><RecentChatsList items={chats.items} activeId={cid} onOpen={openChat} onDelete={removeChat} /></div>
          </div>)}
        <div className="flex-1 space-y-4 overflow-y-auto pr-1" aria-live="polite">
          {msgs.length === 0 && <Empty icon={<MessagesSquare className="h-6 w-6" strokeWidth={1.5} />} title={t("search.empty")} body={t("home.placeholder")} />}
          {msgs.filter((m) => m.role === "user" || m.streaming || m.text || m.error).map((m) => m.role === "user" ? (
            <div key={m.id} className="ml-auto w-fit max-w-[85%] rounded-2xl rounded-br-sm bg-tide-soft px-4 py-2.5 text-[13px] text-ink">{m.text}</div>
          ) : (
            <div key={m.id} className={`mr-2 rounded border px-5 py-4 text-[13px] leading-relaxed ${m.error ? "border-danger/30 bg-danger-soft text-danger" : "border-paper-line bg-paper-card"}`}>
              {m.streaming && !m.text ? <span className="inline-flex items-center gap-2 text-ink-mute"><Spinner />{t("search.thinking")}</span> : <p className="whitespace-pre-wrap">{renderText(m)}</p>}
              {m.files && m.files.length > 0 ? (
                <div className="mt-4 space-y-2 border-t border-paper-line pt-4">
                  <p className="label">{t("chat.files")} <span className="tabular-nums text-ink-faint">{m.files.length}</span></p>
                  {m.files.map((f) => {
                    const c = m.citations?.find((x) => x.asset_id === f.asset_id);
                    const file = c?.page ? { ...f, match: { ...(f.match || {}), page: c.page } as Asset["match"] } : f;
                    return <ChatFile key={f.asset_id} asset={file} label={c?.label} onView={viewer.open} />;
                  })}
                </div>
              ) : m.citations && m.citations.length > 0 && (
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
            <p className="label">{t("chat.allMatches")}</p>
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
