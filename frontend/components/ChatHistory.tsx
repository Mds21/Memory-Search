"use client";
import { MessageSquare, Pin, PinOff, Trash2 } from "lucide-react";
import { useMemo } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { invalidate, useApi } from "@/lib/swr";
import { useUploads } from "@/lib/uploads";
import { LineSkeleton, Sheet } from "./ui";

export interface ChatSummary { id: string; title: string | null; pinned: boolean; updated_at: string; messages: number; preview: string }
type ListResp = { items: ChatSummary[]; retention_days: number };

const DAY = 86_400_000;
function group(iso: string): "today" | "yesterday" | "week" {
  const d = new Date(iso), now = new Date();
  const start = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  return d.getTime() >= start ? "today" : d.getTime() >= start - DAY ? "yesterday" : "week";
}

/** Saved chats: pinned ones stay; others are cleared automatically after a week without activity. */
export default function ChatHistory({ open, onClose, current, onOpen, onDeleted }: {
  open: boolean; onClose: () => void; current: string | null; onOpen: (id: string) => void; onDeleted: (id: string) => void;
}) {
  const { t, lang } = useI18n();
  const { toast } = useUploads();
  const { data, reload } = useApi<ListResp>(open ? "/conversations" : null);
  const items = data?.items;
  const groups = useMemo(() => {
    const g: Record<string, ChatSummary[]> = { pinned: [], today: [], yesterday: [], week: [] };
    for (const c of items || []) (c.pinned ? g.pinned : g[group(c.updated_at)]).push(c);
    return g;
  }, [items]);

  const pin = async (c: ChatSummary) => {
    await api.patch(`/conversations/${c.id}`, { pinned: !c.pinned });
    toast(c.pinned ? t("chat.unpinned") : t("chat.pinned")); reload();
  };
  const del = async (c: ChatSummary) => {
    if (!confirm(t("chat.deleteConfirm"))) return;
    await api.del(`/conversations/${c.id}`); onDeleted(c.id); reload();
  };
  const clear = async () => {
    if (!confirm(t("chat.clearConfirm"))) return;
    await api.del("/conversations"); invalidate("/conversations"); reload();
    if (current && !items?.find((c) => c.id === current)?.pinned) onDeleted(current);
  };
  const when = (iso: string) => new Date(iso).toLocaleString(lang, group(iso) === "week" ? { weekday: "short", hour: "numeric", minute: "2-digit" } : { hour: "numeric", minute: "2-digit" });

  return (
    <Sheet open={open} onClose={onClose} title={t("chat.history")}>
      <div className="pb-2">
        {!items ? <div className="py-4"><LineSkeleton n={4} /></div> : items.length === 0 ? (
          <div className="flex flex-col items-center py-10 text-center"><MessageSquare className="mb-3 h-8 w-8 text-ink-faint" /><p className="text-sm text-ink-mute">{t("chat.none")}</p></div>
        ) : (["pinned", "today", "yesterday", "week"] as const).map((k) => groups[k].length > 0 && (
          <section key={k} className="mb-4">
            <h3 className="eyebrow mb-1.5 flex items-center gap-1.5">{k === "pinned" && <Pin className="h-3 w-3" />}{t(`chat.sec.${k}`)}</h3>
            <ul className="space-y-1">
              {groups[k].map((c) => (
                <li key={c.id} className={`group flex items-center gap-1 rounded-2xl ${c.id === current ? "bg-tide-soft" : "hover:bg-paper-sunk"}`}>
                  <button onClick={() => { onOpen(c.id); onClose(); }} className="tap min-w-0 flex-1 px-3 py-2.5 text-left">
                    <p className={`truncate text-sm font-medium ${c.id === current ? "text-tide-dark" : ""}`}>{c.title || t("chat.untitled")}</p>
                    <p className="truncate text-xs text-ink-mute">{when(c.updated_at)}{c.preview ? ` · ${c.preview}` : ""}</p>
                  </button>
                  <button onClick={() => pin(c)} className={`tap rounded-xl p-2.5 ${c.pinned ? "text-iris" : "text-ink-faint hover:text-ink"}`} aria-label={c.pinned ? t("chat.unpin") : t("chat.pin")} title={c.pinned ? t("chat.unpin") : t("chat.pin")}>
                    {c.pinned ? <PinOff className="h-4 w-4" /> : <Pin className="h-4 w-4" />}</button>
                  <button onClick={() => del(c)} className="tap mr-1 rounded-xl p-2.5 text-ink-faint hover:text-danger" aria-label={t("chat.delete")} title={t("chat.delete")}><Trash2 className="h-4 w-4" /></button>
                </li>))}
            </ul>
          </section>))}
        <div className="mt-2 flex items-center justify-between gap-3 border-t border-paper-line pt-3">
          <p className="text-xs text-ink-mute">{t("chat.retention", { n: data?.retention_days ?? 7 })}</p>
          {items && items.some((c) => !c.pinned) && <button className="btn-ghost shrink-0 !px-2 !py-1 text-xs !text-danger" onClick={clear}>{t("chat.clear")}</button>}
        </div>
      </div>
    </Sheet>
  );
}
