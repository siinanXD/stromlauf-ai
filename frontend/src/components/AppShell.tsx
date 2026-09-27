"use client";

import { Calculator, Cog, Factory, Gauge, MessageSquare, Search } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment, useEffect, useState, type ReactNode } from "react";

import { GlobalSearch } from "@/components/GlobalSearch";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
}

interface NavItem {
  href: string;
  label: string;
  icon: typeof Cog;
  /** Aktiv, wenn der Pfad passt; Standard: Präfix. */
  match?: (pathname: string) => boolean;
}

/** Kern: Maschine und ihre Doku. Planung und Leitstand sind Nebenmodule (Feature-Freeze, siehe AGENTS.md). */
const MAIN_NAV: NavItem[] = [
  { href: "/", label: "Chat", icon: MessageSquare, match: (p) => p === "/" },
  { href: "/werk/maschinen", label: "Maschinen", icon: Cog, match: (p) => p.startsWith("/werk/maschine") },
  { href: "/werk", label: "Werk", icon: Factory, match: (p) => p.startsWith("/werk") && !p.startsWith("/werk/maschine") },
];
const SIDE_NAV: NavItem[] = [
  { href: "/planung", label: "Planung", icon: Calculator },
  { href: "/leitstand", label: "Leitstand", icon: Gauge },
];

function NavLink({ item, pathname }: { item: NavItem; pathname: string }) {
  const { href, label, icon: Icon, match } = item;
  const active = match ? match(pathname) : pathname.startsWith(href);
  return (
    <Link href={href} className="group flex flex-col items-center gap-1">
      <span
        className={cn(
          "grid size-10 place-items-center border",
          active ? "border-white bg-white/15 text-white" : "border-[#3b4f6b] text-nav-foreground group-hover:text-white",
        )}
      >
        <Icon className="size-4" />
      </span>
      <span className={cn("text-[10px]", active ? "text-white" : "text-nav-foreground")}>{label}</span>
    </Link>
  );
}

/** Rahmen aller Seiten: dunkle Navigationsleiste links, Kopfzeile mit Pfad, Suche und Status. */
export function AppShell({ breadcrumb, children }: { breadcrumb: Crumb[]; children: ReactNode }) {
  const pathname = usePathname();
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api
      .health()
      .then(() => setOnline(true))
      .catch(() => setOnline(false));
  }, []);

  return (
    <div className="flex h-full">
      <nav className="flex w-16 shrink-0 flex-col items-center gap-3 bg-nav py-3.5">
        <Link
          href="/"
          className="mb-4 grid size-9 place-items-center bg-primary font-mono text-lg font-semibold text-primary-foreground"
          title="Stromlauf AI"
        >
          S
        </Link>
        {MAIN_NAV.map((item) => (
          <NavLink key={item.href} item={item} pathname={pathname} />
        ))}
        <div className="mt-auto flex flex-col items-center gap-3 border-t border-[#3b4f6b] pt-3 opacity-70" title="Nebenmodule">
          {SIDE_NAV.map((item) => (
            <NavLink key={item.href} item={item} pathname={pathname} />
          ))}
        </div>
      </nav>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-4 border-b border-line bg-card px-6">
          <ol className="flex min-w-0 items-center gap-2 font-mono text-[13px] uppercase">
            {breadcrumb.map((crumb, index) => {
              const last = index === breadcrumb.length - 1;
              return (
                <Fragment key={`${crumb.label}-${index}`}>
                  {index > 0 && <li className="text-muted-foreground">/</li>}
                  <li className={cn("truncate", last ? "font-semibold" : "text-muted-foreground")}>
                    {crumb.href && !last ? (
                      <Link href={crumb.href} className="hover:text-primary">
                        {crumb.label}
                      </Link>
                    ) : (
                      crumb.label
                    )}
                  </li>
                </Fragment>
              );
            })}
          </ol>

          <button
            type="button"
            data-search-trigger
            onClick={() => window.dispatchEvent(new CustomEvent("stromlauf:search"))}
            className="mx-auto hidden h-8 w-full max-w-md items-center gap-2 border border-border bg-background px-3 text-left text-[13px] text-muted-foreground hover:border-primary md:flex"
          >
            <Search className="size-3.5" />
            <span className="flex-1 truncate">Suchen: -K12, X1:5, E0.0 …</span>
            <kbd className="border border-border px-1.5 font-mono text-[11px]">Strg K</kbd>
          </button>

          <span className="ml-auto flex shrink-0 items-center gap-2 text-xs text-muted-foreground">
            <span
              className={cn("size-2 rounded-full", online === null ? "bg-border" : online ? "bg-ok" : "bg-danger")}
            />
            {online === null ? "Verbinde …" : online ? "Backend verbunden" : "Backend nicht erreichbar"}
          </span>
        </header>

        <main className="min-h-0 flex-1">{children}</main>
      </div>
      <GlobalSearch />
    </div>
  );
}
