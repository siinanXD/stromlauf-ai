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

## Werk: Standortplan, Halle, Maschinen, Schaltschrank

Reiter **Werk** oeffnet den **Standortplan** (`/werk`): alle Hallen als Grundriss-Bloecke mit Art
(Grundstoff, Verarbeitung, Lager, Buero), verkleinertem Maschinenlayout und Materialfluss zwischen
den Hallen. Bloecke lassen sich ziehen und in der Groesse aendern; Pfeil vom rechten Griff auf eine
andere Halle zeichnet einen Fluss. Rot ist nur die Zahl laufender Fehlersuchen einer Halle.

**Testwerk Tissue** laden (4 Hallen, 30 Maschinen, Kennzahlen mit Quellen, kein KI-Aufruf):

```bash
python scripts/load_testwerk.py            # --refresh ersetzt ein vorhandenes Testwerk
```

Papiermaschine PM1 in 6 Sektoren liefert Mutterrollen an 6 Verarbeitungslinien (je Hauptmaschine →
Verpackung → Palettierer), dann Lager & Versand mit 8 Verladetoren; das Buero gibt Auftraege.
Daten: `examples/testwerk/testwerk.json`, Recherche: `.ai/research/solution-comparisons/`.

**Halle** (`/werk/halle/{id}`): Maschinen als Kacheln anordnen (Foerderband, Hauptmaschine,
Verpackung ...), Materialfluss als Pfeile zeichnen, Maschinen einer Linie oder eines Sektors
bekommen ein gemeinsames Band (Feld „Linie/Sektor“). Die Kachel zeigt die erste Kennzahl. Jede Maschine hat eine
Maschinenseite mit Foto, zugeordneter Wissensquelle, Fehlerliste (Code, Symptom, Ursache,
Behebung, beteiligte BMK) und Schaltschrankbildern. Im Schaltschrankbild werden Bauteile als
Rechtecke markiert, von Hand oder per **Bauteile erkennen lassen** (Claude Vision schlaegt
Bauteilart und BMK vor, kostet API-Tokens je Bild). Klick auf ein Bauteil zeigt seine Fundstellen
in Stromlaufplan, Stueckliste, Klemmenplan und AWL. `scripts/load_example.py` legt dazu eine
Beispielhalle mit Aufbauplan und 14 fertigen Markierungen an.

### Draufsicht (Vogelperspektive)

Die Maschinenseite hat Tabs **Draufsicht · Signalweg · Fehler · Schaltschrank · Kennzahlen ·
Dokumente**. **Kennzahlen** sind Wert, Einheit und Quelle (URL oder „Richtwert“). Die Draufsicht
zeigt Baugruppen und Feldgeraete (-M1, -B1, -S3 ...) als Rechtecke oder Kreise in mm auf einem
Raster (100/1000 mm). Quelle ist eine Skizze (Upload oder PDF-Seite aus der Doku) oder eine eigene
Zeichnung. **Vorschlaege erkennen** laesst Claude Vision die Skizze lesen (kostet API-Tokens pro
Aufruf); Vorschlaege erscheinen gestrichelt und werden einzeln oder alle bestaetigt. Klick auf ein
Teil zeigt Stueckliste, Klemmen, SPS-Adressen, Stromlaufplan-Seiten und Fehler zu diesem BMK.
Standardformat als JSON-Export: `width_mm`, `depth_mm`, `parts[]` mit `tag`, `kind`, `shape`,
`x_mm`, `y_mm`, `w_mm`, `h_mm`, `rotation_deg`. Referenz: `examples/foerderband/08_Aufstellungsplan_FB-01.*`
(PNG wird aus dem JSON gezeichnet: `python scripts/make_layout_sketch.py`).

**Strg+K** sucht BMK, Klemmen und SPS-Adressen ueber alle Maschinen und springt zur Fundstelle.

## Signalweg, Fehlersuche, Onboarding (ohne KI-Kosten)

Diese drei Funktionen arbeiten nur mit den hochgeladenen Dokumenten, ohne Claude-Aufruf:

- **Signalweg** (Maschinenseite, Tab „Signalweg“): Graph aus Klemmenplan, Stueckliste,
  Symboltabelle und AWL. Links die Quellen, rechts die Folgen, z. B. `-S1 → -X3:1 → E0.0 →
  FB 10 NW 1 → Freigabe → NW 2 → A4.0 → -X3:9 → -K1 → -X4:U → -M1`. Klick oeffnet das Blatt
  mit markierter Spalte bzw. den AWL-Code, Doppelklick verfolgt ab dort. `GET /api/signal-path`.
- **Gefuehrte Fehlersuche** (Tab „Fehler“, „Diagnose“): Pruefschritte aus der Behebung eines
  Fehlereintrags mit Blatt-Verweisen, abhaken (ok / Fehler / uebersprungen), Befund datiert in die
  Fehlerliste uebernehmen. Instandhaltungslog zeigt wiederkehrende Fehler.
- **Onboarding** (Werk, „Aus Dokumentation anlegen“): Name und Typ aus dem Stuecklisten-Titel,
  Fehlerliste aus Handbuch-Tabellen `Symptom | Ursache | Abhilfe`. Draufsicht und
  Schaltschrank-Markierungen bleiben optional (Vision kostet API-Tokens).

## Planung: Vorkalkulation (ohne KI-Kosten)

Reiter **Planung** (`/planung`): Auftrag mit Positionen (Artikel, Menge in Paketen oder Paletten),
Eingang und Wunschtermin eingeben; sofort erscheinen **Verladebereit am** (grün „hält“ oder
„+N Tage“), ein **Zeitplan** je Station (Büro, PM1-Rohpapier, Linien, Verladung; geschlossene Zeiten
schraffiert, Leerlauf wie das Wochenende gestaucht), der **Materialbedarf** mit Herleitung
(Rohpapier aus Blatt × Fläche × Lagen × g/m², daraus Zellstoff, Altpapier, Chemie, Wasser) und die
**Kosten** je Position (Material, Fertigung, Büro, Versand, je Einheit). Tab **Stammdaten** zeigt
Artikel mit Arbeitsplan und Stückliste sowie Materialpreise.

Rechenkern: `backend/app/werk/calc.py` (rein, getestet), Kalender `calendar.py`; API
`POST /api/calc`, `GET /api/articles`, `GET /api/materials`, `PUT /api/master-data`. Annahmen:
freie Kapazität, keine anderen Aufträge, Rohstoffe vorrätig. Preise und Sätze sind Richtwerte;
Maschinenstundensätze sind Kennzahlen der Maschine („Maschinenstundensatz“, €/h) und im Tab
Kennzahlen änderbar. Stammdaten kommen mit `python scripts/load_testwerk.py`.

## MCP-Server (Claude Desktop, Claude Code)

Stromlauf stellt seine Funktionen als MCP-Server bereit: Werk, Maschinen, Kennzeichen,
Dokumentensuche, Signalweg und Vorkalkulation. Nur lesen, auf Stromlauf-Seite kein KI-Aufruf; das
Sprachmodell ist der MCP-Client (Claude Desktop / Claude Code mit dem eigenen Abo, kein API-Guthaben).
Voraussetzung: Backend läuft (Port 8010).

| Werkzeug | Zweck |
|---|---|
| `site_overview`, `hall_details`, `machine_details` | Werk, Hallen, Maschinen mit Kennzahlen, Fehlerliste, Fehlersuchen |
| `search_tags`, `find_references` | Wo kommt -K1 / -X3:1 / E0.0 vor, alle Fundstellen |
| `search_documents` | Semantische oder wörtliche Suche in der Doku |
| `signal_path` | Quellen und Folgen eines Kennzeichens (Klemmenplan, AWL) |
| `list_articles`, `calculate_order` | Vorkalkulation: Termin, Zeitplan, Material, Kosten |

Claude Code (Pfade absolut, dann egal aus welchem Ordner gestartet):

```bash
claude mcp add stromlauf -- C:/dev/Repositories/stromlauf-ai/backend/.venv/Scripts/python.exe C:/dev/Repositories/stromlauf-ai/scripts/mcp_server.py
```

Claude Desktop (`%APPDATA%\Claude\claude_desktop_config.json`, Pfade anpassen; Schrägstriche `/` gehen unter Windows):

```json
{
  "mcpServers": {
    "stromlauf": {
      "command": "C:/dev/Repositories/stromlauf-ai/backend/.venv/Scripts/python.exe",
      "args": ["C:/dev/Repositories/stromlauf-ai/scripts/mcp_server.py"],
      "env": { "STROMLAUF_API": "http://127.0.0.1:8010" }
    }
  }
}
```

Als HTTP-Server (z. B. für den MCP Inspector): `backend/.venv/Scripts/python scripts/mcp_server.py --http` →
`http://127.0.0.1:8765/mcp`. Code: `backend/stromlauf_mcp/`, Suche über `GET /api/search`.

## Chat-Antworten

Antworten sind fest gegliedert: **Kurzantwort** (max. 2 Saetze), **Pruefen** (max. 5 Schritte,
je ein Beleg), **Sicherheit** (nur wenn relevant), **Details** (eingeklappt). Belege schreibt das
Modell als `[[Dateiname|Ort]]`; die Oberflaeche macht daraus Chips und listet nur zitierte Stellen.
Ein Klick auf einen Stromlaufplan-Verweis wie `/3.8` oeffnet rechts Blatt 3 und markiert Spalte 8.
Blatt und Spalten liest das Backend aus der PDF-Textebene (`GET /api/documents/{id}/locate`),
ohne Vision. Nennt die Frage ein Betriebsmittel (-K1), zeigt eine **Befundkarte** Stromlaufplan-
Verweise, Klemmen und SPS-Adressen aus dem Kennzeichen-Index (`GET /api/facts`), nicht vom Modell.

## Architektur

```
frontend/   Next.js + TypeScript: Wissensquellen, Upload, Chat (SSE-Streaming), Seiten-Viewer,
            Werk (Standortplan, Hallen-Baukasten, Maschinenseite, Draufsicht-Editor mit React Flow,
            Planung/Vorkalkulation,
            Schaltschrank-Editor), shadcn/ui im Blaupause-Design, Strg+K-Suche
backend/    FastAPI
  app/ingestion/   Docling (PDF/Office -> Markdown je Seite), AWL-Parser, Kennzeichen-Index,
                   optionale Vision-Analyse der Schaltplanseiten (Claude)
  app/agent/       LangGraph-Agent (Claude) mit Werkzeugen: search_knowledge, find_tag,
                   keyword_search, get_page, view_page, get_plc_block, list_documents
  app/api/         REST + SSE; plant.py: Hallen, Maschinen, Fehlerliste, Schaltschrank-Hotspots,
                   Tag-Suche; layout.py: Draufsicht (Grundflaeche, Teile in mm, Vision-Vorschlaege);
                   site.py: Standortplan, Fluesse zwischen Hallen, Kennzahlen
  app/werk/        Werk-Logik ohne DB und ohne Modell (Standortlage, Kennzahlen, Kalender,
                   Vorkalkulation)
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

## Antwortqualitaet messen

`eval/questions.jsonl` enthaelt 24 Fragen mit Erwartungen (Pflichtangaben, verbotene Angaben, zu
zitierende Quellen), darunter drei Fallen ohne Antwort im Material. `python eval/run_eval.py` schickt
sie an das laufende Backend und bewertet ohne LLM-Richter. Details in [`eval/README.md`](eval/README.md).

## Tests

```bash
cd backend && .venv/Scripts/python -m pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```
