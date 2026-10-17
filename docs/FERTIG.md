# Fertig-Liste Stromlauf AI v1 (öffentliche Demo)

Stand: 2026-10-17 · Linear SIN-799 · freigegeben von Sinan am 2026-10-17.

**Regel:** Erst muss alles funktionieren, bevor Geld ausgegeben wird. Die Demo wird lokal und in CI fertig getestet.
Live geht sie erst, wenn daran nichts mehr gebaut werden muss. Bis dahin fällt kein Hosting-Geld an.

„Fertig“ heißt: **alle Punkte unten abgehakt**. Ein Punkt gilt nur mit Nachweis (CI-Lauf, Datei, Zahl), nicht nach Gefühl.

## Fertig-Liste

- [ ] **1. Beispiel-Doku im Repo.** Frei lizenzierte oder selbst erstellte Doku mit Stromlaufplan und AWL; die Lizenz
  steht in `docs/DATEN.md`. Eine Festo-MPS-Station nur, wenn die Lizenz die Weitergabe erlaubt.
- [ ] **2. Eval in CI.** Das Eval-Set läuft in CI; mindestens 80 % der Antworten sind richtig und nennen die richtige
  Quelle (Blatt/Pfad oder AWL-Netzwerk).
- [ ] **3. Demo-Modus.** Fertig indexierte Beispiel-Maschine, keine eigenen Uploads, Rate-Limit, kein Login.
- [ ] **4. Demo ohne Hosting.** `docker compose up` startet Backend, Frontend und Datenbank mit der Beispiel-Maschine.
  Ein Playwright-Test stellt 10 Fragen im Browser und prüft Antwort und Quelle. Er ist in CI grün, 3 Läufe hintereinander.
- [ ] **5. Hosting (nur nach Freigabe).** Erst wenn 1 bis 4 abgehakt sind, legt der Loop ein Issue mit Label `sinan` an:
  2 bis 3 Optionen mit Monatskosten (bge-m3 braucht etwa 2 GB RAM). Vorher fällt kein Geld an.
- [ ] **6. Keine Bau-Arbeit nach dem Livegang.** Derselbe E2E-Test läuft grün gegen die öffentliche URL.
- [ ] **7. Auftritt.** README mit Screenshot oder GIF, 1-Minuten-Video, Link auf [sjcode.de/-K3](http://sjcode.de/-K3).

## Ist-Stand 2026-10-17

Gemessen am Branch `claude/issue-136-20261017-0731` (Basis `b1dfc68`). Was ohne Docker, Datenbank, Modellschlüssel und
GPU nicht lief, steht unter „Nicht gemessen“.

### Gemessen (heute)

| Prüfung | Ergebnis |
| --- | --- |
| Frontend `npm ci` | ok |
| Frontend `eslint` | 0 Fehler, 1 Warnung (`window.location.href` für interne Navigation) |
| Frontend `next typegen` + `tsc --noEmit` | grün |
| Frontend `vitest` | 23 Dateien, 157 Tests, alle grün |
| Eval-Fragenliste `eval/questions.jsonl` | **69 Fragen** (nicht 24): FB-01 21, UR-01 11, Festo MPS 11, PM1-AR 10, AWL-Praxisprojekte 6, Injection 5, Scan FB-01 5 |

### Letzte gespeicherte Agentenläufe (Referenz 2026-10-02, nicht heute neu gelaufen)

Der Agentenlauf kostet Tokens und braucht Schlüssel; er wurde für dieses Issue nicht gestartet. Quelle:
`eval/results/vergleich_2026-10-02.md`, 20 von 69 Fragen je Modell (FB-01 7, UR-01 5, PM1-AR 4, AWL 2, Festo 1, Injection 1).

| Modell | Fakten | Quellen | Zitate gültig | voll bestanden | USD je Antwort |
| --- | --- | --- | --- | --- | --- |
| claude-sonnet-5-5 | 0,99 | 0,95 | 0,99 | 18 von 20 | 0,046 |
| openai:gpt-6.1-sol | 0,87 | 0,90 | 0,95 | 10 von 20 | 0,012 |

Gegen das Ziel (80 % richtig mit korrekter Quelle) heißt das: Sonnet 5.5 erreicht es auf diesen 20 Fragen
(18 von 20 = 90 %, „voll“ ist Fakten, Quelle und Zitat zusammen). GPT-6.1 Sol nicht (10 von 20 = 50 %). Auf den
übrigen 49 Fragen gibt es keinen aktuellen Lauf.

### Nicht gemessen (braucht Docker, DB, Modell, Browser)

- Backend-Tests (`pytest`, ruff): Abhängigkeiten (Docling, Torch, pgvector) sind in dieser Umgebung nicht eingerichtet.
- Retrieval-Gate, Ingest-Gate, Playwright, Migration und Container-Build: laufen laut `ci.yml` und `eval.yml` in CI;
  deren Status je PR steht dort, nicht hier.
- Wöchentlicher Agentenlauf (`eval.yml`, Gate `--min 0.8`): nur mit `ANTHROPIC_API_KEY`; ein aktueller Wert fehlt hier.

### Lücken gegen die Fertig-Liste

| Punkt | Stand | Was fehlt |
| --- | --- | --- |
| 1 | Offen | `docs/DATEN.md` existiert nicht. Festo-Dateien haben keine Download-URL und die Lizenz („nur lokal testen, nicht weiterverteilen“, `scripts/testdata_manifest.json`) verbietet sie im Repo. Im Repo liegen nur erfundene Anlagen (`examples/foerderband` u. a.), davon FB-01 mit Stromlaufplan und AWL. Entscheidung nötig, ob FB-01 als Demo reicht. |
| 2 | Teilweise | Agentenlauf nur wöchentlich und nur auf FB-01 und Injection (`--only`), nicht auf allen 69 Fragen. Kein Gate auf „richtig mit Quelle“ über das ganze Set; Retrieval-Gate kostet nichts, misst aber nicht den Agenten. Offene Datenlücken: Issue #121 (Signalweg endet an der Meldeleuchte), Aufrufliste OB 1. |
| 3 | Offen | Kein Demo-Modus gefunden: keine Upload-Sperre, kein Rate-Limit, `API_KEY` ist nur ein Schlüssel, kein Login. Ausnahme: `CHAT_MAX_TOOL_CALLS` und `CHAT_TIMEOUT_S` begrenzen je Antwort, aber nicht je Besucher. |
| 4 | Offen | `docker-compose.yml` startet nur `db` und `langflow`. Es gibt ein `backend/Dockerfile`, aber kein Frontend-Dockerfile und keinen Dienst für beides. Die Playwright-Tests laufen gegen eine gemockte API (`e2e/api-mock.ts`); `staging.spec.ts` stellt nur eine Frage mit `E2E_ASK=1`. Kein Test mit 10 Fragen und keine drei Läufe in Folge. |
| 5 | Gesperrt | Erst nach 1 bis 4. |
| 6 | Gesperrt | Erst nach 5. |
| 7 | Offen | README ohne Screenshot, GIF, Video und ohne Link auf sjcode.de/-K3. |

Reihenfolge: 1 und 3 zuerst (Daten und Modus), dann 4 (braucht beide), 2 läuft parallel und blockiert nur den
Abschluss, 7 zuletzt, weil Bild und Video die fertige Demo zeigen.
