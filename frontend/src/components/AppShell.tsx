"use client";

import { Menu, Search, X } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Fragment, useEffect, useState, type ReactNode } from "react";

import { GlobalSearch } from "@/components/GlobalSearch";
import { MachineRail } from "@/components/rail/MachineRail";
import { api, auth, costs, type AuthMe, type WorkspaceBudget } from "@/lib/api";
import { costText } from "@/lib/format";
import { clearToken, getToken, redirectToLogin, tokenValid } from "@/lib/auth";
import { cn } from "@/lib/utils";

export interface Crumb {
  label: string;
  href?: string;
}

/**
 * Rahmen aller Seiten: links die Maschinen-Rail (280 px ab 1280, 72-px-Icon-Rail von 768 bis 1279, Drawer darunter),
 * Kopfzeile mit Pfad, Suche und Status, Banner bei erreichtem KI-Monatslimit.
 */
export function AppShell({ breadcrumb, children }: { breadcrumb: Crumb[]; children: ReactNode }) {
  const pathname = usePathname();
  const [online, setOnline] = useState<boolean | null>(null);
  const [me, setMe] = useState<AuthMe | null>(null);
  const [budget, setBudget] = useState<WorkspaceBudget | null>(null);
  const [drawer, setDrawer] = useState(false);

  useEffect(() => {
    // Monatslimit: Banner, sobald der Workspace am Limit ist (die API lehnt dann jeden KI-Aufruf mit 402 ab)
    costs
      .budget()
      .then(setBudget)
      .catch(() => setBudget(null));
    const onExceeded = () => costs.budget().then(setBudget).catch(() => {});
    window.addEventListener("stromlauf:budget", onExceeded);
    return () => window.removeEventListener("stromlauf:budget", onExceeded);
  }, [pathname]);

  async function raiseCap() {
    if (!budget) return;
    const current = budget.cap_cents === null ? "" : String(Math.round(budget.cap_cents / 100));
    const answer = window.prompt("Neues KI-Monatslimit in Euro (leer = kein Limit):", current);
    if (answer === null) return;
    const euros = answer.trim() === "" ? null : Number(answer.replace(",", "."));
    if (euros !== null && !Number.isFinite(euros)) return;
    try {
      setBudget(await costs.setBudget(euros === null ? null : Math.round(euros * 100)));
    } catch (err) {
      window.alert((err as Error).message);
    }
  }

  useEffect(() => {
    api
      .health()
      .then(() => setOnline(true))
      .catch(() => setOnline(false));
    // Login-Modus: ohne gueltiges Token zur Anmeldung; sonst Nutzer und Workspace anzeigen
    auth
      .mode()
      .then((mode) => {
        if (mode.mode === "jwt" && !tokenValid(getToken())) {
          clearToken();
          redirectToLogin();
          return;
        }
        return auth.me().then(setMe);
      })
      .catch(() => {});
  }, []);

  function logout() {
    clearToken();
    setMe(null);
    redirectToLogin();
  }

  return (
    <div className="flex h-full">
      {/* >= 1280: volle Rail; 768-1279: Icon-Rail; darunter Drawer */}
      <aside className="hidden shrink-0 md:block xl:hidden" data-testid="rail-icons">
        <MachineRail mode="icons" me={me} />
      </aside>
      <aside className="hidden shrink-0 xl:block" data-testid="rail-full">
        <MachineRail mode="full" me={me} />
      </aside>
      {drawer && (
        <div className="fixed inset-0 z-50 flex md:hidden" role="dialog" aria-modal="true" aria-label="Maschinen">
          <div className="h-full w-[280px] max-w-[88vw] shadow-xl" data-testid="rail-drawer">
            <MachineRail mode="full" me={me} onNavigate={() => setDrawer(false)} />
          </div>
          <button type="button" className="flex-1 bg-black/50" aria-label="Menü schließen" onClick={() => setDrawer(false)} />
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-card px-4 md:px-6">
          <button type="button" onClick={() => setDrawer((d) => !d)} className="grid size-9 place-items-center rounded-lg border border-border md:hidden" aria-label={drawer ? "Menü schließen" : "Maschinen öffnen"} aria-expanded={drawer} data-testid="rail-toggle">
            {drawer ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
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

          {me?.via === "jwt" && (
            <span className="ml-auto flex shrink-0 items-center gap-2 text-xs text-muted-foreground" title={me.email ?? ""}>
              <span className="hidden truncate sm:inline">{me.workspace.name}</span>
              <button type="button" onClick={logout} className="border border-border px-2 py-0.5 hover:border-primary hover:text-primary">
                Abmelden
              </button>
            </span>
          )}
          <span className={cn("flex shrink-0 items-center gap-2 text-xs text-muted-foreground", me?.via === "jwt" ? "" : "ml-auto")}>
            <span
              className={cn("size-2 rounded-full", online === null ? "bg-border" : online ? "bg-ok" : "bg-danger")}
            />
            {online === null ? "Verbinde …" : online ? "Backend verbunden" : "Backend nicht erreichbar"}
          </span>
        </header>

        {budget?.exceeded && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-danger/40 bg-danger/10 px-6 py-2 text-sm" role="alert">
            <span>
              KI-Monatslimit erreicht: {costText(budget.month_cents)} von {costText(budget.cap_cents ?? 0)} verbraucht. Chat, Vision und
              Ablauf-Extraktion sind bis zum Monatswechsel gesperrt.
            </span>
            {(me === null || me.workspace.role === "admin") && (
              <button type="button" onClick={raiseCap} className="border border-danger px-2 py-0.5 text-danger hover:bg-danger hover:text-white">
                Limit erhöhen
              </button>
            )}
          </div>
        )}
        <main className="min-h-0 flex-1">{children}</main>
      </div>
      <GlobalSearch />
    </div>
  );
}
