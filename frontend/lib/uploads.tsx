"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { API, api, isOffline, tokens } from "./api";

/** Phones drop off Wi-Fi and mobile data mid-upload: retry a few times (5 s, 15 s, 45 s) before calling it failed. */
async function withRetry<T>(send: () => Promise<T>, onWait: (note: string) => void): Promise<T> {
  for (let attempt = 0; ; attempt++) {
    try { return await send(); } catch (e) {
      if (!isOffline(e) || attempt >= 3) throw e;
      onWait("Connection lost, retrying…");
      await new Promise((r) => setTimeout(r, 5000 * 3 ** attempt));
    }
  }
}

export type UpStatus = "uploading" | "queued" | "processing" | "ready" | "failed" | "duplicate" | "rejected";
export interface UpItem { key: string; name: string; status: UpStatus; progress: number; assetId?: string; detail?: string | null }
interface Ctx {
  items: UpItem[]; addFiles: (f: File[]) => void; importZip: (f: File) => void; busy: number;
  tick: number; // increments when any asset changes, so pages can refetch
  toast: (msg: string, kind?: "ok" | "error") => void; toasts: { id: number; msg: string; kind: string }[];
  retry: (assetId: string) => void;
}
const C = createContext<Ctx>(null as unknown as Ctx);
let seq = 0;

export function UploadsProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<UpItem[]>([]);
  const [tick, setTick] = useState(0);
  const [toasts, setToasts] = useState<Ctx["toasts"]>([]);
  const queue = useRef<(() => Promise<void>)[]>([]);
  const running = useRef(0);

  const toast = useCallback((msg: string, kind: "ok" | "error" = "ok") => {
    const id = ++seq;
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);

  const patch = (key: string, p: Partial<UpItem>) => setItems((xs) => xs.map((x) => (x.key === key ? { ...x, ...p } : x)));

  const pump = useCallback(() => {
    while (running.current < 2 && queue.current.length) {
      const job = queue.current.shift()!;
      running.current++;
      job().finally(() => { running.current--; pump(); });
    }
  }, []);

  const addFiles = useCallback((files: File[]) => {
    for (const f of files) {
      const key = `u${++seq}`;
      setItems((xs) => [{ key, name: f.name, status: "uploading", progress: 0 }, ...xs]);
      queue.current.push(async () => {
        try {
          const r = await withRetry(() => api.upload("/assets", [f], (p) => patch(key, { progress: p })), (n) => patch(key, { status: "uploading", progress: 0, detail: n }));
          const it = r.items[0];
          patch(key, { status: it.status as UpStatus, assetId: it.asset?.asset_id, progress: 100, detail: it.error, ...(it.status === "queued" ? { status: it.asset?.status === "ready" ? "ready" : "queued" } : {}) });
          setTick((t) => t + 1);
        } catch (e: any) { patch(key, { status: "failed", detail: e.message }); }
      });
    }
    pump();
  }, [pump]);

  const importZip = useCallback((f: File) => {
    const key = `u${++seq}`;
    setItems((xs) => [{ key, name: f.name, status: "uploading", progress: 0 }, ...xs]);
    queue.current.push(async () => {
      try {
        const r = await withRetry(() => api.upload("/imports/zip", [f], (p) => patch(key, { progress: p })), (n) => patch(key, { status: "uploading", progress: 0, detail: n }));
        patch(key, { status: "ready", progress: 100, detail: `${r.items.length} files` });
        setItems((xs) => [...r.items.map((it: any, i: number) => ({ key: `z${++seq}`, name: it.filename, status: (it.status === "queued" ? "queued" : it.status) as UpStatus, progress: 100, assetId: it.asset?.asset_id, detail: it.error })), ...xs]);
        setTick((t) => t + 1);
      } catch (e: any) { patch(key, { status: "failed", detail: e.message }); }
    });
    pump();
  }, [pump]);

  const retry = useCallback((assetId: string) => {
    api.post(`/assets/${assetId}/reindex`).then(() => { setItems((xs) => xs.map((x) => (x.assetId === assetId ? { ...x, status: "queued", detail: null } : x))); setTick((t) => t + 1); }).catch((e) => toast(e.message, "error"));
  }, [toast]);

  // live processing status over SSE (F16); reconnects with a fresh token
  useEffect(() => {
    let es: EventSource | null = null, stop = false, timer: any;
    const connect = async () => {
      if (stop) return;
      try { await api.get("/me"); } catch { return; } // also refreshes an expired access token
      const t = tokens.get();
      if (!t || stop) return;
      es = new EventSource(`${API}/events?access_token=${encodeURIComponent(t.access_token)}`);
      es.addEventListener("asset", (ev) => {
        const d = JSON.parse((ev as MessageEvent).data);
        setItems((xs) => xs.map((x) => (x.assetId === d.asset_id ? { ...x, status: d.status, detail: d.detail } : x)));
        setTick((n) => n + 1);
        if (d.status === "failed") toast(`${d.filename}: ${d.detail || "processing failed"}`, "error");
      });
      es.onerror = () => { es?.close(); timer = setTimeout(connect, 4000); };
    };
    connect();
    return () => { stop = true; es?.close(); clearTimeout(timer); };
  }, [toast]);

  const busy = items.filter((i) => i.status === "uploading" || i.status === "queued" || i.status === "processing").length;
  return <C.Provider value={{ items, addFiles, importZip, busy, tick, toast, toasts, retry }}>{children}</C.Provider>;
}
export const useUploads = () => useContext(C);
