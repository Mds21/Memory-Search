import type { Metadata, Viewport } from "next";
import "@fontsource-variable/source-serif-4";
import "@fontsource-variable/hanken-grotesk";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";
import { themeScript } from "@/lib/theme";

export const metadata: Metadata = { title: "Smriti: search your memories and documents", description: "Find any photo, video or document by describing it." };
export const viewport: Viewport = {
  width: "device-width", initialScale: 1,
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#fafafa" }, { media: "(prefers-color-scheme: dark)", color: "#141415" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body><I18nProvider><AuthProvider>{children}</AuthProvider></I18nProvider></body>
    </html>
  );
}
