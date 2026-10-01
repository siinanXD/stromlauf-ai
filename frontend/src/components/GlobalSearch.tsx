"use client";

import { MessageSquare } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Command, CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { searchTags, type TagSearchHit } from "@/lib/api";

const TYPE_LABELS: Record<string, string> = {
  device: "Betriebsmittel",
  device_pin: "Geräteanschluss",
  terminal: "Klemme",
  plc_address: "SPS-Adresse",
  plc_symbol: "Symbol",
};

/** Strg+K: BMK, Klemmen und SPS-Adressen ueber alle Maschinen finden und direkt hinspringen. */
export function GlobalSearch() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<TagSearchHit[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    const onOpen = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("stromlauf:search", onOpen);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("stromlauf:search", onOpen);
    };
  }, []);

  useEffect(() => {
    if (!query.trim()) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      searchTags(query)
        .then((result) => !cancelled && setHits(result))
        .catch(() => !cancelled && setHits([]))
        .finally(() => !cancelled && setLoading(false));
    }, 200);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [query]);

  const visible = query.trim() ? hits : [];
  const machines = new Map<string, { name: string; hits: TagSearchHit[] }>();
  const orphans: TagSearchHit[] = [];
  for (const hit of visible) {
    if (!hit.machines.length) orphans.push(hit);
    for (const machine of hit.machines) {
      const entry = machines.get(machine.id) ?? { name: machine.name, hits: [] };
      entry.hits.push(hit);
      machines.set(machine.id, entry);
    }
  }

  function go(href: string) {
    setOpen(false);
    setQuery("");
    router.push(href);
  }

  return (
    <CommandDialog
      open={open}
      onOpenChange={setOpen}
      title="Suche"
      description="Betriebsmittel, Klemmen und SPS-Adressen finden"
      className="rounded-none!"
    >
      <Command shouldFilter={false}>
      {/* Treffer kommen gefiltert vom Backend, cmdk soll nicht erneut filtern */}
      <CommandInput value={query} onValueChange={setQuery} placeholder="-K12, X1:5, E0.0 …" className="font-mono" />
      <CommandList>
        {query.trim() && !loading && <CommandEmpty>Keine Treffer für „{query.trim()}“.</CommandEmpty>}
        {!query.trim() && <div className="px-3 py-6 text-center text-sm text-muted-foreground">BMK, Klemme oder SPS-Adresse eingeben.</div>}
        {[...machines.entries()].map(([machineId, entry]) => (
          <CommandGroup key={machineId} heading={entry.name}>
            {entry.hits.map((hit) => (
              <CommandItem
                key={`${machineId}-${hit.tag}`}
                value={`${machineId} ${hit.tag}`}
                onSelect={() => go(`/werk/maschine/${machineId}?tag=${encodeURIComponent(hit.tag)}`)}
              >
                <span className="font-mono text-primary">{hit.tag}</span>
                <span className="text-xs text-muted-foreground">{TYPE_LABELS[hit.tag_type] ?? hit.tag_type}</span>
                <span className="ml-auto text-xs text-muted-foreground">{hit.occurrences}×</span>
              </CommandItem>
            ))}
          </CommandGroup>
        ))}
        {orphans.length > 0 && (
          <CommandGroup heading="Ohne Maschine – im Chat fragen">
            {orphans.map((hit) => (
              <CommandItem key={`chat-${hit.tag}`} value={`chat ${hit.tag}`} onSelect={() => go(`/?q=${encodeURIComponent(`Was ist ${hit.tag}?`)}`)}>
                <MessageSquare className="size-3.5" />
                <span className="font-mono text-primary">{hit.tag}</span>
                <span className="ml-auto text-xs text-muted-foreground">{hit.occurrences}×</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
      </CommandList>
      </Command>
    </CommandDialog>
  );
}
