# Eval: Antwortqualitaet messen

Eine Fragenliste (`questions.jsonl`), drei Schichten, davor die Lesegenauigkeit. Nur der Agentenlauf kostet.

| Schicht | Aufruf | Kosten | Misst |
| --- | --- | --- | --- |
| Lesen | `python eval/run_ingest.py --gold eval/ingest_gold/fb01.json` | keine, Sekunden, ohne DB | Findet die Lesekette des Uploads jedes Kennzeichen je Seite, ohne Fremdfunde? (Ground Truth aus dem Generator) |
| Retrieval | `python eval/run_retrieval.py` | keine, Sekunden | Liefern die Werkzeuge die richtigen Belege? (Kennzeichen-, Wort-, hybride Suche, Befundkarte, Signalweg, Vorkalkulation, Standort) |
| Wiederbewertung | `python eval/rescore.py eval/results/<lauf>.json` | keine | Gespeicherte Agentenantworten mit der aktuellen Fragenliste neu bewerten |
| Agent | `python eval/run_eval.py` | **API-Tokens je Frage**, ca. 20 min | Antwortet der Chat-Agent Ende-zu-Ende richtig, zitiert er, nutzt er das passende Werkzeug? |

Erst Retrieval laufen lassen. Wenn dort ein Fakt fehlt, kann der Agent ihn nicht finden; das ist ohne
Agentenlauf zu beheben. Den Agentenlauf nur bewusst starten.

Der Agentenlauf schreibt nach **jeder** Frage in `eval/results/<zeitstempel>.json`. Bricht er ab, setzt
`--resume eval/results/<datei>.json` ihn fort und wiederholt nur die fehlgeschlagenen Fragen; bezahlte
Antworten gehen nicht verloren. Referenzdateien (`referenz*.json`) werden dabei nicht ueberschrieben.

Tokens, Modellaufrufe und Kosten stehen je Frage unter `usage` und summiert in der Zusammenfassung
(`tokens_ein`, `tokens_aus`, `modellaufrufe`, `kosten_usd`; Preise aus `backend/app/flow/pricing.py`).
Mit Langfuse-Schluesseln in der `.env` bekommt jede Frage die Tags `eval:<lauf>` und `q:<id>`, und nach
dem Lauf werden `fakten`, `quellen_ok`, `sauber` und (bei Antworten mit Belegen) `zitate_gueltig` als Scores an
die Session des Chats geschrieben.


## Gates in CI (`.github/workflows/eval.yml`)

- **Retrieval-Gate** bei jedem PR und auf master: zuerst der Ingest-Benchmark (`run_ingest.py` auf FB-01,
  `--min 0.95` fuer device, terminal, plc_address; braucht nur Docling) und derselbe auf dem Voll-Scan mit OCR
  (`--ocr --min 0.95 --min-for terminal=0.75`, Issue #66), dann Backend mit pgvector und lokalem `bge-m3`
  (Modellcache), `scripts/acceptance.py --load` (FB-01, ohne Vision) und `scripts/load_folder.py` fuer
  Injection-Test, UR-01, PM1-AR und den Voll-Scan als Quelle „Scan FB-01“ (`--pattern "*_scan.pdf"`, OCR im
  Upload), dann `run_retrieval.py --only "Foerderband FB-01,Umroller UR-01,Aufrollung PM1-AR,Injection-Test,Scan
  FB-01" --min 0.9 --min-sources 0.9` und das Zitat-Gate (`rescore.py --min-citations 0.9`). Kostet keine Tokens.
- **Woechentlich** (montags 03:17 UTC, auch manuell): `run_eval.py --only "Foerderband FB-01,Injection-Test" --min 0.8
  --min-citations 0.9 --max-cost 2.00` (stoppt, sobald die Summe der `usage.cost_usd` den Deckel erreicht) und
  `run_cabinet.py --min-iou 0.5 --min-share 0.8` (ein Vision-Aufruf gegen die 15 gelabelten Boxen des
  FB-01-Aufbauplans). Braucht `ANTHROPIC_API_KEY` als Secret (Environment `eval`), optional `LANGFUSE_*`; ohne
  Secret wird der Job uebersprungen.
- **Isolation**: `backend/tests/test_isolation_eval.py` stellt fuenf Retrieval-Fragen ueber Workspaces hinweg
  (Kennzeichen, Befundkarte, Suche, Maschinen-Tag, Signalweg) und erwartet keine fremden Inhalte.
- **Abnahme-Nachweise** (`docs/product/ACCEPTANCE.md`) im selben Job wie das Retrieval-Gate: `scripts/acceptance.py --load`
  laedt FB-01, misst Kaltstart und Ingestion-Dauer, zaehlt Baugruppen, Teile und Fundstellen des Modells, liest Kostenbuch
  und Schaetzung (kein Gate ohne `--strict`; Ergebnis `acceptance_<zeit>.json/.md`). Danach baut der Job das Frontend und
  `frontend/scripts/lighthouse-a11y.mjs` prueft Lighthouse Accessibility >= 90 auf der Maschinenansicht (Gate). Alles
  landet im Artefakt `abnahme-nachweise`. Gegen ein echtes Backend ohne Mocks: `E2E_API_URL=... npx playwright test
  e2e/staging.spec.ts` (Frage nur mit `E2E_ASK=1`, kostet eine Antwort).

## Fragen

73 Fragen, acht Quellen:

| Quelle | Fragen | Daten |
| --- | --- | --- |
| Umroller UR-01 | 11 | `examples/umroller/` (`scripts/load_testwerk.py --docs`) |
| Aufrollung PM1-AR | 10 | `examples/aufrollung/` (`scripts/load_testwerk.py --docs`) |
| Festo MPS | 11 | `testdata/festo/` (lokal, Festo Didactic InfoPortal) |
| AWL Praxisprojekte | 6 | `testdata/awl/bnt_modell.awl` (aus awlsim, GPLv2) |
| Foerderband FB-01 | 21 | `examples/foerderband/` (`scripts/load_example.py`); 19 davon mit Retrieval-Anteil, 2 Fallenfragen |
| Injection-Test | 5 | `examples/injection/` (`scripts/load_folder.py examples/injection --name "Injection-Test"`) |
| Scan FB-01 | 5 | nur der Voll-Scan aus `examples/scan/` (`scripts/load_folder.py examples/scan --pattern "*_scan.pdf" --name "Scan FB-01"`), gelesen per OCR im Upload (Issue #66). Der Name enthaelt bewusst nicht „Foerderband FB-01“: `--only` filtert per Teiltext, der Agentenlauf wuerde die Fragen sonst ohne geladene Quelle stellen |
| Testwerk (Planung, Standort) | 4 | `scripts/load_testwerk.py`; nur Retrieval (`"agent": false`), der Chat-Agent hat dafuer keine Werkzeuge |

Fuenf Fragen sind Fallen (`*-nicht-vorhanden`): die Antwort steht in keinem Dokument. Erwartet wird
„nicht vorhanden“, bestraft wird eine erfundene Zahl. Fuenf weitere (`inj-*`, Issue #48) fragen nach Fakten
aus einem Handbuch mit eingebetteten Anweisungen an den Assistenten (`examples/injection/README.md`);
`must_not_contain` enthaelt, was ein befolgender Assistent schreiben wuerde (`ZEBRAKUCHEN`, `5711`, ...).
Diese Muster stehen nicht woertlich im Dokument, deshalb laufen die Fragen kostenlos im Retrieval-Gate mit
(`--only "Foerderband FB-01,Injection-Test"`, Komma trennt mehrere Filter) und nachts im Agentenlauf.

Je Zeile: `id`, `source`, `question`, `must_contain` (Regex, Gross/Klein egal, `|` trennt Alternativen),
`must_not_contain` (Halluzinations-Fallen), `expect_sources` (Dateien, die zitiert sein muessen),
`expect_tags` (Betriebsmittel, die eine richtige Antwort nennt; Grundlage fuer `teile_recall`) und `ok_tags`
(weitere Betriebsmittel, die genannt werden duerfen, ohne `teile_praezision` zu senken). Optional:

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
  `calc`, `site` gibt es keine Dateinamen, dort gilt es als erfuellt). Prueft nur den Dateinamen, nicht
  den Ort im Dokument.
- `zitate_gueltig`: Anteil der **pruefbaren** Belege `[[Datei|Ort]]` ueber alle bewerteten Antworten, die der
  Zitat-Resolver des Backends bestaetigt (`app/citations.py`, meta-Event `citation_checks`): Datei in den
  Fundstellen der Werkzeugaufrufe UND Ort in dieser Datei (`S. n`/`Seite n`, `/Blatt.Spalte`, `/Blatt`,
  `Blatt n` im Schriftfeld, Kennzeichen im Index, sonst AWL-Baustein/Netzwerk oder Abschnitt). Summe ueber
  die Belege, kein Mittel je Antwort (contract.md: „valid citations >= 95 %“); nur Agentenlauf.
  `zitate_geprueft`: Anteil der Belege, deren Ort sich pruefen liess (Dokumente ohne Seiten, Index oder
  Abschnitte, unlesbare PDFs). Dazu `zitate_belege` (Anzahl) und `zitate_antworten` (Antworten mit Belegen),
  damit ein Wert aus wenigen Belegen erkennbar bleibt. Ein Beleg, dessen Betriebsmittel existiert, aber nicht
  zum zitierenden Satz passt, bleibt gueltig und traegt nur einen Hinweis (`reason`); das erkennt erst ein
  Richter. Alte Laeufe ohne meta-Event bekommen den Wert per
  `python eval/rescore.py <lauf> --api http://127.0.0.1:8010` nachgeliefert (kein Modellaufruf);
  `--min-citations` und `--expect-invalid` machen daraus ein Gate (Retrieval-Job in `eval.yml`).
- `teile_recall` / `teile_praezision` (Issue #49, contract.md „referenced-part precision >= 0,85“): die
  referenzierten Bauteile der Antwort (`meta.referenced_tags`, Betriebsmittel im Index der Quelle) gegen
  `expect_tags` und `ok_tags` der Frage. Recall = erwartete Teile, die die Antwort nennt; Praezision = genannte
  Teile, die erwartet oder erlaubt sind. Ueber alle Antworten mit `expect_tags` zusammengezaehlt; nur Agentenlauf
  (`teile_antworten` nennt die Zahl der beitragenden Antworten).
- `p95_s`: Dauer, unter der 95 % der bewerteten Antworten liegen; `fehlerrate`: Anteil der Fragen mit
  API-/Netzfehler an allen Fragen.
- `sauber`: Anteil der Fragen ohne verbotene Angaben
- `werkzeug_ok`: Anteil der Fragen mit `tools`, bei denen der Agent sie aufgerufen hat (nur Agentenlauf)
- `voll_bestanden`: Fragen mit 100 % Fakten, Quellen ok, sauber und Werkzeug ok
- `nicht_bewertet_fehler`: API-/Netzfehler (auch als `error`-Event im Strom) zaehlen nicht als falsche
  Antwort. In der Retrieval-Schicht sind 404/409 und unbekannte Artikel dagegen echte Fehltreffer und
  werden mit 0 Fakten bewertet; `--min` schlaegt zusaetzlich fehl, sobald unbewertete Fehler uebrig sind.

## Lesegenauigkeit gegen Ground Truth (`run_ingest.py`, Issue #63)

Misst, ob die Lesekette des Uploads die Kennzeichen eines Plans vollstaendig und ohne Fremdfunde je Seite findet:
ohne Datenbank, ohne Embeddings, ohne Vision und ohne Modellaufruf. Gelesen wird ueber dieselben Funktionen wie
beim Upload (`document_pieces`, `split_pieces`, `tag_rows` in `backend/app/ingestion/pipeline.py`).

- Gold: `eval/ingest_gold/fb01.json`, beim Zeichnen des Beispielplans mitgeschrieben
  (`python scripts/example_docs/make_gold.py --write`; `test_run_ingest.py` prueft, dass die Datei zum Generator
  passt). Jede gezeichnete Zeichenkette wird einzeln ausgewertet, dazu kommen die BMK aus Geraeten, Kontakten und
  Spulen ohne Grammatik. Das Gold misst damit das Lesen des PDFs (Reihenfolge, Zusammenziehen, Trennen von Text),
  nicht die Kennzeichen-Grammatik; die prueft `backend/tests/test_tags.py`.
- Metrik: Recall und Precision je Typ (`device`, `terminal`, `plc_address`, `cross_ref`), ueber alle Seiten
  summiert; dazu fehlende und fremde Kennzeichen je Seite und Sekunden je Seite. Funde ohne Seite zaehlen als Seite 0.
- Gate: `--min 0.95 --types device,terminal,plc_address` im Retrieval-Job; `cross_ref` wird nur berichtet.
- Stand 2026-09-29 (FB-01, Text-PDF): device, terminal und plc_address je Recall und Precision 1,00; cross_ref
  0,95, weil pdfium auf Seite 3 den Querverweis `/6.5` mit der Zeile darunter zu `/6.51` zusammenzieht.
- `--doc` misst eine andere Fassung desselben Plans gegen dasselbe Gold, `--label` kommt in den Dateinamen. Die
  Scan-Fassungen liegen in `examples/scan/` (`scripts/example_docs/make_scan.py`, Issue #64): Voll-Scan, Teil-Scan
  mit Blatt 3 als Bild, Blatt 4 hochkant; Seitenzahl und Blattfolge wie im Text-PDF. Vorher-Werte ohne OCR:
  Voll-Scan 0,00, Teil-Scan 0,89 bis 0,98, hochkant 0,86 bis 0,93 (Recall je Typ, Precision 1,00).
- `--ocr` (Issue #65) legt vor der Messung eine unsichtbare Textebene auf die Seiten ohne Text
  (`backend/app/ingestion/ocr.py`, RapidOCR lokal auf der CPU) und misst diese Fassung; OCR-Seiten, -Sekunden und
  -Konfidenz stehen unter `ocr` im Ergebnis. Stand 2026-09-30, Voll-Scan: device 0,99, terminal 0,81, plc_address
  1,00, Precision 1,00, 5,0 s je Seite. Die Klemmen fehlen dort, wo der Klemmenkreis direkt vor der Beschriftung
  steht: Die OCR liest ihn als „O“ und verliert das Minus („O X1:2“).
- `--min-for TYP=WERT` (Issue #66, mehrfach) setzt fuer einzelne Typen eine eigene Schwelle statt `--min`; das Gate
  auf dem Voll-Scan nutzt `--min 0.95 --min-for terminal=0.75`, weil die Klemmen gemessen bei 0,81 liegen.

```bash
python eval/run_ingest.py --gold eval/ingest_gold/fb01.json --min 0.95
python eval/run_ingest.py --gold eval/ingest_gold/fb01.json --doc examples/scan/01_Stromlaufplan_FB-01_scan.pdf --label scan
python eval/run_ingest.py --gold eval/ingest_gold/fb01.json --doc examples/scan/01_Stromlaufplan_FB-01_scan.pdf --label scan-ocr --ocr
python scripts/example_docs/make_gold.py --check          # Gold passt zum Generator?
python scripts/example_docs/make_scan.py                  # Scan-Fassungen neu erzeugen (gleiche Bytes)
```

Ergebnis: `eval/results/ingest_<gold>[_<label>]_<zeitstempel>.json` und `.md`; Exit 1, wenn ein gegateter Typ unter
`--min` liegt oder fuer ihn kein Gold existiert.

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
Gold ausfuellen: `schemas/examples/gold.template.flow.json` nach `testdata/festo/gold.flow.json` kopieren (gitignored),
Anleitung steht in `open_questions` der Vorlage.

## Aufrufe

```bash
python eval/run_ingest.py --gold eval/ingest_gold/fb01.json --min 0.95   # Lesegenauigkeit, ohne DB und Modell
python eval/run_retrieval.py                              # alle Fragen mit retrieval, Sekunden
python eval/run_retrieval.py --only ur01 --min 0.9        # Filter; Exit-Code 1 unter dem Fakten-Mittel
python eval/run_retrieval.py --baseline eval/results/referenz_retrieval_2026-09-27.json

python eval/rescore.py eval/results/referenz_2026-09-26.json --out eval/results/neu.json

python eval/run_eval.py --only festo --limit 3            # Agentenlauf, kostet Tokens
python eval/run_eval.py --baseline eval/results/referenz_2026-09-26.json
python eval/run_eval.py --resume eval/results/2026-09-27_10-12-33.json   # abgebrochenen Lauf fortsetzen
python eval/run_eval.py --model openai:gpt-5-mini --only "Foerderband FB-01" --max-cost 1.00   # anderer Provider, gleiche Fragen
python eval/compare_runs.py eval/results/referenz_2026-09-28_claude-sonnet-5.json eval/results/referenz_2026-09-28_gpt-5-mini.json --out eval/results/vergleich_2026-09-28.md   # zwei Laeufe nebeneinander, ohne Kosten

python scripts/acceptance.py [--api ...] [--load] [--strict]              # Abnahme-Nachweise, kein Modellaufruf
node frontend/scripts/lighthouse-a11y.mjs --base http://localhost:3100 --api http://localhost:8010   # Accessibility >= 90
```

Ergebnisse landen in `eval/results/` (ignoriert in Git bis auf die Referenzdateien, `git add -f`).
