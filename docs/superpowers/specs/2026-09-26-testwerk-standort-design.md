# Testwerk Tissue, Teil 1: Standortplan und Testwerk

Stand: 2026-09-26 · Auftrag: Produktionswerk mit Grundstoffhalle (Papiermaschine in Sektoren),
6 Verarbeitungslinien, Fertigwarenlager mit LKW-Toren, Büro; später Auftragsdurchlauf und
Vorkalkulation. Entscheidungen des Nutzers: Domäne **Papier/Tissue**, Start mit **Standort + Testwerk**.
Recherche: `.ai/research/solution-comparisons/2026-09-26-werkssimulation.md`.

## Gesamtbild (4 Teile, je eigene Spec, Plan, PR)

1. **Standort + Testwerk** (diese Spec): Standortplan mit Hallen und Materialfluss zwischen Hallen,
   Linien/Sektoren in der Halle, Maschinen-Kennzahlen mit Quelle, Testwerk als Beispieldaten.
2. Vorkalkulation: Artikel, Rezeptur/Stückliste, Arbeitsplan je Artikel; Auftrag → Material, Dauer, Termin.
3. Durchlauf-Simulation: Büro-Stationen, Warteschlangen, Lager, Tore, LKW, Zeitplan, Simulationsuhr.
4. Test-Doku für komplexe Maschinen (generiert wie FB-01, keine fremde Herstellerdoku).

Für alle Teile gilt: deterministisch, kein LLM-/Vision-Aufruf, keine API-Kosten.

## Annahmen

- Demo-/Testwerk: fiktive Maschinen mit realen, belegten Kennzahlen. Keine Herstellernamen als
  Maschinennamen; das reale Vorbild steht nur in der Quelle der Kennzahl.
- „Kommissioniermaschine“ am Linienende = Palettierer. Kommissioniert wird im Lager (Teil 3).
- Ein Standort. Keine Tabelle `sites`, der Standortplan zeigt alle Hallen (YAGNI).

## Testwerk

| Halle | Art | Inhalt |
|---|---|---|
| Papiermaschine PM1 | Grundstoff | Sektoren S1 Stoffaufbereitung, S2 Chemikaliendosierung, S3 Stoffauflauf & Former, S4 Pressenpartie, S5 Yankee & Haube, S6 Aufrollung, dazu Mutterrollenpuffer |
| Verarbeitung | Verarbeitung | 6 Linien, je Hauptmaschine → Verpackung → Palettierer: Toilettenpapier, Küchenrolle, Servietten, Kosmetiktücher, Falthandtücher, Industrierollen |
| Lager & Versand | Lager | Palettenförderer, Stretchwickler & Etikettierer, Hochregallager, Kommissionierplatz, Verladetore 1–8 |
| Büro | Büro | keine Maschinen; Beschreibung nennt Kundenservice, Finanzen, Arbeitsvorbereitung, Einkauf, Versand, Geschäftsführung |

Materialfluss zwischen Hallen: PM1 → Verarbeitung „Mutterrollen“, Verarbeitung → Lager „Paletten“,
Büro → Verarbeitung „Aufträge“. In den Hallen: Fluss je Linie bzw. Sektorkette.

Kennzahlen mit Quelle (Auswahl): PM1 2,8 m / 2.200 m/min / ~30.000 t/a (Valmet Advantage DCT),
Toilettenpapier-Umroller 200 m/min, 10 Logs/min (Perini X3), Säge 135 Schnitte/min (PCMC),
Folienverpacker 220 Pakete/min (Casmatic CMW208), LKW 33 Europaletten, Beladung 30–90 min.
Werte ohne Herstellerangabe heißen „Richtwert“, abgeleitete Werte nennen die Rechnung.

Daten liegen in `examples/testwerk/testwerk.json`, der Lader `scripts/load_testwerk.py` legt sie über
die API an (`--refresh` ersetzt die vier Hallen gleichen Namens).

## Datenmodell

- `halls` + Spalten `kind` (generic|base|production|warehouse|office, Standard generic),
  `site_x`, `site_y`, `site_w`, `site_h` (Standortplan, px).
- `machines` + Spalte `line` (Linie/Sektor, Text, leer = keine Gruppe).
- Neue Tabelle `site_flows`: id, from_hall_id, to_hall_id, label.
- Neue Tabelle `machine_specs`: id, machine_id, position, label, value, unit, source.
- **Migration:** `create_all` legt nur Tabellen an. Neue Spalten auf bestehenden Tabellen kommen
  über eine Liste in `db.py` (`ALTER TABLE … ADD COLUMN IF NOT EXISTS`), idempotent beim Start.
  Alembic erst, wenn eine nicht-additive Änderung kommt (Umbenennen, Typwechsel).

## API

- `GET /api/site` → Hallen (Art, Rechteck, Anzahl Maschinen/Fehler, Linien, Mini-Layout der
  Maschinen: id, name, Typ, Position, Linie) + Standort-Flüsse. Hallen ohne Rechteck bekommen
  eine Standardposition im Raster.
- `PATCH /api/halls/{id}` zusätzlich `kind`, `site_x/y/w/h`.
- `PUT /api/site/flows` ersetzt alle Standort-Flüsse (wie Hallen-Flüsse).
- Maschine: `line` in Anlegen/Ändern/Ausgabe; Ausgabe `key_figure` (erste Kennzahl, z. B. „2.200 m/min“).
- `GET/PUT /api/machines/{id}/specs` (Liste ersetzen).

## Oberfläche (Blaupause, kein neues Token)

- **`/werk` = Standortplan** (React Flow): Hallen als Grundriss-Blöcke mit Kopfzeile
  „ART · NAME“ in Plex Mono, innen verkleinertes Maschinen-Layout mit Linienbändern; Fluss zwischen
  Hallen als blaue Pfeile mit Beschriftung; Schriftfeld „STANDORTPLAN“ unten rechts.
  Ziehen verschiebt, Griffe ändern die Größe, vom rechten Griff auf eine Halle zieht einen Fluss.
  Rechts: gewählte Halle (Art wählbar, Maschinen, Linien, „Halle öffnen“) und „Halle anlegen“.
  Rot nur für die Fehlerzahl einer Halle mit offenen Fehlern.
- **`/werk/halle/[id]` = Hallen-Baukasten** (bisheriger Inhalt von `/werk`): Linienbänder hinter den
  Kacheln (Hüllrechteck je `line`, Beschriftung oben links), Feld „Linie/Sektor“ im Auswahlpanel,
  Kennzahl auf der Kachel. Brotkrumen Werk › Halle › Maschine.
- **Maschinenseite:** neuer Tab **Kennzahlen** (Kennzahl | Wert | Einheit | Quelle), bearbeitbar.
- Mobil: Standortplan scroll- und zoombar, Panel unter dem Plan (wie Hallen-Baukasten).

## Tests

- pytest: Testwerk-JSON (4 Hallen, 6 Linien × 3 Maschinen, Flüsse zeigen auf vorhandene
  Maschinen, jede Kennzahl hat Quelle), Standardposition für Hallen ohne Rechteck, Spec-Validierung.
- vitest: Linienbänder aus Positionen, Skalierung des Mini-Layouts in den Hallenblock.
- Browser: Standortplan, Halle mit Linien, Kennzahlen-Tab; Lader gegen lokales Backend.
