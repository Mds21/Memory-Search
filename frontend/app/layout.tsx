import ServerStatus from "@/components/ServerStatus";
import type { Metadata, Viewport } from "next";
import "@fontsource-variable/roboto-mono";
import "@fontsource/kaushan-script";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";
import { themeScript } from "@/lib/theme";

export const metadata: Metadata = { title: "Smriti: search your memories and documents", description: "Find any photo, video or document by describing it." };
export const viewport: Viewport = {
  width: "device-width", initialScale: 1,
  themeColor: "#0e0e0e",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
      <body><I18nProvider><AuthProvider>{children}</AuthProvider><ServerStatus /></I18nProvider></body>
    </html>
  );
}
