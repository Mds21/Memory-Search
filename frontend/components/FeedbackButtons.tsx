"use client";
import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import { useUploads } from "@/lib/uploads";

export default function FeedbackButtons({ messageId }: { messageId: string }) {
  const { t } = useI18n();
  const { toast } = useUploads();
  const [v, setV] = useState(0);
  const send = async (value: 1 | -1) => { setV(value); try { await api.post("/feedback", { value, message_id: messageId }); toast(t("search.thanks")); } catch { setV(0); } };
  return (
    <div className="flex gap-1">
      <button className={`btn-ghost !p-1.5 ${v === 1 ? "!text-tide" : ""}`} onClick={() => send(1)} aria-label={t("search.helpful")} title={t("search.helpful")}><ThumbsUp className="h-3.5 w-3.5" /></button>
      <button className={`btn-ghost !p-1.5 ${v === -1 ? "!text-danger" : ""}`} onClick={() => send(-1)} aria-label={t("search.notHelpful")} title={t("search.notHelpful")}><ThumbsDown className="h-3.5 w-3.5" /></button>
    </div>
  );
}
