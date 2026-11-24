"use client";
import { abs, api } from "./api";
import type { Asset } from "./types";

/** Fresh signed link + the file itself (signed links expire, so always fetch at click time). */
async function fetchFile(a: Pick<Asset, "asset_id" | "title" | "doc_label">) {
  const d = await api.get<Asset>(`/assets/${a.asset_id}`);
  const res = await fetch(abs(d.original_url));
  if (!res.ok) throw new Error(res.statusText);
  const blob = await res.blob();
  return { d, file: new File([blob], a.title, { type: d.mime_type || blob.type }) };
}

/** Opens the phone's share sheet with the actual file (WhatsApp, mail, Drive...); falls back to a link, then to copying it. */
export async function shareAsset(a: Pick<Asset, "asset_id" | "title" | "doc_label">): Promise<"shared" | "copied" | "cancelled"> {
  const { d, file } = await fetchFile(a);
  const nav = navigator as Navigator & { canShare?: (x: ShareData) => boolean };
  const title = a.doc_label || a.title;
  try {
    if (nav.share && nav.canShare?.({ files: [file] })) { await nav.share({ files: [file], title }); return "shared"; }
    if (nav.share) { await nav.share({ title, url: abs(d.original_url) }); return "shared"; }
  } catch (e: any) {
    if (e?.name === "AbortError") return "cancelled";
    throw e;
  }
  await navigator.clipboard.writeText(abs(d.original_url));
  return "copied";
}

export async function downloadAsset(a: Pick<Asset, "asset_id" | "title" | "doc_label">) {
  const { file } = await fetchFile(a);
  const u = URL.createObjectURL(file);
  const el = document.createElement("a");
  el.href = u; el.download = a.title; el.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}

/** Search link for a word or phrase: lets details on one page lead to related files. */
export const searchHref = (q: string) => `/search?q=${encodeURIComponent(q)}`;
export const monthHref = (iso?: string | null) => (iso ? `/timeline?month=${iso.slice(0, 7)}` : "/timeline");
