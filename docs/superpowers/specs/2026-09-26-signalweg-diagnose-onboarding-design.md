# Signalweg, geführte Fehlersuche, Anlagen-Onboarding

Stand: 2026-09-26 · Auftrag: „alle drei bauen, dann zeigen; keine API-Kosten“

## Harte Vorgabe: ohne Claude

Alle drei Funktionen arbeiten deterministisch aus Dokumenten, die schon hochgeladen sind:
Klemmenplan (CSV), Stückliste (XLSX), Symboltabelle (SDF), AWL, Markdown-Tabellen aus Handbüchern
(Chunks, damit auch Docling-PDFs gehen). Kein LLM- oder Vision-Aufruf. Kostenpflichtige Ergänzungen
(Draufsicht/Schaltschrank per Vision) bleiben die vorhandenen Knöpfe auf der Maschinenseite.
Design: Blaupause-Bausteine; kein eigener Figma-Entwurf (Auftrag: erst bauen, dann zeigen).

## 1. Signalweg als Diagramm

**Graph je Wissensquelle** (`app/ingestion/signal_graph.py`, rein, getestet):
- Knoten: `device` (-K1), `terminal` (-X3:1), `address` (E0.0), `network` (FB 10 NW 2), `variable` (#Freigabe).
- Kanten mit Richtung des Signals:
  - Klemmenplan-Zeile mit Eingangsadresse (E…): Feldgerät → Klemme → Adresse.
  - Zeile mit Ausgangsadresse (A…) oder Schaltgerät intern (-K1): intern → Klemme → extern.
  - Versorgungszeilen (+24 V, 0 V, PE, -X1, -X2) werden übersprungen.
  - AWL: jede gelesene Größe → Netzwerk → jede geschriebene Größe. FB-Parameter werden über den `CALL`
    im OB (Parameter := Adresse) bzw. den Deklarationskommentar „(E0.0)“ an Adressen gebunden.
  - Symboltabelle: Symbol = Adresse (gleicher Knoten).
- `signal_path(graph, tag, depth=8)` → Knoten mit Ebene (negativ = Quelle, positiv = Folge) und Kanten;
  Knoten mit mehr als 8 Nachbarn werden nicht weiter aufgefächert (Sammelschienen, Karten).
- Knoten tragen `ref` (Blatt/Spalte aus Stückliste/Klemmenplan) bzw. Baustein/Netzwerk.

**API:** `GET /api/signal-path?tag=&source_id=` (404, wenn Kennzeichen nicht im Graph).
**Frontend:** Komponente `SignalPath` (React Flow, Ebenen links → rechts, Start hervorgehoben).
Einstieg: Maschinenseite Tab **Signalweg** (Eingabe + Vorschlag aus gewähltem Teil) und Knopf
„Signalweg“ im Draufsicht-Panel und in der Befundkarte. Klick: Gerät/Klemme → Seitenansicht mit
Spaltenmarkierung; Netzwerk → AWL-Text im Seitenpanel.

## 2. Geführte Fehlersuche

- Neue Tabelle `diagnosis_sessions`: id, machine_id, fault_id (nullable), started_at, finished_at,
  steps (JSON: text, tag, ref, status ok|nok|skip|open, note), outcome (resolved|unresolved), finding.
  Nur neue Tabelle, keine Änderung an bestehenden (create_all).
- Schritte (rein, `diagnosis.py`): aus „Behebung“ der Fehlerzeile, getrennt an Satzenden und „;“,
  plus je beteiligtem BMK ohne eigenen Schritt „{BMK} prüfen“; jeder Schritt bekommt den ersten
  Blatt-Verweis des BMK.
- API: Session anlegen, Schritt setzen, abschließen; Liste je Maschine (Instandhaltungslog).
  Abschluss mit „in Fehlerliste übernehmen“ hängt den Befund datiert an Ursache/Behebung an.
- Frontend: im Tab Fehler je Zeile „Diagnose starten“ → Checkliste (✓ / ✗ / –, Notiz, Beleg-Chip),
  Abschluss-Dialog; darunter Instandhaltungslog mit Häufigkeit je Fehlercode.

## 3. Anlagen-Onboarding aus der Doku

- `GET /api/sources/{id}/onboarding` → Vorschlag: Name (Stücklisten-Titel oder Quellenname),
  Maschinentyp (Schlüsselwörter), Anzahl Betriebsmittel, Fehlerliste aus Markdown-Tabellen mit
  Spalten Symptom | Ursache | Prüfung/Abhilfe/Behebung (Kennzeichen daraus extrahiert, Verweis =
  Dokument + Kapitelüberschrift), Hinweise auf optionale Vision-Schritte.
- `POST /api/halls/{id}/onboard` mit Name, Typ, source_id, ausgewählten Fehlern → Maschine + Fehler.
- Frontend: im Werk „Aus Dokumentation anlegen“ → Quelle wählen → Vorschau mit Häkchen → anlegen →
  Maschinenseite.

## Tests

pytest mit den FB-01-Beispieldateien: Graph (-S1 → -X3:1 → E0.0 → NW1 → … → A4.0 → -X3:9 → -K1 →
-X4:U → -M1), Schritte aus Fehlertext, Fehler-Tabellen-Parser, Onboarding-Vorschlag. Frontend: tsc,
lint, vitest, Build; Browser-Durchlauf ohne Chat.
