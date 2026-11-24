"use client";
/**
 * Small, safe Markdown renderer for assistant replies: headings, paragraphs, bullet and numbered lists (nested by
 * indent), **bold**, *italic*, `code`, code blocks, links and [S1] citations. Builds React elements only (no HTML
 * injection), so anything the model writes is displayed as text.
 */
import { Fragment, type ReactNode } from "react";

type Cite = (label: string, key: string) => ReactNode;

const INLINE = /(\[\s*S\s*\d+\s*\])|\*\*([^*]+)\*\*|__([^_]+)__|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|(https?:\/\/[^\s)<]+[^\s)<.,;:!?'"])|\*([^*\s][^*]*)\*/g;

function inline(text: string, cite: Cite, k: string): ReactNode[] {
  const out: ReactNode[] = [];
  let last = 0, i = 0;
  for (const m of text.matchAll(INLINE)) {
    if (m.index! > last) out.push(text.slice(last, m.index));
    const key = `${k}-${i++}`;
    if (m[1]) out.push(cite(m[1].replace(/[\[\]\s]/g, ""), key));
    else if (m[2] || m[3]) out.push(<strong key={key} className="font-semibold text-ink">{inline(m[2] || m[3], cite, key)}</strong>);
    else if (m[4]) out.push(<code key={key} className="rounded bg-paper-sunk px-1 py-0.5 font-mono text-[.85em]">{m[4]}</code>);
    else if (m[5]) out.push(<a key={key} href={m[6]} target="_blank" rel="noopener noreferrer" className="font-medium text-iris underline decoration-iris/30 underline-offset-2 hover:decoration-iris">{m[5]}</a>);
    else if (m[7]) out.push(<a key={key} href={m[7]} target="_blank" rel="noopener noreferrer" className="break-all font-medium text-iris underline decoration-iris/30 underline-offset-2 hover:decoration-iris">{m[7].replace(/^https?:\/\//, "")}</a>);
    else if (m[8]) out.push(<em key={key}>{m[8]}</em>);
    last = m.index! + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

interface Item { depth: number; ordered: boolean; text: string }

export default function Markdown({ text, cite }: { text: string; cite: Cite }) {
  // A run of 3+ citations ("[S1][S2][S3]...") is noise: the files are already shown as cards under the message.
  const lines = text.replace(/\r/g, "").replace(/(?:\s*\[\s*S\s*\d+\s*\]){3,}/g, "").split("\n");
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: Item[] = [];
  let code: string[] | null = null;

  const flushPara = () => {
    if (!para.length) return;
    const k = `p${blocks.length}`;
    blocks.push(<p key={k}>{para.map((l, i) => <Fragment key={i}>{i > 0 && <br />}{inline(l, cite, `${k}-${i}`)}</Fragment>)}</p>);
    para = [];
  };
  const flushList = () => {
    if (!list.length) return;
    const k = `l${blocks.length}`;
    const ordered = list[0].ordered;
    const Tag = ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={k} className={`space-y-1 pl-5 ${ordered ? "list-decimal" : "list-disc"} marker:text-ink-faint`}>
        {list.map((it, i) => <li key={i} style={it.depth ? { marginLeft: `${it.depth * 1.1}rem`, listStyleType: "circle" } : undefined} className="pl-0.5">{inline(it.text, cite, `${k}-${i}`)}</li>)}
      </Tag>);
    list = [];
  };

  for (const raw of lines) {
    if (code !== null) {
      if (/^\s*```/.test(raw)) { blocks.push(<pre key={`c${blocks.length}`} className="overflow-x-auto rounded-xl bg-paper-sunk p-3 font-mono text-xs leading-relaxed">{code.join("\n")}</pre>); code = null; }
      else code.push(raw);
      continue;
    }
    if (/^\s*```/.test(raw)) { flushPara(); flushList(); code = []; continue; }
    const line = raw.replace(/\s+$/, "");
    if (!line.trim()) { flushPara(); flushList(); continue; }
    const h = /^\s{0,3}(#{1,6})\s+(.*)$/.exec(line);
    if (h) {
      flushPara(); flushList();
      const k = `h${blocks.length}`;
      blocks.push(<p key={k} className={`font-semibold text-ink ${h[1].length <= 2 ? "text-[15px]" : "text-sm"} pt-1`}>{inline(h[2].replace(/\s*#+$/, ""), cite, k)}</p>);
      continue;
    }
    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) { flushPara(); flushList(); blocks.push(<hr key={`r${blocks.length}`} className="border-paper-line" />); continue; }
    const li = /^(\s*)([-*•+]|\d+[.)])\s+(.*)$/.exec(line);
    if (li) {
      flushPara();
      const ordered = /\d/.test(li[2]);
      if (list.length && list[0].ordered !== ordered && li[1].length === 0) flushList();
      list.push({ depth: Math.min(3, Math.floor(li[1].replace(/\t/g, "  ").length / 2)), ordered, text: li[3] });
      continue;
    }
    if (list.length && /^\s{2,}\S/.test(raw)) { list[list.length - 1].text += " " + line.trim(); continue; }  // wrapped list item
    flushList();
    para.push(line.trim());
  }
  if (code !== null) blocks.push(<pre key={`c${blocks.length}`} className="overflow-x-auto rounded-xl bg-paper-sunk p-3 font-mono text-xs">{(code as string[]).join("\n")}</pre>);
  flushPara(); flushList();
  return <div className="space-y-2.5 break-words">{blocks}</div>;
}
