import React from "react";
import type { Filters, Parsed } from "./types";

export function highlight(text: string, terms: string[]): React.ReactNode {
  const ts = terms.filter((t) => t.length > 1).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!text || !ts.length) return text;
  const re = new RegExp(`(${ts.join("|")})`, "giu");
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i} className="hl">{part}</mark> : <React.Fragment key={i}>{part}</React.Fragment>));
}
export const termsOf = (q?: string) => (q || "").toLowerCase().split(/[\s,.;:?!]+/).filter((w) => w.length > 2);

export const emptyFilters = (): Filters => ({ kinds: [], date_from: null, date_to: null, place: null, tags: [], language: null, collection_id: null });
export const emptyParsed = (raw = ""): Parsed => ({ raw, language: null, intent: "mixed", semantic_query: "", semantic_query_en: null, filters: emptyFilters(), followup: false });

export function dateChipLabel(f: Filters, lang: string): string | null {
  if (!f.date_from && !f.date_to) return null;
  const a = f.date_from ? new Date(f.date_from + "T00:00:00") : null, b = f.date_to ? new Date(f.date_to + "T00:00:00") : null;
  if (a && b) {
    if (a.getFullYear() === b.getFullYear() && a.getMonth() === 0 && a.getDate() === 1 && b.getMonth() === 11 && b.getDate() === 31) return String(a.getFullYear());
    if (a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === 1) return a.toLocaleDateString(lang, { month: "long", year: "numeric" });
    if (+a === +b) return a.toLocaleDateString(lang, { dateStyle: "medium" });
  }
  const f1 = (d: Date | null) => (d ? d.toLocaleDateString(lang, { dateStyle: "medium" }) : "…");
  return `${f1(a)} – ${f1(b)}`;
}

export const monthLabel = (period: string, lang: string) => {
  const [y, m] = period.split("-").map(Number);
  return new Date(y, (m || 1) - 1, 1).toLocaleDateString(lang, { month: "short", year: "numeric" });
};
export function monthBounds(period: string) {
  const [y, m] = period.split("-").map(Number);
  const last = new Date(y, m, 0).getDate();
  return { from: `${period}-01`, to: `${period}-${String(last).padStart(2, "0")}` };
}
