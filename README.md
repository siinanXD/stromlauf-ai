# Stromlauf AI

Chatbot für industrielle Elektrodokumentation: Stromlaufpläne, Stücklisten, Klemmenpläne,
Siemens STEP 7 AWL-Programme und Handbücher. Der Agent verfolgt Betriebsmittel (`-K12`),
Klemmen (`-X1:5`) und SPS-Adressen (`E0.0`) über alle Dokumente hinweg.

## Start

```bash
cp .env.example .env          # ANTHROPIC_API_KEY eintragen
docker compose up -d db       # Postgres + pgvector auf Port 5433
```

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install torch --index-url https://download.pytorch.org/whl/cu126   # NVIDIA-GPU; sonst weglassen
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/uvicorn app.main:app --reload --port 8010
```

```bash
cd frontend
npm install
npm run dev                   # http://localhost:3100
```

Beim ersten Upload lädt das Backend das Embedding-Modell (`BAAI/bge-m3`, ca. 2 GB) und die
Docling-Layoutmodelle von Hugging Face.

## In 5 Minuten ausprobieren

Im Ordner [`examples/foerderband/`](examples/foerderband/) liegt eine komplette, frei erfundene
Anlagendokumentation: Stromlaufplan (7 Blaetter), Stueckliste, Klemmenplan, STEP 7 AWL-Programm,
Symboltabelle und Betriebsanleitung, alle mit denselben Kennzeichen. Backend laeuft, dann:

```bash
python scripts/load_example.py       # legt die Quelle an, laedt 6 Dateien, wartet auf die Ingestion
```

Danach im Frontend fragen, zum Beispiel: *„Was haengt an E0.3 und wo ist das im Plan?“* oder
*„Warum leuchtet -H2 nach 20 Sekunden?“* Weitere Fragen mit Loesungsweg in
[`examples/foerderband/README.md`](examples/foerderband/README.md).

## Architektur

```
frontend/   Next.js + TypeScript: Wissensquellen, Upload, Chat (SSE-Streaming), Seiten-Viewer
backend/    FastAPI
  app/ingestion/   Docling (PDF/Office -> Markdown je Seite), AWL-Parser, Kennzeichen-Index,
                   optionale Vision-Analyse der Schaltplanseiten (Claude)
  app/agent/       LangGraph-Agent (Claude) mit Werkzeugen: search_knowledge, find_tag,
                   keyword_search, get_page, view_page, get_plc_block, list_documents
  app/api/         REST + SSE
Postgres + pgvector   Dokumente, Chunks mit Embeddings (HNSW), Kennzeichen-Index, Chats
SQLite                LangGraph-Checkpointer (Gesprächsverlauf), backend/data/checkpoints.sqlite
Langflow (optional)   docker compose --profile langflow up -d  ->  http://localhost:7860
```

Wie Zusammenhänge entstehen:

1. **Kennzeichen-Index** (`tag_occurrences`): Jede Fundstelle von BMK, Klemme, SPS-Adresse und
   Seitenverweis wird normalisiert gespeichert (`E 0.0`, `%I0.0`, `I0.0` -> `E0.0`).
   `find_tag` liefert damit Plan, Stückliste, Klemmenplan und AWL-Netzwerk in einer Abfrage.
2. **Vision-Analyse** (optional je Upload): Claude beschreibt jede Schaltplanseite strukturiert
   (Betriebsmittel, Verbindungen, Klemmen, Querverweise). Kostet API-Tokens pro Seite.
3. **view_page**: Der Agent sieht sich zur Laufzeit eine Seite als Bild an, wenn Text nicht reicht.

## Unterstützte Dateien

| Typ | Endungen |
| --- | --- |
| Stromlaufplan, Klemmenplan, Stückliste, Handbuch | `.pdf`, `.xlsx`, `.csv`, `.docx`, `.pptx`, `.md`, `.html`, `.txt`, Bilder |
| SPS-Programm | `.awl` (STEP 7 AWL-Quelle) |
| Symboltabelle | `.sdf` |

Gescannte PDFs: `OCR_ENABLED=true` in `.env`.

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
cd frontend && npm run lint && npx tsc --noEmit
```
