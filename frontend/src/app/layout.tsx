import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Stromlauf AI",
  description: "Chatbot für Stromlaufpläne, Stücklisten, Klemmenpläne und Siemens AWL",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="de" className={`${plexSans.variable} ${plexMono.variable} h-full antialiased`}>
      <body className="h-full font-sans">
        {children}
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}
