"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API, api, tokens } from "./api";
import type { User } from "./types";
import { useI18n } from "./i18n";

interface AuthCtx { user: User | null; loading: boolean; login: (e: string, p: string) => Promise<void>; register: (e: string, p: string, name: string, lang: string) => Promise<void>; logout: () => void; setUser: (u: User) => void }
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);

async function authCall(path: string, body: object) {
  let res: Response;
  try { res = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }
  catch { throw new Error(`Cannot reach the server at ${API}. Check that the backend is running and that CORS allows this site.`); }
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
  const logout = useCallback(() => { tokens.set(null); setUser(null); location.href = "/login"; }, []);
  return <Ctx.Provider value={{ user, loading, login, register, logout, setUser }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
