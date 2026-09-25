# Eval: Antwortqualitaet messen

24 Fragen mit Erwartungen in `questions.jsonl`, drei Wissensquellen:

| Quelle | Fragen | Daten |
| --- | --- | --- |
| Foerderband FB-01 | 7 | `examples/foerderband/` (im Repo) |
| Festo MPS | 11 | `testdata/festo/` (lokal, Festo Didactic InfoPortal) |
| AWL Praxisprojekte | 6 | `testdata/awl/bnt_modell.awl` (aus awlsim, GPLv2) |

Drei Fragen sind Fallen: die Antwort steht in keinem Dokument. Erwartet wird „nicht vorhanden“,
bestraft wird eine erfundene Zahl.

## Ergebnisse (Referenzlaeufe in `results/`)

| Modell | voll bestanden | Fakten | Quellen | sauber | Dauer/Frage | Kosten/Lauf |
| --- | --- | --- | --- | --- | --- | --- |
| claude-opus-5 (`referenz_2026-09-26.json` + AWL-Nachlauf) | 24/24 | 1,00 | 1,00 | 1,00 | 30 s | n. a. |
| claude-sonnet-5 (`referenz_sonnet-5_2026-09-26.json`) | 23/24 | 1,00 | 0,96 | 1,00 | 23,5 s | 1,96 $ |

Standard ist deshalb `CHAT_MODEL=claude-sonnet-5`.

## Testdaten beschaffen (nicht im Repo)

`testdata/` ist ignoriert (Festo-Unterlagen sind Eigentum von Festo Didactic). Zum Nachbauen:

- Festo InfoPortal: `.../Infoportal/mps/DistributionConveyorStation/Documentation/CircuitDiagrams.pdf`,
  `.../InfoPortal/mps/SeparatingStation/Documentation/Manual.pdf`, `.../CircuitDiagrams.pdf` (Station Trennen)
  nach `testdata/festo/` mit den Namen `Festo_MPS_Verteilen-Band_Stromlaufplan.pdf`,
  `Festo_MPS_Trennen_Handbuch.pdf`, `Festo_MPS_Trennen_Stromlaufplan.pdf`.
- `git clone https://github.com/mbuesch/awlsim testdata/awlsim`, dann `testdata/awlsim/tests/tc999_projects/bnt_modell.awl`
  nach `testdata/awl/` kopieren.
- Laden: `python scripts/load_folder.py testdata/festo --name "Festo MPS"` und
  `python scripts/load_folder.py testdata/awl --name "AWL Praxisprojekte"`.

## Bewertung ohne LLM-Richter

Jede Frage hat `must_contain` (Regex-Muster, die in der Antwort stehen muessen), `must_not_contain`
(Halluzinations-Fallen) und `expect_sources` (Dateien, die als Quelle zitiert sein muessen).
Gleiche Antwort ergibt immer gleiche Punktzahl; eine veraenderte Zahl bedeutet also eine veraenderte
Antwort, nicht einen anderen Richter.

```bash
python eval/run_eval.py                        # alle 24 Fragen, ca. 20 min, ein Agentenlauf je Frage
python eval/run_eval.py --only festo           # nur eine Quelle
python eval/run_eval.py --baseline eval/results/2026-09-26_10-00-00.json   # Vergleich mit frueherem Lauf
python eval/run_eval.py --resume eval/results/<lauf>.json                  # abgebrochenen Lauf fortsetzen
```

Ergebnisse landen in `eval/results/` (ignoriert in Git bis auf eine Referenzdatei).

## Modelle vergleichen

`CHAT_MODEL` in `.env` umstellen, Backend neu starten, Lauf mit `--baseline` gegen den Referenzlauf.
Der Runner summiert Token und rechnet mit den Listenpreisen (`PRICES` in `run_eval.py`) die Kosten
je Lauf aus, so steht neben der Trefferquote auch der Preis:

```bash
python eval/run_eval.py --baseline eval/results/referenz_2026-09-26.json
```

## Langfuse

Sind `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` gesetzt (im Backend und in der Shell des Runners),
bekommt jede Frage einen Trace mit Tags `eval:<lauf>` und `q:<frage>`, und der Runner haengt die
drei Bewertungen als Scores an. In Langfuse lassen sich dann Laeufe und Modelle nebeneinander
vergleichen, inklusive Tokens und Kosten je Frage.

## Kennzahlen

- `fakten_mittel`: Anteil gefundener Pflichtangaben, gemittelt ueber alle Fragen
- `quellen_ok`: Anteil der Fragen, bei denen alle erwarteten Dokumente zitiert wurden
- `sauber`: Anteil der Fragen ohne verbotene Angaben
- `voll_bestanden`: Fragen mit 100 % Fakten, Quellen ok und sauber
- `kosten_usd`, `tokens_input`, `tokens_output`: Verbrauch des Laufs (braucht das SSE-Ereignis `usage` aus dem Backend)

## Fragen ergaenzen

Eine Zeile JSON anhaengen. Muster sind Regex, `|` trennt Alternativen (`"4 s|4 Sekunden"`).
Vor dem Eintragen die Musterantwort im Dokument nachschlagen, nicht aus einer Agentenantwort abschreiben.
