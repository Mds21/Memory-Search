import type { Parsed } from "./types";

export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";
export const ORIGIN = new URL(API).origin;
const KEY = "smriti.tokens";

export interface Tokens { access_token: string; refresh_token: string }
export const tokens = {
  get(): Tokens | null { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; } },
  set(t: Tokens | null) { try { t ? localStorage.setItem(KEY, JSON.stringify(t)) : localStorage.removeItem(KEY); } catch { /* storage unavailable */ } },
};
export const abs = (u?: string | null) => (u ? (u.startsWith("http") ? u : ORIGIN + u) : "");

export class ApiError extends Error { constructor(public status: number, message: string) { super(message); } }

let refreshing: Promise<boolean> | null = null;
async function refresh(): Promise<boolean> {
  const t = tokens.get();
  if (!t) return false;
  refreshing ||= fetch(`${API}/auth/refresh`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ refresh_token: t.refresh_token }) })
    .then(async (r) => { if (!r.ok) return false; tokens.set(await r.json()); return true; })
    .catch(() => false).finally(() => { refreshing = null; });
  return refreshing;
}

export async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  const t = tokens.get();
  if (t) headers.set("Authorization", `Bearer ${t.access_token}`);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const res = await fetch(API + path, { ...init, headers });
  if (res.status === 401 && retry && (await refresh())) return raw(path, init, false);
  return res;
}

async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await raw(path, init);
  if (!res.ok) {
    let msg = res.statusText;
    try { const d = await res.json(); msg = typeof d.detail === "string" ? d.detail : JSON.stringify(d.detail); } catch { /* not json */ }
    if (res.status === 401) { tokens.set(null); if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) location.href = "/login"; }
    throw new ApiError(res.status, msg);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T,>(p: string) => json<T>(p),
  post: <T,>(p: string, body?: unknown) => json<T>(p, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T,>(p: string, body: unknown) => json<T>(p, { method: "PATCH", body: JSON.stringify(body) }),
  del: <T = void,>(p: string) => json<T>(p, { method: "DELETE" }),
  upload(path: string, files: File[], onProgress?: (pct: number) => void): Promise<{ items: any[] }> {
    return new Promise((resolve, reject) => {
      const send = (retry: boolean) => {
        const fd = new FormData();
        const field = path.includes("zip") ? "file" : "files";
        files.forEach((f) => fd.append(field, f));
        const xhr = new XMLHttpRequest();
        xhr.open("POST", API + path);
        const t = tokens.get();
        if (t) xhr.setRequestHeader("Authorization", `Bearer ${t.access_token}`);
        xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(Math.round((e.loaded / e.total) * 100));
        xhr.onload = async () => {
          if (xhr.status === 401 && retry && (await refresh())) return send(false);
          if (xhr.status >= 200 && xhr.status < 300) return resolve(JSON.parse(xhr.responseText));
          let msg = xhr.statusText;
          try { msg = JSON.parse(xhr.responseText).detail || msg; } catch { /* ignore */ }
          reject(new ApiError(xhr.status, String(msg)));
        };
        xhr.onerror = () => reject(new ApiError(0, "Cannot reach the server"));
        xhr.send(fd);
      };
      send(true);
    });
  },
};

export interface StreamHandlers {
  parsed?: (d: { parsed: Parsed; conversation_id: string }) => void;
  results?: (d: { results: any[]; total: number; took_ms: number }) => void;
  token?: (text: string) => void;
  done?: (d: { message_id: string; conversation_id: string; citations: any[] }) => void;
  error?: (message: string) => void;
}

/** POST /chat and read the Server-Sent Events stream (EventSource cannot POST). */
export async function chatStream(body: object, h: StreamHandlers, signal?: AbortSignal) {
  const res = await raw("/chat", { method: "POST", body: JSON.stringify(body), signal });
  if (!res.ok || !res.body) { h.error?.(`Request failed (${res.status})`); return; }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i); buf = buf.slice(i + 2);
      let ev = "message", data = "";
      for (const line of block.split("\n")) { if (line.startsWith("event: ")) ev = line.slice(7); else if (line.startsWith("data: ")) data += line.slice(6); }
      if (!data) continue;
      const d = JSON.parse(data);
      if (ev === "parsed") h.parsed?.(d); else if (ev === "results") h.results?.(d); else if (ev === "token") h.token?.(d.text);
      else if (ev === "done") h.done?.(d); else if (ev === "error") h.error?.(d.message);
    }
  }
}
