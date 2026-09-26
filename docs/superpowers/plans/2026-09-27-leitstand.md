# Testwerk Teil 3: Leitstand Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deterministische Durchlauf-Simulation aller Aufträge (Büro, PM1, Linien, Lager, Tore) mit Abspielseite „Leitstand“.

**Architecture:** Reiner Simulationskern `backend/app/werk/sim.py` (Ereignisschleife mit heapq, nutzt `calc.py`/`calendar.py`), Tabellen für Kunden, Aufträge, Bestand; API `planning`-nah in `backend/app/api/orders.py`; Testwerk-Daten über `PUT /api/master-data`. Frontend: reiner Zustand-zur-Uhrzeit `frontend/src/lib/leitstand.ts`, Seite `/leitstand`.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest; Next.js 16, React 19, vitest.

**Spec:** `docs/superpowers/specs/2026-09-27-leitstand-design.md`

## Global Constraints

- Kein LLM-/Vision-Aufruf; deterministisch (gleiche Eingabe → gleiches Ergebnis, stabile Reihenfolge bei Gleichstand über laufende Nummer).
- Nur neue Tabellen; `articles.price` über `app/migrations.py`.
- Blaupause: Blau = Arbeit/Auswahl, Grün = hält, Schwarz = Verspätung, Rot nur Fehler.
- Richtwerte (Preise, Kreditlimits, Personenzahl, Klärungsdauer) mit Quelle „Richtwert (Annahme)“.

## Review Focus

1. Auftrag über Kreditlimit am Freitagnachmittag: Klärung läuft über das Wochenende im Bürokalender weiter.
2. Bestand deckt nur einen Teil: Rest wird gefertigt, Bestand fällt nie unter 0, zwei Aufträge reservieren nicht dieselben Einheiten.
3. Mehr LKW als Tore: Überzählige warten, keine Doppelbelegung eines Tors.
4. Auftrag ohne Arbeitsplan oder mit gelöschter Maschine: Hinweis, Simulation läuft weiter.
5. Leere Auftragsliste oder nur Aufträge aus Bestand: gültiges Ergebnis, Seite zeigt sinnvollen Zustand.

---

### Task 1: Simulationskern
**Files:** Create `backend/app/werk/sim.py`, Test `backend/tests/test_sim.py`.
**Produces:** `Customer(id, name, credit_limit)`, `SimLine(article: calc.Article, quantity, unit)`, `SimOrder(id, number, customer, received_at, due, lines)`, `simulate(orders, stock: dict[str, int], materials, settings: calc.Settings, workers: dict[str, int], credit_hold_min: float, prices: dict[str, float]) -> dict` mit `orders[{id, number, customer, value, pallets, due, received_at, shipped_at, days_delta, on_time, stages[{stage, label, resource, slot, arrive, start, end}], trucks[{truck, dock, start, end}], positions[{code, units, from_stock, produced}]}]`, `resources[{key, label, kind, capacity}]`, `stock{code: {name, units_per_pallet, points[[t, units]]}}`, `closed`, `kpis{on_time_rate, avg_lead_hours, utilization{key: pct}, avg_wait_hours{key: h}}`, `start`, `end`, `warnings`.
- [ ] Failing tests (Spec „Tests“): gemeinsame Person, Kreditklärung, GF ab 100 Paletten, Bestand voll/teilweise, EDD auf der Linie, Tore begrenzt, Bestandsverlauf ≥ 0, Kennzahlen, leere Liste, Artikel ohne Arbeitsplan.
- [ ] Implementieren, GREEN, Commit `feat(leitstand): Simulationskern`.

### Task 2: Daten, API, Testwerk
**Files:** Modify `models.py`, `migrations.py`, `api/planning.py` (Stammdaten: Preis, Kunden, Bestand, Aufträge), `examples/testwerk/testwerk.json` (Generator), `scripts/load_testwerk.py`; Create `api/orders.py`; Tests `test_testwerk_data.py`, `test_leitstand_example.py`.
- [ ] Failing tests: Testwerk hat 6 Kunden, 14 Aufträge in KW 40, Bestand für 5 Artikel, Preise > 0, `workers` je Büro-Station; Beispiel-Simulation (ohne DB): alle Aufträge verladen, mindestens eine Kreditklärung, mindestens ein Auftrag aus Bestand, Termintreue zwischen 0 und 1.
- [ ] Modelle, Migration `articles.price`, API (`GET /api/customers`, `GET/POST /api/orders`, `DELETE /api/orders/{id}`, `GET /api/stock`, `POST /api/simulation`), Stammdaten-Import erweitert, Lader, Daten.
- [ ] GREEN, Backend neu starten, Lader `--refresh`, `curl` Simulation. Commit `feat(leitstand): Auftragsbuch, Bestand und Simulations-API`.

### Task 3: Zustand zur Uhrzeit
**Files:** `frontend/src/lib/api.ts` (Typen, `orders`, `simulation`), Create `frontend/src/lib/leitstand.ts`, `leitstand.test.ts`.
**Produces:** `stateAt(result, t: number)` → Büro je Station {busy[{slot, order}], queue[], hold[]}, Fertigung je Ressource {current {order, progress}, queue[]}, Bestand je Artikel (Einheiten), Tore je Platz {order, truck, progress}, wartende LKW, heute raus, Auftragsstatus je Auftrag, offen/geschlossen je Kalender.
- [ ] Failing tests mit kleinem Ergebnis-Objekt, GREEN, Commit.

### Task 4: Seite Leitstand
**Files:** Create `frontend/src/app/leitstand/page.tsx`, `components/leitstand/{Clock,OrderBook,OfficeZone,ProductionZone,StockZone,ShippingZone,OrderPath}.tsx`; Modify `AppShell.tsx` (Nav).
- [ ] Umsetzung nach Mockup; Uhr per requestAnimationFrame, Tempo 1 h/6 h/1 d je Sekunde, Schieberegler; Klick auf Auftrag → Weg; Kennzahlen.
- [ ] lint, tsc, test; Browser: Abspielen, Schieben, Auftrag wählen, mobil. Commit.

### Task 5: Auftrag aus Planung anlegen
- [ ] Knopf „Als Auftrag anlegen“ in `/planung` → `POST /api/orders` (Kunde aus Formular), Toast mit Nummer und Link zum Leitstand. Browser. Commit.

### Task 6: Doku, Review, PR
- [ ] README/AGENTS, Suiten + Build, Abschluss-Review, Fixes, PR.
