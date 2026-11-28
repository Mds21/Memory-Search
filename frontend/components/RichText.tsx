"use client";
import { Fragment, type ReactNode } from "react";

/** The small amount of formatting chat answers use: paragraphs, "- " / "1. " lists, **bold**, and [S1] citations
 *  (rendered by `cite`). Unclosed markers stay as plain text, so a reply that is still streaming never breaks. */
export default function RichText({ text, cite }: { text: string; cite: (label: string, key: string) => ReactNode }) {
  const blocks: { list: "ul" | "ol" | null; lines: string[] }[] = [];
  for (const raw of text.replace(/\r/g, "").split("\n")) {
    const line = raw.trimEnd();
    const kind = /^\s*[-*•]\s+/.test(line) ? "ul" : /^\s*\d+[.)]\s+/.test(line) ? "ol" : null;
    const last = blocks[blocks.length - 1];
    if (!line.trim()) { if (last && (last.list || last.lines.length)) blocks.push({ list: null, lines: [] }); continue; }
    if (last && last.list === kind && (kind || last.lines.length)) last.lines.push(line);
    else blocks.push({ list: kind, lines: [line] });
  }

  const inline = (s: string, k: string): ReactNode[] =>
    s.split(/(\*\*[^*\n]+\*\*|\[\s*S\s*\d+\s*\])/g).map((part, i) => {
      const key = `${k}-${i}`;
      if (/^\*\*[^*]+\*\*$/.test(part)) return <strong key={key} className="font-semibold text-ink">{part.slice(2, -2)}</strong>;
      if (/^\[\s*S\s*\d+\s*\]$/.test(part)) return <Fragment key={key}>{cite(part.replace(/[\[\]\s]/g, ""), key)}</Fragment>;
      return <Fragment key={key}>{part}</Fragment>;
    });

  return (
    <div className="space-y-2.5">
      {blocks.filter((b) => b.lines.length).map((b, i) => {
        if (!b.list) return <p key={i} className="whitespace-pre-wrap">{inline(b.lines.join("\n"), `p${i}`)}</p>;
        const Tag = b.list;
        return (
          <Tag key={i} className={`space-y-1 pl-5 ${Tag === "ul" ? "list-disc" : "list-decimal"} marker:text-ink-faint`}>
            {b.lines.map((l, j) => <li key={j}>{inline(l.replace(/^\s*(?:[-*•]|\d+[.)])\s+/, ""), `l${i}-${j}`)}</li>)}
          </Tag>);
      })}
    </div>
  );
}
