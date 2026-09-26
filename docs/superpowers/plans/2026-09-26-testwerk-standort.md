# Testwerk Teil 1: Standortplan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Standortplan mit Hallen (Art, Lage, Materialfluss zwischen Hallen), Linien/Sektoren in der Halle, Maschinen-Kennzahlen mit Quelle und ein ladbares Testwerk Tissue.

**Architecture:** Reine Logik in `backend/app/werk/site.py` und `backend/app/migrations.py`, dünne API in `backend/app/api/site.py` plus Erweiterungen in `plant.py`. Frontend: reine Geometrie in `frontend/src/lib/site.ts`, Standortplan `/werk` (React Flow, schwebende Kanten), Hallen-Baukasten zieht nach `/werk/halle/[id]` und bekommt Linienbänder. Testwerk als JSON + Lader über die API.

**Tech Stack:** FastAPI, SQLAlchemy 2, Postgres; Next.js 16, React 19, @xyflow/react 12, vitest 4, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-testwerk-standort-design.md`

## Global Constraints

- Kein LLM-/Vision-Aufruf in Code, Tests, Lader oder Verifikation.
- Blaupause-Tokens aus `globals.css`, kein neues Token; Blau = Auswahl/Fluss, Rot nur Fehlerzahl.
- Tabellen per `create_all`; neue Spalten nur über `app/migrations.py` (`ADD COLUMN IF NOT EXISTS`).
- Hallenarten genau: `generic|base|production|warehouse|office` → Halle, Grundstoff, Verarbeitung, Lager, Büro.
- Kennzahl ohne Herstellerangabe: Quelle beginnt mit „Richtwert“. Keine Herstellernamen als Maschinennamen.
- Ruff line-length 100 (E501 ignoriert); Frontend: `npm run lint && npx tsc --noEmit && npm test`.
- Next.js 16: vor Routing-Code `node_modules/next/dist/docs` zu dynamischen Routen prüfen; Muster von `app/werk/maschine/[id]/page.tsx` übernehmen.

## Review Focus

1. Bestehende DB ohne neue Spalten: Start muss Spalten anlegen, alte Hallen gelten als `generic` ohne Lage.
2. Hallen ohne Lage (`site_w == 0`): Standortplan setzt sie überlappungsfrei unter die platzierten.
3. Halle löschen mit Standort-Flüssen: Flüsse verschwinden mit (FK `ON DELETE CASCADE`), kein 500.
4. Lader zweimal ohne `--refresh`: bricht mit Hinweis ab statt zu verdoppeln; mit `--refresh` bleiben fremde Standort-Flüsse erhalten.
5. Halle ohne Maschinen im Mini-Plan: keine Division durch null, leerer Block.

---

### Task 1: Migration und reine Standortlogik

**Files:**
- Create: `backend/app/migrations.py`, `backend/app/werk/__init__.py`, `backend/app/werk/site.py`
- Modify: `backend/app/db.py` (init_db ruft Migrationen), `backend/app/models.py`
- Test: `backend/tests/test_site.py`

**Interfaces:**
- Produces: `ADDITIVE_COLUMNS: list[tuple[str, str, str]]`, `upgrade_statements() -> list[str]`;
  `HALL_KINDS: tuple[str, ...]`; `place_halls(rects: list[tuple[float, float, float, float]]) -> list[tuple[...]]`;
  `check_site_flows(flows: list[tuple[str, str]], hall_ids: set[str]) -> None` (ValueError);
  `clean_specs(specs: list[dict]) -> list[dict]`; `key_figure(specs: list[dict]) -> str`;
  `dock_count(specs: list[dict]) -> int`.
- Models: `Hall.kind/site_x/site_y/site_w/site_h`, `Machine.line`, `Machine.specs` (order_by position,
  delete-orphan), `SiteFlow(id, from_hall_id, to_hall_id, label)` FKs `ON DELETE CASCADE`,
  `MachineSpec(id, machine_id, position, label, value, unit, source)`.

- [ ] **Step 1: Failing tests** in `test_site.py`:
  - `upgrade_statements()[0] == "ALTER TABLE halls ADD COLUMN IF NOT EXISTS kind VARCHAR(24) NOT NULL DEFAULT 'generic'"`, eine Anweisung je Spalte (halls: kind, site_x, site_y, site_w, site_h; machines: line).
  - `place_halls([(0,0,0,0)]*4)` → `[(40,40,360,260),(460,40,360,260),(880,40,360,260),(40,360,360,260)]`.
  - `place_halls([(100,100,300,200),(0,0,0,0)])[1] == (40,360,360,260)` (unter der untersten Kante + 60).
  - `check_site_flows([("a","a")], {"a"})`, `[("a","x")]`, doppelter Fluss → ValueError.
  - `clean_specs([{"label":" Leistung ","value":"10","unit":"Logs/min","source":"x"},{"label":"  ","value":"1"}])` → eine Zeile, getrimmt, `position` 0.
  - `key_figure([{"value":"2.200","unit":"m/min"}]) == "2.200 m/min"`, `key_figure([]) == ""`.
  - `dock_count([{"label":"Anzahl Tore","value":"8"},{"label":"Anzahl Tore","value":"zwei"}]) == 8`.
- [ ] **Step 2:** `cd backend && .venv/Scripts/python -m pytest tests/test_site.py -q` → Expected: FAIL (ImportError).
- [ ] **Step 3:** Implementieren; `init_db` führt nach `create_all` jede Anweisung aus `upgrade_statements()` aus.
- [ ] **Step 4:** Test erneut → PASS; ganze Suite grün.
- [ ] **Step 5:** Commit `feat(werk): Hallenart, Standortlage, Linien und Kennzahlen im Datenmodell`.

### Task 2: API Standort, Hallen, Kennzahlen

**Files:**
- Create: `backend/app/api/site.py`
- Modify: `backend/app/api/plant.py`, `backend/app/schemas.py`, `backend/app/main.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `GET /api/site` → `{halls: [{id, name, kind, description, x, y, w, h, machine_count, fault_count, lines, docks, machines: [{id, name, machine_type, pos_x, pos_y, line}]}], flows: [{id, from_hall_id, to_hall_id, label}]}`;
  `PUT /api/site/flows` (Liste `{from_hall_id, to_hall_id, label}`, 400 bei ValueError);
  `GET/PUT /api/machines/{id}/specs` (`{label, value, unit, source}` → mit `id, position`);
  Halle: `kind, site_x, site_y, site_w, site_h` in Out/Create/Update (400 bei unbekannter Art);
  Maschine: `line` in Create/Update/Out, Out zusätzlich `key_figure`, `hall_name`.

- [ ] **Step 1:** Implementieren (Logik nur aus Task 1 aufrufen). `lines` = eindeutige nicht-leere `line` in Maschinenreihenfolge.
- [ ] **Step 2:** Backend neu starten (preview `backend`), prüfen: `curl /api/site` (alte Hallen mit Standardlage), `PATCH` Art, `PUT` Flüsse mit Selbstfluss → 400, Specs PUT/GET, Halle mit Fluss löschen → 204.
- [ ] **Step 3:** `pytest -q` und `ruff check app` grün.
- [ ] **Step 4:** Commit `feat(werk): API Standortplan, Standort-Flüsse und Kennzahlen`.

### Task 3: Testwerk-Daten und Lader

**Files:**
- Create: `examples/testwerk/testwerk.json`, `scripts/load_testwerk.py`, `backend/tests/test_testwerk_data.py`

**Interfaces:**
- JSON: `{halls: [{name, kind, description, site: {x,y,w,h}, machines: [{key, name, machine_type, line, x, y, description, specs: [{label, value, unit, source}]}], flows: [[fromKey, toKey, label]]}], site_flows: [[hallName, hallName, label]]}`.
- Hallen: „Papiermaschine PM1“ (base, 7 Maschinen, Linie „PM1 Tissuemaschine“ für S1–S6), „Verarbeitung“ (production, Linien „L1 Toilettenpapier“ … „L6 Industrierollen“ je Hauptmaschine → Verpackung → Palettierer), „Lager & Versand“ (warehouse, Linien „Einlagerung“, „Versand“, Verladetore mit Kennzahl „Anzahl Tore“ = 8), „Büro“ (office, keine Maschinen). Standort-Flüsse: PM1 → Verarbeitung „Mutterrollen“, Verarbeitung → Lager „Paletten“, Büro → Verarbeitung „Aufträge“.

- [ ] **Step 1: Failing test** `test_testwerk_data.py`: Arten genau {base, production, warehouse, office}; Verarbeitung hat 6 Linien × 3 Maschinen und je Linie Typen main → packaging → robot über die Flüsse; alle Fluss-Schlüssel existieren; Schlüssel eindeutig; jede Kennzahl hat label, value, source; `machine_type` gültig; Standort-Flüsse nennen vorhandene Hallen; Summe „Anzahl Tore“ = 8.
- [ ] **Step 2:** Test → FAIL (Datei fehlt).
- [ ] **Step 3:** JSON schreiben (Kennzahlen und Quellen aus der Recherche), Lader: bestehende Testwerk-Hallen → ohne `--refresh` Abbruch mit Hinweis, mit `--refresh` löschen; anlegen, Lage setzen, Maschinen, Kennzahlen, Hallen-Flüsse; Standort-Flüsse = vorhandene fremde + neue.
- [ ] **Step 4:** Test → PASS. Lader gegen lokales Backend zweimal (ohne, dann mit `--refresh`), `GET /api/site` zeigt 4 Hallen, 30 Maschinen.
- [ ] **Step 5:** Commit `feat(werk): Testwerk Tissue als Beispieldaten mit Lader`.

### Task 4: Frontend-Typen und Geometrie

**Files:**
- Create: `frontend/src/lib/site.ts`, `frontend/src/lib/site.test.ts`
- Modify: `frontend/src/lib/api.ts`

**Interfaces:**
- Produces: `HallKind`, `HALL_KIND_LABELS`, `SiteHall`, `SiteMachine`, `SiteFlow`, `SiteData`, `MachineSpec`;
  `plant.getSite()`, `plant.replaceSiteFlows(flows)`, `plant.getSpecs(id)`, `plant.replaceSpecs(id, specs)`,
  `plant.updateHall` mit Art und Lage, `Machine.line/key_figure/hall_name`;
  `laneBoxes(items: {line: string; x: number; y: number}[], tile: {w: number; h: number}, pad = 16, header = 22): {line: string; x: number; y: number; w: number; h: number}[]`;
  `miniPlan(machines: SiteMachine[], size: {w: number; h: number}): {scale: number; tiles: Rect[]; lanes: Lane[]}`.

- [ ] **Step 1: Failing tests** `site.test.ts`: `laneBoxes` gruppiert nach Linie, ignoriert leere Linie, Hülle = Kacheln + pad, oben + header; `miniPlan([], {w:300,h:200})` → `{scale:0, tiles:[], lanes:[]}`; alle Kacheln und Bänder von `miniPlan` liegen innerhalb `size`; Maßstab höchstens 0,35.
- [ ] **Step 2:** `npm test -- site` → FAIL.
- [ ] **Step 3:** Implementieren, Typen in `api.ts`.
- [ ] **Step 4:** `npm test`, `npx tsc --noEmit` grün.
- [ ] **Step 5:** Commit `feat(werk): Frontend-Typen und Geometrie fuer Standortplan und Linien`.

### Task 5: Hallen-Baukasten unter /werk/halle/[id]

**Files:**
- Create: `frontend/src/app/werk/halle/[id]/page.tsx`, `frontend/src/components/hall/LaneNode.tsx`
- Modify: `frontend/src/components/HallCanvas.tsx`, `frontend/src/components/hall/MachineNode.tsx`, `frontend/src/app/werk/maschine/[id]/page.tsx` (Brotkrumen)

**Interfaces:**
- Consumes: `laneBoxes`, `Machine.line/key_figure/hall_name`, `HALL_KIND_LABELS`.

- [ ] **Step 1:** Seite aus bisherigem `/werk` übernehmen, ohne Hallenliste; Kopf: Name, Art-Auswahl, Anzahl, Onboarding, „Halle löschen“ (danach `/werk`). Panel: Anlegen, Auswahl mit Feld „Linie/Sektor“ (datalist vorhandener Linien).
- [ ] **Step 2:** Linienbänder: `laneBoxes` aus Live-Positionen der Knoten, Knotentyp `lane` (nicht wählbar/ziehbar, zIndex −1, pointer-events none), Beschriftung Plex Mono oben links.
- [ ] **Step 3:** Kachel zeigt `key_figure`; Maschinenseite Brotkrumen Werk › Halle (`/werk/halle/{hall_id}`) › Maschine.
- [ ] **Step 4:** lint, tsc, test grün; Browser: Halle Verarbeitung zeigt 6 Bänder, Kachel verschieben → Band folgt, Linie ändern → neues Band.
- [ ] **Step 5:** Commit `feat(werk): Hallen-Baukasten unter /werk/halle mit Linienbaendern`.

### Task 6: Standortplan /werk

**Files:**
- Create: `frontend/src/components/site/SiteCanvas.tsx`, `frontend/src/components/site/HallBlockNode.tsx`, `frontend/src/components/site/SiteFlowEdge.tsx`
- Modify: `frontend/src/app/werk/page.tsx`

**Interfaces:**
- Consumes: `plant.getSite/updateHall/replaceSiteFlows/createHall`, `miniPlan`, `FlowEdgeData` (Beschriftung/Löschen wie Hallen-Fluss).

- [ ] **Step 1:** `HallBlockNode`: Rahmen 1,5 px Linie (gewählt 2,5 px Primär), Kopfzeile Nav-Farbe mit Name in Plex Mono, rote Fehlerzahl nur bei `fault_count > 0`, Mini-Plan (SVG) mit Bändern und Kacheln, `docks` Tore als Kerben an der rechten Wand, `NodeResizer` bei Auswahl (min 200 × 140), Griffe links/rechts.
- [ ] **Step 2:** `SiteFlowEdge`: gerade Linie zwischen den Blockrändern (Schnittpunkt der Mittellinie mit dem Rechteck, React-Flow-Muster „floating edges“ via `useInternalNode`), Pfeil, Beschriftung wie `FlowEdge`.
- [ ] **Step 3:** Seite: Kopf „STANDORTPLAN“ + Zähler + „Halle anlegen“ (Name, Art); Panel gewählte Halle (Art-Auswahl, Maschinen/Linien/Fehler, Linienliste, „Halle öffnen →“), ohne Auswahl Hallenliste; Schriftfeld unten rechts „BLATT STANDORT | WERK | n Hallen · m Maschinen“; Ziehen/Größe speichern Lage, Fluss ziehen speichert Standort-Flüsse.
- [ ] **Step 4:** lint, tsc, test grün; Browser: 4 Hallen wie Mockup, Halle ziehen/Größe ändern bleibt nach Neuladen, Fluss anlegen/umbenennen/löschen, mobil 375 px ohne horizontales Scrollen der Seite.
- [ ] **Step 5:** Commit `feat(werk): Standortplan mit Hallenbloecken und Materialfluss`.

### Task 7: Tab Kennzahlen

**Files:**
- Create: `frontend/src/components/machine/SpecsTab.tsx`
- Modify: `frontend/src/app/werk/maschine/[id]/page.tsx`

- [ ] **Step 1:** Tabelle Kennzahl | Wert | Einheit | Quelle (URL als Link, sonst Text), Zeile hinzufügen/bearbeiten/löschen, „Speichern“ → `replaceSpecs`, Toast.
- [ ] **Step 2:** lint, tsc, test; Browser: Umroller L1 zeigt 3 Kennzahlen mit Links, Änderung bleibt nach Neuladen, Kachel zeigt neue erste Kennzahl.
- [ ] **Step 3:** Commit `feat(werk): Tab Kennzahlen auf der Maschinenseite`.

### Task 8: Doku, Gesamtprüfung, PR

- [ ] **Step 1:** README (Testwerk laden, Routen), AGENTS.md (Routen, `app/werk/`, Migrationsliste, Lader).
- [ ] **Step 2:** Ganze Suiten: `pytest -q`, `ruff check app`, `npm run lint && npx tsc --noEmit && npm test && npm run build`.
- [ ] **Step 3:** Abschluss-Review über den Branch, Befunde fixen, Push, PR gegen master.
