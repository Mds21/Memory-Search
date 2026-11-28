"use client";
import { Bookmark, Check, ChevronUp, Copy, History, LayoutGrid, MessageSquarePlus, RotateCcw, Sparkles, X } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import AssetTile from "@/components/AssetTile";
import ChatComposer from "@/components/ChatComposer";
import ChatFile from "@/components/ChatFile";
import FeedbackButtons from "@/components/FeedbackButtons";
import QueryChips from "@/components/QueryChips";
import { RecentChatsList, useChats } from "@/components/RecentChats";
import RichText from "@/components/RichText";
import { Empty, GridSkeleton, Spinner } from "@/components/ui";
import { assetHref, useViewer } from "@/components/useViewer";
import { api, chatStream, emptyUnlessOffline } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import type { Asset, Citation, Parsed } from "@/lib/types";
import { useUploads } from "@/lib/uploads";
import { termsOf } from "@/lib/util";

interface Msg {
  id: string; role: "user" | "assistant"; text: string; citations?: Citation[]; files?: Asset[]; messageId?: string;
  streaming?: boolean; error?: boolean; suggestions?: string[]; ask?: string;
}

const cleanText = (s: string) => s.replace(/\s*\[(?:the\s+)?library[_ ]overview\]/gi, "");

function Typing() {
  return (
    <span className="inline-flex items-center gap-1 py-2" aria-label="…">
      {[0, 150, 300].map((d) => <span key={d} className="h-1.5 w-1.5 animate-pulse rounded-full bg-ink-mute" style={{ animationDelay: `${d}ms` }} />)}
    </span>);
}

function SearchView() {
  const { t } = useI18n();
  const { user } = useAuth();
  const { toast } = useUploads();
  const params = useSearchParams();
  const router = useRouter();
  const chats = useChats();
  const [showRecent, setShowRecent] = useState(false);
  const [sheet, setSheet] = useState(false);
  const opened = useRef<string | null>(null);
  const [q, setQ] = useState("");
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [results, setResults] = useState<Asset[] | null>(null);
  const [meta, setMeta] = useState<{ total: number; took: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [cid, setCid] = useState<string | null>(null);
  const [starters, setStarters] = useState<string[]>([]);
  const [copied, setCopied] = useState<string | null>(null);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const started = useRef<string | null>(null);
  const lastQuery = useRef("");
  const terms = termsOf(parsed?.semantic_query || q);
  // Everything that can open in the viewer: files shared in the chat plus the latest matches (deduplicated).
  const viewable = [...msgs.flatMap((m) => m.files || []), ...(results || [])].filter((a, i, all) => all.findIndex((b) => b.asset_id === a.asset_id) === i);
  const viewer = useViewer(viewable, parsed?.semantic_query);

  useEffect(() => { api.get<{ items: string[] }>("/chat/starters").then((r) => setStarters(r.items)).catch(() => {}); }, []);

  const send = useCallback(async (text: string) => {
    if (!text.trim() || busy) return;
    lastQuery.current = text;
    const aid = `a${Date.now()}`;
    setMsgs((m) => [...m.map((x) => ({ ...x, suggestions: undefined })), { id: `u${Date.now()}`, role: "user", text },
                    { id: aid, role: "assistant", text: "", streaming: true, ask: text }]);
    setQ(""); setBusy(true);
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
        done: (d) => upd({ streaming: false, citations: d.citations, files: d.files, messageId: d.message_id, suggestions: d.suggestions }),
        error: (e) => upd({ streaming: false, error: true, text: e }),
      }, abort.current.signal);
    } catch (e: any) { if (e.name !== "AbortError") upd({ streaming: false, error: true, text: e.message || t("common.error") }); }
    upd({ streaming: false });
    setBusy(false);
    chats.reload();  // the chat (and its new position) shows up in Recent chats
  }, [busy, cid, t, chats.reload, router]); // eslint-disable-line react-hooks/exhaustive-deps

  const stop = () => { abort.current?.abort(); setBusy(false); setMsgs((ms) => ms.map((m) => (m.streaming ? { ...m, streaming: false } : m))); };

  // A question typed on the home page arrives as ?q=. Start it from a timer so React's dev double-mount (which runs
  // the cleanup below and would abort the request) cancels the timer instead of the request; send each ?q= once.
  useEffect(() => {
    const s = params.get("q");
    if (!s || started.current === s) return;
    const id = setTimeout(() => { started.current = s; send(s); }, 0);
    return () => clearTimeout(id);
  }, [params, send]);
  // Follow the conversation as it streams, without yanking the page (scroll only the chat column).
  useEffect(() => { const el = scroller.current; if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }); }, [msgs]);
  useEffect(() => () => abort.current?.abort(), []);

  /** Reopens a saved chat: every message with its files, and the last search's matches. */
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
  const copy = async (m: Msg) => {
    try { await navigator.clipboard.writeText(cleanText(m.text).replace(/\s*\[\s*S\s*\d+\s*\]/g, "").replace(/\*\*/g, "")); setCopied(m.id); setTimeout(() => setCopied(null), 1500); }
    catch { toast(t("common.error"), "error"); }
  };

  const citeLink = (m: Msg) => (label: string, key: string) => {
    const c = m.citations?.find((x) => x.label === label);
    if (!c) return null; // a citation the answer didn't end up using: hide it
    const res = results?.find((r) => r.asset_id === c.asset_id) || m.files?.find((f) => f.asset_id === c.asset_id);
    const href = res ? assetHref({ ...res, match: res.match ? { ...res.match, page: c.page ?? res.match.page } : ({ page: c.page } as any) }) : cite(c);
    return <Link key={key} href={href} title={c.title} className="mx-0.5 inline-block rounded-md bg-tide-soft px-1.5 align-baseline font-mono text-[11px] font-medium leading-5 text-tide transition-colors hover:bg-tide-ring/40">{label}</Link>;
  };

  const count = meta?.total ?? results?.length ?? 0;
  const firstName = (user?.display_name || "").split(" ")[0];
  const lastAssistant = [...msgs].reverse().find((m) => m.role === "assistant");

  const matches = (
    <>
      {parsed && (
        <div className="mb-6 space-y-3">
          <p className="label">{t("chat.allMatches")}</p>
          <QueryChips parsed={parsed} onChange={applyChips} />
          <div className="flex items-center justify-between font-mono text-xs tabular-nums text-ink-mute">
            <span>{results ? `${count} ${count === 1 ? t("search.matches").replace(/^matches$/, "match") : t("search.matches")}${meta ? ` · ${meta.took} ms` : ""}` : t("search.thinking")}</span>
            <button className="btn-ghost font-sans" onClick={save}><Bookmark className="h-4 w-4" strokeWidth={1.75} />{t("search.save")}</button>
          </div>
        </div>)}
      {results === null ? (parsed || busy ? <GridSkeleton n={8} /> : null)
        : results.length === 0 ? <Empty title={t("search.none")} />
        : <div className="masonry">{results.map((a) => <AssetTile key={a.asset_id} asset={a} terms={terms} onOpen={(x) => { setSheet(false); viewer.open(x); }} />)}</div>}
    </>);

  return (
    <div className="mx-auto grid max-w-[1440px] grid-cols-[minmax(0,1fr)] lg:grid-cols-[minmax(0,42rem)_minmax(0,1fr)] lg:gap-10 lg:px-8 lg:py-8">
      <section aria-label={t("chat.title")}
        className="relative flex h-[calc(100dvh-8rem-env(safe-area-inset-bottom))] min-w-0 flex-col lg:sticky lg:top-24 lg:h-[calc(100vh-8rem)]">
        <div className="flex items-center justify-between gap-3 border-b border-paper-line/70 px-4 py-3 lg:border-0 lg:px-0 lg:pb-5 lg:pt-0">
          <h1 className="text-[13px] font-medium uppercase tracking-label text-ink lg:hidden">{t("chat.title")}</h1>
          <h1 className="h-page hidden lg:block">{t("chat.title")}</h1>
          <div className="flex items-center gap-1">
            <button className={`btn-ghost !h-9 ${showRecent ? "!bg-paper-sunk !text-ink" : ""}`} onClick={() => { setShowRecent((v) => !v); if (!showRecent) chats.reload(); }}
              aria-expanded={showRecent} aria-label={t("chat.recent")} title={t("chat.recent")}>
              <History className="h-4 w-4" strokeWidth={1.75} /><span className="hidden sm:inline">{t("chat.recent")}</span>
              {chats.items?.length ? <span className="tabular-nums text-ink-faint">{chats.items.length}</span> : null}</button>
            {msgs.length > 0 && <button className="btn-ghost !h-9" onClick={reset} aria-label={t("search.new")} title={t("search.new")}>
              <MessageSquarePlus className="h-4 w-4" strokeWidth={1.75} /><span className="hidden sm:inline">{t("search.new")}</span></button>}
          </div>
        </div>
        {showRecent && (
          <div className="absolute inset-x-3 top-14 z-20 animate-rise rounded-xl border border-paper-line bg-paper-card p-2 shadow-lift lg:inset-x-0" role="dialog" aria-label={t("chat.recent")}>
            <div className="mb-1 flex items-center justify-between px-3 pt-1"><p className="label">{t("chat.recent")}</p>
              <button className="btn-ghost !h-8 !w-8 !p-0" onClick={() => setShowRecent(false)} aria-label={t("common.close")}><X className="h-4 w-4" strokeWidth={1.5} /></button></div>
            <div className="max-h-[55vh] overflow-y-auto"><RecentChatsList items={chats.items} activeId={cid} onOpen={openChat} onDelete={removeChat} /></div>
          </div>)}

        <div ref={scroller} className="flex-1 overflow-y-auto overscroll-contain px-4 py-5 lg:px-1" aria-live="polite">
          {msgs.length === 0 ? (
            <div className="mx-auto flex min-h-full max-w-md flex-col justify-end pb-2 lg:justify-center lg:pb-6">
              <span className="mb-5 flex h-11 w-11 items-center justify-center rounded-full bg-tide-soft text-tide"><Sparkles className="h-5 w-5" strokeWidth={1.75} /></span>
              <h2 className="text-2xl font-light uppercase tracking-display text-ink">{firstName ? `${t("chat.hello")}, ${firstName}` : t("chat.hello")}</h2>
              <p className="mt-2 text-[15px] leading-relaxed text-ink-soft sm:text-sm">{t("chat.intro")}</p>
              {starters.length > 0 && (
                <div className="mt-6 flex flex-wrap gap-2 sm:grid sm:grid-cols-2">
                  {starters.map((s) => (
                    <button key={s} onClick={() => send(s)}
                      className="rounded-full border border-paper-line bg-paper-card px-4 py-2 text-left text-[14px] text-ink-soft transition-colors hover:border-tide/50 hover:text-ink active:bg-paper-sunk sm:rounded-xl sm:py-3 sm:text-[13px]">{s}</button>))}
                </div>)}
            </div>
          ) : (
            <div className="space-y-6">
              {msgs.filter((m) => m.role === "user" || m.streaming || m.text || m.error).map((m) => m.role === "user" ? (
                <div key={m.id} className="flex justify-end">
                  <div className="max-w-[85%] whitespace-pre-wrap rounded-[1.25rem] rounded-br-md bg-tide-soft px-4 py-2.5 text-[15px] leading-relaxed text-ink sm:text-[14px]">{m.text}</div>
                </div>
              ) : (
                <div key={m.id} className="flex gap-3">
                  <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-tide-soft text-tide" aria-hidden><Sparkles className="h-3.5 w-3.5" strokeWidth={2} /></span>
                  <div className="min-w-0 flex-1 text-[15px] leading-relaxed text-ink sm:text-[14px]">
                    {m.streaming && !m.text ? <Typing /> : m.error ? (
                      <div className="rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-danger">
                        <p>{m.text || t("common.error")}</p>
                        {m.ask && <button className="btn-ghost -ml-2 mt-1 !h-8 text-danger" onClick={() => send(m.ask!)}><RotateCcw className="h-3.5 w-3.5" />{t("chat.retry")}</button>}
                      </div>
                    ) : <RichText text={cleanText(m.text)} cite={citeLink(m)} />}

                    {m.files && m.files.length > 0 && (
                      <div className="mt-4 space-y-2 rounded-xl border border-paper-line bg-paper-card/60 p-2">
                        <p className="label px-2 pt-1">{t("chat.files")} <span className="tabular-nums text-ink-faint">{m.files.length}</span></p>
                        {m.files.map((f) => {
                          const c = m.citations?.find((x) => x.asset_id === f.asset_id);
                          const file = c?.page ? { ...f, match: { ...(f.match || {}), page: c.page } as Asset["match"] } : f;
                          return <ChatFile key={f.asset_id} asset={file} label={c?.label} onView={viewer.open} />;
                        })}
                      </div>)}

                    {!m.streaming && !m.error && m.text && (
                      <div className="mt-2 flex items-center gap-1 text-ink-mute">
                        <button className="btn-ghost !h-8 !w-8 !p-0" onClick={() => copy(m)} aria-label={t("chat.copy")} title={t("chat.copy")}>
                          {copied === m.id ? <Check className="h-3.5 w-3.5 text-ok" /> : <Copy className="h-3.5 w-3.5" strokeWidth={1.75} />}</button>
                        {m.messageId && <FeedbackButtons messageId={m.messageId} />}
                      </div>)}

                    {m === lastAssistant && !busy && m.suggestions && m.suggestions.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-2" aria-label={t("chat.suggested")}>
                        {m.suggestions.map((s) => (
                          <button key={s} onClick={() => send(s)}
                            className="rounded-full border border-paper-line bg-paper-card px-3.5 py-1.5 text-[13px] text-ink-soft transition-colors hover:border-tide/50 hover:text-ink active:bg-paper-sunk">{s}</button>))}
                      </div>)}
                  </div>
                </div>))}
            </div>)}
        </div>

        <div className="space-y-2 px-3 pb-3 pt-1 lg:px-0 lg:pb-0">
          {results !== null && count > 0 && (
            <button onClick={() => setSheet(true)} className="mx-auto flex items-center gap-2 rounded-full border border-paper-line bg-paper-card px-4 py-1.5 text-[13px] text-ink-soft shadow-soft lg:hidden">
              <LayoutGrid className="h-3.5 w-3.5" strokeWidth={1.75} />{count} {count === 1 ? t("search.matches").replace(/^matches$/, "match") : t("search.matches")}<ChevronUp className="h-3.5 w-3.5" /></button>)}
          <ChatComposer value={q} onChange={setQ} onSend={send} onStop={stop} busy={busy} autoFocus />
        </div>
      </section>

      <section aria-label={t("search.results")} className="hidden min-w-0 lg:block">{matches}</section>

      {sheet && (
        <div className="fixed inset-0 z-50 flex items-end bg-night/60 lg:hidden" role="dialog" aria-modal aria-label={t("chat.allMatches")} onClick={() => setSheet(false)}>
          <div className="max-h-[85dvh] w-full animate-rise overflow-y-auto rounded-t-2xl bg-paper px-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))] pt-3" onClick={(e) => e.stopPropagation()}>
            <div className="sticky top-0 z-10 -mx-4 mb-3 flex items-center justify-between bg-paper px-4 pb-2 pt-1">
              <span className="mx-auto h-1 w-10 rounded-full bg-paper-line" aria-hidden />
              <button className="btn-ghost absolute right-2 top-0 !h-9 !w-9 !p-0" onClick={() => setSheet(false)} aria-label={t("common.close")}><X className="h-4 w-4" /></button>
            </div>
            {matches}
          </div>
        </div>)}
      {viewer.node}
    </div>
  );
}

export default function SearchPage() { return <Suspense fallback={<div className="p-8"><Spinner /></div>}><SearchView /></Suspense>; }
