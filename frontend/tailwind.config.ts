import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#17181A", soft: "#3A3D42", mute: "#62666D", faint: "#8E9299" },
        paper: { DEFAULT: "#F3F4F1", card: "#FBFBF9", line: "#D9DCD4", sunk: "#E8EAE4" },
        tide: { DEFAULT: "#2D3FA6", dark: "#1F2D80", soft: "#E6E9F5", ring: "#9AA5DC" },
        glow: { DEFAULT: "#F2B632", soft: "#FBEFCB" },
        danger: { DEFAULT: "#B23A2E", soft: "#F7E4E1" },
        ok: { DEFAULT: "#2F7A4B", soft: "#E1F0E6" },
      },
      borderRadius: { none: "0", sm: "2px", DEFAULT: "3px", md: "3px", lg: "4px", xl: "4px", "2xl": "6px", full: "9999px" },
      fontFamily: {
        sans: ["\"Hanken Grotesk Variable\"", "Noto Sans", "Noto Sans Devanagari", "Noto Sans Tamil", "system-ui", "sans-serif"],
        serif: ["\"Source Serif 4 Variable\"", "Noto Serif", "Noto Serif Devanagari", "Noto Serif Tamil", "Georgia", "serif"],
      },
      boxShadow: { lift: "0 12px 28px -18px rgba(23,24,26,.45)" },
    },
  },
  plugins: [],
};
export default config;
