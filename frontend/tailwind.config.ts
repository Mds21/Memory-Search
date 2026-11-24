import type { Config } from "tailwindcss";

/** Colors come from CSS variables (app/globals.css) so light and dark share one set of names. */
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: v("ink"), soft: v("ink-soft"), mute: v("ink-mute"), faint: v("ink-faint") },
        paper: { DEFAULT: v("paper"), card: v("paper-card"), line: v("paper-line"), sunk: v("paper-sunk") },
        tide: { DEFAULT: v("tide"), dark: v("tide-dark"), soft: v("tide-soft"), ring: v("tide-ring") },
        glow: { DEFAULT: v("glow"), soft: v("glow-soft") },
        danger: { DEFAULT: v("danger"), soft: v("danger-soft") },
        ok: { DEFAULT: v("ok"), soft: v("ok-soft") },
        night: "#0c0c0d", // overlays, the lightbox and toasts stay dark in both themes
      },
      borderRadius: { none: "0", sm: "4px", DEFAULT: "6px", md: "8px", lg: "10px", xl: "12px", "2xl": "16px", full: "9999px" },
      fontFamily: {
        sans: ["\"Hanken Grotesk Variable\"", "Noto Sans", "Noto Sans Devanagari", "Noto Sans Tamil", "system-ui", "sans-serif"],
        serif: ["\"Source Serif 4 Variable\"", "Noto Serif", "Noto Serif Devanagari", "Noto Serif Tamil", "Georgia", "serif"],
        mono: ["ui-monospace", "\"SF Mono\"", "\"Cascadia Mono\"", "Consolas", "monospace"],
      },
      boxShadow: {
        soft: "0 1px 2px rgb(0 0 0 / 0.05)",
        lift: "0 8px 24px rgb(0 0 0 / 0.08), 0 1px 2px rgb(0 0 0 / 0.04)",
      },
      transitionTimingFunction: { DEFAULT: "cubic-bezier(0.22, 1, 0.36, 1)" },
      transitionDuration: { DEFAULT: "150ms" },
      keyframes: { rise: { from: { opacity: "0", transform: "translateY(8px)" }, to: { opacity: "1", transform: "none" } } },
      animation: { rise: "rise 360ms cubic-bezier(0.22, 1, 0.36, 1) both" },
    },
  },
  plugins: [],
};
export default config;
