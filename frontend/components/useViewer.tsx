"use client";
import dynamic from "next/dynamic";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import type { Asset } from "@/lib/types";

// The viewer is only needed after a click, so keep it out of every page's initial bundle.
const Lightbox = dynamic(() => import("./Lightbox"), { ssr: false });

export const assetHref = (a: Asset, q?: string) =>
  a.kind === "document" ? `/documents/${a.asset_id}${a.match?.page ? `?page=${a.match.page}` : ""}${q ? `${a.match?.page ? "&" : "?"}q=${encodeURIComponent(q)}` : ""}` : `/media/${a.asset_id}`;

/** Opens photos/videos in the lightbox and documents on their own page. */
export function useViewer(list: Asset[], q?: string) {
  const router = useRouter();
  const [id, setId] = useState<string | null>(null);
  const media = list.filter((a) => a.kind !== "document");
  const idx = id ? media.findIndex((a) => a.asset_id === id) : -1;
  const open = useCallback((a: Asset) => (a.kind === "document" ? router.push(assetHref(a, q)) : setId(a.asset_id)), [router, q]);
  const node = idx >= 0 ? <Lightbox items={media} index={idx} onIndex={(i) => setId(media[i].asset_id)} onClose={() => setId(null)} /> : null;
  return { open, node };
}
