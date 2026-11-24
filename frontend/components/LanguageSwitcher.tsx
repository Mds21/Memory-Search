"use client";
import { Languages } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useI18n } from "@/lib/i18n";
import { LANGS } from "@/lib/messages";

export default function LanguageSwitcher({ compact }: { compact?: boolean }) {
  const { lang, setLang } = useI18n();
  const { user } = useAuth();
  return (
    <label className="relative inline-flex items-center gap-2 text-sm text-ink-soft">
      <Languages className="h-4 w-4" aria-hidden />
      <span className="sr-only">Language</span>
      <select className={`rounded-md border border-paper-line bg-paper-card py-1 pl-2 pr-6 text-sm ${compact ? "w-24" : ""}`} value={lang}
        onChange={(e) => { setLang(e.target.value); if (user) api.patch("/me", { language: e.target.value }).catch(() => {}); }}>
        {LANGS.map((l) => <option key={l.code} value={l.code}>{l.label}</option>)}
      </select>
    </label>
  );
}
