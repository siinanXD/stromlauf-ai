# Signalweg, Diagnose, Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drei deterministische Funktionen: Signalweg-Diagramm, geführte Fehlersuche mit Log, Onboarding einer Maschine aus der Doku.

**Architecture:** Reine Parser/Graph-Module in `backend/app/ingestion/` (pytest gegen FB-01), dünne Router in `backend/app/api/`, React-Komponenten in `frontend/src/components/{signal,diagnosis,onboarding}/`.

**Tech Stack:** FastAPI, SQLAlchemy, openpyxl, bestehender `awl_parser` · Next.js 16, React Flow, shadcn.

**Spec:** `docs/superpowers/specs/2026-09-26-signalweg-diagnose-onboarding-design.md`

## Global Constraints

- Kein LLM-/Vision-Aufruf in Code, Tests oder Verifikation.
- Nur neue Tabellen (`diagnosis_sessions`), keine Spalten an bestehenden Tabellen.
- Rohdateien über `Document.storage_path`; Markdown-Tabellen über `Chunk.content`.

## Review Focus

1. Quelle ohne Klemmenplan/AWL (z. B. nur PDFs) → Signalweg 404 mit Hinweis, keine 500. Test in Task 1.
2. Kennzeichen an Sammelschiene (-X2:2, 0 V) → Graph explodiert nicht (Hub-Grenze). Test in Task 1.
3. Fehler ohne Behebungstext → Diagnose hat mindestens die BMK-Schritte oder einen Freitext-Schritt. Test in Task 3.
4. Handbuch ohne Fehlertabelle → Onboarding-Vorschlag mit leerer Fehlerliste. Test in Task 5.
5. Doppeltes Onboarding derselben Quelle in dieselbe Halle → zweite Maschine mit Namenszusatz, kein Fehler. Prüfung in Task 6.

---

### Task 1: Signal-Graph (rein)
**Files:** Create `backend/app/ingestion/signal_graph.py`, `backend/tests/test_signal_graph.py`.
**Produces:** `Node(id, kind, label, ref)`, `Graph(nodes: dict[str, Node], edges: set[tuple[str,str]])`, `build_graph(terminal_rows: list[list[str]], bom_rows: list[tuple[str,str,str]], symbols: list[dict], awl_text: str) -> Graph`, `signal_path(graph, tag, depth=8, hub=8) -> dict | None` (`nodes: [{id, kind, label, ref, level}]`, `edges: [{source, target}]`).
- [ ] Tests (FB-01-Dateien): Pfad von -S1 enthält in Reihenfolge -X3:1, E0.0, ein Netzwerk, A4.0, -X3:9, -K1, -X4:U, -M1 (Level streng steigend entlang dieser Kette); -M1 hat Level > 0 von -S1 aus; `signal_path(g, "-X2:2")` hat < 40 Knoten; leerer Graph → None.
- [ ] RED → GREEN → Commit `feat(signal): Signalgraph aus Klemmenplan, Symboltabelle und AWL`.

### Task 2: Signalweg-API + UI
**Files:** Create `backend/app/api/signal.py`, `frontend/src/components/signal/SignalPath.tsx`; Modify `main.py`, `lib/api.ts`, Maschinenseite (Tab „Signalweg“), `PartPanel.tsx` (Knopf), `FactCard.tsx` (Knopf → Maschine), Loader für Quelle (Cache je Quelle + mtime).
- [ ] curl `/api/signal-path?tag=-S1&source_id=<FB01>`; Browser: Tab Signalweg zeigt Kette, Klick auf -K1 öffnet Blatt.
- [ ] Commit `feat(signal): Signalweg-Diagramm auf der Maschinenseite`.

### Task 3: Diagnose-Schritte (rein) + Modell
**Files:** Create `backend/app/ingestion/diagnosis.py`, `backend/tests/test_diagnosis.py`; Modify `models.py` (`DiagnosisSession`), `schemas.py`.
**Produces:** `build_steps(fix: str, tags: list[str], refs: dict[str,str]) -> list[dict]`, `append_finding(text: str, finding: str, day: date) -> str`.
- [ ] Tests: Sätze getrennt, BMK ohne eigenen Schritt ergänzt, Refs gesetzt, leerer fix → Schritte nur aus BMK bzw. ein „Befund aufnehmen“-Schritt; `append_finding` hängt „[26.09.2026] …“ an.
- [ ] Commit `feat(diagnose): Pruefschritte aus der Fehlerliste`.

### Task 4: Diagnose-API + UI
**Files:** Create `backend/app/api/diagnosis.py`, `frontend/src/components/diagnosis/DiagnosisRunner.tsx`, `MaintenanceLog.tsx`; Modify `FaultTable.tsx` (Knopf), Maschinenseite, `lib/api.ts`.
- [ ] Browser: Diagnose zu E-PH starten, Schritte abhaken, abschließen mit Übernahme → Log-Eintrag, Fehlerzeile enthält Befund. Testdaten danach entfernen.
- [ ] Commit `feat(diagnose): gefuehrte Fehlersuche mit Instandhaltungslog`.

### Task 5: Onboarding-Vorschlag (rein)
**Files:** Create `backend/app/ingestion/onboarding.py`, `backend/tests/test_onboarding.py`.
**Produces:** `fault_rows_from_markdown(markdown: str, doc_label: str) -> list[dict]`, `guess_machine(name_hints: list[str]) -> tuple[str, str]`.
- [ ] Tests: FB-01-Handbuch → 5 Fehler mit Symptom/Ursache/Prüfung, Tags, Verweis „Betriebsanleitung Kap. 6“; Tabelle ohne passende Spalten → []; „Stueckliste Foerderband FB-01“ → („Foerderband FB-01“, "conveyor").
- [ ] Commit `feat(onboarding): Vorschlag aus Stueckliste und Handbuch`.

### Task 6: Onboarding-API + UI
**Files:** Create `backend/app/api/onboarding.py`, `frontend/src/components/onboarding/OnboardingDialog.tsx`; Modify `werk/page.tsx`, `lib/api.ts`, `main.py`.
- [ ] Browser: „Aus Dokumentation anlegen“ → FB-01 → Vorschau → anlegen → Maschinenseite mit Fehlern; zweimal → Namenszusatz „(2)“. Testmaschinen danach löschen.
- [ ] Commit `feat(onboarding): Maschine aus der Dokumentation anlegen`.

### Task 7: Abschluss
- [ ] README/AGENTS, volle Checks, Review durch frischen Agenten, Fix-Pass, Push, PR gegen `master`.
