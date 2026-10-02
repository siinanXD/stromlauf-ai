import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

// Variable Fonts: eine Datei je Familie deckt alle Schnitte der Figma-Textstile ab (Inter 400-700, Mono 500)
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-jetbrains-mono",
  subsets: ["latin"],
});

/** Vor dem ersten Rendern: Theme aus localStorage ("stromlauf:theme") oder Systemeinstellung, ohne Flackern. */
const THEME_SCRIPT = `(function(){try{var t=localStorage.getItem("stromlauf:theme");if(t!=="light"&&t!=="dark"){t=window.matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light"}document.documentElement.setAttribute("data-theme",t)}catch(e){}})();`;

export const metadata: Metadata = {
  title: "Stromlauf AI",
  description: "Chatbot für Stromlaufpläne, Stücklisten, Klemmenpläne und Siemens AWL",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="de" className={`${inter.variable} ${jetbrainsMono.variable} h-full antialiased`} suppressHydrationWarning>
      <body className="h-full font-sans">
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
        {children}
        <Toaster position="bottom-right" />
      </body>
    </html>
  );
}
