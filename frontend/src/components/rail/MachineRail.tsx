"use client";

import { Calculator, Factory, Gauge, LayoutList, MessageSquare, Moon, Plus, Search, Sun } from "lucide-react";
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
 * darunter Werk und die Nebenmodule, unten Nutzer und Monatskosten. `mode="icons"` ist die 72-px-Variante.
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
        "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] hover:bg-nav-hover hover:text-nav-foreground-strong",
        active ? "bg-nav-hover text-nav-foreground-strong" : "text-nav-foreground",
        !full && "justify-center px-0",
      )}
    >
      <Icon className="size-4 shrink-0" />
      {full && <span>{label}</span>}
    </Link>
  );

  return (
    <nav aria-label="Maschinen und Bereiche" className={cn("flex h-full flex-col bg-nav text-nav-foreground", full ? "w-[280px]" : "w-[72px]")}>
      <div className={cn("flex items-center gap-2.5 px-3 pt-3.5 pb-2", !full && "justify-center px-0")}>
        <Link href="/" onClick={onNavigate} className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary font-mono text-lg font-semibold text-primary-foreground" title="Stromlauf AI">
          S
        </Link>
        {full && (
          <div className="min-w-0">
            <div className="truncate text-[13px] font-semibold text-nav-foreground-strong">Stromlauf AI</div>
            <div className="truncate text-[11px]">{me?.workspace.name ?? "Werk"}</div>
          </div>
        )}
        <button type="button" onClick={toggleTheme} className={cn("rounded-md p-1.5 hover:bg-nav-hover hover:text-nav-foreground-strong", full && "ml-auto")} aria-label={theme === "dark" ? "Helles Design" : "Dunkles Design"} title="Design wechseln">
          {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>
      </div>

      {full && (
        <label className="mx-3 mb-2 flex h-9 items-center gap-2 rounded-lg border border-[#2a2f39] bg-nav-hover px-2.5 text-[13px]">
          <Search className="size-3.5 shrink-0" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Maschine suchen …"
            aria-label="Maschine suchen"
            className="min-w-0 flex-1 bg-transparent text-nav-foreground-strong outline-none placeholder:text-nav-foreground"
          />
        </label>
      )}

      <div className={cn("px-2", !full && "px-3")}>
        {navLink("/werk/maschinen", "Alle Maschinen", LayoutList, pathname === "/werk/maschinen")}
        {navLink("/", "Chat über alles", MessageSquare, pathname === "/")}
      </div>

      <div className="mt-1 min-h-0 flex-1 overflow-y-auto px-2 [scrollbar-width:thin]" data-testid="machine-rail">
        {full && <p className="px-2.5 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-[0.06em]">Maschinen</p>}
        {machines === null && full && <p className="px-2.5 py-1 text-xs">Lade …</p>}
        {machines && machines.length === 0 && full && <p className="px-2.5 py-1 text-xs">Noch keine Maschine. Unten „Maschine hinzufügen“.</p>}
        <ul className="space-y-0.5">
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
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 hover:bg-nav-hover",
                    active ? "bg-nav-hover text-nav-foreground-strong" : "text-nav-foreground",
                    !full && "justify-center px-0",
                  )}
                >
                  {full ? (
                    <>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px] font-medium text-nav-foreground-strong">{m.name}</span>
                        <span className="block truncate text-[11px]">
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
                    <span className="grid size-8 place-items-center rounded-md border border-[#2a2f39] font-mono text-[11px] font-semibold text-nav-foreground-strong">
                      {m.name.slice(0, 2).toUpperCase()}
                    </span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
        <Link href="/werk" onClick={onNavigate} className={cn("mt-1 flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] hover:bg-nav-hover hover:text-nav-foreground-strong", !full && "justify-center px-0")} title="Maschine hinzufügen">
          <Plus className="size-4 shrink-0" />
          {full && <span>Maschine hinzufügen</span>}
        </Link>
      </div>

      <div className={cn("border-t border-[#2a2f39] px-2 py-2", !full && "px-3")}>
        {navLink("/werk", "Werk", Factory, pathname === "/werk" || pathname.startsWith("/werk/halle"))}
        {full ? (
          <details className="group">
            <summary className="cursor-pointer list-none rounded-lg px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-[0.06em] hover:text-nav-foreground-strong">Mehr</summary>
            {navLink("/planung", "Planung", Calculator, pathname.startsWith("/planung"))}
            {navLink("/leitstand", "Leitstand", Gauge, pathname.startsWith("/leitstand"))}
          </details>
        ) : (
          <>
            {navLink("/planung", "Planung", Calculator, pathname.startsWith("/planung"))}
            {navLink("/leitstand", "Leitstand", Gauge, pathname.startsWith("/leitstand"))}
          </>
        )}
      </div>

      {full && (
        <div className="border-t border-[#2a2f39] px-3 py-2.5 text-[11px]">
          <div className="truncate text-nav-foreground-strong">{me?.email ?? (me?.via === "api_key" ? "Dienstzugang" : "Lokal, ohne Anmeldung")}</div>
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
