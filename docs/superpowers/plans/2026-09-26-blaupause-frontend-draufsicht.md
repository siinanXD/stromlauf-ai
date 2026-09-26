# Blaupause-Frontend und Maschinen-Draufsicht Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Blaupause-Designsystem mit App-Shell und globaler BMK-Suche, plus Maschinen-Draufsicht (Datenmodell in mm, Vision-Vorschläge, React-Flow-Editor) mit FB-01 als Referenz.

**Architecture:** Backend bekommt zwei Tabellen (`machine_layouts`, `layout_parts`), einen Router `app/api/layout.py` und `app/ingestion/layout_vision.py` nach dem Muster von `cabinet_vision.py`. Frontend bekommt shadcn/ui-Basis, `AppShell`, `LayoutCanvas` (React Flow) und eine in Tabs gegliederte Maschinenseite.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest · Next.js 16, React 19.2, Tailwind 4, shadcn/ui, @xyflow/react 12, @tanstack/react-table, cmdk, lucide-react, sonner.

**Spec:** `docs/superpowers/specs/2026-09-26-blaupause-frontend-draufsicht-design.md` · Design: Figma `25Zi2sbyA5rXJcwViTqB10` Frame `5:273`

## Global Constraints

- Tokens: bg `#F4F1E8`, surface `#FBF9F3`, surface-2 `#EFEBE0`, border `#AEB9C7`, text/nav `#14263D`, muted `#5A6A80`, accent `#1E5BD8`, accent-fg `#FFFFFF`, danger `#D7263D`, ok `#1F7A4D`, grid `#E3E7EC`. Radius 0. Nur helles Theme.
- Rot (`danger`) nur für Fehler und Not-Halt, nie für Auswahl.
- Schriften: IBM Plex Sans (UI), IBM Plex Mono (Überschriften, BMK, Adressen, Maße).
- Koordinaten in mm, Ursprung oben links, x rechts, y unten.
- `kind` ∈ Motor, Sensor, Taster, Not-Halt, Leuchte, Schaltschrank, Band/Förderer, Rahmen, Schutztür, Sonstiges.
- Neue Abhängigkeiten nur: shadcn/ui (+ Radix), @xyflow/react, @tanstack/react-table, cmdk, lucide-react, sonner.
- Next.js 16: vor jedem neuen Next-API-Gebrauch `frontend/node_modules/next/dist/docs/` lesen (frontend/AGENTS.md).
- Vision kostet API-Tokens: nie automatisch in Tests oder Loader ohne `--vision` aufrufen.
- UI-Texte deutsch, Code-Kommentare deutsch ohne Umlaute wie im Bestand.

## Review Focus

1. Layout mit `width_mm`/`depth_mm` = 0 (leer begonnen, Vision ohne Maße) → `to_parts` darf nicht teilen/abstürzen, nutzt Fallback 1000 × 1000 mm. Test in Task 1.
2. Teil wird über den Rand gezogen oder negativ → Backend klemmt auf `0 ≤ x ≤ width_mm - w_mm`. Test in Task 1 (`clamp_part`).
3. Suche mit `k1`, ` -x1:5 `, `%I0.0`, leer oder nur `-` → normalisiert bzw. leere Liste, kein 500. Test in Task 3.
4. Maschine ohne verknüpfte Quelle → Panel zeigt „Keine Dokumentation verknüpft“ statt leerer Fehlerzeilen. Prüfung in Task 9.
5. Maschine/Halle löschen → Layout-Skizze auf Platte wird mit gelöscht. Prüfung in Task 2.

---

### Task 0: Worktree lauffähig machen

**Files:** keine Repo-Dateien.

- [ ] **Step 1:** `.env` aus Hauptcheckout hardlinken, `backend/.venv` und `backend/data` als Junction verlinken (Memory `stromlauf-dev-setup`), in `frontend/` echtes `npm ci`.
- [ ] **Step 2:** `cd backend && .venv/Scripts/python -m pytest -q` → alle bestehenden Tests grün. `cd frontend && npx tsc --noEmit` → 0 Fehler.

### Task 1: Layout-Umrechnung (reine Funktionen)

**Files:**
- Create: `backend/app/ingestion/layout_geometry.py`
- Test: `backend/tests/test_layout_geometry.py`

**Interfaces:**
- Produces: `LAYOUT_KINDS: tuple[str, ...]`; `to_parts(items: list[dict], width_mm: float, depth_mm: float) -> list[dict]` (Keys: tag, label, kind, shape, x_mm, y_mm, w_mm, h_mm, rotation_deg, confidence); `clamp_part(x, y, w, h, width_mm, depth_mm) -> tuple[float, float, float, float]`; `FALLBACK_MM = 1000.0`.

- [ ] **Step 1: Tests schreiben**

```python
def test_to_parts_converts_relative_to_mm():
    [p] = to_parts([{"kind": "Motor", "tag": "m1", "x": 0.1, "y": 0.2, "w": 0.05, "h": 0.1, "confidence": 0.9}], 6000, 1000)
    assert (p["x_mm"], p["y_mm"], p["w_mm"], p["h_mm"]) == (600, 200, 300, 100)
    assert p["tag"] == "-M1" and p["kind"] == "Motor" and p["shape"] == "rect"

def test_to_parts_zero_size_uses_fallback():
    [p] = to_parts([{"kind": "Sensor", "x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}], 0, 0)
    assert p["x_mm"] == 500 and p["w_mm"] == 100

def test_to_parts_unknown_kind_becomes_sonstiges_and_garbage_dropped():
    parts = to_parts([{"kind": "Rakete", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}, {"kind": "Motor", "x": "abc"}], 1000, 1000)
    assert [p["kind"] for p in parts] == ["Sonstiges"]

def test_to_parts_circle_shape_and_clamped_to_bounds():
    [p] = to_parts([{"kind": "Not-Halt", "shape": "circle", "x": 0.98, "y": -0.2, "w": 0.1, "h": 0.1}], 1000, 1000)
    assert p["shape"] == "circle" and p["x_mm"] + p["w_mm"] <= 1000 and p["y_mm"] == 0

def test_clamp_part_keeps_part_inside():
    assert clamp_part(-50, 900, 200, 200, 1000, 1000) == (0, 800, 200, 200)
    assert clamp_part(0, 0, 5000, 10, 1000, 1000) == (0, 0, 1000, 10)
```

- [ ] **Step 2:** `.venv/Scripts/python -m pytest tests/test_layout_geometry.py -q` → FAIL (ImportError).
- [ ] **Step 3:** Implementieren. Minimale Teilgröße 1 mm; Tag über `normalize_tag`, leer bleibt leer; mm auf 1 Nachkommastelle runden.
- [ ] **Step 4:** Tests → PASS.
- [ ] **Step 5:** Commit `feat(layout): Umrechnung Vision-Rechtecke in mm`.

### Task 2: Datenmodell und Layout-API

**Files:**
- Modify: `backend/app/models.py` (nach `CabinetHotspot`), `backend/app/schemas.py`, `backend/app/main.py` (Router registrieren), `backend/app/api/plant.py` (`_remove_machine_files` um `machine.layout.image_path` erweitern)
- Create: `backend/app/api/layout.py`

**Interfaces:**
- Consumes: `to_parts`, `clamp_part`, `LAYOUT_KINDS` (Task 1).
- Produces: Modelle `MachineLayout` (`machine_layouts`), `LayoutPart` (`layout_parts`) gemäß Spec §3; `Machine.layout` (uselist=False, cascade delete-orphan). Schemas `LayoutIn{width_mm, depth_mm, document_id?, page?, scale_note}`, `LayoutPartIn`, `LayoutPartUpdate` (alles optional), `LayoutPartOut`, `LayoutOut{id, machine_id, width_mm, depth_mm, has_image, document_id, page, scale_note, updated_at, parts}`. Endpunkte exakt wie Spec §3-Tabelle; `export` liefert `LayoutOut` als Download.

- [ ] **Step 1:** Modelle + Schemas + Router schreiben. PUT legt an oder aktualisiert; POST/PATCH von Teilen läuft durch `clamp_part`; `kind` außerhalb `LAYOUT_KINDS` → 400. Bild-Upload nutzt `_store_image` aus `plant.py` (importieren, nicht kopieren).
- [ ] **Step 2:** Backend starten (`preview_start backend`), per `curl`: Maschine anlegen → `PUT layout {width_mm:6000, depth_mm:1500}` → Teil anlegen mit `x_mm:-10` → Antwort `x_mm == 0`. `GET layout` einer Maschine ohne Layout → 404.
- [ ] **Step 3:** Skizze hochladen, Maschine löschen → Datei unter `data/images/` ist weg.
- [ ] **Step 4:** `pytest -q` grün. Commit `feat(layout): Datenmodell und API fuer Maschinen-Draufsicht`.

### Task 3: Globale Tag-Suche

**Files:**
- Modify: `backend/app/api/plant.py` (Endpoint), `backend/app/schemas.py` (`TagSearchHit{tag, tag_type, machines: list[{id, name}], occurrences: int}`)
- Modify: `backend/app/ingestion/tags.py` (`search_key(q: str) -> str | None`)
- Test: `backend/tests/test_tags.py`

**Interfaces:**
- Produces: `GET /api/tags/search?q=` → `list[TagSearchHit]` (max 30, sortiert nach Tag-Länge, dann Tag). `search_key` liefert normalisierten Präfix oder `None` bei leerer/sinnloser Eingabe.

- [ ] **Step 1: Tests**

```python
def test_search_key_normalizes():
    assert search_key("k1") == "-K1"
    assert search_key(" -x1:5 ") == "-X1:5"
    assert search_key("%I0.0") == "E0.0"

def test_search_key_rejects_empty():
    assert search_key("") is None and search_key("  - ") is None
```

- [ ] **Step 2:** FAIL → implementieren (`normalize_tag`, danach `None`, wenn Ergebnis ohne alphanumerisches Zeichen) → PASS.
- [ ] **Step 3:** Endpoint: `TagOccurrence.tag.like(f"{key}%")`, gruppiert nach tag/tag_type, Maschinen über `Machine.source_id == TagOccurrence.source_id`. `search_key` None → `[]`.
- [ ] **Step 4:** curl `/api/tags/search?q=k1` gegen geladenes Beispiel liefert `-K1` mit Maschine FB-01. Commit `feat(search): globale BMK-Suche`.

### Task 4: Vision-Erkennung für Draufsichten

**Files:**
- Create: `backend/app/ingestion/layout_vision.py`
- Modify: `backend/app/api/layout.py` (`POST /api/layouts/{id}/detect`)
- Test: `backend/tests/test_layout_geometry.py` (`parse_vision_json`)

**Interfaces:**
- Consumes: `to_parts` (Task 1), `render_page_png` aus `ingestion/vision.py`, `_load_png`-Logik aus `cabinet_vision.py` (in gemeinsame Hilfsfunktion `load_png(path) -> bytes` in `cabinet_vision.py` belassen und importieren).
- Produces: `detect_layout(png: bytes, known_tags: list[str]) -> dict` mit `{"items": [...], "width_mm": float|None, "depth_mm": float|None}`; `parse_vision_json(text: str) -> dict` (wirft `ValueError` ohne JSON).

- [ ] **Step 1: Test** — `parse_vision_json('bla {"items": [], "width_mm": 6000} bla') == {"items": [], "width_mm": 6000}`; `parse_vision_json("kein json")` wirft `ValueError`.
- [ ] **Step 2:** FAIL → implementieren → PASS.
- [ ] **Step 3:** Prompt: Draufsicht einer Maschine/Anlage; feste `kind`-Liste; `shape` rect/circle; BMK nur wenn lesbar; Gesamtmaße aus Maßketten in mm, sonst null; nur JSON. Endpoint: Bildquelle = Layout-Skizze, sonst `document_id`+`page`, sonst 400 „Keine Skizze hinterlegt“. Unbestätigte Vision-Teile ersetzen; Maße nur setzen, wenn Layout 0 hat. Fehler → 502.
- [ ] **Step 4:** Commit `feat(layout): Vision-Vorschlaege aus Skizze`. (Kein Live-Aufruf ohne Nutzerfreigabe.)

### Task 5: Referenzskizze FB-01

**Files:**
- Create: `scripts/make_layout_sketch.py`, `examples/foerderband/08_Aufstellungsplan_FB-01.png`, `examples/foerderband/08_Aufstellungsplan_FB-01.json`
- Modify: `scripts/load_example.py`, `examples/foerderband/README.md`

**Interfaces:**
- Produces: JSON im Format `{"width_mm", "depth_mm", "scale_note", "parts": [LayoutPartIn…]}`; `load_example.py` ruft `PUT layout`, lädt PNG als Skizze hoch, legt Teile an (`confirmed: true`, `origin: manual`), idempotent (vorhandene Teile vorher löschen).

- [ ] **Step 1:** BMK und Einbauort aus `02_Stueckliste_FB-01.xlsx` lesen; Feldgeräte (Einbauort nicht Schaltschrank) gehen in die Skizze, Schaltschrank als ein Teil.
- [ ] **Step 2:** Skript zeichnet 1:1 aus dem JSON (Pillow, 2400 px breit, weißer Grund, schwarze Linien, Maßkette 6000, Schriftfeld „FB-01 Aufstellungsplan M 1:50“). JSON ist die Quelle, PNG wird erzeugt.
- [ ] **Step 3:** `python scripts/make_layout_sketch.py` erzeugt PNG; Bild ansehen (Read) und prüfen, dass alle BMK lesbar sind.
- [ ] **Step 4:** `python scripts/load_example.py` → Layout mit allen Teilen vorhanden (`GET layout`). Zweiter Lauf erzeugt keine Duplikate.
- [ ] **Step 5:** Commit `feat(examples): Aufstellungsplan FB-01 als Referenz-Draufsicht`.

### Task 6: Designsystem und App-Shell

**Files:**
- Modify: `frontend/package.json`, `frontend/src/app/globals.css`, `frontend/src/app/layout.tsx`, `frontend/src/app/page.tsx`, `frontend/src/app/werk/page.tsx`, `frontend/src/app/werk/maschine/[id]/page.tsx` (nur Einbettung in Shell)
- Create: `frontend/components.json`, `frontend/src/components/ui/*` (shadcn: button, badge, input, tabs, table, dialog, tooltip, command, sonner), `frontend/src/lib/utils.ts`, `frontend/src/components/AppShell.tsx`, `frontend/src/components/Tag.tsx`
- Delete: `frontend/src/components/AppNav.tsx` (durch Shell ersetzt)

**Interfaces:**
- Produces: `<AppShell breadcrumb={Crumb[]}>{children}</AppShell>` mit `Crumb = {label: string; href?: string}`; Slot `data-search-trigger` für Task 10. `<Tag value="-M1" onClick? />`. Tailwind-Farbklassen `bg-bg, bg-surface, bg-surface-2, border-border, text-text, text-muted, bg-accent, text-accent, text-danger, text-ok, bg-nav` + `font-sans`/`font-mono` = Plex.

- [ ] **Step 1:** shadcn init (Tailwind 4, neutral, CSS-Variablen), Komponenten hinzufügen; shadcn-Variablen (`--primary`, `--background`, `--radius` …) auf Blaupause-Tokens mappen; Dark-Block entfernen.
- [ ] **Step 2:** Plex-Fonts über `next/font/google` (Doku in node_modules prüfen), Geist entfernen.
- [ ] **Step 3:** `AppShell`: Nav-Leiste 64 px `#14263D` mit lucide-Icons (MessageSquare „Chat“, Factory „Werk“), aktive Route hell hinterlegt; Kopfzeile 56 px mit Breadcrumb in Mono-Großbuchstaben, Suchfeld-Platzhalter „Suchen: -K12, X1:5, E0.0 …“ + `Strg K`, Backend-Status aus `api.health()`. Alle drei Seiten nutzen die Shell.
- [ ] **Step 4:** `npm run lint && npx tsc --noEmit && npm run build` grün. Frontend im Browser-Pane öffnen, Screenshot von `/` und `/werk`: Tokens, Schriften, Nav sichtbar, keine Konsolenfehler.
- [ ] **Step 5:** Commit `feat(ui): Blaupause-Designsystem und App-Shell`.

### Task 7: API-Client für Layout und Suche

**Files:** Modify `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: Typen `LayoutKind` (Union der 10 Arten), `LAYOUT_KINDS: LayoutKind[]`, `LayoutPart`, `LayoutPartInput`, `Layout`, `TagSearchHit`; `layout = { get(machineId): Promise<Layout|null> (404→null), put(machineId, body), uploadImage(machineId, file), imageUrl(machineId), createPart(layoutId, body), updatePart(partId, body), deletePart(partId), detect(layoutId), exportUrl(layoutId) }`; `api.searchTags(q): Promise<TagSearchHit[]>`.

- [ ] **Step 1:** Implementieren, Felder 1:1 wie Backend-Schemas (snake_case).
- [ ] **Step 2:** `npx tsc --noEmit` grün. Commit `feat(ui): API-Client fuer Layout und Suche`.

### Task 8: LayoutCanvas (React Flow)

**Files:**
- Create: `frontend/src/components/layout/LayoutCanvas.tsx`, `frontend/src/components/layout/PartNode.tsx`, `frontend/src/components/layout/TitleBlock.tsx`, `frontend/src/components/layout/geometry.ts`
- Modify: `frontend/package.json` (`@xyflow/react`)

**Interfaces:**
- Consumes: `layout.*` (Task 7), `Tag` (Task 6).
- Produces: `<LayoutCanvas layout={Layout} machineName={string} selectedId={string|null} onSelect={(part: LayoutPart|null) => void} onChanged={() => void} />`. `geometry.ts`: `MM_TO_PX = 0.15` (6000 mm ≈ 900 px bei Zoom 1), `partToNode(part): Node`, `nodeToPatch(node): LayoutPartUpdate`.

- [ ] **Step 1:** Teile → Nodes (Position/Größe in px), `PartNode` zeichnet Rechteck/Kreis: Rand `text` 1.5 px, BMK in Mono; ausgewählt = Akzentblau 2 px + 4 Eckquadrate (NodeResizer); unbestätigt = gestrichelt Akzent + „Vorschlag · NN %“; Not-Halt-Kreis rot gefüllt.
- [ ] **Step 2:** Hintergrund: `<Background variant="lines">` zweifach (Raster 10 mm und 100 mm in `grid`-Farbe); Layout-Rahmen width×depth als nicht verschiebbarer Node; Skizze (falls `has_image`) als Hintergrundbild-Node mit 35 % Deckkraft, Schalter „Skizze einblenden“.
- [ ] **Step 3:** Werkzeugleiste oben links (Auswahl, Rechteck, Kreis; Klick auf Fläche im Zeichenmodus legt 300×300 mm „Sonstiges“ an), rechts „N Vorschläge prüfen“ (öffnet Liste: bestätigen/verwerfen, „Alle bestätigen“). Schriftfeld unten rechts (Maschine, Blatt, „Draufsicht“, Maße `width × depth`).
- [ ] **Step 4:** Drag/Resize-Ende → `updatePart` (optimistisch, bei Fehler `onChanged()` + Toast). Entf-Taste löscht ausgewähltes Teil nach Bestätigung.
- [ ] **Step 5:** Mit FB-01 im Browser prüfen: Teile an richtiger Stelle gegenüber Skizze, Drag speichert (Reload behält Position), Screenshot neben Figma-Frame 5:273 legen. Commit `feat(werk): Draufsicht-Editor mit React Flow`.

### Task 9: Maschinenseite mit Tabs, Detail-Panel, Fehlertabelle

**Files:**
- Modify: `frontend/src/app/werk/maschine/[id]/page.tsx` (zerlegen)
- Create: `frontend/src/components/machine/PartPanel.tsx`, `frontend/src/components/machine/FaultTable.tsx`, `frontend/src/components/machine/FaultDialog.tsx`, `frontend/src/components/machine/LayoutEmptyState.tsx`, `frontend/src/components/machine/DocumentsTab.tsx`

**Interfaces:**
- Consumes: `LayoutCanvas` (Task 8), `plant.lookupTag`, `plant` Fault-Funktionen, `PageViewer`, `CabinetEditor`.
- Produces: Tabs `Draufsicht | Fehler (n) | Schaltschrank | Dokumente`; `?tag=` in URL wählt passendes Teil und Tab Draufsicht.

- [ ] **Step 1:** Seite zerlegen: Kopf (Name in Mono-Großbuchstaben, Zeile „Typ · Halle · n Quellen · n Betriebsmittel“), Tabs, bestehende Funktionen (Quelle wählen, Maschinenbild, Schaltschrank-Upload) wandern in „Dokumente“ bzw. „Schaltschrank“.
- [ ] **Step 2:** `PartPanel`: dunkle Kopfzeile „AUSGEWÄHLT“, BMK groß in Akzent, Badge bestätigt/Vorschlag, Felder BMK/Bezeichnung/Art/Drehung (Grad) editierbar; Trefferliste aus `lookupTag` gruppiert nach doc_type mit Sprung in `PageViewer`; „Letzte Fehler“ = Fehler mit diesem Tag (roter Punkt); Buttons „Im Stromlaufplan öffnen“ (erster schematic-Treffer), „Im Chat fragen“ (`/?q=Was ist -M1?`). Ohne Quelle: Hinweis „Keine Dokumentation verknüpft“ + Link auf Tab Dokumente.
- [ ] **Step 3:** `FaultTable` mit TanStack Table: Spalten Code, Symptom, Ursache, Betriebsmittel (Tags klickbar → Draufsicht-Auswahl), Quelle; Sortierung per Klick, Filter-Chip nach ausgewähltem Tag; Anlegen/Bearbeiten im `FaultDialog`, Löschen mit Bestätigung.
- [ ] **Step 4:** `LayoutEmptyState`: „Skizze hochladen“, „Dokumentseite wählen“ (Dokument + Seite aus Quelle), „Leer beginnen“ (Breite/Tiefe in mm), danach Button „Vorschläge erkennen (kostet API-Tokens)“.
- [ ] **Step 5:** Lint/tsc/build grün; im Browser FB-01: `-M1` klicken → Panel zeigt Stückliste/Klemmen/SPS-Treffer; Maschine ohne Quelle zeigt Hinweis; Fehlertab sortiert. Commit `feat(werk): Maschinenseite mit Tabs, Detailpanel und Fehlertabelle`.

### Task 10: Globale Suche (Strg+K)

**Files:**
- Create: `frontend/src/components/GlobalSearch.tsx`
- Modify: `frontend/src/components/AppShell.tsx`

**Interfaces:**
- Consumes: `api.searchTags` (Task 7), shadcn `command` + `dialog`.

- [ ] **Step 1:** `CommandDialog`, öffnet per Strg+K/Cmd+K und Klick auf Suchfeld; Eingabe entprellt 200 ms; Treffer gruppiert nach Maschine, Zeile = Tag (Mono) + Typ + Anzahl Fundstellen; Enter → `/werk/maschine/{id}?tag={tag}`; Tag ohne Maschine → Chat mit Frage.
- [ ] **Step 2:** Im Browser: Strg+K, `k1` tippen → `-K1` unter FB-01, Enter springt auf Maschinenseite mit ausgewähltem Teil bzw. Treffern. Commit `feat(ui): globale BMK-Suche mit Strg+K`.

### Task 11: Abschluss

**Files:** Modify `README.md`, `AGENTS.md` (Routen/Datenmodell ergänzen)

- [ ] **Step 1:** README/AGENTS: Datenmodell um `MachineLayout -> LayoutPart`, neue Skizze im Beispiel, Vision-Kosten für Draufsicht.
- [ ] **Step 2:** Volle Prüfung: `pytest -q`, `npm run lint`, `npx tsc --noEmit`, `npm run build`; E2E-Durchlauf aus Spec „Tests“ mit Screenshot.
- [ ] **Step 3:** Commit `docs: Draufsicht und Blaupause-UI dokumentiert`, Branch pushen, PR gegen `master` öffnen (nicht mergen).
