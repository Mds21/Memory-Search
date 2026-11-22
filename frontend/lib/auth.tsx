"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { API, api, tokens } from "./api";
import type { User } from "./types";
import { useI18n } from "./i18n";

export interface RegisterData { display_name?: string; email?: string; phone?: string; password: string; language: string }
interface AuthCtx {
  user: User | null; loading: boolean; login: (identifier: string, p: string) => Promise<void>; register: (d: RegisterData) => Promise<void>;
  loginWithGoogle: (credential: string, lang: string) => Promise<void>; adopt: (signedIn: any) => void; logout: () => void; setUser: (u: User) => void;
}
const Ctx = createContext<AuthCtx>(null as unknown as AuthCtx);
const USER_KEY = "smriti.user";

/** The last known profile is kept locally so the app shell paints immediately; /me still verifies it in the background. */
const cachedUser = (): User | null => { try { return tokens.get() ? JSON.parse(localStorage.getItem(USER_KEY) || "null") : null; } catch { return null; } };
const storeUser = (u: User | null) => { try { u ? localStorage.setItem(USER_KEY, JSON.stringify(u)) : localStorage.removeItem(USER_KEY); } catch { /* storage unavailable */ } };

async function authCall(path: string, body: object) {
  const res = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const d = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = d.detail;
    throw new Error(typeof detail === "string" ? detail : "Please check what you entered and try again.");
  }
  return d;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUserState] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { setLang } = useI18n();
  const setUser = useCallback((u: User | null) => { setUserState(u); storeUser(u); }, []);

  useEffect(() => {
    if (!tokens.get()) { setLoading(false); return; }
    const c = cachedUser();
    if (c) { setUserState(c); setLoading(false); }
    api.get<User>("/me").then((u) => setUser(u)).catch(() => { tokens.set(null); setUser(null); }).finally(() => setLoading(false));
  }, [setUser]);

  const finish = useCallback((d: any) => { tokens.set({ access_token: d.access_token, refresh_token: d.refresh_token }); setUser(d.user); if (d.user?.language) setLang(d.user.language); }, [setLang, setUser]);
  const login = useCallback(async (identifier: string, password: string) => finish(await authCall("/auth/login", { identifier, password })), [finish]);
  const register = useCallback(async (d: RegisterData) => finish(await authCall("/auth/register", d)), [finish]);
  const loginWithGoogle = useCallback(async (credential: string, language: string) => finish(await authCall("/auth/google", { credential, language })), [finish]);
  const logout = useCallback(() => {
    tokens.set(null); storeUser(null); setUserState(null);
    try { (window as any).google?.accounts?.id?.disableAutoSelect?.(); } catch { /* Google script not loaded */ }  // no silent re-sign-in after signing out
    location.href = "/login";
  }, []);
  return <Ctx.Provider value={{ user, loading, login, register, loginWithGoogle, adopt: finish, logout, setUser: setUser as (u: User) => void }}>{children}</Ctx.Provider>;
}
export const useAuth = () => useContext(Ctx);
