# Eval: Antwortqualitaet messen

Eine Fragenliste (`questions.jsonl`), drei Schichten. Die ersten beiden kosten nichts.

| Schicht | Aufruf | Kosten | Misst |
| --- | --- | --- | --- |
| Retrieval | `python eval/run_retrieval.py` | keine, Sekunden | Liefern die Werkzeuge die richtigen Belege? (Kennzeichen-, Wort-, hybride Suche, Befundkarte, Signalweg, Vorkalkulation, Standort) |
| Wiederbewertung | `python eval/rescore.py eval/results/<lauf>.json` | keine | Gespeicherte Agentenantworten mit der aktuellen Fragenliste neu bewerten |
| Agent | `python eval/run_eval.py` | **API-Tokens je Frage**, ca. 20 min | Antwortet der Chat-Agent Ende-zu-Ende richtig, zitiert er, nutzt er das passende Werkzeug? |

Erst Retrieval laufen lassen. Wenn dort ein Fakt fehlt, kann der Agent ihn nicht finden; das ist ohne
Agentenlauf zu beheben. Den Agentenlauf nur bewusst starten.

## Fragen

51 Fragen, sechs Quellen:

| Quelle | Fragen | Daten |
| --- | --- | --- |
| Foerderband FB-01 | 9 | `examples/foerderband/` (`scripts/load_example.py`) |
| Umroller UR-01 | 11 | `examples/umroller/` (`scripts/load_testwerk.py --docs`) |
| Aufrollung PM1-AR | 10 | `examples/aufrollung/` (`scripts/load_testwerk.py --docs`) |
| Festo MPS | 11 | `testdata/festo/` (lokal, Festo Didactic InfoPortal) |
| AWL Praxisprojekte | 6 | `testdata/awl/bnt_modell.awl` (aus awlsim, GPLv2) |
| Testwerk (Planung, Standort) | 4 | `scripts/load_testwerk.py`; nur Retrieval (`"agent": false`), der Chat-Agent hat dafuer keine Werkzeuge |

Fuenf Fragen sind Fallen (`*-nicht-vorhanden`): die Antwort steht in keinem Dokument. Erwartet wird
„nicht vorhanden“, bestraft wird eine erfundene Zahl.

Je Zeile: `id`, `source`, `question`, `must_contain` (Regex, Gross/Klein egal, `|` trennt Alternativen),
`must_not_contain` (Halluzinations-Fallen), `expect_sources` (Dateien, die zitiert sein muessen). Optional:

- `retrieval`: `{"mode": "tag|semantic|keyword|fact|signal|calc|site", "query": ...}` — Anfrage der
  Retrieval-Schicht. Die kuerzeste Anfrage, die die Belege liefert (`"Blockade"` statt der ganzen Frage).
  Bei `calc` ist `query` der Auftrag mit Artikelcodes, bei `site` ein Namensteil der Halle.
- `tools`: Werkzeuge, die der Agent aufrufen soll (`find_tag`, `search_knowledge`, `keyword_search`).
- `agent: false`: nur Retrieval.

Vor dem Eintragen die Musterantwort im Dokument nachschlagen, nicht aus einer Agentenantwort abschreiben.
Nach einer Aenderung: `python eval/rescore.py eval/results/referenz_2026-09-26.json` zeigt, was sich
an der Bewertung des Referenzlaufs aendert, ohne den Agenten zu bezahlen.

## Bewertung ohne LLM-Richter

Gleiche Antwort ergibt immer gleiche Punktzahl (`evallib.py`):

- `fakten_mittel`: Anteil gefundener `must_contain`-Muster, gemittelt ueber alle Fragen
- `quellen_ok`: Anteil der Fragen, bei denen alle erwarteten Dokumente zitiert wurden (bei `signal`,
  `calc`, `site` gibt es keine Dateinamen, dort gilt es als erfuellt)
- `sauber`: Anteil der Fragen ohne verbotene Angaben
- `werkzeug_ok`: Anteil der Fragen mit `tools`, bei denen der Agent sie aufgerufen hat (nur Agentenlauf)
- `voll_bestanden`: Fragen mit 100 % Fakten, Quellen ok, sauber und Werkzeug ok
- `nicht_bewertet_fehler`: API-/Netzfehler (auch als `error`-Event im Strom) zaehlen nicht als falsche
  Antwort. In der Retrieval-Schicht sind 404/409 und unbekannte Artikel dagegen echte Fehltreffer und
  werden mit 0 Fakten bewertet; `--min` schlaegt zusaetzlich fehl, sobald unbewertete Fehler uebrig sind.

## Ablauf-Extraktion gegen Gold (`run_flow.py`)

Misst ein Extraktions-JSON (`scripts/extract_flow.py`) gegen `testdata/festo/gold.flow.json`, ohne Modellaufruf:

- I/O-Liste: Recall und Precision ueber die normalisierte Adresse; je Treffer Symbol, Richtung, Art, Kontakt
  und BMK, aber nur wo das Gold sie nennt.
- Schrittkette: Anzahl mit Toleranz 25 % (mindestens 1), Wiedererkennung der Schrittnamen, Transitionen.
- Belege: Anteil Annahmen, mittlere Sicherheit, Verweise ohne I/O-Punkt. Kosten, Latenz und Trace-ID aus `meta`.

```bash
python eval/run_flow.py --pred eval/results/festo_pred.flow.json [--min-recall 0.9 --min-precision 0.9]
```

Ergebnis: `eval/results/flow_<zeitstempel>.json`. Exit 2, solange das Gold noch die Vorlage ist
(`summary` beginnt mit `VORLAGE`); Exit 1 unter einer Schwelle oder bei Schrittanzahl ausserhalb der Toleranz.
Gold ausfuellen: `testdata/festo/README.md`.

## Aufrufe

```bash
python eval/run_retrieval.py                              # alle Fragen mit retrieval, Sekunden
python eval/run_retrieval.py --only ur01 --min 0.9        # Filter; Exit-Code 1 unter dem Fakten-Mittel
python eval/run_retrieval.py --baseline eval/results/referenz_retrieval_2026-09-27.json

python eval/rescore.py eval/results/referenz_2026-09-26.json --out eval/results/neu.json

python eval/run_eval.py --only festo --limit 3            # Agentenlauf, kostet Tokens
python eval/run_eval.py --baseline eval/results/referenz_2026-09-26.json
```

Ergebnisse landen in `eval/results/` (ignoriert in Git bis auf die Referenzdateien, `git add -f`).
