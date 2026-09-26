# Strukturierte Chat-Antworten mit Belegen und Befundkarte

Stand: 2026-09-26 · Design freigegeben: Figma `25Zi2sbyA5rXJcwViTqB10`, Seite „Chat-Antwort (A+C)“, Frame 7:6

## Ziel

Instandhalter und Konstrukteure (beide gleich wichtig) bekommen eine kurze, immer sichtbare
Antwort, konkrete Prüfschritte mit klickbaren Belegen und Details nur auf Wunsch. Ein Klick auf
einen Stromlaufplan-Verweis (`/3.8`) öffnet die Seite und markiert die Spalte.

Erfolg: Frage „-K1 zieht an, Motor brummt, dreht nicht“ gegen FB-01 liefert Kurzantwort,
Prüfschritte mit Belegen, Befundkarte für -M1; Klick auf `/3.8` zeigt Blatt 3 mit markierter Spalte 8.

## Nicht im Umfang

JSON-Ausgabe des Modells (Variante B), Markierung einzelner Bauteile statt Spalten,
Zeilen-/Pfad-Raster anderer Normen, Export der Antwort.

## 1. Antwortformat (Prompt)

Der System-Prompt schreibt eine feste Gliederung vor, Überschriften exakt so:

```
## Kurzantwort      2–3 Sätze, wichtigste Belege
## Prüfen           nummerierte Schritte, je Schritt ein Beleg am Ende (nur bei Handlungsfragen)
## Details          Signalweg, Tabellen, AWL-Erklärung (optional, wird eingeklappt)
## Sicherheit       nur wenn die Frage Arbeiten an der Anlage berührt (optional)
```

Belegsyntax: `[[Dateiname|Ort]]`, Ort ist eines von `/3.8` (Blatt.Spalte), `S. 12`,
`FB 10 NW 3`, `Kap. 6`, `-X4:U`. Dateiname exakt wie in den Werkzeug-Ergebnissen.
Freitext-Fragen ohne Handlungsbezug dürfen `## Prüfen` weglassen.

## 2. Backend

**`app/ingestion/pdf_layout.py`** (pypdfium2-Textebene, kein Vision):
- `sheet_page(path, sheet) -> int | None`: PDF-Seite, auf der „Blatt {sheet}“ steht; sonst
  `sheet`, wenn die Seite existiert.
- `page_columns(path, page) -> list[Column]`: Spaltenkopf = Folge 1..N (N≥4) einzelner Ziffern
  auf gleicher Höhe im oberen Drittel. Grenzen = Mitte zwischen Nachbarzentren, außen halber
  Abstand. Vertikal vom Kopf bis zur ersten Schriftfeld-Zeile (unterstes Viertel), sonst 85 %.
  Werte relativ 0..1 zum gerenderten Bild (Ursprung oben links).

**`GET /api/documents/{id}/locate?ref=/3.8`** → `{page, column, box | null}`. `S. 12` → nur `page`.
Nicht-PDF → 400, unbekanntes Blatt → 404.

**Befundkarte:** `GET /api/facts?tag=-M1&source_ids=…` → `{tag, title, bom_line, rows: [{label,
values: [{text, document_id, filename, page, ref}]}]}`. Reine Funktion
`build_fact_card(tag, hits)` baut Zeilen „Stromlaufplan“ (Seiten/Verweise), „Klemmen“
(Klemmen-Tags aus Klemmenplan-Zeilen, die den BMK nennen), „SPS“ (Adressen aus Symboltabelle/AWL-
Zeilen mit dem BMK), „Stückliste“ (Bezeichnung). Leere Zeilen entfallen; ohne Treffer 404.

## 3. Frontend

- `lib/answer.ts` (rein, getestet mit Vitest): `parseCitations(md)` ersetzt `[[Datei|Ort]]`
  durch Platzhalter-Links `cite:N` und liefert die Liste der Belege; `splitSections(md)` teilt
  nach den vier Überschriften, Rest bleibt „frei“ (alte Antworten, abweichendes Format);
  `citationLabel(cite, docType)` → „Stromlaufplan /3.8“.
- `AnswerView`: Werkzeugzeile eingeklappt („▸ N Schritte · M Fundstellen“), Befundkarte,
  Kurzantwort, Prüfen (Karten mit Beleg rechts), Sicherheit (dunkler Randstrich), Details
  eingeklappt (`<details>`), Belege gruppiert nach Dokument – nur zitierte.
- Belege werden über `message.sources` (Dateiname → document_id, doc_type) aufgelöst; nicht
  auflösbare bleiben als nicht klickbarer Text sichtbar.
- `PageViewer` bekommt `ref`: ruft `locate`, springt zur Seite, legt die Spaltenmarkierung als
  Overlay über das Bild. Auf Desktop als rechte Spalte neben dem Chat, auf Mobil als Vollbild.
  Knopf „{BMK} im Werk zeigen“ über `searchTags` (erste Maschine).
- Befundkarte: BMK = erstes Geräte-Kennzeichen in der Nutzerfrage; lädt `/api/facts`,
  erscheint nur bei Treffern.

## Fehlerbehandlung

Locate-Fehler → Seite ohne Markierung öffnen (Toast-Hinweis nur bei 404 Blatt). Facts-Fehler →
Karte entfällt still. Parser darf nie werfen: bei kaputtem Markdown Fallback auf Rohtext.

## Tests

pytest: `sheet_page`/`page_columns` gegen `examples/foerderband/01_Stromlaufplan_FB-01.pdf`
(8 Spalten, Blatt 3 = Seite 3), `build_fact_card` mit Fixture-Treffern. Vitest: Parser.
E2E: eine echte Chat-Frage gegen FB-01 (kostet Tokens für eine Antwort).
