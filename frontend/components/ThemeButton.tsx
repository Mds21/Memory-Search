"use client";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "@/lib/theme";

/** Cycles dark → light → system. Works signed in or out, since the choice lives in this browser. */
export default function ThemeButton() {
  const { pref, cycle } = useTheme();
  const Icon = pref === "dark" ? Moon : pref === "light" ? Sun : Monitor;
  const label = `Theme: ${pref}`;
  return <button type="button" onClick={cycle} className="btn-ghost !h-9 !w-9 !p-0" aria-label={label} title={label}><Icon className="h-4 w-4" strokeWidth={1.5} /></button>;
}
