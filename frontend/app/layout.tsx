import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { I18nProvider } from "@/lib/i18n";
import { AuthProvider } from "@/lib/auth";
import { themeScript } from "@/lib/theme";
import { API } from "@/lib/api";

// Self-hosted at build time by next/font: no render-blocking request to Google, no layout shift.
const inter = Inter({ subsets: ["latin"], display: "swap", variable: "--font-inter" });

export const metadata: Metadata = { title: "Smriti: search your memories and documents", description: "Find any photo, video or document by describing it." };
export const viewport: Viewport = {
  width: "device-width", initialScale: 1, viewportFit: "cover",  // draw under the notch; layouts pad with safe-area insets
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#FAFAFA" }, { media: "(prefers-color-scheme: dark)", color: "#0A0A0A" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const apiOrigin = new URL(API).origin;
  return (
    <html lang="en" className={inter.variable} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        {/* open the connection to the API early: saves a round trip on the first data and image requests */}
        <link rel="preconnect" href={apiOrigin} crossOrigin="anonymous" />
        <link rel="dns-prefetch" href={apiOrigin} />
      </head>
      <body><I18nProvider><AuthProvider>{children}</AuthProvider></I18nProvider></body>
    </html>
  );
}
