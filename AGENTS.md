# AGENTS.md – Stromlauf AI

Chatbot für industrielle Elektrodokumentation: Stromlaufpläne, Stücklisten,
Klemmenpläne, Siemens STEP 7 AWL, Handbücher. Verfolgt Betriebsmittel (`-K12`),
Klemmen (`-X1:5`) und SPS-Adressen (`E0.0`) über alle Dokumente. Details: `README.md`.

Workspace-Regeln gelten zusätzlich: `C:\Dev\CLAUDE.md` → `AI-Workspace\shared-rules\`.
Frontend-spezifisch: `frontend/AGENTS.md` (Next.js-Version mit Breaking Changes).

## Fokus

Die **Maschine** ist die zentrale Einheit: ihre Dokumentation (Wissensquelle), Signalweg, Fehlerliste,
Fehlersuche, Schaltschrank, Draufsicht, Kennzahlen. Neue Arbeit geht zuerst dorthin; Einstieg ist die
Maschinenuebersicht `/werk/maschinen` (`GET /api/machines`). **Planung** (`/planung`) und **Leitstand**
(`/leitstand`) sind Nebenmodule im Feature-Freeze: nur Fehlerbehebung, keine neuen Funktionen, in der
Navigation abgesetzt. Vor jeder Erweiterung dort: Nutzt das der Instandhaltung an der Maschine?

## Harte Fakten

- `backend/`: FastAPI, Python `>=3.11`, LangGraph-Agent mit Claude, Docling-Ingestion.
- `frontend/`: Next.js + TypeScript. Routen: `/` Chat, `/werk/maschinen` Maschinenuebersicht, `/werk` Standortplan,
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
- Signalweg, Fehlersuche und Onboarding sind deterministisch (keine API-Kosten); Parser in
  `backend/app/ingestion/{signal_graph,diagnosis,onboarding}.py`, Tests gegen `examples/foerderband/`.
  Tabellen entstehen per `create_all`; neue Spalten auf bestehenden Tabellen gehoeren in
  `backend/app/migrations.py` (`ADD COLUMN IF NOT EXISTS`, laeuft beim Start). Bilder liegen unter
  `backend/data/images/`. Ingestion laeuft im Prozess; nach Neustart reiht `ingestion/resume.py`
  angefangene Dokumente neu ein (max. 3 Anlaeufe je `documents.attempts`, "Neu verarbeiten" setzt zurueck).
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
- Git-Remote `origin` = github.com/siinanXD/stromlauf-ai (privat).

## Build & Test

```bash
docker compose up -d db
cd backend && .venv/Scripts/uvicorn app.main:app --reload --port 8010
cd frontend && npm run dev        # http://localhost:3100

cd backend && .venv/Scripts/python -m pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
python eval/run_retrieval.py      # Eval ohne Kosten; eval/run_eval.py kostet Tokens je Frage
```

Einrichtung der venv und des GPU-Torch: `README.md` Abschnitt „Start“.

Ordner hieß bis 2026-09-25 `Stromlauf ai`. Die `.venv` im Backend stammt vom alten Pfad
und muss neu erstellt werden.

GitHub-Remote: `siinanXD/stromlauf-ai` (privat, seit 2026-09-25). Beispielanlage: `examples/foerderband/`, Laden mit `python scripts/load_example.py`.
MCP-Server: `backend/stromlauf_mcp/` (nur httpx + mcp 2.x, importiert nichts aus `app`), Start
`backend/.venv/Scripts/python scripts/mcp_server.py`; Werkzeuge nur lesend, Tests mit httpx.MockTransport.
Testdokumentation UR-01/PM1-AR: Generator `scripts/testdoku/` (model, render_pdf, render_rest, machines/*),
Ausgabe `examples/umroller/`, `examples/aufrollung/`; `scripts/load_testwerk.py --docs` laedt und verknuepft.
Testwerk Tissue (4 Hallen, 30 Maschinen): `examples/testwerk/testwerk.json`, Laden mit `python scripts/load_testwerk.py [--refresh]`.
