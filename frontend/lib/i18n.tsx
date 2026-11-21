"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { MESSAGES } from "./messages";

interface I18n { lang: string; setLang: (l: string) => void; t: (key: string, vars?: Record<string, string | number>) => string }
const Ctx = createContext<I18n>({ lang: "en", setLang: () => {}, t: (k) => k });
const KEY = "smriti.lang";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [lang, setLangState] = useState("en");
  useEffect(() => {
    try { const s = localStorage.getItem(KEY); if (s && MESSAGES[s]) setLangState(s); else { const n = navigator.language.slice(0, 2); if (MESSAGES[n]) setLangState(n); } } catch { /* ignore */ }
  }, []);
  const setLang = useCallback((l: string) => { setLangState(l); try { localStorage.setItem(KEY, l); } catch { /* ignore */ } document.documentElement.lang = l; }, []);
  useEffect(() => { document.documentElement.lang = lang; }, [lang]);
  const value = useMemo<I18n>(() => ({
    lang, setLang,
    t: (key, vars) => {
      let s = MESSAGES[lang]?.[key] ?? MESSAGES.en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
      return s;
    },
  }), [lang, setLang]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
export const useI18n = () => useContext(Ctx);
