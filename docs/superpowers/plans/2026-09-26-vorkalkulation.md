# Testwerk Teil 2: Vorkalkulation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seite „Planung“: Auftrag → Verladetermin, Zeitplan je Station, Materialbedarf, Kosten (Richtwerte), aus Stammdaten des Testwerks.

**Architecture:** Reiner Rechenkern `backend/app/werk/calendar.py` + `calc.py` (Dataclasses rein, Ergebnis raus); ORM-Tabellen für Stammdaten, dünne API `backend/app/api/planning.py` baut die Dataclasses; Testwerk-JSON + Lader liefern Daten. Frontend: reine Zeitachse `frontend/src/lib/timeline.ts`, Seite `/planung` mit Tabs Kalkulation/Stammdaten.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest; Next.js 16, React 19, vitest.

**Spec:** `docs/superpowers/specs/2026-09-26-vorkalkulation-design.md`

## Global Constraints

- Kein LLM-/Vision-Aufruf. Nur neue Tabellen (`create_all`).
- Blaupause: Blau = Aktion/Balken, Grün `ok` = Termin hält, Rot nur Fehler. Plex Mono für Zahlen.
- Preise und Sätze ohne Quelle: Quelle-Text „Richtwert (Annahme)“.
- Zeiten naiv lokal (Europe/Berlin gedacht), ISO-Strings `YYYY-MM-DDTHH:MM`.
- Zahlen deutsch formatieren im Frontend (`toLocaleString("de-DE")`).

## Review Focus

1. Auftrag am Freitagnachmittag/Wochenende: Büro läuft Montag weiter, Produktion nicht blockiert.
2. Menge 0, negative Menge, unbekannter Artikel: 400 mit klarer Meldung; Artikel ohne Arbeitsplan: Hinweis, keine Linienzeit, kein Absturz.
3. Zwei Positionen auf derselben Linie: nacheinander; auf verschiedenen Linien: parallel.
4. Kennzahl „Maschinenstundensatz“ fehlt oder ist Text: Kosten 0 € + Hinweis, kein 500.
5. Sehr große Menge (z. B. 1 000 000 Pakete): endet in endlicher Zeit, Zeitachse bleibt lesbar.

---

### Task 1: Kalender

**Files:** Create `backend/app/werk/calendar.py`, Test `backend/tests/test_calendar.py`

**Interfaces — Produces:** `Window = {"days": list[int], "from": "HH:MM", "to": "HH:MM"} | "24/7"`;
`next_open(t: datetime, window) -> datetime`; `add_work(t: datetime, minutes: float, window) -> datetime`
(beginnt bei `next_open`, überspringt geschlossene Zeit); `closed_spans(start, end, window) -> list[tuple[datetime, datetime]]`.

- [ ] Failing tests: Büro Mo–Fr 07–16: Fr 15:30 + 60 → Mo 07:30; Sa 10:00 next_open → Mo 07:00; Di 06:00 + 30 → Di 07:30; 24/7: + 90 → +90 min; `add_work(t, 0)` = `next_open(t)`; `closed_spans(Fr 12:00, Mo 12:00)` enthält Fr 16:00–Mo 07:00.
- [ ] RED, implementieren (minutengenau, Schleife über Tagesfenster), GREEN, Commit `feat(planung): Arbeitszeit-Kalender`.

### Task 2: Rechenkern

**Files:** Create `backend/app/werk/calc.py`, Test `backend/tests/test_calc.py`

**Interfaces — Produces (Dataclasses):** `Article(id, code, name, unit_name, units_per_pallet, sheets_per_unit, sheet_w_mm, sheet_l_mm, plies, gsm, waste_pct, line, routing: list[Step], bom: list[BomLine])`;
`Step(machine_id, machine_name, line, rate, rate_unit: "unit_min"|"pallet_h", setup_min, coupled, hourly_rate: float|None, basis)`;
`Material(code, name, unit, price, price_source, made_on: Step|None (rate in Einheit/h), bom: list[BomLine])`;
`BomLine(material_code, qty, per: "unit"|"pallet")`; `Settings(calendars, office_steps, office_rate, truck_capacity, load_min, docks)`;
`Position(article, quantity, unit: "unit"|"pallet")`;
`calculate(received_at: datetime, due: date|None, positions: list[Position], materials: dict[str, Material], settings: Settings) -> dict`
(Schlüssel: `ready_at, meets_due, days_delta, summary, stations, materials, costs, positions, warnings`);
`paper_kg_per_unit(article) -> float`; `parse_number(text: str) -> float|None`.
Rohpapier = Material mit `code == "ROHPAPIER"`, Einheit t.

- [ ] Failing tests:
  - `paper_kg_per_unit(TP 1200 Blatt, 98×125 mm, 3 Lagen, 16 g/m², 3 %) == pytest.approx(0.7268, abs=1e-4)`.
  - `parse_number("1.500") == 1500`, `"2,8" == 2.8`, `"~30.000" == 30000`, `"30–90" is None`, `"Dampf" is None`.
  - Stücklisten: 10 000 Pakete TP → Rohpapier 7,268 t → Zellstoff 0,55 t/t; Hülsen 8/Paket; Paletten ⌈10 000/84⌉ = 120 (per „pallet“).
  - Linie: Schritte 35 Pak/min, 220 Pak/min, 60 Paletten/h (84 Pak/Pal) gekoppelt → Engpass 35, Dauer = max Rüstzeit + 10 000/35 min.
  - Ablauf ab Fr 25.09.2026 15:30: Büro endet Mo 09:15 (30+60+45+30 min, GF weil ≥ 100 Paletten); PM1 danach; LKW ⌈Paletten/33⌉, Runden ⌈LKW/8⌉ × 45 min im Versandfenster.
  - Zwei Positionen gleiche Linie → zweite startet nach Ende der ersten; andere Linie → Start nach eigenem Papier.
  - Wunschtermin: `meets_due` True/False, `days_delta`.
  - Kosten: Material = Menge × Preis; Linie = Gruppendauer × Summe Sätze; fehlender Satz → 0 und Warnung; Büro+Versand nach Paletten verteilt; `per_unit` je Position.
  - Artikel ohne Arbeitsplan → Warnung, Position ohne Linienzeit, Ergebnis vorhanden. Menge ≤ 0 → ValueError.
- [ ] RED, implementieren, GREEN, Commit `feat(planung): Rechenkern Vorkalkulation`.

### Task 3: Stammdaten, API, Testwerk-Daten, Lader

**Files:** Modify `backend/app/models.py`, `schemas.py`, `main.py`, `examples/testwerk/testwerk.json` (über Generator im Scratchpad), `scripts/load_testwerk.py`; Create `backend/app/api/planning.py`; Test `backend/tests/test_testwerk_data.py` (erweitern), `backend/tests/test_planning_example.py`.

**Interfaces — Produces:** Tabellen `articles`, `materials`, `bom_lines`, `routing_steps`, `plant_settings(key, value JSON)`;
`GET /api/articles`, `GET /api/materials`, `GET /api/plant-settings`, `POST /api/calc` (Body `{received_at, due_date, positions:[{article_id, quantity, unit}]}`); `planning.build_inputs(session)` → Dataclasses.
JSON: `articles[] {code, name, unit_name, units_per_pallet, tech{…}, routing[{machine, rate, rate_unit, setup_min, coupled, basis}], bom[{material, qty, per}]}`, `materials[] {code, name, unit, price, price_source, made_on?{machine, rate_per_h}, bom[]}`, `settings{…}`; Maschinen bekommen Kennzahl „Maschinenstundensatz“ (€/h, Richtwert (Annahme)).

- [ ] Failing test: Testwerk-Daten — 8 Artikel, jede Linie L1–L6 hat ≥ 1 Artikel, Arbeitsplan-Maschinen existieren, Stücklisten-Materialien existieren, jeder Preis > 0 mit Quelle, Rohpapier mit Eigenfertigung auf `pm1-s6`, jede Maschine in Arbeitsplänen hat Maschinenstundensatz.
- [ ] Failing test `test_planning_example.py`: Testwerk-JSON → Dataclasses (ohne DB, Hilfsfunktion im Test oder `calc.from_json`), Auftrag 10 000 Pakete TP + 40 Paletten KR ab Fr 25.09.2026 15:30 → verladebereit Mo 28.09.2026, Engpass L1-UR, 160 Paletten, 5 LKW.
- [ ] Implementieren: Modelle, API (400 bei Menge ≤ 0/unbekanntem Artikel), Daten, Lader (Stammdaten nach Hallen; `--refresh` ersetzt Artikel/Materialien mit gleichem Code).
- [ ] GREEN; Backend neu starten, Lader `--refresh`, `curl POST /api/calc` prüfen. Commit `feat(planung): Stammdaten, API und Testwerk-Daten`.

### Task 4: Frontend-Typen und Zeitachse

**Files:** Modify `frontend/src/lib/api.ts`; Create `frontend/src/lib/timeline.ts`, `timeline.test.ts`

**Interfaces — Produces:** Typen `Article, MaterialInfo, CalcRequest, CalcResult, CalcStation`; `planning.articles()`, `planning.calc(body)`;
`timeAxis(spans: {start: number; end: number}[], width: number, opts?: {gapMin?: number; breakPx?: number}) -> {x(t: number): number; breaks: {x: number; w: number; minutes: number}[]; ticks: {x: number; label: string; day: boolean}[]}` — Zeiten in ms; Lücken ohne Aktivität > 6 h werden auf `breakPx` (22) gestaucht.

- [ ] Failing tests: lineare Abbildung ohne Lücke; Lücke Fr 16:00–Mo 07:00 wird zu einem Bruch von 22 px und Mo 07:00 liegt direkt dahinter; x ist monoton; Tagesticks an Mitternacht, Stundenticks alle 4 h.
- [ ] RED, implementieren, GREEN, Commit `feat(planung): Frontend-Typen und Zeitachse`.

### Task 5: Seite Planung (Kalkulation)

**Files:** Create `frontend/src/app/planung/page.tsx`, `frontend/src/components/planning/OrderForm.tsx`, `Schedule.tsx`, `MaterialTable.tsx`, `CostTable.tsx`; Modify `frontend/src/components/AppShell.tsx` (Nav „Planung“, Icon Calculator).

- [ ] Formular (Kunde, Eingang `datetime-local`, Wunschtermin `date`, Positionen Artikel/Menge/Einheit, „+ Position“, ✕), Berechnung bei Änderung (entprellt 250 ms, letzte Antwort gewinnt).
- [ ] Ergebnis: Terminkopf (grün „hält · N Tage Puffer“ oder schwarz „+N Tage“), Kennzahlen, Zeitplan-SVG (Zeilen je Station, Schraffur aus `closed` je Station, Brüche, Engpass umrandet), Materialtabelle mit Herleitung, Kosten je Position + Summe, Hinweise.
- [ ] lint, tsc, test; Browser: Beispielauftrag = Mockup-Werte, Freitag-Fall, Menge 0 → Hinweis, mobil 375 px. Commit `feat(planung): Seite Planung mit Termin, Zeitplan, Material und Kosten`.

### Task 6: Tab Stammdaten

**Files:** Create `frontend/src/components/planning/MasterData.tsx`; Modify `planung/page.tsx`.

- [ ] Artikel-Liste (Code, Name, Linie, Einheit, je Palette, Rohpapier kg/Einheit), aufklappbar: Arbeitsplan (Maschine, Leistung, Rüstzeit, Herleitung, Stundensatz) und Stückliste; Materialtabelle mit Preis und Quelle.
- [ ] lint, tsc, test, Browser. Commit `feat(planung): Tab Stammdaten`.

### Task 7: Doku, Gesamtprüfung, Review, PR

- [ ] README/AGENTS (Route `/planung`, Rechenmodell, Kostenhinweis), Suiten + Build, Abschluss-Review, Fixes, Push, PR.
