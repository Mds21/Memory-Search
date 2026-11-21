import type { Metadata, Viewport } from "next";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";

export const metadata: Metadata = { title: "Smriti: search your memories and documents", description: "Find any photo, video or document by describing it." };
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0E7C86" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body><I18nProvider><AuthProvider>{children}</AuthProvider></I18nProvider></body>
    </html>
  );
}
