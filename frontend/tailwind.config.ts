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
        // "tide" is the accent: ochre gold. Name kept so existing components follow the new palette.
        tide: { DEFAULT: v("tide"), dark: v("tide-dark"), soft: v("tide-soft"), ring: v("tide-ring"), on: v("on-tide") },
        glow: { DEFAULT: v("glow"), soft: v("glow-soft") },
        danger: { DEFAULT: v("danger"), soft: v("danger-soft") },
        ok: { DEFAULT: v("ok"), soft: v("ok-soft") },
        night: "#0b0b0b", // overlays, the lightbox and toasts stay dark in both themes
      },
      borderRadius: { none: "0", sm: "3px", DEFAULT: "4px", md: "6px", lg: "8px", xl: "10px", "2xl": "14px", full: "9999px" },
      fontFamily: {
        sans: ["\"Roboto Mono Variable\"", "Noto Sans Mono", "Noto Sans Devanagari", "Noto Sans Tamil", "ui-monospace", "monospace"],
        mono: ["\"Roboto Mono Variable\"", "ui-monospace", "Consolas", "monospace"],
        script: ["\"Kaushan Script\"", "cursive"],
        serif: ["\"Roboto Mono Variable\"", "ui-monospace", "monospace"],
      },
      letterSpacing: { label: "0.14em", display: "0.2em" },
      boxShadow: {
        soft: "0 1px 2px rgb(0 0 0 / 0.08)",
        lift: "0 18px 40px -18px rgb(0 0 0 / 0.55)",
      },
      transitionTimingFunction: { DEFAULT: "cubic-bezier(0.22, 1, 0.36, 1)" },
      transitionDuration: { DEFAULT: "180ms" },
      keyframes: { rise: { from: { opacity: "0", transform: "translateY(10px)" }, to: { opacity: "1", transform: "none" } } },
      animation: { rise: "rise 420ms cubic-bezier(0.22, 1, 0.36, 1) both" },
    },
  },
  plugins: [],
};
export default config;
