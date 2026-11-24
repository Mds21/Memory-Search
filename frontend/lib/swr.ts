"use client";
/**
 * Tiny stale-while-revalidate cache for GET requests.
 * - Revisiting a section renders cached data instantly, then refreshes quietly in the background.
 * - Identical requests in flight are shared (no duplicate fetches).
 * - `prefetch()` warms the cache, e.g. when the pointer hovers a nav link.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";

interface Entry { data?: unknown; error?: unknown; at: number; inflight?: Promise<unknown> }
const cache = new Map<string, Entry>();
const subs = new Map<string, Set<() => void>>();
const FRESH_MS = 15_000; // within this window a remount does not refetch

const notify = (key: string) => subs.get(key)?.forEach((f) => f());

function load<T>(key: string, force = false): Promise<T> {
  const e = cache.get(key);
  if (e?.inflight) return e.inflight as Promise<T>;
  if (!force && e?.data !== undefined && Date.now() - e.at < FRESH_MS) return Promise.resolve(e.data as T);
  const p = api.get<T>(key)
    .then((data) => { cache.set(key, { data, at: Date.now() }); notify(key); return data; })
    .catch((error) => { cache.set(key, { ...cache.get(key), error, at: Date.now(), inflight: undefined }); notify(key); throw error; });
  cache.set(key, { ...e, at: e?.at ?? 0, inflight: p });
  return p;
}

export const prefetch = (key: string) => { load(key).catch(() => {}); };
export const peek = <T,>(key: string) => cache.get(key)?.data as T | undefined;
/** Drop cached entries whose key starts with any prefix, so the next visit refetches. */
export const invalidate = (...prefixes: string[]) => { for (const k of [...cache.keys()]) if (prefixes.some((p) => k.startsWith(p))) { const e = cache.get(k)!; cache.set(k, { ...e, at: 0 }); } };
export const mutateCache = <T,>(key: string, data: T) => { cache.set(key, { data, at: Date.now() }); notify(key); };

/**
 * @param key   API path (null = don't fetch yet)
 * @param dep   any value that should trigger a background refresh when it changes (e.g. the uploads tick)
 */
export function useApi<T>(key: string | null, dep?: unknown) {
  const [, force] = useState(0);
  const keyRef = useRef(key);
  keyRef.current = key;

  useEffect(() => {
    if (!key) return;
    const f = () => force((n) => n + 1);
    if (!subs.has(key)) subs.set(key, new Set());
    subs.get(key)!.add(f);
    load(key).catch(() => {});
    return () => { subs.get(key)?.delete(f); };
  }, [key]);

  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (key) load(key, true).catch(() => {});
  }, [dep]); // eslint-disable-line react-hooks/exhaustive-deps

  const e = key ? cache.get(key) : undefined;
  const reload = useCallback(() => (keyRef.current ? load<T>(keyRef.current, true) : Promise.resolve(undefined as T)), []);
  return { data: e?.data as T | undefined, error: e?.data === undefined ? e?.error : undefined, loading: !!key && e?.data === undefined && !e?.error, reload };
}
