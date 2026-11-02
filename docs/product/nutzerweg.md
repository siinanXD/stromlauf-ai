# Nutzerwege

`npm run test:nutzerweg` (in `frontend`) spielt FB-01 in der laufenden Compose-Demo durch, nur über die Oberfläche
(`frontend/e2e/nutzerweg.spec.ts`, Wrapper `frontend/scripts/nutzerweg.mjs`). Jeder Weg prüft einen fachlichen Wert, nicht
nur „Seite lädt“.

```bash
docker compose --profile demo up --build -d --wait     # Demo starten, FB-01 wird im Hintergrund gelesen
cd frontend && LIVE_URL=http://localhost:3100 npm run test:nutzerweg
```

- `LIVE_API_URL` (Standard `http://localhost:8010`) braucht der Wrapper nur, um zu warten, bis FB-01 gelesen ist.
- Exit 0 = alle Wege grün, 1 = mindestens ein Weg rot, 2 = nicht prüfbar (kein `LIVE_URL`, Frontend oder Backend nicht
  erreichbar, FB-01 nach 8 Minuten nicht gelesen). Solange das Hosting aussteht (SIN-1251), ist die öffentliche Demo
  „nicht prüfbar“; der Lauf gegen die lokale Demo ist der Nachweis.
- Ausgabe: `NUTZERWEG_DIR` (Standard `../tmp/nutzerweg`) mit `ergebnis.md`, `playwright.json` und je Weg einem Screenshot,
  auch bei Rot.
- Kein Modellaufruf: `POST /api/chat` wird abgefangen, die Meldung zeigt deshalb „Die Antwort ist fehlgeschlagen“. Geprüft
  wird, was ohne Modell antwortet (Fehlerliste, Befundkarte, Signalweg, Planseite). `NUTZERWEG_CHAT=1` lässt den Aufruf
  durch und kostet bei gesetztem Schlüssel Geld; Antworttext und Belege prüft weiterhin `e2e/demo.spec.ts` (`E2E_CHAT=1`).

## Wege und Vorlage

Figma: `wtxajO1YC5HvtQG7CI44BC`, Seite „Screens · Desktop“ (Vorlagen und Beispieldaten: `design/figma/README.md`).

| Weg | Prüft | Figma-Frame |
| --- | --- | --- |
| 1 `maschine-oeffnen` | Übersicht → FB-01, Kopf, Meldungsfeld, Bereich Aufbau | `Desktop · Störfall mit Detail` (Kopfzeile, Spalte Störfälle) |
| 2 `stoerfall-melden` | Meldung → Block Fehlerliste mit E-F2 und Ursache „Motorschutz -F2 ausgelöst“ | `Desktop · Störfall mit Detail` (Block-Karte „Fehlerliste“) |
| 3 `quelle-der-antwort` | Fehlereintrag nennt „Stromlaufplan Blatt 3“; Bauteil -F2, Befundkarte `/3.2`, Planseite des Stromlaufplans öffnet | `Desktop · Störfall mit Detail` (Detail -F2: Befundkarte, Planseite-Karte) |
| 4 `signalweg-oeffnen` | „Signalweg öffnen“ → Hauptweg -F2 bis -M1 über -X3:3, E0.2, FB 10 NW 1, A4.0, -X3:9, -K1, -X4:U | `Desktop · Signalweg Vollbild` |
| 5 `signalweg-quelle` | Planseite-Karte „Seite 3“, „Groß öffnen“ zeigt `01_Stromlaufplan_FB-01.pdf`, Seite 3 | `Desktop · Signalweg Vollbild` (Auswahl, Planseite-Karte) |

Screenshots des Laufs vom 2026-11-02 neben den Frames: `docs/assets/nutzerweg/` (`figma-*.png` = Vorlage, `1-…` bis `5-…` = Lauf).

### Abweichung der Vorlage (Weg 4)

Der Frame `Desktop · Signalweg Vollbild` und `design/figma/beispiele/signalweg.json` zeigen den Weg -F2 → E0.2 → FB 10 NW 4
→ A4.3 → -X3:12 → -H2. Die Demo liefert seit Issue #121 (vorwärts gewinnt der Weg zum Motor) -F2 → … → -K1 → -M1; -H2 steht
nicht mehr im Hauptweg. Der Weg prüft das Verhalten der Demo, nicht den älteren Frame. Die Vorlage muss nachgezogen werden
(Figma-Frame und Beispiel-JSON neu aus `scripts/figma_json.py` erzeugen).

## Regel

Sichtbare Änderungen erweitern den Weg im selben PR (`AGENTS.md`, Abschnitt „Nutzerweg“). Ein roter Weg wird ein eigenes
kleines Issue; er wird nicht aus dem Test genommen, um grün zu werden.
