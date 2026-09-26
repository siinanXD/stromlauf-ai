# Blaupause-Frontend und Maschinen-Draufsicht (MVP)

Stand: 2026-09-26 · Status: Design freigegeben (Figma Richtung C), Spec vom Agenten erstellt

## Ziel

1. Stromlauf AI bekommt ein einheitliches, professionelles Erscheinungsbild ("Blaupause"),
   das sich wie ein technisches Zeichnungsblatt anfühlt.
2. Jede Maschine bekommt eine **Draufsicht**: Baugruppen und Feldgeräte (-M1, -B1, -S3 …) als
   bemaßte Formen in mm. Die Draufsicht wird aus einer Skizze in den Unterlagen per Claude Vision
   vorgeschlagen oder manuell gezeichnet. Klick auf ein Teil zeigt alles, was die Doku zu diesem
   BMK weiß.

Erfolg: Für FB-01 lässt sich aus der Referenzskizze eine Draufsicht erzeugen, bestätigen und
per Klick auf `-M1` zu Stückliste, Klemmen, SPS-Adresse und Fehlern springen.

## Vorgaben

- Design: Figma `25Zi2sbyA5rXJcwViTqB10`, Frame 5:273 (Richtung C, Akzent Blau `#1E5BD8`,
  Rot `#D7263D` nur für Fehler/Not-Halt). Nur helles Theme im MVP.
- Stack bleibt: Next.js 16 / React 19.2 / Tailwind 4, FastAPI + SQLAlchemy, Tabellen per `create_all`.
- Neue Frontend-Abhängigkeiten (alle MIT/ISC, Lizenz-Policy grün): shadcn/ui (Radix), `@xyflow/react`,
  `@tanstack/react-table`, `cmdk`, `lucide-react`, `sonner`.
- Skizzenformat der echten Unterlagen ist unbekannt → ein festes **Datenformat**, zwei Eingabewege.

## Nicht im MVP

Hallen-Baukasten auf React Flow, TanStack Query, Dark Mode, 3D, automatisches Finden der
Skizzenseite in PDFs (Nutzer wählt Bild oder Dokumentseite), Rotation per Maus (nur Feld).

## 1. Designsystem

- `globals.css`: Blaupause-Tokens ersetzen die heutigen Variablen (gleiche Namen, damit
  bestehende Klassen weiter greifen) plus `--grid`, `--nav`. Dark-Mode-Block entfällt.
- Schriften über `next/font/google`: IBM Plex Sans (UI), IBM Plex Mono (Überschriften, BMK,
  Adressen, Maße). Radius 0.
- shadcn/ui initialisieren, Komponenten: button, badge, input, tabs, table, dialog, tooltip,
  command, sonner. Theme-Variablen von shadcn auf die Blaupause-Tokens mappen.
- Hilfskomponente `Tag` (Mono, Akzentfarbe, klickbar) für BMK/Adressen überall gleich.

## 2. App-Shell

- `AppShell` mit linker Navigationsleiste (dunkel `#14263D`, Icons + Label: Chat, Werk) und
  Kopfzeile (Breadcrumb, globale Suche, Backend-Status).
- **Globale Suche** (`cmdk`, Strg+K): tippt man `-K1`, `X1:5` oder `E0.0`, kommen Treffer
  gruppiert nach Maschine. Neuer Endpoint `GET /api/tags/search?q=` sucht in `TagOccurrence`
  (normalisiert, Präfix-Treffer, max. 30) und liefert Tag, Typ, Maschine(n) der Quelle.
  Auswahl öffnet `/werk/maschine/{id}?tag=…`.
- Chat- und Werk-Seiten laufen in der Shell; ihr Innenleben wird nur auf Tokens umgestellt.

## 3. Datenformat "Maschinen-Layout"

```
MachineLayout  (1:1 zu Machine)
  id, machine_id (unique), width_mm, depth_mm,
  image_path?  (hochgeladene Skizze)  | document_id? + page?  (Seite aus der Doku)
  scale_note  ("M 1:50", frei), updated_at

LayoutPart
  id, layout_id, tag (normalisiert, darf leer sein), label, kind,
  shape: "rect" | "circle", x_mm, y_mm, w_mm, h_mm, rotation_deg,
  confidence?, origin: "manual" | "vision", confirmed
```

Ursprung oben links, x nach rechts, y nach unten, Werte in mm. `kind` aus fester Liste:
Motor, Sensor, Taster, Not-Halt, Leuchte, Schaltschrank, Band/Förderer, Rahmen, Schutztür, Sonstiges.

API (in `plant.py` bzw. neuem Router `layout.py`):

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/machines/{id}/layout` | Layout + Teile, 404 wenn keins |
| PUT | `/api/machines/{id}/layout` | anlegen/ändern (Maße, Quelle) |
| POST | `/api/machines/{id}/layout/image` | Skizze hochladen |
| GET | `/api/machines/{id}/layout/image` | Skizze ausliefern (Hintergrund) |
| POST | `/api/layouts/{id}/parts` | Teil anlegen |
| PATCH/DELETE | `/api/layout-parts/{id}` | Teil ändern/löschen |
| POST | `/api/layouts/{id}/detect` | Vision-Vorschläge (kostet API-Tokens) |
| GET | `/api/layouts/{id}/export` | JSON im Standardformat |

## 4. Vision-Erkennung

`ingestion/layout_vision.py`, gleiches Muster wie `cabinet_vision.py`:
Bildquelle = hochgeladene Skizze oder `render_page_png(document, page)`. Prompt fordert
Draufsicht-Teile als relative Rechtecke (0..1), `kind` aus der festen Liste, BMK nur wenn lesbar,
plus optional erkannte Gesamtmaße in mm. Bekannte Geräte-BMK der Quelle werden als Hinweis
mitgegeben. Reine Funktion `to_parts(items, width_mm, depth_mm)` rechnet in mm um, klemmt Werte,
normalisiert Tags und verwirft Unsinn — die ist unit-getestet. Erkannte Gesamtmaße setzen
`width_mm/depth_mm` nur, wenn das Layout noch keine hat. Alte unbestätigte Vision-Teile werden
ersetzt, bestätigte bleiben.

## 5. Draufsicht im Frontend

Maschinenseite wird in Tabs gegliedert: **Draufsicht · Fehler · Schaltschrank · Dokumente**.

- `LayoutCanvas` auf React Flow: Hintergrund-Raster (10/100 mm), optional Skizze halbtransparent
  darunter, Teile als eigene Node-Typen (Rechteck/Kreis), Maßstab mm→px mit Zoom.
  Drag + Resize (NodeResizer) speichern per PATCH beim Loslassen.
- Unbestätigte Teile gestrichelt blau mit Sicherheit in %; Kopfleiste zeigt
  "N Vorschläge prüfen" → alle bestätigen / einzeln bestätigen / verwerfen.
- Werkzeuge: Auswahl, Rechteck, Kreis; Schriftfeld unten rechts (Maschine, Maße, Quelle).
- Seitenpanel "Ausgewählt": BMK, Bezeichnung, Art (editierbar), darunter
  Treffer aus `lookup_tag` (Stückliste, Klemmen, SPS, Seiten mit Sprung in `PageViewer`) und
  Fehler der Maschine mit diesem Tag.
- Leerer Zustand: "Skizze hochladen", "Dokumentseite wählen" oder "Leer beginnen" (Maße eingeben).
- Fehlerliste als TanStack-Table (sortieren, Filter nach Tag), Bearbeiten im Dialog.

## 6. Referenzbeispiel FB-01

- `examples/foerderband/08_Aufstellungsplan_FB-01.png`: per Skript (`scripts/make_layout_sketch.py`,
  Pillow) gezeichnete Draufsicht mit Band 6000 × 800 mm, -M1, -B1, -B2, Tastern, Not-Halt,
  Schaltschrank, Maßkette und Schriftfeld. BMK aus der Stückliste.
- `08_Aufstellungsplan_FB-01.json`: Soll-Layout im Standardformat.
- `load_example.py` legt das Layout aus dem JSON an (ohne Vision, ohne Kosten); mit `--vision`
  kann die Erkennung gegen das Soll verglichen werden.

## Fehlerbehandlung

Backend: 404/400/415 wie bestehende Endpunkte, Vision-Fehler → 502 mit Meldung, fehlender
API-Key → 502 "ANTHROPIC_API_KEY fehlt". Frontend: jede Aktion zeigt Fehler per `sonner`-Toast,
Speichern nach Drag ist optimistisch und wird bei Fehler zurückgesetzt.

## Tests

- Backend pytest: `to_parts` (Umrechnung, Klemmen, Tag-Normalisierung, ungültige Einträge),
  Tag-Suche-Normalisierung als reine Funktion. API-Tests nur, wenn eine Test-DB ohne großen
  Aufwand möglich ist (heute gibt es keine DB-Tests).
- Frontend: `npm run lint`, `npx tsc --noEmit`, `npm run build`; manuelle Prüfung im Browser-Pane
  gegen den Figma-Frame (Screenshot-Vergleich).
- End-to-end: Beispiel laden, Draufsicht FB-01 öffnen, `-M1` anklicken, Treffer sichtbar.

## Reihenfolge

1. Designsystem + Shell  2. Backend-Layout (Modell, API, Tests)  3. Referenzskizze + Loader
4. Draufsicht-Canvas + Panel  5. Tabs, Fehlertabelle, globale Suche  6. Vision-Erkennung
