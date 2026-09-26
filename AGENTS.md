# AGENTS.md – Stromlauf AI

Chatbot für industrielle Elektrodokumentation: Stromlaufpläne, Stücklisten,
Klemmenpläne, Siemens STEP 7 AWL, Handbücher. Verfolgt Betriebsmittel (`-K12`),
Klemmen (`-X1:5`) und SPS-Adressen (`E0.0`) über alle Dokumente. Details: `README.md`.

Workspace-Regeln gelten zusätzlich: `C:\Dev\CLAUDE.md` → `AI-Workspace\shared-rules\`.
Frontend-spezifisch: `frontend/AGENTS.md` (Next.js-Version mit Breaking Changes).

## Harte Fakten

- `backend/`: FastAPI, Python `>=3.11`, LangGraph-Agent mit Claude, Docling-Ingestion.
- `frontend/`: Next.js + TypeScript. Routen: `/` Chat, `/werk` Hallen-Baukasten, `/werk/maschine/[id]`.
- Werk-Datenmodell (`models.py`): Hall -> Machine (-> KnowledgeSource) -> FaultEntry, CabinetImage -> CabinetHotspot,
  Machine -> MachineLayout (1:1, mm) -> LayoutPart.
  Tabellen entstehen per `create_all`; Bilder liegen unter `backend/data/images/`.
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
cd frontend && npm run lint && npx tsc --noEmit
```

Einrichtung der venv und des GPU-Torch: `README.md` Abschnitt „Start“.

Ordner hieß bis 2026-09-25 `Stromlauf ai`. Die `.venv` im Backend stammt vom alten Pfad
und muss neu erstellt werden.

GitHub-Remote: `siinanXD/stromlauf-ai` (privat, seit 2026-09-25). Beispielanlage: `examples/foerderband/`, Laden mit `python scripts/load_example.py`.
