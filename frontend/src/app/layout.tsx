import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

/** Vor dem ersten Rendern: Theme aus localStorage ("stromlauf:theme") oder Systemeinstellung, ohne Flackern. */
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("stromlauf:theme");if(t!=="light"&&t!=="dark"){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.setAttribute("data-theme",t)}catch(e){}})();`;

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
    <html lang="de" className={`${inter.variable} ${plexMono.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="h-full font-sans">
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        {children}
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}
