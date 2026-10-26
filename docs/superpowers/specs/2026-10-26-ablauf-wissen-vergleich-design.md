# Ablauf, Wissen, Modellvergleich – Design (26.10.2026)

Entscheidung Sinan, 26.10.2026: Stromlauf AI bekommt als erstes Produkt eine sichtbare Pipeline
(„Dateien rein, Lösung raus“), einen Agenten, der je Maschine dazulernt, und einen Vergleich der
verfügbaren Modelle nach Sorgfalt und Kosten. Alles so klein wie möglich (Ponytail), alles getrackt
(Langfuse, Kostenbuch), Frontend selbsterklärend. Gebaut lokal, Branch `claude/ablauf-mvp`.

Reihenfolge: Baustein 1 zuerst und komplett, dann 2, dann 3. Jeder Baustein ist ein eigener PR.

## Was schon da ist und wiederverwendet wird

| Baustein | Vorhanden | Datei |
| --- | --- | --- |
| Upload und Lesen | `upload_document`, `ingest_document` (Status pending/processing/ready/failed, `progress`) | `backend/app/api/sources.py`, `backend/app/ingestion/pipeline.py` |
| Maschine anlegen | Onboarding-Vorschlag und `onboard` | `backend/app/api/onboarding.py` |
| Steckbrief | `build_profile` | `backend/app/ingestion/profile.py` |
| Maschinenmodell | `build_map` | `backend/app/ingestion/machine_map.py` |
| Agent | LangGraph `agent ↔ tools`, SSE-Events `tool_start`/`tool_end`/`sources` | `backend/app/agent/graph.py`, `backend/app/api/chat.py` |
| Tracing | `trace_config(session_id, tags, model)`, `langfuse_client()` | `backend/app/tracing.py` |
| Kostenbuch | `ledger.record`, `pricing.cost_usd`, Tabelle `ai_call_ledger` | `backend/app/ledger.py`, `backend/app/pricing.py` |
| Modelle | `make_chat_model("ollama:…" / "openai:…" / "claude-…")` | `backend/app/llm.py` |
| Eval | `run_eval.py --model`, `evallib.score`, `compare_runs.py`, Langfuse-Scores | `eval/` |
| React Flow | `@xyflow/react` 12, Muster in `SignalGraph.tsx` | `frontend/src/components/signal/` |
| Beispielanlage | Förderband FB-01 (7 Dateien) | `examples/foerderband/` |

Neu sind nur: eine Tabelle `runs`, ein Orchestrator, eine Seite, später eine Tabelle `machine_notes`
und ein Vergleichsschritt.

---

## Baustein 1: Ablauf (Pipeline sichtbar)

### Ziel

Sinan zieht die Förderband-Dateien in die Seite `/ablauf`, drückt Start und sieht, wie sieben Knoten
nacheinander grün werden. Am Ende steht das Ergebnis (Steckbrief, Modell, drei Agent-Antworten) und
ein Link zur Maschinenseite. Jeder Knoten zeigt beim Klick Eingabe, Ausgabe, Dauer und Langfuse-Link.

### Backend

**Tabelle `runs`** (`app/models.py`, Alembic-Revision `0006_runs` unter `backend/alembic/versions/`;
`migrations.py` ist eingefroren):

| Spalte | Typ | Inhalt |
| --- | --- | --- |
| id | str (uuid hex) | |
| workspace_id | str | wie alle WorkspaceScoped |
| source_id | str | angelegte Wissensquelle |
| machine_id | str, null | ab Schritt 3 |
| status | str | `laeuft`, `fertig`, `fehler` |
| steps | JSON | Liste, siehe unten |
| model | str | Modell für Schritt 6 |
| trace_url | str, null | Langfuse-Trace des Laufs |
| error | str, null | |
| created_at, finished_at | datetime | |

**Schritt-Eintrag** (JSON in `steps`):

```json
{"key": "lesen", "label": "Lesen", "status": "laeuft", "started_at": "...", "finished_at": null,
 "input": "3 Dateien", "output": "412 Abschnitte, 118 Kennzeichen", "trace_url": null, "error": null}
```

Reine Zustandslogik in `app/ablauf/schritte.py` (ohne DB, mit Tests): Liste der Schritte, Übergänge,
`naechster_schritt`, `mit_status`. Orchestrator in `app/ablauf/lauf.py`: führt die Schritte nacheinander
im Hintergrund-Thread aus (gleiches Muster wie `ingest_document`), schreibt nach jedem Schritt die
`runs`-Zeile. Fehler in einem Schritt setzen den Schritt und den Lauf auf `fehler`, die übrigen Schritte
bleiben `wartet`; nichts wirft nach außen.

**Schritte:**

| # | key | Tut | Ausgabe (Kurztext) |
| --- | --- | --- | --- |
| 1 | hochladen | Wissensquelle anlegen, Dateien speichern, `detect_doc_type` | Dateien mit erkanntem Typ |
| 2 | lesen | `ingest_document` je Dokument, nacheinander | Abschnitte, Kennzeichen, Seiten, Hinweise |
| 3 | maschine | Onboarding-Vorschlag holen, Halle „Ablauf“ (anlegen falls fehlt), `onboard` | Maschinenname, Typ, Störfälle |
| 4 | steckbrief | `build_profile` | Dokumenttypen, Abdeckung, Lücken |
| 5 | modell | `build_map` | Zonen, Bauteile |
| 6 | zusammenfassung | bestehender Agent, drei feste Fragen über den Graphen (eigener Thread je Frage, `thread_id = run:<id>:<n>`) | drei Antworten mit Belegen |
| 7 | fertig | Link `/werk/maschine/<id>` | |

Drei Fragen für Schritt 6 (fest in `app/ablauf/fragen.py`, damit Baustein 3 dieselben nimmt):
„Was ist das für eine Anlage und was tut sie?“, „Welche Antriebe gibt es und wer schaltet sie?“,
„Welche Lücken hat die Dokumentation?“.

**Modell für Schritt 6:** `ABLAUF_MODEL` in den Settings, Standard `ollama:qwen3.5:9b` (lokal, kein
Schlüssel, Kosten 0). Fehlt Ollama, meldet Schritt 6 „Modell nicht erreichbar“ als Fehler; Schritte 1–5
sind davon unabhängig.

**Tracing:** Ein Trace je Lauf über `langfuse_client()` (Span `ablauf`, `session_id = run:<id>`, Tags
`ablauf`, `model:<…>`). Jeder Schritt ein Kind-Span mit Ein-/Ausgabe als Metadaten; Schritt 6 übergibt
`trace_config("run:<id>", ["ablauf", "zusammenfassung"], model)`, damit die LangChain-Aufrufe unter
demselben Session-Schlüssel landen. `trace_url` zeigt auf die Langfuse-Session, nur wenn Tracing aktiv
ist; sonst `null`, und die Seite zeigt „Tracing aus“. Kosten von Schritt 6 laufen wie im Chat über
`ledger.record` mit Zweck `ablauf.zusammenfassung`.

**API** (`app/api/ablauf.py`, Router `/api/runs`):

- `POST /api/runs` (multipart: `files[]`, optional `name`): 201 mit `RunOut`, startet den Lauf.
  Demo-Modus lehnt wie der Upload mit 403 ab.
- `GET /api/runs/{id}`: `RunOut` (alle Schritte, Ergebnis-Teile sobald vorhanden).
- `GET /api/runs`: letzte 20 Läufe des Workspaces (id, status, name, created_at).

`RunOut` enthält `result`: `{profile: SourceProfile | null, map_counts: {zones, parts} | null,
answers: [{question, answer_md, sources}] | null, machine_id}`.

### Frontend

Seite `frontend/src/app/ablauf/page.tsx`, in der Kopfzeile als dritter Eintrag „Ablauf“ neben Chat und
Werk (AppShell-Brotkrumen, kein neues Navigationskonzept).

Aufbau (Desktop drei Zonen untereinander, Handy gleich, nur schmaler):

1. **Start:** Dropzone (`<input type="file" multiple>` plus Drag-and-drop), Liste der gewählten Dateien,
   Knopf „Lauf starten“. Hinweistext in einem Satz: „Stromlaufplan, Stückliste, AWL oder Handbuch hier
   ablegen. Alles Weitere passiert von selbst.“
2. **Ablauf:** React Flow, nur lesend (`nodesDraggable={false}`, `panOnScroll`), sieben Knoten in einer
   Reihe mit Pfeilen. Knoten: Label, Status-Punkt, Kurzausgabe (eine Zeile), Dauer. Farben über
   Tokens: wartet `muted`, läuft `primary` (Ring pulsiert, außer `prefers-reduced-motion`), fertig
   `success`, fehler `destructive`. Klick oder Enter öffnet rechts (Handy: unten als Sheet) ein Panel mit
   Eingabe, Ausgabe, Dauer, Fehler, Link „In Langfuse öffnen“.
3. **Ergebnis:** erscheint, sobald Schritt 4 fertig ist, wächst mit: Steckbrief (bestehende
   Komponente aus `/quelle/[id]` wiederverwenden), Modell-Zahlen, drei Antworten als Markdown mit
   Quellen-Chips (bestehende `Message`-Komponente), Knopf „Maschine öffnen“.

Status: `GET /api/runs/{id}` alle 2 s bis `fertig`/`fehler`, dann Stopp. Kein SSE, kein WebSocket.

Reine Logik in `frontend/src/components/ablauf/knoten.ts` (Schritte → Nodes/Edges, Status → Klasse),
mit Vitest. React-Flow-Zeichnung in `AblaufGraph.tsx`, Panel in `SchrittPanel.tsx`.

### Tests und Abnahme

- `backend/tests/test_ablauf_schritte.py`: Zustandsübergänge, Fehler stoppt Folge-Schritte, Kurztexte.
- `backend/tests/test_ablauf_api.py`: `POST /api/runs` mit `examples/foerderband/` (ohne Vision),
  Schritt 6 per Monkeypatch durch festen Text ersetzt; am Ende `status == fertig`, Maschine existiert,
  Steckbrief hat Dokumenttypen, `map_counts.parts > 0`. Läuft in CI im vorhandenen Backend-Job.
- `frontend`: Vitest für `knoten.ts`; Playwright `e2e/ablauf.spec.ts`: Förderband hochladen, warten bis
  alle sieben Knoten `data-status="fertig"`, Ergebnis sichtbar, axe ohne Verstöße.
- Live-Beleg im PR: Screenshot der Seite mit grünen Knoten und Langfuse-Session-Link.

### Ausgelassen

Editor zum Verdrahten, Wiederholen einzelner Knoten, mehrere Läufe gleichzeitig (Ingestion ist ohnehin
seriell), Abbrechen, Deploy. Alles später einzeln nachrüstbar.

---

## Baustein 2: Wissen (der Agent lernt je Maschine)

### Ziel

Jede Maschine hat ein Gedächtnis aus belegten Sätzen. Der Agent liest es bei jeder Antwort mit, ergänzt
es nach jedem Lauf und jeder Antwort, und Sinan sieht und korrigiert es. Korrekturen gewinnen.

### Backend

**Tabelle `machine_notes`:** id, workspace_id, machine_id, text (ein Satz), quelle (`lauf` | `chat` |
`mensch`), belege (JSON: `[{document_id, page}]`), gesperrt (bool, Mensch hat es gesetzt), created_at,
run_id/conversation_id (null).

**Lern-Schritt:** Neuer Schritt „Lernen“ im Ablauf (vor „Fertig“): das Modell bekommt die drei
Antworten und den Steckbrief und liefert höchstens fünf Sätze als JSON (`{text, belege}`); nur Sätze mit
mindestens einem Beleg werden gespeichert (`app/wissen/lernen.py`, rein: Parsen, Beleg-Prüfung,
Dubletten über normalisierten Text). Nach einer Chat-Antwort mit Quellen dasselbe im Hintergrund,
höchstens zwei Sätze; Fehler dort sind still (Log), nie Teil der Antwort.

**Lesen:** `system_prompt_for` bekommt einen Block „Bisher über diese Maschine gelernt“ mit den
jüngsten 30 Sätzen (gesperrte zuerst), als Daten markiert wie Dokumentinhalt (`<kontext>`).
`PROMPT_VERSION` erhöhen.

**API:** `GET/POST/PATCH/DELETE /api/machines/{id}/notes`. PATCH setzt `gesperrt=true`.

**Obsidian:** Jede Änderung schreibt `DATA_DIR/wissen/<maschinenname>.md` neu (Frontmatter:
machine_id, Stand; je Satz eine Zeile mit Beleg). Der Ordner lässt sich als Vault öffnen. Kein Sync in
`siinanXD/gedaechtnis`, bis Sinan das ausdrücklich will.

### Frontend

Tab „Wissen“ auf der Maschinenseite (Aufbau-Bereich): Liste der Sätze mit Beleg-Chip, Quelle-Badge,
Schloss-Symbol für gesperrt, Stift zum Bearbeiten, Papierkorb. Im Ablauf ein Knoten „Lernen“ mit
Ausgabe „4 Sätze gelernt“.

### Tests

Rein: Parsen, Beleg-Pflicht, Dubletten, Prompt-Block. API: Lauf erzeugt Sätze, PATCH sperrt, DELETE
entfernt, nächste Antwort enthält den Block (Monkeypatch auf den Prompt-Bau). Markdown-Datei existiert.

### Ausgelassen

Vektorsuche über Notizen (30 Sätze passen in den Prompt), Notizen über Maschinen hinweg, Widersprüche
automatisch auflösen (der Mensch sperrt die richtige Fassung).

---

## Baustein 3: Modellvergleich (wer liefert sorgfältig und günstig)

### Ziel

Dieselben drei Fragen laufen parallel über alle konfigurierten Modelle. Eine Tabelle zeigt je Modell:
Fakten-Score, Zitate gültig, Dauer, Tokens, Kosten. Jeder Lauf bleibt als Referenz gespeichert.

### Backend

`VERGLEICH_MODELLE` in den Settings, kommagetrennt, Standard leer (= Schritt wird übersprungen).
Beispiel: `ollama:qwen3.5:9b,ollama:qwen3.5:4b,openai:gpt-5-mini,claude-haiku-4-5`. Es laufen nur
Modelle, deren Schlüssel vorhanden ist (`missing_key`); fehlende stehen in der Tabelle als
„kein Schlüssel“.

Optionaler Schritt „Vergleich“ im Ablauf nach „Zusammenfassung“: je Modell ein Thread (`ThreadPoolExecutor`,
höchstens 4 gleichzeitig), jede Frage mit `evallib.score` gegen die Erwartungen der Fragen bewertet.
Erwartungen je Frage liegen in `app/ablauf/fragen.py` neben dem Fragetext (Kennzeichen und Wörter, die
eine richtige Antwort nennt; für das Förderband aus `examples/foerderband/README.md` abgeleitet; für fremde
Anlagen nur `zitate_gueltig` und `sauber`). Ergebnis als JSON in `runs.steps[vergleich].result`:
`[{model, fakten, zitate_gueltig, dauer_s, tokens_ein, tokens_aus, kosten_usd, trace_url, fehler}]`.
Kosten über `pricing.cost_usd` und `ledger.record` mit Zweck `ablauf.vergleich`. Langfuse: Tags
`vergleich`, `model:<…>`, Scores wie im Eval.

Kostendeckel: `VERGLEICH_MAX_USD` je Lauf, Standard 0,50. Vor dem Start Schätzung aus Tokenzahl der
Zusammenfassung mal Preis; liegt sie darüber, läuft nur die kostenlose Teilmenge und die Tabelle sagt
warum.

### Frontend

Im Ergebnis-Bereich eine Tabelle „Modellvergleich“, sortiert nach Fakten-Score, dann Kosten; beste
Zeile markiert. Klick auf eine Zeile zeigt die drei Antworten dieses Modells. Hinweis in einem Satz:
„Scores sind Stichproben mit drei Fragen, keine Rangliste.“

### Tests

Rein: Auswahl nur mit Schlüssel, Kostendeckel, Sortierung. API: zwei Fake-Modelle (Monkeypatch) liefern
unterschiedliche Antworten, Tabelle enthält beide mit Scores.

### Offene Entscheidung (Sinan)

Seit 25.10. gilt „nur Abo, keine API“ (SIN-1053) für Worker und Prüfer. Der Vergleich mit OpenAI- und
Anthropic-Modellen braucht API-Schlüssel und kostet je Lauf Cent-Beträge. Ohne Freigabe laufen nur
Ollama-Modelle. Freigabe heißt: Schlüssel in `.env`, Deckel `VERGLEICH_MAX_USD` bleibt.

---

## Ergänzung 27.10.2026 (Sinan nach dem ersten Handy-Test)

Drei Punkte, in dieser Reihenfolge: 0 (Fehlerbehebung), 5 (Zeiten), 4 (Ordner). Baustein 1 ist gebaut
(SIN-1103, PR #177); 2 und 3 bleiben wie oben.

### Fix 0: Produktionsbuild auf Windows und Seitenwechsel ohne Neuladen

Befund: Der Dev-Server kompiliert jede Seite beim ersten Aufruf, das wirkt wie ein Neuladen. Der
Produktionsbuild (`next build`) läuft auf Windows nicht, weil `src/components/sps/WhyTree.tsx` und
`src/components/sps/whyTree.ts` sich nur in der Schreibweise unterscheiden (TS1149). Fix: `whyTree.ts`
nach `whyTreeLogik.ts` (reine Logik) umbenennen, Importe nachziehen, `tsc`, Vitest und Build müssen auf
Windows und Linux grün sein. Danach läuft die Tailnet-Bereitstellung über `next start` (Port 3101),
nicht über den Dev-Server. Beleg: `npm run build` grün auf Windows, Seitenwechsel im Tailnet unter
200 ms (Playwright-Messung `navigation` im Bericht).

### Baustein 5: Zeiten im Blick

Ziel: Je Schritt und je Modellantwort ist die Dauer sichtbar und vergleichbar, damit Beschleunigung
messbar wird.

- Backend: `GET /api/runs/zeiten` liefert je Schritt über die letzten 50 Läufe des Workspaces: Anzahl,
  Mittel, Median, Langsamster, Letzter (aus `runs.steps[*].started_at/finished_at`, rein berechnet in
  `app/ablauf/zeiten.py`, mit Tests). Dazu je Lauf die Summe und die Dauer von Schritt 6 je Frage
  (aus `steps[zusammenfassung].result[*].dauer_s`, neu mitgeschrieben).
- Zielwerte in `app/ablauf/zeiten.py` (`ZIELE`): lesen ≤ 60 s je Dokument, zusammenfassung ≤ 30 s je
  Frage, gesamt ≤ 180 s für das Förderband. Überschreitung wird in der Antwort als `ueber_ziel`
  markiert.
- Frontend: Abschnitt „Zeiten“ unten auf `/ablauf`: Tabelle je Schritt (Mittel, Letzter, Langsamster,
  Ziel), rote Zelle bei `ueber_ziel`, ein Satz „Langsamster Schritt der letzten 50 Läufe: Lesen,
  im Mittel 48 s“. Keine Diagramme in v1.
- Langfuse bleibt die Quelle für Tokens und Modell-Latenz; die Tabelle verlinkt die Session des
  langsamsten Laufs.
- Tests: rein (Kennzahlen, Zielwert-Vergleich, leere Liste), API (zwei Läufe → korrekte Mittelwerte),
  Vitest (Zelle rot bei `ueber_ziel`).

### Baustein 4: Ordner-Upload mit Maschinenerkennung

Ziel: Ein ganzer Ordner (auch verschachtelt, auch gemischt) wird abgelegt; das System bündelt die
Dateien zu Anlagen, schlägt die Maschinen vor, und je Anlage läuft der Ablauf aus Baustein 1.

Erkennung in drei Stufen, vom Sicheren zum Unsicheren (Entscheidung Sinan, 27.10.: beides kommt vor,
Unterordner und gemischte Ordner):

1. **Unterordner:** jeder Unterordner mit mindestens einer erlaubten Datei ist eine Anlage; Dateien
   direkt im Wurzelordner gehen in Stufe 2.
2. **Kennzeichen:** Anlagenkennzeichen aus Dateiname (`_FB-01`, `FB01`), Schriftfeld (vorhandener
   `title_block`-Leser) und `=`-Präfixen im Kennzeichen-Index. Gleiche Kennung = gleiche Anlage.
   Rein, ohne Modell, in `app/ablauf/gruppieren.py` mit Tests gegen `examples/` (Förderband,
   Umroller, Aufrollung gemischt in einem Ordner müssen drei Gruppen ergeben).
3. **Ähnlichkeit (Rückfall):** Dateien ohne Kennung werden nach dem Lesen per Embedding-Ähnlichkeit
   der nächsten Gruppe zugeordnet; liegt die Ähnlichkeit unter einer Schwelle, bleibt die Datei
   „unzugeordnet“ und die Seite fragt nach. Nie stillschweigend raten.

Ablauf: Upload (Ordner per `webkitdirectory` und Drag-and-drop, relative Pfade werden mitgeschickt) →
neuer Schritt „Gruppieren“ zwischen „Lesen“ und „Maschine anlegen“ → die Seite zeigt den Vorschlag
(„3 Anlagen erkannt“, je Anlage die Dateien, Herkunft der Zuordnung: Ordner, Kennung, Ähnlichkeit)
und lässt Dateien per Auswahl umsortieren → „Weiter“ startet je Anlage die Schritte Maschine,
Steckbrief, Modell, Zusammenfassung. Ein Lauf hat dann mehrere Anlagen; der Graph zeigt je Anlage
eine Reihe.

Backend: `POST /api/runs` nimmt zusätzlich `paths[]` (relative Pfade je Datei); `runs.steps` bekommt den
Schritt `gruppieren` mit `result = {gruppen: [{name, quelle, dateien}], unzugeordnet: [...]}`;
`POST /api/runs/{id}/gruppen` übernimmt die bestätigte Einteilung und setzt den Lauf fort. Je Gruppe
eine Wissensquelle und eine Maschine; Halle „Ablauf“ wie bisher.

Grenzen v1: höchstens 200 Dateien oder 500 MB je Lauf (klare Fehlermeldung darüber), keine ZIP-Dateien,
keine Erkennung über Bildinhalte. Ausgelassen: automatisches Zusammenlegen bereits vorhandener
Maschinen.

Tests: rein (drei Stufen, gemischter Beispielordner → drei Gruppen, unzugeordnete Datei), API (Ordner
mit zwei Anlagen → zwei Maschinen), Playwright (Ordner ablegen, Vorschlag bestätigen, zwei Reihen grün).

---

## Reihenfolge und Zeit

| Baustein | Dauer (Schätzung) | PR |
| --- | --- | --- |
| 1 Ablauf | 4 h, gebaut (SIN-1103) | `feat(ablauf): Pipeline sichtbar mit Langfuse-Trace` |
| 0 Fix Casing/Build | 1 h | `fix(frontend): whyTree-Logik umbenannt, Produktionsbuild auf Windows` |
| 5 Zeiten | 3 h | `feat(ablauf): Zeiten je Schritt mit Zielwerten` |
| 4 Ordner | 1 Tag | `feat(ablauf): Ordner-Upload mit Maschinenerkennung` |
| 2 Wissen | 3 h | `feat(wissen): Maschine lernt belegte Sätze` |
| 3 Vergleich | 2 h | `feat(vergleich): Modelle parallel nach Sorgfalt und Kosten` |

Je Baustein ein Linear-Issue im Projekt „Stromlauf AI“ (unter SIN-823 „Nächste Schritte planen“),
Branch `claude/…`, PR mit `## Ausgelassen` und Live-Beleg.
