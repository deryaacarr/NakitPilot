import type { Metadata } from "next";
import { Manrope, Source_Serif_4 } from "next/font/google";

import { PwaProvider } from "@/components/pwa/pwa-provider";
import { ToastProvider } from "@/components/ui/toast";
import { env } from "@/lib/env";

import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin", "latin-ext"],
});

const sourceSerif = Source_Serif_4({
  variable: "--font-source-serif",
  subsets: ["latin", "latin-ext"],
});

export const metadata: Metadata = {
  title: {
    default: env.appName,
    template: `%s · ${env.appName}`,
  },
  description: "KOBİ tahsilat ve nakit takip platformu",
  manifest: "/manifest.webmanifest",
  themeColor: "#0f4c81",
  appleWebApp: {
    capable: true,
    title: "NakitPilot",
    statusBarStyle: "default",
  },
  icons: {
    icon: [
      { url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" },
      { url: "/icons/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
    apple: [{ url: "/icons/icon-192.png", sizes: "192x192", type: "image/png" }],
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="tr" className={`${manrope.variable} ${sourceSerif.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-slate-50 font-sans text-slate-900">
        <ToastProvider>
          {children}
          <PwaProvider />
        </ToastProvider>
      </body>
    </html>
  );
}
