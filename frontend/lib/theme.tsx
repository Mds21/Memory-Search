"use client";
import { useCallback, useEffect, useState } from "react";

export type ThemePref = "system" | "light" | "dark";
const KEY = "smriti.theme";

/** Runs before first paint (inlined in <head>) so the page never flashes the wrong theme. */
export const themeScript = `(function(){try{var p=localStorage.getItem("${KEY}")||"system";var d=p==="dark"||(p==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);document.documentElement.dataset.theme=d?"dark":"light";}catch(e){}})();`;

function apply(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.theme = dark ? "dark" : "light";
}

export function useTheme() {
  const [pref, setPref] = useState<ThemePref>("system");
  useEffect(() => {
    let p: ThemePref = "system";
    try { p = (localStorage.getItem(KEY) as ThemePref) || "system"; } catch { /* storage unavailable */ }
    setPref(p);
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => { let cur: ThemePref = "system"; try { cur = (localStorage.getItem(KEY) as ThemePref) || "system"; } catch { /* ignore */ } if (cur === "system") apply("system"); };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  const set = useCallback((p: ThemePref) => { setPref(p); try { localStorage.setItem(KEY, p); } catch { /* ignore */ } apply(p); }, []);
  const cycle = useCallback(() => set(pref === "system" ? "light" : pref === "light" ? "dark" : "system"), [pref, set]);
  return { pref, set, cycle };
}
