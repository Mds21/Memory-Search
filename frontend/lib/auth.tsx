"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API, api, tokens, server, UNREACHABLE } from "./api";
import type { User } from "./types";
import { useI18n } from "./i18n";

interface AuthCtx { user: User | null; loading: boolean; login: (e: string, p: string) => Promise<void>; register: (e: string, p: string, name: string, lang: string) => Promise<void>; google: (credential: string, lang: string) => Promise<void>; logout: () => void; setUser: (u: User) => void }
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

async function authCall(path: string, body: object) {
  let res: Response;
  try { res = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch { server.set(false); throw new Error("Can't reach your Memory Search server. Your files are safe; try again in a minute."); }
  if (UNREACHABLE.has(res.status)) { server.set(false); throw new Error("Can't reach your Memory Search server. Your files are safe; try again in a minute."); }
  server.set(true);
  const d = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = d.detail;
    throw new Error(typeof detail === "string" ? detail : Array.isArray(detail) ? "Check your email and use a password of at least 8 characters." : "Request failed");
  }
  return d;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { setLang } = useI18n();

  useEffect(() => {
    if (!tokens.get()) { setLoading(false); return; }
    api.get<User>("/me").then((u) => setUser(u)).catch(() => tokens.set(null)).finally(() => setLoading(false));
  }, []);

  const finish = useCallback((d: any) => { tokens.set({ access_token: d.access_token, refresh_token: d.refresh_token }); setUser(d.user); if (d.user?.language) setLang(d.user.language); }, [setLang]);
  const login = useCallback(async (email: string, password: string) => finish(await authCall("/auth/login", { email, password })), [finish]);
  const register = useCallback(async (email: string, password: string, display_name: string, language: string) => finish(await authCall("/auth/register", { email, password, display_name, language })), [finish]);
  const google = useCallback(async (credential: string, language: string) => finish(await authCall("/auth/google", { credential, language })), [finish]);
  const logout = useCallback(() => { tokens.set(null); setUser(null); location.href = "/login"; }, []);
  return <Ctx.Provider value={{ user, loading, login, register, google, logout, setUser }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
