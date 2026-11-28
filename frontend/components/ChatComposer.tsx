"use client";
import { ArrowUp, Square } from "lucide-react";
import { useEffect, useRef } from "react";
import { useI18n } from "@/lib/i18n";

interface Props { value: string; onChange: (v: string) => void; onSend: (v: string) => void; onStop?: () => void; busy?: boolean; autoFocus?: boolean }

/** The chat's message box: grows with the text (up to ~6 lines), Enter sends, Shift+Enter starts a new line, and while
 *  an answer streams the send button becomes Stop. 16 px text on phones so iOS doesn't zoom in on focus. */
export default function ChatComposer({ value, onChange, onSend, onStop, busy, autoFocus }: Props) {
  const { t } = useI18n();
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const f = () => ref.current?.focus();
    window.addEventListener("smriti:focus-search", f);
    if (autoFocus && window.matchMedia("(pointer: fine)").matches) ref.current?.focus(); // phones: don't pop the keyboard
    return () => window.removeEventListener("smriti:focus-search", f);
  }, [autoFocus]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [value]);

  const send = () => { if (value.trim() && !busy) onSend(value.trim()); };

  return (
    <form onSubmit={(e) => { e.preventDefault(); send(); }}
      className="flex items-end gap-2 rounded-[1.6rem] border border-paper-line bg-paper-card p-1.5 pl-4 shadow-soft transition-[border-color] focus-within:border-tide/70">
      <textarea ref={ref} rows={1} value={value} onChange={(e) => onChange(e.target.value)} enterKeyHint="send"
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); send(); } }}
        placeholder={t("chat.placeholder")} aria-label={t("chat.placeholder")}
        style={{ outline: "none", boxShadow: "none" }}
        className="max-h-40 min-h-[2.5rem] flex-1 resize-none bg-transparent py-2 text-base leading-6 placeholder:text-ink-faint sm:text-[14px]" />
      {busy && onStop ? (
        <button type="button" onClick={onStop} className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-ink text-paper transition-opacity hover:opacity-85" aria-label={t("chat.stop")} title={t("chat.stop")}>
          <Square className="h-3.5 w-3.5" fill="currentColor" strokeWidth={0} /></button>
      ) : (
        <button className="btn-primary !h-10 !w-10 shrink-0 !p-0 !tracking-normal" disabled={!value.trim() || busy} aria-label={t("search.send")}>
          <ArrowUp className="h-[18px] w-[18px]" strokeWidth={2} /></button>
      )}
    </form>
  );
}
