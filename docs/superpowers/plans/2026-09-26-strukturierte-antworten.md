# Strukturierte Chat-Antworten Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chat-Antworten in fester Gliederung mit klickbaren Belegen, Spaltenmarkierung im Stromlaufplan und Befundkarte.

**Architecture:** Prompt legt Gliederung und Belegsyntax fest; Backend liefert Blatt/Spalten-Geometrie aus der PDF-Textebene und eine Befundkarte aus dem Tag-Index; Frontend parst das Markdown (reine Funktionen, Vitest) und rendert Abschnitte.

**Tech Stack:** FastAPI, pypdfium2, pytest · Next.js 16, react-markdown, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-26-strukturierte-antworten-design.md`

## Global Constraints

- Überschriften exakt: `## Kurzantwort`, `## Prüfen`, `## Details`, `## Sicherheit`.
- Belegsyntax exakt: `[[Dateiname|Ort]]`.
- Keine Vision-Aufrufe für Markierungen. Blaupause-Tokens, Rot nur für Fehler.
- Neue Abhängigkeit nur `vitest` (MIT, devDependency).

## Review Focus

1. Antwort ohne Gliederung (alte Verläufe) → wird unverändert als Markdown gezeigt. Test in Task 4.
2. Beleg mit unbekanntem Dateinamen → sichtbar, nicht klickbar, kein Absturz. Test in Task 4.
3. PDF ohne Spaltenkopf oder ohne „Blatt N“ → Seite öffnet ohne Markierung. Test in Task 1.
4. Streaming bricht mitten in `[[...` ab → Rohtext bis zum Ende, kein Fehler. Test in Task 4.
5. Frage ohne BMK → keine Befundkarte, kein Request. Prüfung in Task 6.

---

### Task 1: Blatt- und Spaltenerkennung

**Files:** Create `backend/app/ingestion/pdf_layout.py`, `backend/tests/test_pdf_layout.py`; Modify `backend/app/api/sources.py` (Endpoint `locate`), `backend/app/schemas.py` (`LocateOut{page:int, column:int|None, box:{x0,y0,x1,y1}|None}`).

**Interfaces:** Produces `Column(n:int, x0:float, x1:float, y0:float, y1:float)`, `sheet_page(path, sheet) -> int|None`, `page_columns(path, page) -> list[Column]`, `parse_ref(ref) -> tuple[int|None, int|None, int|None]` (sheet, column, page).

- [ ] Tests: `sheet_page(FB01, 3) == 3`; `len(page_columns(FB01, 3)) == 8`; Spalte 8 `x1 > 0.9` und `x0 > 0.8`; alle `y0 < 0.1`, `y1` zwischen 0.7 und 0.9; `parse_ref("/3.8") == (3, 8, None)`, `parse_ref("S. 12") == (None, None, 12)`, `parse_ref("Kap. 6") == (None, None, None)`; `page_columns` auf Seite ohne Kopf (AWL-freie Stückliste gibt es nicht als PDF → Test mit Seite 1 des FB01, falls Kopf fehlt, sonst synthetisch leeres PDF über pypdfium2) → `[]`.
- [ ] RED → implementieren → GREEN, Suite grün.
- [ ] Endpoint + curl `/api/documents/<FB01>/locate?ref=/3.8` → page 3, column 8, box gesetzt.
- [ ] Commit `feat(chat): Blatt und Spalte aus Stromlaufplan-Verweisen bestimmen`.

### Task 2: Befundkarte

**Files:** Create `backend/app/api/facts.py` (Router, in `main.py` registrieren), `backend/app/ingestion/fact_card.py`, `backend/tests/test_fact_card.py`; Modify `schemas.py` (`FactCard`, `FactRow`, `FactValue`).

**Interfaces:** `build_fact_card(tag: str, hits: list[FactHit]) -> dict | None` mit `FactHit = dict(tag, doc_type, filename, document_id, page, section, context)`.

- [ ] Tests mit Fixture-Treffern: Klemmenplan-Kontext „-X4:U | -M1:U1 …“ ergibt Zeile Klemmen mit `-X4:U`; Symboltabelle-Kontext mit „A4.0 … -K1“ ergibt SPS-Zeile bei Tag -K1; Stromlaufplan-Treffer S. 3 ergibt Zeile Stromlaufplan mit `S. 3`; Stückliste-Kontext liefert `bom_line`; keine Treffer → None.
- [ ] RED → GREEN; Endpoint `GET /api/facts?tag=&source_ids=` (404 ohne Treffer); curl mit -M1 gegen FB-01.
- [ ] Commit `feat(chat): Befundkarte aus dem Kennzeichen-Index`.

### Task 3: Prompt

**Files:** Modify `backend/app/agent/prompts.py` (Abschnitt „Antwortformat“ ersetzen).

- [ ] Gliederung + Belegsyntax + Regeln aus Spec §1 eintragen; Tabellen nur in Details; keine Werkzeug-Nacherzählung.
- [ ] Commit `feat(chat): feste Antwortgliederung und Belegsyntax im Prompt`.

### Task 4: Parser (Vitest)

**Files:** Modify `frontend/package.json` (vitest, Script `test`); Create `frontend/src/lib/answer.ts`, `frontend/src/lib/answer.test.ts`.

**Interfaces:** `type Citation = {index:number; filename:string; loc:string}`; `parseCitations(md) -> {markdown:string; citations:Citation[]}` (Ersatz `[label](cite:N)`, unvollständiges `[[` am Ende bleibt Text); `splitSections(md) -> {kurz?:string; pruefen?:string; details?:string; sicherheit?:string; frei:string}`; `citationLabel(c, docType?) -> string`; `refOf(loc) -> {ref?:string; page?:number}`.

- [ ] Tests für Review-Focus 1, 2, 4 plus Normalfall.
- [ ] RED → GREEN (`npm test`). Commit `feat(chat): Parser fuer Antwortabschnitte und Belege`.

### Task 5: Antwortansicht und Seitenansicht mit Markierung

**Files:** Create `frontend/src/components/chat/AnswerView.tsx`, `CitationChip.tsx`, `SourcesFooter.tsx`; Modify `Message.tsx`, `PageViewer.tsx` (Prop `reference?: string`, Overlay), `lib/api.ts` (`locate`, `facts`), `app/page.tsx` (Seitenansicht rechts statt Overlay auf `lg`).

- [ ] Umsetzen gemäß Figma 7:6; `tsc`, `lint`, `test` grün.
- [ ] Commit `feat(chat): gegliederte Antwort, klickbare Belege, Spaltenmarkierung`.

### Task 6: Befundkarte im Chat

**Files:** Create `frontend/src/components/chat/FactCard.tsx`; Modify `AnswerView.tsx`.

- [ ] BMK aus Nutzerfrage (erstes Geräte-Kennzeichen, Regex wie Backend `-[A-Z]{1,3}\d+`), sonst keine Karte.
- [ ] Commit `feat(chat): Befundkarte ueber der Antwort`.

### Task 7: E2E und Abschluss

- [ ] Backend neu starten, eine echte Frage gegen FB-01 (kostet eine Antwort), Screenshot; Klick `/3.8` zeigt Markierung.
- [ ] README-Abschnitt Chat ergänzen; Commit, Push, PR (Basis: `claude/enterprise-frontend-machine-setup-486dcf`).
