"use client";

import { Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { awlNetworks, awlWhy, type AwlMissingReason, type AwlNetwork, type WhyData } from "@/lib/api";
import type { DetailRef } from "@/lib/detail";
import { cn } from "@/lib/utils";

import { WhyTree } from "./WhyTree";

/** Baustein = Teil vor " NW " in der Referenz ("FB 10 NW 2" -> "FB 10"). */
export function blockOf(network: AwlNetwork): string {
  return network.ref.split(" NW ")[0] || network.ref;
}

export function groupByBlock(networks: AwlNetwork[]): { block: string; networks: AwlNetwork[] }[] {
  const groups = new Map<string, AwlNetwork[]>();
  for (const n of networks) groups.set(blockOf(n), [...(groups.get(blockOf(n)) ?? []), n]);
  return [...groups].map(([block, items]) => ({ block, networks: items }));
}

const MISSING: Record<AwlMissingReason, string> = {
  no_program: "In der Dokumentation dieser Maschine liegt kein SPS-Programm (AWL).",
  unknown_output: "Dieser Ausgang kommt im Programm nicht vor.",
  not_written: "Kein Netzwerk schreibt diesen Ausgang.",
};

type Load<T> = { status: "loading" } | { status: "error" } | { status: "done"; data: T } | { status: "missing"; reason: AwlMissingReason };

/** Tab SPS im Aufbau: Bausteinliste, Netzwerke im Klartext und "Warum kommt … nicht?". */
export function SpsTab({ sourceId, onOpenDetail }: { sourceId: string; onOpenDetail: (detail: DetailRef) => void }) {
  const [load, setLoad] = useState<Load<AwlNetwork[]>>({ status: "loading" });
  const [block, setBlock] = useState<string | null>(null);
  const [output, setOutput] = useState("");
  const [why, setWhy] = useState<Load<WhyData> | null>(null);

  useEffect(() => {
    let cancelled = false;
    awlNetworks(sourceId)
      .then((r) => !cancelled && setLoad(r.ok ? { status: "done", data: r.data.networks } : { status: "missing", reason: r.reason }))
      .catch(() => !cancelled && setLoad({ status: "error" }));
    return () => {
      cancelled = true;
    };
  }, [sourceId]);

  const groups = useMemo(() => (load.status === "done" ? groupByBlock(load.data) : []), [load]);
  const current = groups.find((g) => g.block === block) ?? groups[0];

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    const text = output.trim();
    if (!text) return;
    setWhy({ status: "loading" });
    try {
      const r = await awlWhy(sourceId, text);
      setWhy(r.ok ? { status: "done", data: r.data } : { status: "missing", reason: r.reason });
    } catch {
      setWhy({ status: "error" });
    }
  }

  if (load.status === "loading") return <p className="p-3 text-sm text-muted-foreground">SPS-Programm wird geladen …</p>;
  if (load.status === "error") return <p className="p-3 text-sm text-muted-foreground">Das SPS-Programm konnte nicht geladen werden. Später erneut versuchen.</p>;
  if (load.status === "missing") return <p data-testid="sps-empty" className="p-3 text-sm text-muted-foreground">{MISSING[load.reason]}</p>;

  return (
    <div data-testid="sps-tab" className="flex h-full min-h-0 flex-col gap-3 overflow-auto p-3">
      <form className="flex max-w-md items-center gap-2" onSubmit={ask}>
        <label className="min-w-0 flex-1">
          <span className="sr-only">Ausgang für „Warum kommt … nicht?“</span>
          <Input value={output} onChange={(e) => setOutput(e.target.value)} placeholder="Warum kommt … nicht? z. B. A4.0" className="h-11" />
        </label>
        <Button type="submit" variant="outline" className="h-11">
          <Search /> Warum?
        </Button>
      </form>

      {why && (
        <section aria-label="Warum kommt der Ausgang nicht?" data-testid="why-result" className="rounded-lg border border-border bg-card p-3">
          {why.status === "loading" && <p className="text-sm text-muted-foreground">Wird gesucht …</p>}
          {why.status === "error" && <p className="text-sm text-muted-foreground">Die Rückverfolgung hat nicht geklappt. Erneut versuchen.</p>}
          {why.status === "missing" && <p className="text-sm text-muted-foreground">{MISSING[why.reason]}</p>}
          {why.status === "done" && <WhyTree data={why.data} onOpenDetail={onOpenDetail} />}
        </section>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-3 md:flex-row">
        <nav aria-label="Bausteine" className="shrink-0 md:w-48">
          <ul className="flex flex-row flex-wrap gap-1 md:flex-col">
            {groups.map((g) => (
              <li key={g.block}>
                <button
                  type="button"
                  aria-current={g.block === current?.block ? "true" : undefined}
                  onClick={() => setBlock(g.block)}
                  className={cn("min-h-11 w-full rounded-md px-3 text-left text-sm", g.block === current?.block ? "bg-accent font-semibold text-primary" : "text-muted-foreground hover:text-foreground")}
                >
                  {g.block}
                  <span className="ml-2 text-footnote">{g.networks.length}</span>
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <section aria-label={current ? `Netzwerke von ${current.block}` : "Netzwerke"} className="min-w-0 flex-1">
          <ol className="flex flex-col gap-3">
            {current?.networks.map((n) => (
              <li key={n.id} data-network={n.id} className="rounded-lg border border-border bg-card p-3">
                <h3 className="text-sm font-semibold">
                  Netzwerk {n.number}
                  {n.title ? <span className="font-normal text-muted-foreground">{` · ${n.title}`}</span> : null}
                </h3>
                {n.comment && <p className="text-footnote text-muted-foreground">{n.comment}</p>}
                <ul className="mt-1 flex flex-col gap-1">
                  {n.klartext.map((line, i) => (
                    <li key={i} className="text-sm">{line}</li>
                  ))}
                </ul>
                {n.other.length > 0 && <pre className="mt-2 overflow-x-auto font-mono text-[12px] text-muted-foreground">{n.other.join("\n")}</pre>}
              </li>
            ))}
          </ol>
        </section>
      </div>
    </div>
  );
}
