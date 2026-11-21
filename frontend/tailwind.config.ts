import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: "#101828", soft: "#344054", mute: "#667085", faint: "#98A2B3" },
        paper: { DEFAULT: "#F5F6F8", card: "#FFFFFF", line: "#E4E7EC", sunk: "#EDEFF3" },
        tide: { DEFAULT: "#0E7C86", dark: "#0A5D65", soft: "#E3F3F4", ring: "#7CC4CA" },
        glow: { DEFAULT: "#F6C453", soft: "#FFF4D6" },
        danger: { DEFAULT: "#C2362B", soft: "#FDECEA" },
        ok: { DEFAULT: "#1E8A4C", soft: "#E4F5EA" },
      },
      fontFamily: { sans: ["Inter", "Noto Sans", "Noto Sans Devanagari", "Noto Sans Tamil", "system-ui", "sans-serif"] },
      boxShadow: { lift: "0 1px 2px rgba(16,24,40,.06), 0 8px 24px -12px rgba(16,24,40,.18)" },
    },
  },
  plugins: [],
};
export default config;
