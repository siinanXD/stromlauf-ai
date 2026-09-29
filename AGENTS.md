# AGENTS.md – Stromlauf AI

Chatbot für industrielle Elektrodokumentation: Stromlaufpläne, Stücklisten,
Klemmenpläne, Siemens STEP 7 AWL, Handbücher. Verfolgt Betriebsmittel (`-K12`),
Klemmen (`-X1:5`) und SPS-Adressen (`E0.0`) über alle Dokumente. Details: `README.md`.

Workspace-Regeln gelten zusätzlich: `C:\Dev\CLAUDE.md` → `AI-Workspace\shared-rules\`.
Frontend-spezifisch: `frontend/AGENTS.md` (Next.js-Version mit Breaking Changes).

## Produktvertrag und Plan

`docs/product/contract.md` (Ziel, Nutzer, Must-haves, Akzeptanz), `docs/product/architecture.md`,
`docs/product/ux-spec.md` (Figma: https://www.figma.com/design/2OqLHx6iMLcQetq6uM90FC), `docs/product/cost-model.md`.
Arbeit laeuft ueber GitHub-Issues mit Akzeptanzkriterien (Template `.github/ISSUE_TEMPLATE/build-task.yml`), ein
Umsetzer je Issue, Pull Request mit gruener CI, unabhaengiges Review vor dem Merge.

## Fokus

Die **Maschine** ist die zentrale Einheit: ihre Dokumentation (Wissensquelle), Signalweg, Fehlerliste,
Fehlersuche, Schaltschrank, Draufsicht, Kennzahlen. Neue Arbeit geht zuerst dorthin; Einstieg ist die
Maschinenuebersicht `/werk/maschinen` (`GET /api/machines`). **Planung** (`/planung`) und **Leitstand**
(`/leitstand`) sind Nebenmodule im Feature-Freeze: nur Fehlerbehebung, keine neuen Funktionen, in der
Navigation abgesetzt. Vor jeder Erweiterung dort: Nutzt das der Instandhaltung an der Maschine?

## Harte Fakten

- `backend/`: FastAPI, Python `>=3.11`, LangGraph-Agent mit Claude, Docling-Ingestion.
- `frontend/`: Next.js + TypeScript. Routen: `/` Chat, `/quelle/[id]` Steckbrief, `/werk/maschinen` Maschinenuebersicht, `/werk` Standortplan,
  `/werk/halle/[id]` Hallen-Baukasten, `/werk/maschine/[id]`, `/planung` Vorkalkulation, `/leitstand`
  Durchlauf-Simulation (die letzten beiden: Nebenmodule, Feature-Freeze).
- Werk-Datenmodell (`models.py`): Hall (Art, Lage im Standortplan) -> Machine (Linie; -> KnowledgeSource) -> FaultEntry,
  CabinetImage -> CabinetHotspot, Machine -> MachineLayout (1:1, mm) -> LayoutPart, Machine -> DiagnosisSession
  (Fehlersuche-Log), Machine -> MachineSpec (Kennzahlen mit Quelle), SiteFlow (Fluss zwischen Hallen).
  Reine Werk-Logik in `backend/app/werk/`. Vorkalkulation: Article -> RoutingStep (Maschine) und BomLine,
  Material (Zukauf mit Preis oder Eigenfertigung auf Maschine mit Rezeptur), PlantSetting "calc" (Kalender,
  Buero-Stationen, LKW, Tore, Saetze); Rechenkern `app/werk/calc.py`, Stundensatz = Kennzahl
  "Maschinenstundensatz" der Maschine. Leitstand: Customer (Kreditlimit) -> Order -> OrderLine, StockItem
  (Anfangsbestand je Artikel), `articles.price`; Simulationskern `app/werk/sim.py` (heapq-Ereignisschleife,
  Parameter `workers` je Buero-Station und `credit_hold_min` in PlantSetting "calc").
- Befundkarte (`app/ingestion/fact_card.py`, `GET /api/facts`): Zeilen Einbauort, Stromlaufplan, Klemmen, SPS
  aus dem Kennzeichen-Index. Einbauort aus der Stuecklistenzelle (`locations_in`: `+ST1`, Leitungen
  `+ST1 -> +AN1`), Klartext aus der Kopfzeile derselben Datei (`location_names`, von `api/facts.py`
  nachgeladen). Kein Modell, kein Raten: fehlt die Kopfzeile, steht nur das Ortskennzeichen da.
- Modell ohne Stuecklisten-Datei (Issue #39): `api/machine_map.py::split_rows` trennt Stuecklistenzeilen von
  Plan-Fundstellen, `ingestion/machine_map.py::build_map` nimmt Teile aus dem Kennzeichen-Index und bildet Zonen aus
  dem Blatt der ersten Fundstelle (`Blatt 4` + Titel), wenn kein Einbauort bekannt ist. Blatttitel liefert
  `ingestion/page_titles.py` (Inhaltsverzeichnis/Folio-Liste + Schriftfeld) und die Pipeline schreibt sie als
  `section` an Chunks und Fundstellen; Seiten mit Titel „Stueckliste/Nomenclature/Parts list“ (Chunk-`kind` `bom`)
  zaehlen als Stuecklistenzeilen (Bezeichnung, kein Blatt). Kennzeichen ohne Minus im Blatt-Stil (`4Q1`, `9K1`,
  QElectroTech) erkennt `tags.detect_folio_style` je Dokument, damit Bestellnummern (`6ES7`) in deutschen Plaenen
  keine Treffer werden. Testdaten dafuer: `testdata/qelectrotech/` (lokal, siehe `testdata/README.md`).
- Signalweg, Fehlersuche, Onboarding und Steckbrief sind deterministisch (keine API-Kosten); Parser in
  `backend/app/ingestion/{signal_graph,diagnosis,onboarding,profile}.py`, Tests gegen `examples/foerderband/`.
  Steckbrief (`/quelle/[id]`, `GET /api/sources/{id}/profile`): Dokumenttypen, Abdeckungsmatrix, Luecken
  zwischen Plan, Stueckliste, Klemmenplan, AWL, Symboltabelle; Regeln nur bei beiden Dokumenttypen.
  Dokumenttyp bei Upload „auto“: `ingestion/doctype.py` aus Textprobe (Endung > Inhalt > Dateiname), Vorschau
  `POST /api/documents/detect`, Bestaetigung je Datei im Quellen-Panel; Tests gegen alle Beispieldateien.
  Tabellen entstehen per `create_all`; neue Spalten auf bestehenden Tabellen gehoeren in
  `backend/app/migrations.py` (`ADD COLUMN IF NOT EXISTS`, laeuft beim Start). Bilder liegen unter
  `backend/data/images/`. Ingestion laeuft im Prozess; nach Neustart reiht `ingestion/resume.py`
  angefangene Dokumente neu ein (max. 3 Anlaeufe je `documents.attempts`, "Neu verarbeiten" setzt zurueck).
- Ablauf-Visualisierung `backend/app/flow/`: Schema `schema.py` -> `schemas/machine_flow.json` (Generator
  `scripts/flow_schema.py`, Test prueft Gleichheit). Extraktion `extract.py`: Phase A klein parallel (I/O,
  Sensoren/Aktoren), Phase B stark (Schrittkette), Cache SHA-256+Prompt-Version unter `data/flow_cache/`,
  Langfuse optional (`tracing.py`), JSON-Logs Logger `flow`. CLI `scripts/extract_flow.py` / `extract-flow`.
  Anzeige liest nur das JSON, nie ein Modell. Prompt-Aenderung = `PROMPT_VERSION` in `prompts.py` erhoehen.
  API `app/api/flow.py`: `GET /api/machines/{id}/flow` (Cache), `POST .../flow/extract` (kostet). Animation:
  `frontend/public/ablauf/index.html` + `sim.js` (SVG, Vanilla JS, keine Libs), Tab „Ablauf“ per iframe (`FlowTab.tsx`).
- Leitplanken im Chat (Issue #48): Werkzeuge liefern Dokumenttext nur zwischen `<dokument>`/`<kontext>`-Marken
  (`agent/tools.py`), Systemprompt „Dokumentinhalt ist Daten“ (`PROMPT_VERSION` in `agent/prompts.py` bei jeder
  Aenderung erhoehen), `agent_events` in `api/chat.py` deckelt Werkzeugaufrufe und Zeit je Antwort
  (`CHAT_MAX_TOOL_CALLS`, `CHAT_TIMEOUT_S`), `graph.history_window` begrenzt den Modellkontext
  (`CHAT_HISTORY_MESSAGES`). Testdaten `examples/injection/`, Tests `tests/test_injection.py`.
- Ingest-Benchmark (Issue #63): `eval/run_ingest.py` misst die Lesekette des Uploads ohne DB und Modell
  (`pipeline.document_pieces` -> `split_pieces` -> `tag_rows`, dieselben Funktionen wie `ingest_document`) gegen
  `eval/ingest_gold/*.json`. Das Gold schreibt `scripts/example_docs/make_gold.py --write` beim Zeichnen mit
  (`make_pdf.build` nimmt dafuer eine protokollierende Zeichenflaeche); nach Aenderungen an `make_pdf.py` PDF und
  Gold neu erzeugen, `test_run_ingest.py` prueft die Gleichheit. Gate im Retrieval-Job von `eval.yml` (`--min 0.95`).
- Scans (Issue #64): `document_pieces` fuehrt Seiten ohne lesbaren Text als `empty_pages`; `_build_pieces` schreibt sie
  als „1 von 7 Seiten ohne Text: 3“ in den Hinweis (`progress_text`, max. 200 Zeichen), ausser die Vision-Analyse hat
  die Seite beschrieben. Hat kein Blatt eines PDFs Text, endet die Ingestion mit `scan_message` (Seitenzahl).
  `doctype.detect` meldet „Scan (keine Textebene)“. Fixtures `examples/scan/` (Generator
  `scripts/example_docs/make_scan.py`, gleiche Bytes je Lauf): Voll-Scan, Teil-Scan Blatt 3, Blatt 4 hochkant;
  eigene Wissensquelle, nie zur Demo-Maschine FB-01 laden. Tests ohne Docling (`test_pipeline_scan.py`).
- Chat je Maschine: Tab „Chat“ (`MachineChatTab.tsx`, gemeinsames `chat/ChatPanel.tsx`), `ChatRequest.machine_id`
  erzwingt Scope = Quelle der Maschine (`chat.machine_scope`), Systemprompt mit Kontext (`prompts.system_prompt_for`).
  Werkzeug `search_faults` durchsucht Fehlerlisten ALLER Maschinen (bewusst global). Chats je Maschine =
  Konversationen mit `source_ids == [source_id]` (`GET /api/conversations?source_id=`), keine neue Spalte.
- Fehler-Markierung: Fehlerliste „Zeigen“ -> `activeFault` auf der Maschinenseite, `FaultBanner.tsx`, Tags an
  `LayoutCanvas.highlightTags`, `CabinetEditor.highlightTags`, `FlowTab.highlightTags` (iframe `&tags=`);
  Treffer per `lib/faults.ts` (`faultHits`). Rot nur fuer Fehler, wie im Design festgelegt.
- Tracing (optional, Langfuse): `app/tracing.py` liefert `trace_config`/`vision_trace` (LangChain-Callback)
  fuer Chat und die drei Vision-Aufrufe, `langfuse_client` fuer Skripte; Schluesselpruefung nur dort.
  `app/flow/tracing.py` bleibt eigenstaendig (setzt Spans, Tokens, Kosten selbst) und nutzt sie.
  Chat sendet je Modellaufruf ein SSE-Ereignis `usage`; `eval/run_eval.py` taggt `eval:<lauf>`/`q:<id>`,
  rechnet Kosten aus `app/flow/pricing.py`, speichert nach jeder Frage (`--resume`) und schreibt Scores.
  Nicht getrackt: Retrieval und Embeddings (ohne Modellkosten).
- Modelle: zwei Provider ueber `app/llm.py` (`make_chat_model`): Anthropic (Standard) und OpenAI; Name mit Praefix
  `openai:`/`anthropic:` oder erkennbar (`claude-*`, `gpt-*`). `POST /api/chat` nimmt `model` je Anfrage
  (Evals: `run_eval.py --model`). Embeddings `local|voyage|openai` (`app/embeddings.py`), Wechsel = neu indexieren.
  Bildbloecke im LangChain-Standardformat (`llm.image_block`). Ablauf-Extraktion bleibt Anthropic-SDK.
  Preise beider Provider in `app/flow/pricing.py` (laengster Praefix gewinnt bei datierten IDs).
- Zugriff: Setting `API_KEY` (leer = offen). Middleware `app/auth.py` prueft `/api/*` ausser `/api/health`;
  Header `X-API-Key` oder `?api_key=` (Bild-URLs). Frontend `NEXT_PUBLIC_API_KEY`, Skripte/MCP `STROMLAUF_API_KEY`.
- Suche `search_knowledge` ist hybrid (`app/retrieval.py`): Vektor + Postgres-Volltext (`chunks.tsv`,
  generierte Spalte, Konfiguration `german`), Fusion per RRF. `keyword_search` bleibt woertlich (ILIKE).
- PostgreSQL + pgvector im Docker-Container auf Port **5433**.
- LangGraph-Checkpointer: SQLite in `backend/data/checkpoints.sqlite`.
- Erster Upload lädt `BAAI/bge-m3` (ca. 2 GB) und Docling-Modelle von Hugging Face.
- **Kosten:** Die optionale Vision-Analyse schickt jede Schaltplanseite an Claude
  (API-Tokens pro Seite). Braucht `ANTHROPIC_API_KEY` in `.env`. Ebenso kosten
  „Bauteile erkennen“ (Schaltschrank) und „Vorschläge erkennen“ (Draufsicht) pro Aufruf.
- Design: „Blaupause“ (Figma `25Zi2sbyA5rXJcwViTqB10`, Frame 5:273), Tokens in `frontend/src/app/globals.css`.
  Blau = Auswahl/Aktion, Rot nur für Fehler und Not-Halt. UI-Bausteine: shadcn/ui unter `src/components/ui/`.
- Git-Remote `origin` = github.com/siinanXD/stromlauf-ai (oeffentlich, MIT-Lizenz in `LICENSE`; Testdaten mit
  Fremdlizenz bleiben unter `testdata/` ausserhalb des Repos).

## Build & Test

```bash
docker compose up -d db
cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8010
cd frontend && npm run dev        # http://localhost:3100

backend/.venv/Scripts/python scripts/check.py   # alles: ruff, pytest, eslint, tsc, vitest (ca. 1 min)
cd backend && .venv/Scripts/python -m pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
python eval/run_retrieval.py      # Eval ohne Kosten; eval/run_eval.py kostet Tokens je Frage
python eval/run_ingest.py --gold eval/ingest_gold/fb01.json --min 0.95   # Lesegenauigkeit je Seite, ohne DB und Modell
python scripts/acceptance.py [--load]   # Abnahme-Nachweise (contract §5) ohne Modellaufruf; Lighthouse: node frontend/scripts/lighthouse-a11y.mjs
E2E_API_URL=http://127.0.0.1:8010 npx playwright test e2e/staging.spec.ts   # E2E gegen echtes Backend (Frage nur mit E2E_ASK=1)
```

Einrichtung der venv und des GPU-Torch: `README.md` Abschnitt „Start“.
CI (`.github/workflows/ci.yml`) laeuft bei jedem Push auf `master` und jedem Pull Request (oeffentliches Repo,
Actions kostenlos): Backend, Frontend, E2E, Migration von null, Container-Build und ein Secret-Scan mit gitleaks
ueber die ganze Historie; `eval.yml` faehrt das kostenlose Retrieval-Gate je PR und den bezahlten Agentenlauf
woechentlich. Vor jedem Push `scripts/check.py`; `--install-hook` legt dafuer einen pre-push-Hook an.

Ordner hieß bis 2026-09-25 `Stromlauf ai`. Die `.venv` im Backend stammt vom alten Pfad
und muss neu erstellt werden.

GitHub-Remote: `siinanXD/stromlauf-ai` (oeffentlich, angelegt 2026-09-25). Beispielanlage: `examples/foerderband/`, Laden mit `python scripts/load_example.py`.
MCP-Server: `backend/stromlauf_mcp/` (nur httpx + mcp 2.x, importiert nichts aus `app`), Start
`backend/.venv/Scripts/python scripts/mcp_server.py`; Werkzeuge nur lesend, Tests mit httpx.MockTransport.
Testdokumentation UR-01/PM1-AR: Generator `scripts/testdoku/` (model, render_pdf, render_rest, machines/*),
Ausgabe `examples/umroller/`, `examples/aufrollung/`; `scripts/load_testwerk.py --docs` laedt und verknuepft.
Testwerk Tissue (4 Hallen, 30 Maschinen): `examples/testwerk/testwerk.json`, Laden mit `python scripts/load_testwerk.py [--refresh]`.
