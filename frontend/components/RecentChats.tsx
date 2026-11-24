"use client";
import { ArrowRight, MessageSquare, Trash2 } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { Spinner } from "./ui";

export interface ChatSummary { id: string; title: string | null; updated_at: string; messages?: number }

/** "2 h ago", "yesterday", "12 Mar". */
export function ago(iso: string, lang = "en") {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : `${iso}Z`);
  const s = (Date.now() - d.getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  if (s < 60) return rtf.format(0, "second");
  if (s < 3600) return rtf.format(-Math.round(s / 60), "minute");
  if (s < 86400) return rtf.format(-Math.round(s / 3600), "hour");
  if (s < 7 * 86400) return rtf.format(-Math.round(s / 86400), "day");
  return d.toLocaleDateString(lang, { day: "numeric", month: "short" });
}

export function useChats() {
  const [items, setItems] = useState<ChatSummary[] | null>(null);
  const reload = useCallback(() => api.get<{ items: ChatSummary[] }>("/conversations").then((r) => setItems(r.items)).catch(() => setItems([])), []);
  useEffect(() => { reload(); }, [reload]);
  const remove = async (id: string) => { setItems((x) => x?.filter((c) => c.id !== id) ?? null); await api.del(`/conversations/${id}`).catch(() => reload()); };
  return { items, reload, remove };
}

/** The list inside the search page's "Recent chats" panel: open one to continue it, or delete it. */
export function RecentChatsList({ items, activeId, onOpen, onDelete }:
  { items: ChatSummary[] | null; activeId: string | null; onOpen: (id: string) => void; onDelete: (id: string) => void }) {
  const { t, lang } = useI18n();
  if (!items) return <div className="flex justify-center py-6"><Spinner className="text-ink-mute" /></div>;
  if (!items.length) return <p className="px-3 py-6 text-center text-[13px] text-ink-mute">{t("chat.none")}</p>;
  return (
    <ul className="space-y-0.5">
      {items.map((c) => (
        <li key={c.id} className={`group flex items-center gap-1 rounded-sm pr-1 transition-colors ${c.id === activeId ? "bg-tide-soft" : "hover:bg-paper-sunk"}`}>
          <button type="button" onClick={() => onOpen(c.id)} className="flex min-w-0 flex-1 items-center gap-3 px-3 py-2.5 text-left">
            <MessageSquare className={`h-4 w-4 shrink-0 ${c.id === activeId ? "text-tide" : "text-ink-mute"}`} strokeWidth={1.5} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium">{c.title || t("chat.untitled")}</span>
              <span className="block text-[11px] uppercase tracking-[0.06em] text-ink-faint">{ago(c.updated_at, lang)}</span>
            </span>
          </button>
          <button type="button" onClick={() => onDelete(c.id)} className="btn-ghost !h-8 !w-8 shrink-0 !p-0 opacity-0 transition-opacity focus:opacity-100 group-hover:opacity-100"
            aria-label={`${t("chat.delete")}: ${c.title || ""}`} title={t("chat.delete")}><Trash2 className="h-3.5 w-3.5" strokeWidth={1.5} /></button>
        </li>))}
    </ul>
  );
}

/** "Recent chats" on Home: pick up a conversation where you left it. */
export default function RecentChats() {
  const { t, lang } = useI18n();
  const { items } = useChats();
  if (!items?.length) return null;
  return (
    <section className="mt-16">
      <div className="mb-6 flex items-end gap-4">
        <div><h2 className="text-[13px] font-medium uppercase tracking-label">{t("chat.recent")}</h2><span className="bar mt-2.5" aria-hidden /></div>
        <span className="flex-1" />
        <Link href="/search" className="inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-label text-ink-mute transition-colors hover:text-ink">{t("search.new")}<ArrowRight className="h-3.5 w-3.5" strokeWidth={1.5} /></Link>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.slice(0, 6).map((c) => (
          <Link key={c.id} href={`/search?c=${c.id}`} className="group flex items-center gap-3 rounded border border-paper-line bg-paper-card px-4 py-3.5 transition-colors hover:border-tide/50">
            <MessageSquare className="h-4 w-4 shrink-0 text-ink-mute transition-colors group-hover:text-tide" strokeWidth={1.5} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium">{c.title || t("chat.untitled")}</span>
              <span className="block text-[11px] uppercase tracking-[0.06em] text-ink-faint">{ago(c.updated_at, lang)}{c.messages ? ` · ${Math.ceil(c.messages / 2)} ${t("chat.turns")}` : ""}</span>
            </span>
          </Link>))}
      </div>
    </section>
  );
}
