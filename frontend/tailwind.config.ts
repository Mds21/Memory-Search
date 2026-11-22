import type { Config } from "tailwindcss";

/** Colors are CSS variables (RGB triplets in globals.css) so light/dark themes swap without `dark:` variants. */
const v = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  darkMode: ["class", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: v("ink"), soft: v("ink-soft"), mute: v("ink-mute"), faint: v("ink-faint") },
        paper: { DEFAULT: v("paper"), card: v("card"), line: v("line"), sunk: v("sunk") },
        tide: { DEFAULT: v("tide"), dark: v("tide-dark"), soft: v("tide-soft"), ring: v("tide-ring") },
        iris: { DEFAULT: v("iris"), soft: v("iris-soft") },
        glow: { DEFAULT: v("glow"), soft: v("glow-soft") },
        danger: { DEFAULT: v("danger"), soft: v("danger-soft") },
        ok: { DEFAULT: v("ok"), soft: v("ok-soft") },
        /** Fixed dark surface for overlays, toasts and the viewer, the same in both themes. */
        night: { DEFAULT: "#0A0A0A", soft: "#171717" },
      },
      fontFamily: { sans: ["var(--font-inter)", "Inter", "Noto Sans", "Noto Sans Devanagari", "Noto Sans Tamil", "system-ui", "sans-serif"] },
      boxShadow: {
        lift: "0 1px 2px rgb(var(--shadow) / .06), 0 12px 32px -16px rgb(var(--shadow) / .28)",
        soft: "0 1px 2px rgb(var(--shadow) / .05), 0 4px 12px -6px rgb(var(--shadow) / .12)",
        glow: "0 0 0 1px rgb(var(--ink) / .12), 0 10px 28px -12px rgb(var(--shadow) / .45)",
      },
      borderRadius: { "4xl": "2rem" },
      keyframes: {
        "fade-up": { from: { opacity: "0", transform: "translateY(6px)" }, to: { opacity: "1", transform: "none" } },
        "fade-in": { from: { opacity: "0" }, to: { opacity: "1" } },
        "scale-in": { from: { opacity: "0", transform: "scale(.97)" }, to: { opacity: "1", transform: "none" } },
      },
      animation: {
        "fade-up": "fade-up .35s cubic-bezier(.2,.7,.2,1) both",
        "fade-in": "fade-in .25s ease-out both",
        "scale-in": "scale-in .2s cubic-bezier(.2,.7,.2,1) both",
      },
    },
  },
  plugins: [],
};
export default config;
