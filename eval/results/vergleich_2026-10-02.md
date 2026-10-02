# Modellvergleich 2026-10-02 (Agent v3, Prompt v3, Signalweg-Werkzeug)

20 Fragen je Modell aus `eval/questions.jsonl` (FB-01 7, UR-01 5, PM1-AR 4, AWL 2, Festo 1, Injection 1),
gleiches Backend (Branch `feat/agent-v3`, PR #119), gleiche Dokumente, Lauf `python eval/run_eval.py --model <m> --only <ids>
--out eval/results/referenz_2026-10-02_<m>.json`. Kennzahlen nur ueber beantwortete Fragen; Kosten nach
`app/flow/pricing.py` mit Cache-Tokens (Stand 2026-10-02).

| Modell | ok/Fehler | Fakten | Quellen | Zitate gueltig | voll | USD gesamt | USD je Antwort | s je Antwort | Cache-Anteil | Modellaufrufe | signal_path | Werkzeuge je Antwort |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-sonnet-5-5 | 20/0 | 0.988 | 0.95 | 0.991 | 18 | 0.927 | 0.046 | 12.2 | 48 % | 2.8 | 14 | 3.0 |
| claude-sonnet-5 (nur 6 Fragen) | 6/14 | 0.958 | 0.83 | 0.944 | 4 | 0.226 | 0.038 | 10.9 | 47 % | 2.5 | 3 | 2.3 |
| openai:gpt-6.1-sol | 20/0 | 0.872 | 0.90 | 0.947 | 10 | 0.232 | 0.012 | 12.6 | 76 % | 3.1 | 19 | 2.4 |
| openai:gpt-5.4-mini@none | 20/0 | 0.820 | 0.95 | 0.721 | 11 | 0.082 | 0.004 | 5.5 | 62 % | 2.2 | 11 | 1.8 |
| claude-haiku-4-5 | 20/0 | 0.793 | 0.80 | 0.891 | 11 | 0.326 | 0.016 | 8.3 | 21 % | 2.3 | 8 | 1.9 |
| openai:gpt-5-mini | 20/0 | 0.764 | 0.85 | 0.866 | 9 | 0.130 | 0.007 | 26.7 | 68 % | 2.7 | 13 | 1.7 |
| openai:gpt-5.6-terra@none | 20/0 | 0.750 | 0.85 | 0.938 | 11 | 0.178 | 0.009 | 6.2 | 76 % | 2.3 | 12 | 1.8 |
| ollama:qwen35-4b-32k (lokal) | 20/0 | 0.524 | 0.60 | 0.350 | 5 | 0 | 0 | 6.4 | - | - | 5 | 1.3 |
| ollama:qwen35-9b-32k (lokal) | 19/1 | 0.375 | 0.47 | 0.500 | 4 | 0 | 0 | 17.4 | - | - | 6 | 0.8 |

Nicht gelaufen: `claude-opus-5-5` (Anthropic-Guthaben um 01:49 Uhr erschoepft, 20 von 20 Fragen 400); aus demselben Grund
hat `claude-sonnet-5` nur 6 Fragen. Beide nach Aufladen mit `--resume` nachholen.

## Lesart

- **Beste Qualitaet:** Sonnet 5.5. 0,99 Fakten, 18 von 20 voll bestanden, Zitate fast immer gueltig. 4,6 Cent je Antwort,
  12 s. Nutzt `signal_path` in 14 von 20 Antworten und ruft im Schnitt drei Werkzeuge.
- **Bestes Verhaeltnis:** GPT-6.1 Sol. 0,87 Fakten, 0,95 gueltige Zitate, 1,2 Cent je Antwort (ein Viertel von Sonnet 5.5),
  gleiche Dauer. Werkzeuge ueber die Responses-API (langchain-openai routet GPT-6 mit tools selbst), Cache-Anteil 76 %.
- **Schnellstes und billigstes mit brauchbaren Fakten:** gpt-5.4-mini@none. 5,5 s, 0,4 Cent, 0,82 Fakten. Schwaeche: nur
  72 % der Belege gueltig (schreibt Spalten ohne Beleg). Fuer die Kurzantwort im Betrieb reicht das nicht ohne Zitatpruefung.
- **Haiku 4.5** ist mit 1,6 Cent teurer als 6.1 Sol und schwaecher (0,79). Der Cache greift bei Haiku erst ab 4096 Token,
  deshalb nur 21 % Cache-Anteil. Kein Kandidat mehr.
- **gpt-5-mini** denkt lang (27 s) und liegt bei 0,76; Snapshot wird 2026-12-11 abgeschaltet. Nachfolger terra@none ist
  viermal schneller, aber ohne Nachdenken nicht besser (0,75).
- **Lokal (RTX 3080, 10 GB):** qwen3.5 4b erreicht 0,52 Fakten in 6 s, Belege zu zwei Dritteln erfunden
  (`[[Stromlaufplan|Ort]]`, `/S.9`). 9b ist schlechter (0,38) und langsam (17 s, p95 49 s): mit 32k Kontext passt es neben
  bge-m3 nicht mehr in den VRAM. Abstand zur Cloud: rund 0,3 bis 0,45 Fakten.

## Was alle Modelle gleichermassen verfehlen (Daten, nicht Modell)

- `fb01-signal-s1`, `ur01-signal-s4`, `pm1ar-signal-s4`: Der deterministische Hauptweg endet an der Meldeleuchte statt am
  Motor (Issue #121). Die Modelle nennen deshalb E0.0, A4.0, NW 1 nicht, obwohl sie `signal_path` aufrufen. Prompt v3 sagt
  zudem, den Signalweg nicht zu wiederholen, weil der Block ihn zeigt; die Eval misst aber genannte Knoten.
- `ur01-f7` und `ur01-k3` fehlt `-M6`, `ur01-e12` fehlt `-X3:11`, `pm1ar-reissleine` fehlt `E1.4`: dieselben Luecken bei
  Sonnet, GPT und Qwen. Pruefen, ob der Hauptweg diese Knoten als Abzweig fuehrt (dann in die Werkzeugausgabe aufnehmen).
- `awl-ob1-aufrufe` (Festo-AWL): nur Sonnet 5.5 findet alle Bausteinnamen; `get_plc_block` liefert einen Baustein, die
  Frage braucht die Aufrufliste des OB 1.

## Kosten des Tages

Bezahlt wurden rund 2,1 USD fuer die Tabelle (OpenAI 0,62, Anthropic 1,48) plus rund 1,5 USD verlorene Antworten durch den
Importfehler in `run_eval.py` (gpt-5.4-mini und gpt-6.1-sol je einmal komplett, siehe Commit `4f32b8f`).

## Empfehlung

1. Standard fuer Antworten: `openai:gpt-6.1-sol` (Qualitaet nahe Sonnet 5.5 bei einem Viertel der Kosten), Sonnet 5.5 als
   Referenz fuer schwierige Faelle. `CHAT_MODEL` bleibt bis zur Entscheidung des Owners `claude-sonnet-5`.
2. Issue #121 beheben, dann die drei Signalweg-Fragen neu messen; erwartet: Sonnet 5.5 und 6.1 Sol auf 1,0.
3. Lokal: Antworten von Sonnet 5.5 und 6.1 Sol als Lehrer sammeln, Belegformat und Werkzeugwahl daraus als Regeln und
   Beispiele in einen Prompt fuer kleine Modelle, dann qwen3.5 4b neu messen. Erst danach ueber Fine-Tuning entscheiden.
