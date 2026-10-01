# Figma-Vorlagen

Das Figma-Plugin „Stromlauf Vorlagen füllen“ baut iOS-artige Screens aus JSON. Die Dateien in diesem Ordner
legen fest, welches JSON es bekommt, und liefern Beispiele mit echten Daten.

Figma-Datei: https://www.figma.com/design/wtxajO1YC5HvtQG7CI44BC

## Vorlagen

| `vorlage` | Screen | Inhalt |
| --- | --- | --- |
| `stoerfall-antwort` | Antwort zu einem Störfall | Meldung, Treffer der Fehlerliste, Antworttext, Bauteile mit Art, Stellen im Plan, Belege, Signalweg |
| `signalweg` | Signalweg | Hauptweg eines Kennzeichens in festen Spalten, mit Abzweigen und Herkunft je Kante |
| `stoerfaelle` | Störfall-Liste | Störfälle (Chats) einer Maschine mit Ort |

Jede Datei hat oben `vorlage` und `"version": 1`. Neu sind nur die Felder der obersten Ebene (`maschine`, `frage`,
`zeit`, `antwort`, `ort`); alles darunter hat die Form der API-Typen in `frontend/src/lib/api.ts` (`FaultHits`,
`PlanSpot`, `SignalMainData`, `Conversation` …). Das Plugin nimmt diese Dateien so an.

- `schemas/`: JSON Schema 2020-12 je Vorlage, gemeinsame Typen in `defs.schema.json`. Zusätzliche Felder der API
  sind erlaubt, die oberste Ebene ist fest.
- `beispiele/`: je Vorlage eine Datei mit Daten der Beispielanlage Förderband FB-01 (`examples/foerderband/`),
  erzeugt mit `scripts/figma_json.py`.

## JSON erzeugen

`scripts/figma_json.py` holt die Daten, baut das JSON und prüft es gegen das Schema (mit `jsonschema`, sonst mit
einer eingebauten Prüfung). Kein Weg fragt ein Modell: der Antworttext kommt aus einem gespeicherten Chat
(`--conversation`) oder aus `--antwort`.

**Mit laufendem Backend** (nur die öffentliche API; Adresse `--api` oder `STROMLAUF_API_URL`, Standard
`http://localhost:8010`; Schlüssel aus `STROMLAUF_API_KEY`):

```bash
backend/.venv/Scripts/python scripts/figma_json.py --vorlage stoerfall-antwort --maschine "Foerderband FB-01" --conversation <Chat-ID> --out antwort.json
backend/.venv/Scripts/python scripts/figma_json.py --vorlage stoerfaelle --maschine "Foerderband FB-01" --out stoerfaelle.json
```

**Offline** (ohne Backend und Datenbank): liest einen Beispielordner wie einen Upload und ruft die Funktionen des
Backends direkt auf. Die erste PDF braucht wegen Docling etwa 15 s.

```bash
backend/.venv/Scripts/python scripts/figma_json.py --offline examples/foerderband --vorlage signalweg --maschine "Foerderband FB-01" --tag -F2 --out signalweg.json
```

Offline gibt es keine Datenbank-IDs (sie heißen `offline-…`), keine Treffer an anderen Maschinen und keine
erledigten Störfälle; die Störfall-Liste enthält nur den Störfall, den `--meldung` anlegt. Halle und Fehlerliste
kennt der Offline-Weg nur für FB-01 (`scripts/load_example.py`). Alle Optionen stehen im Kopf des Skripts.

## Beispiele neu erzeugen

Die Beispiel-Antwort ist kein Modelltext, sondern der Eintrag E-F2 der Fehlerliste (Ursache und Behebung) mit den
Belegen aus seinem `doc_ref`.

```bash
A="E-F2: Motorschutz -F2 ausgeloest (E0.2 = 0) [[01_Stromlaufplan_FB-01.pdf|Blatt 3]]. -F2 pruefen, Motorstrom -M1 messen (Nennstrom 3,5 A). Nach Abkuehlen einschalten, mit -S1 quittieren [[06_Betriebsanleitung_FB-01.md|Kap. 6]]."
O=(--offline examples/foerderband --maschine "Foerderband FB-01" --zeit 2026-10-01T09:41:00+02:00)
backend/.venv/Scripts/python scripts/figma_json.py --vorlage stoerfall-antwort "${O[@]}" --meldung "Störung Motorschutz Förderband" --antwort "$A" --out design/figma/beispiele/stoerfall-antwort.json
backend/.venv/Scripts/python scripts/figma_json.py --vorlage signalweg "${O[@]}" --tag -F2 --out design/figma/beispiele/signalweg.json
backend/.venv/Scripts/python scripts/figma_json.py --vorlage stoerfaelle "${O[@]}" --meldung "Störung Motorschutz Förderband" --out design/figma/beispiele/stoerfaelle.json
```

`backend/tests/test_figma_json.py` prüft den Offline-Weg gegen FB-01 und, dass die Beispiele zum Schema passen.
