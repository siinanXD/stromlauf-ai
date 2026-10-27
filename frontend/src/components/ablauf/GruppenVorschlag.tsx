"use client";

import { kannStarten, verschiebe, type Gruppierung } from "@/components/ablauf/ordner";

const QUELLE = { ordner: "Ordner", kennung: "Kennung", mensch: "Mensch" } as const;

/** Erkannte Anlagen prüfen: Namen ändern, Dateien verschieben, Unzugeordnetes zuordnen, dann alle starten. */
export function GruppenVorschlag({
  gruppierung,
  onChange,
  onStart,
  onAbbrechen,
  disabled = false,
}: {
  gruppierung: Gruppierung;
  onChange: (g: Gruppierung) => void;
  onStart: () => void;
  onAbbrechen: () => void;
  disabled?: boolean;
}) {
  const { gruppen, unzugeordnet } = gruppierung;

  /** Auswahl "Verschieben nach …" für eine Datei; die eigene Gruppe ist nicht wählbar. */
  const waehle = (pfad: string, eigene: string | null) => (
    <select
      value=""
      disabled={disabled}
      aria-label={`${pfad} verschieben nach`}
      onChange={(e) => e.target.value && onChange(verschiebe(gruppierung, pfad, e.target.value))}
      className="min-h-11 shrink-0 rounded-md border border-border bg-card px-2 text-footnote"
    >
      <option value="" disabled>
        Verschieben nach …
      </option>
      {gruppen
        .filter((g) => g.id !== eigene)
        .map((g) => (
          <option key={g.id} value={g.id}>
            {g.name || "(ohne Namen)"}
          </option>
        ))}
      <option value="neu">neue Anlage</option>
      {eigene && <option value="ohne">ohne</option>}
    </select>
  );

  const zeile = (pfad: string, eigene: string | null) => (
    <li key={pfad} className="flex flex-wrap items-center gap-2 py-1 pl-3 pr-1">
      <span className="min-w-0 flex-1 truncate font-mono text-footnote" title={pfad}>
        {pfad}
      </span>
      {waehle(pfad, eigene)}
    </li>
  );

  return (
    <section aria-label="Erkannte Anlagen" className="space-y-3">
      <h2 className="text-headline font-semibold">
        {gruppen.length} {gruppen.length === 1 ? "Anlage" : "Anlagen"} erkannt
      </h2>
      {gruppen.map((g, i) => (
        <div key={g.id} className="rounded-md border border-border">
          <div className="flex flex-wrap items-center gap-2 border-b border-border p-2">
            <input
              type="text"
              value={g.name}
              disabled={disabled}
              aria-label={`Name der Anlage ${i + 1}`}
              onChange={(e) => onChange({ ...gruppierung, gruppen: gruppen.map((x) => (x.id === g.id ? { ...x, name: e.target.value } : x)) })}
              className="min-h-11 min-w-0 flex-1 rounded-md border border-border bg-background px-3 text-subhead"
            />
            <span className="rounded-md border border-border px-2 py-0.5 text-caption-1 text-muted-foreground">{QUELLE[g.quelle]}</span>
          </div>
          <ul className="divide-y divide-border" aria-label={`Dateien von Anlage ${i + 1}`}>
            {g.dateien.map((d) => zeile(d.pfad, g.id))}
          </ul>
        </div>
      ))}
      {unzugeordnet.length > 0 && (
        <div className="rounded-md border border-border">
          <div className="border-b border-border p-2">
            <h3 className="text-subhead font-semibold">Unzugeordnet</h3>
            <p className="text-footnote text-muted-foreground">Bitte zuordnen</p>
          </div>
          <ul className="divide-y divide-border" aria-label="Unzugeordnete Dateien">
            {unzugeordnet.map((d) => zeile(d.pfad, null))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onStart}
          disabled={disabled || !kannStarten(gruppierung)}
          className="min-h-11 rounded-md bg-primary px-4 text-subhead font-medium text-primary-foreground disabled:opacity-50"
        >
          Alle starten
        </button>
        <button
          type="button"
          onClick={onAbbrechen}
          disabled={disabled}
          className="min-h-11 rounded-md border border-border bg-card px-4 text-subhead font-medium hover:bg-muted disabled:opacity-50"
        >
          Verwerfen
        </button>
      </div>
    </section>
  );
}
