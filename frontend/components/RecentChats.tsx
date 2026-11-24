"use client";
import { ChevronRight, MessageSquare, Pin } from "lucide-react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import { useApi } from "@/lib/swr";
import type { ChatSummary } from "./ChatHistory";

/** "Continue a chat" on Home: pinned chats first, then the most recent. */
export default function RecentChats() {
  const { t } = useI18n();
  const items = useApi<{ items: ChatSummary[] }>("/conversations").data?.items;
  if (!items?.length) return null;
  return (
    <section className="mt-10 animate-fade-up">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[15px] font-semibold"><MessageSquare className="h-4 w-4 text-iris" />{t("chat.continue")}</h2>
        <Link href="/search" className="btn-ghost !py-1 text-xs">{t("chat.newChat")}<ChevronRight className="h-3.5 w-3.5" /></Link>
      </div>
      <div className="-mx-4 flex snap-x gap-2.5 overflow-x-auto px-4 pb-1 no-scrollbar sm:mx-0 sm:grid sm:grid-cols-3 sm:px-0">
        {items.slice(0, 6).map((c) => (
          <Link key={c.id} href={`/search?c=${c.id}`} className="tap w-64 shrink-0 snap-start rounded-2xl border border-paper-line bg-paper-card p-3.5 shadow-soft transition-all hover:-translate-y-0.5 hover:shadow-lift sm:w-auto">
            <p className="flex items-center gap-1.5 truncate text-sm font-medium">{c.pinned && <Pin className="h-3.5 w-3.5 shrink-0 text-iris" />}<span className="truncate">{c.title || t("chat.untitled")}</span></p>
            <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-ink-mute">{c.preview}</p>
          </Link>))}
      </div>
    </section>
  );
}
