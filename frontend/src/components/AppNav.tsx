"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Chat" },
  { href: "/werk", label: "Werk" },
];

/** Kopfzeile mit Logo und Hauptnavigation, in Sidebar und Werk-Seiten gleich. */
export function AppNav() {
  const pathname = usePathname();
  return (
    <div className="flex items-center gap-2 px-4 py-4">
      <span className="grid h-7 w-7 place-items-center rounded-md bg-accent font-bold text-accent-fg">⚡</span>
      <span className="font-semibold tracking-tight">Stromlauf AI</span>
      <nav className="ml-auto flex gap-1 text-sm">
        {LINKS.map((link) => {
          const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
          return (
            <Link
              key={link.href}
              href={link.href}
              className={`rounded-md px-2 py-1 ${active ? "bg-surface-2 font-medium" : "text-muted hover:bg-surface-2 hover:text-text"}`}
            >
              {link.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
