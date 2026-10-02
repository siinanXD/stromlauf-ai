"use client";

import { Factory, LayoutList, MessageSquare, Moon, Plus, Search, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { costs, plant, type AuthMe, type MachineListItem, type WorkspaceBudget } from "@/lib/api";
import { costText } from "@/lib/format";
import { filterMachines } from "@/lib/machines";
import { cn } from "@/lib/utils";

export type RailMode = "full" | "icons";

/** Ampel je Maschine: gruen = Doku fertig, blau = wird verarbeitet, gelb = keine Doku. */
export function machineStatus(m: MachineListItem): { tone: "ok" | "busy" | "warn"; label: string } {
  if (m.document_count === 0) return { tone: "warn", label: "keine Doku" };
  if (m.ready_document_count < m.document_count) return { tone: "busy", label: "wird verarbeitet" };
  return { tone: "ok", label: "bereit" };
}

export function readTheme(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

export function applyTheme(theme: "light" | "dark") {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("stromlauf:theme", theme);
  } catch {
    /* privates Fenster o. ae.: dann gilt das Theme nur fuer diese Seite */
  }
}

/**
 * Linke Rail (Figma "Desktop / Start"): Marke, Suche, Maschinenliste mit Status, "Maschine hinzufügen",
 * darunter Werk, unten Nutzer und Monatskosten. `mode="icons"` ist die 72-px-Variante.
 */
export function MachineRail({ mode, me, onNavigate }: { mode: RailMode; me: AuthMe | null; onNavigate?: () => void }) {
  const pathname = usePathname();
  const [machines, setMachines] = useState<MachineListItem[] | null>(null);
  const [query, setQuery] = useState("");
  const [budget, setBudget] = useState<WorkspaceBudget | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    let cancelled = false;
    plant
      .listMachines()
      .then((list) => !cancelled && setMachines(list))
      .catch(() => !cancelled && setMachines([]));
    costs
      .budget()
      .then((b) => !cancelled && setBudget(b))
      .catch(() => {});
    const current = readTheme();
    Promise.resolve().then(() => !cancelled && setTheme(current));
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  const shown = useMemo(() => filterMachines(machines ?? [], query), [machines, query]);
  const activeId = pathname.startsWith("/werk/maschine/") ? pathname.split("/")[3] : null;
  const full = mode === "full";

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    applyTheme(next);
    setTheme(next);
  }

  const navLink = (href: string, label: string, Icon: typeof Factory, active: boolean) => (
    <Link
      href={href}
      onClick={onNavigate}
      title={label}
      className={cn(
        "flex min-h-11 items-center gap-2.5 rounded-md px-2.5 text-subhead hover:bg-muted hover:text-foreground",
        active ? "bg-primary-soft font-semibold text-primary" : "text-muted-foreground",
        !full && "mx-auto size-11 justify-center px-0",
      )}
    >
      <Icon className="size-4 shrink-0" />
      {full && <span>{label}</span>}
    </Link>
  );

  return (
    <nav
      aria-label="Maschinen und Bereiche"
      className={cn("flex h-full flex-col border-r-[0.5px] border-border bg-card text-muted-foreground", full ? "w-[280px]" : "w-[72px]")}
    >
      <div className={cn("flex items-center gap-2.5 px-3 pt-5 pb-2", !full && "flex-col justify-center gap-3.5 px-0")}>
        <Link href="/" onClick={onNavigate} className="grid size-10 shrink-0 place-items-center rounded-md bg-primary text-headline text-primary-foreground" title="Stromlauf AI">
          S
        </Link>
        {full && (
          <div className="min-w-0">
            <div className="truncate text-subhead font-semibold text-foreground">Stromlauf AI</div>
            <div className="truncate text-footnote">{me?.workspace.name ?? "Werk"}</div>
          </div>
        )}
        <button
          type="button"
          onClick={toggleTheme}
          className={cn("grid size-11 shrink-0 place-items-center rounded-full hover:bg-muted hover:text-foreground", full && "ml-auto")}
          aria-label={theme === "dark" ? "Helles Design" : "Dunkles Design"}
          title="Design wechseln"
        >
          {theme === "dark" ? <Sun className="size-5" /> : <Moon className="size-5" />}
        </button>
      </div>

      {full && (
        <label className="mx-3 mb-2 flex h-11 items-center gap-2 rounded-md bg-bg-fill px-3 text-subhead">
          <Search className="size-4 shrink-0" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Maschine suchen …"
            aria-label="Maschine suchen"
            className="min-w-0 flex-1 bg-transparent text-foreground outline-none"
          />
        </label>
      )}

      <div className={cn("space-y-0.5 px-2", !full && "space-y-3.5 px-3")}>
        {navLink("/werk/maschinen", "Alle Maschinen", LayoutList, pathname === "/werk/maschinen")}
        {navLink("/", "Chat über alles", MessageSquare, pathname === "/")}
      </div>

      <div className="mt-1 min-h-0 flex-1 overflow-y-auto px-2 [scrollbar-width:thin]" data-testid="machine-rail">
        {full && <p className="px-2.5 pt-3 pb-1 text-footnote font-semibold uppercase">Maschinen</p>}
        {machines === null && full && <p className="px-2.5 py-1 text-footnote">Lade …</p>}
        {machines && machines.length === 0 && full && <p className="px-2.5 py-1 text-footnote">Noch keine Maschine. Unten „Maschine hinzufügen“.</p>}
        <ul className={cn("space-y-0.5", !full && "mt-3.5 flex flex-col items-center gap-3.5 space-y-0")}>
          {shown.map((m) => {
            const status = machineStatus(m);
            const active = m.id === activeId;
            return (
              <li key={m.id}>
                <Link
                  href={`/werk/maschine/${m.id}?tab=chat`}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  title={`${m.name} · ${status.label}`}
                  className={cn(
                    "flex items-center gap-2.5 rounded-md",
                    full ? "min-h-11 px-2.5 py-1.5" : "justify-center",
                    full && (active ? "bg-primary-soft" : "hover:bg-muted"),
                  )}
                >
                  {full ? (
                    <>
                      <span className="min-w-0 flex-1">
                        <span className={cn("block truncate text-subhead", active ? "font-semibold text-primary" : "text-foreground")}>{m.name}</span>
                        <span className="block truncate text-footnote text-muted-foreground">
                          {m.line || m.hall_name || "—"} · {m.document_count} Dok.
                        </span>
                      </span>
                      <span
                        className={cn("size-2 shrink-0 rounded-full", status.tone === "ok" ? "bg-ok" : status.tone === "busy" ? "animate-pulse bg-primary" : "bg-warn")}
                        aria-label={status.label}
                        role="img"
                      />
                    </>
                  ) : (
                    <span
                      className={cn(
                        "grid size-11 place-items-center rounded-md text-footnote font-semibold",
                        active ? "bg-primary-soft text-primary" : "bg-bg-fill text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {m.name.slice(0, 2).toUpperCase()}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
        <Link
          href="/werk"
          onClick={onNavigate}
          className={cn("mt-1 flex min-h-11 items-center gap-2.5 rounded-md px-2.5 text-subhead text-primary hover:bg-muted", !full && "mx-auto mt-3.5 size-11 justify-center px-0")}
          title="Maschine hinzufügen"
        >
          <Plus className="size-5 shrink-0" />
          {full && <span>Maschine hinzufügen</span>}
        </Link>
      </div>

      <div className={cn("space-y-0.5 border-t-[0.5px] border-border px-2 py-2", !full && "space-y-2 px-3")}>
        {navLink("/werk", "Werk", Factory, pathname === "/werk" || pathname.startsWith("/werk/halle"))}
      </div>

      {full && (
        <div className="border-t-[0.5px] border-border px-3 py-2.5 text-footnote">
          <div className="truncate text-foreground">{me?.email ?? (me?.via === "api_key" ? "Dienstzugang" : "Lokal, ohne Anmeldung")}</div>
          {budget && (
            <div className={cn(budget.exceeded && "text-warn")} data-testid="rail-month-cost">
              KI diesen Monat {costText(budget.month_cents)}
              {budget.cap_cents !== null && ` von ${costText(budget.cap_cents)}`}
            </div>
          )}
        </div>
      )}
    </nav>
  );
}
