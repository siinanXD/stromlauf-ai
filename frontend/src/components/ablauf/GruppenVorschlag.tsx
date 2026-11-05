"use client";

import { useEffect, useRef, useState } from "react";

import { MAX_JE_ANLAGE, startHindernis, verschiebe, type Gruppierung } from "@/components/ablauf/ordner";
import { formatWert, type Vorschlaege } from "@/components/ablauf/vorschlag";

const QUELLE = { ordner: "Ordner", kennung: "Kennung", mensch: "Mensch" } as const;

/** Erkannte Anlagen prüfen: Namen ändern, Dateien verschieben, Unzugeordnetes zuordnen (ein Ähnlichkeits-Vorschlag erst nach „Übernehmen“), dann alle starten. */
export function GruppenVorschlag({
  gruppierung,
  vorschlaege = {},
  vorschlagHinweis = null,
  onChange,
  onStart,
  onAbbrechen,
  disabled = false,
}: {
  gruppierung: Gruppierung;
  vorschlaege?: Vorschlaege;
  /** Stand der Ähnlichkeitsprüfung („wird geprüft …“ oder warum es keinen Vorschlag gibt). */
  vorschlagHinweis?: string | null;
  onChange: (g: Gruppierung) => void;
  onStart: () => void;
  onAbbrechen: () => void;
  disabled?: boolean;
}) {
  const { gruppen, unzugeordnet } = gruppierung;
  const hindernis = startHindernis(gruppierung);
  // Nach dem Verschieben hängt die Datei in einer anderen Liste (neu eingehängt): Fokus dorthin zurückgeben.
  const selects = useRef(new Map<string, HTMLSelectElement>());
  const fokus = useRef<string | null>(null);
  useEffect(() => {
    if (fokus.current === null) return;
    selects.current.get(fokus.current)?.focus();
    fokus.current = null;
  }, [gruppierung]);

  const verschiebeNach = (pfad: string, ziel: string) => {
    fokus.current = pfad;
    onChange(verschiebe(gruppierung, pfad, ziel));
  };

  const zeile = (pfad: string, eigene: string | null) => {
    const v = eigene === null ? vorschlaege[pfad] : undefined;
    const vorgeschlagen = v && gruppen.find((g) => g.id === v.gruppeId);
    return (
      <Zeile
        key={pfad}
        pfad={pfad}
        vorschlag={v && vorgeschlagen ? { name: vorgeschlagen.name || "(ohne Namen)", wert: v.wert, onUebernehmen: () => verschiebeNach(pfad, v.gruppeId) } : undefined}
        ziele={gruppen.filter((g) => g.id !== eigene)}
        mitOhne={eigene !== null}
        disabled={disabled}
        selectRef={(el) => {
          if (el) selects.current.set(pfad, el);
          else selects.current.delete(pfad);
        }}
        onVerschiebe={(ziel) => verschiebeNach(pfad, ziel)}
      />
    );
  };

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
            {g.dateien.length > MAX_JE_ANLAGE && (
              <p className="w-full text-footnote text-danger">
                {g.name.trim() || "Anlage"}: {g.dateien.length} Dateien, höchstens {MAX_JE_ANLAGE} je Anlage
              </p>
            )}
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
            {vorschlagHinweis && (
              <p role="status" className="text-footnote text-muted-foreground">
                {vorschlagHinweis}
              </p>
            )}
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
          disabled={disabled || hindernis !== null}
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
      <p role="status" className="text-footnote text-muted-foreground">
        {hindernis}
      </p>
    </section>
  );
}

/** Eine Datei mit Zielauswahl; verschoben wird erst per Knopf, die Auswahl allein ändert nichts (WCAG 3.2.2). */
function Zeile({
  pfad,
  vorschlag,
  ziele,
  mitOhne,
  disabled,
  selectRef,
  onVerschiebe,
}: {
  pfad: string;
  vorschlag?: { name: string; wert: number; onUebernehmen: () => void };
  ziele: Gruppierung["gruppen"];
  mitOhne: boolean;
  disabled: boolean;
  selectRef: (el: HTMLSelectElement | null) => void;
  onVerschiebe: (ziel: string) => void;
}) {
  const [ziel, setZiel] = useState("");
  return (
    <li className="flex flex-wrap items-center gap-2 py-1 pl-3 pr-1">
      <span className="min-w-0 flex-1 truncate font-mono text-footnote" title={pfad}>
        {pfad}
      </span>
      {vorschlag && (
        <div className="order-last flex w-full flex-wrap items-center gap-2">
          <span className="min-w-0 flex-1 text-footnote text-muted-foreground">
            Vorschlag: {vorschlag.name} · Ähnlichkeit {formatWert(vorschlag.wert)}
          </span>
          <button
            type="button"
            disabled={disabled}
            onClick={vorschlag.onUebernehmen}
            aria-label={`${pfad} nach ${vorschlag.name} übernehmen`}
            className="min-h-11 shrink-0 rounded-md border border-border bg-card px-3 text-footnote font-medium hover:bg-muted disabled:opacity-50"
          >
            Übernehmen
          </button>
        </div>
      )}
      <select
        ref={selectRef}
        value={ziel}
        disabled={disabled}
        aria-label={`${pfad} verschieben nach`}
        onChange={(e) => setZiel(e.target.value)}
        className="min-h-11 shrink-0 rounded-md border border-border bg-card px-2 text-footnote"
      >
        <option value="" disabled>
          Verschieben nach …
        </option>
        {ziele.map((g) => (
          <option key={g.id} value={g.id}>
            {g.name || "(ohne Namen)"}
          </option>
        ))}
        <option value="neu">neue Anlage</option>
        {mitOhne && <option value="ohne">ohne</option>}
      </select>
      <button
        type="button"
        disabled={disabled || ziel === ""}
        onClick={() => onVerschiebe(ziel)}
        aria-label={`${pfad} jetzt verschieben`}
        className="min-h-11 shrink-0 rounded-md border border-border bg-card px-3 text-footnote font-medium hover:bg-muted disabled:opacity-50"
      >
        Verschieben
      </button>
    </li>
  );
}
