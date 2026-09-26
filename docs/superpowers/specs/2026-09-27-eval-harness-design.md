# Eval-Harness: Retrieval-Schicht, Wiederbewertung, Testdoku-Fragen

Stand: 2026-09-27 · Auftrag: „mach den Eval-Harness“. Baut auf dem vorhandenen `eval/` auf
(`questions.jsonl`, `run_eval.py`, Referenzlauf 2026-09-26). Ziel: Werkzeuge, Prompts und Agent
messbar machen, ohne dass jeder Messlauf API-Tokens kostet.

## Was fehlt heute

`run_eval.py` schickt jede Frage an den Chat-Agenten: ein Lauf über 24 Fragen dauert ca. 20 min und
kostet Tokens pro Frage. Es gibt keine kostenlose Vorstufe, die prüft, ob die Werkzeuge die richtigen
Belege liefern, und eine gespeicherte Antwort kann nicht mit geänderten Erwartungen neu bewertet
werden. Die Testdokumentationen UR-01 und PM1-AR (PR #15) und das Testwerk sind nicht abgedeckt.

## Drei Schichten, eine Fragenliste

`eval/questions.jsonl` bleibt die einzige Quelle. Je Zeile wie bisher `id`, `source`, `question`,
`must_contain` (Regex), `must_not_contain`, `expect_sources`; neu und optional:

- `retrieval`: `{"mode": "tag|semantic|keyword|fact|signal|calc|site", "query": <str|object>}` —
  Anfrage für die kostenlose Schicht. Fehlt es, ist die Frage nur ein Agentenfall (Festo, AWL, Fallen).
- `tools`: Werkzeugnamen, die der Agent benutzen soll (`find_tag`, `search_knowledge`, ...).
- `agent`: `false` für Fragen, die der Chat-Agent nicht beantworten kann (Testwerk: Vorkalkulation,
  Standort — dafür gibt es nur HTTP/MCP). Voreinstellung `true`.

1. **Retrieval (kostenlos, deterministisch) — `python eval/run_retrieval.py`:** ruft je Frage den
   Endpunkt der Anfrage auf (`/api/search?mode=`, `/api/facts`, `/api/signal-path`, `/api/calc`,
   `/api/site`), macht aus der Antwort Text plus zitierte Dateinamen und bewertet mit denselben
   Regeln wie der Agentenlauf (`fakten`, `quellen`, `sauber`). Bei `signal`, `calc`, `site` gibt es
   keine Dateinamen; `quellen_ok` gilt dort als erfüllt. `calc` löst Artikelcodes über
   `/api/articles` in IDs auf. Ergebnis `eval/results/retrieval_<zeitstempel>.json`.
   Läuft in Sekunden; `--min 0.9` liefert Exit-Code 1 unter dem Mittelwert (Prüfkette).
2. **Agent (kostet Tokens) — `python eval/run_eval.py`:** wie bisher, zusätzlich `--limit N`,
   `--min`, Bewertung `werkzeug_ok` (erwartete `tools` wurden aufgerufen; `null`, wenn keine
   erwartet). Fragen mit `agent: false` werden übersprungen. Nicht ohne Rückfrage starten.
3. **Wiederbewertung (kostenlos) — `python eval/rescore.py <ergebnis.json>`:** bewertet gespeicherte
   Antworten, Quellen und Werkzeugaufrufe mit der aktuellen `questions.jsonl` neu. Damit lassen
   sich Muster nachschärfen, ohne den Agenten erneut zu bezahlen. Fragen, die im Lauf fehlen,
   werden gezählt, nicht bewertet.

Gemeinsame Logik liegt in `eval/evallib.py` (Laden und Prüfen der Fragen, SSE-Parser, Bewertung,
Zusammenfassung, Abflachen der Endpunkt-Antworten, Vergleich mit Baseline). Die Skripte sind dünn.

## Fragen ergänzen

Neu: Umroller UR-01 (10, eine Falle), Aufrollung PM1-AR (9, eine Falle), Foerderband FB-01 (+2:
Befundkarte, Signalweg), Testwerk (4: Linien der Halle Verarbeitung, Tore des Lagers, Beispielauftrag
der Vorkalkulation, Engpass Falthandtücher; `agent: false`). Fakten stammen aus den Beispieldateien
in `examples/`, nicht aus Agentenantworten. Bestehende Fragen bekommen `retrieval` und `tools`,
wo die Antwort über ein Werkzeug direkt zu finden ist.

## Kennzahlen

Wie bisher `fakten_mittel`, `quellen_ok`, `sauber`, `voll_bestanden`, `dauer_mittel_s`; neu
`werkzeug_ok` (Anteil der Fragen mit erwarteten Werkzeugen, die sie benutzt haben). Retrieval-Läufe
haben keine Dauer je Frage von Bedeutung und keine `werkzeug_ok`.

## Nicht enthalten

LLM-Richter (kostet, nicht reproduzierbar), automatische Prompt-Optimierung, Modellvergleich (geht
über zwei Agentenläufe und `--baseline`).

## Tests (pytest, ohne Netz)

`backend/tests/test_eval.py` lädt `eval/evallib.py` per `importlib` wie `test_load_testwerk.py`:
Fragenliste gültig (IDs eindeutig, Regex kompilieren, `retrieval.mode` bekannt, `agent: false` nur mit
`retrieval`); Bewertung inkl. `werkzeug_ok`; SSE-Parser gegen einen Beispielstrom; Abflachen je
Modus; Zusammenfassung mit Fehlerfällen; Baseline-Vergleich; `rescore` auf dem Referenzlauf
2026-09-26 reproduziert dessen Kennzahlen. Live-Nachweis: `run_retrieval.py` gegen das lokale
Backend, alle Fragen mit `retrieval` ≥ 0,9 im Mittel; Referenzdatei per `git add -f`.
