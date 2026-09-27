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

## Schema-Migrationen (Alembic)

Das Schema wird beim Start über Alembic auf den neuesten Stand gebracht (`init_db()` ruft
`alembic upgrade head`). Von Hand aus `backend/`: `alembic upgrade head`, `alembic current`,
`alembic downgrade base`. Die Baseline `0001_stromlauf_baseline` legt auf einer leeren Datenbank alle
Tabellen an und bringt eine Datenbank aus der früheren `create_all`-Zeit über die additiven
Statements in `app/migrations.py` auf denselben Stand. Neue Schemaänderungen: Modell ändern, dann
`alembic revision --autogenerate -m "kurz-was"` (braucht eine laufende Datenbank), Datei prüfen,
committen. `backend/tests/test_alembic_baseline.py` hält Baseline und Modell deckungsgleich; CI
prüft die Migration von null gegen `pgvector/pgvector:pg17`.

## Deployment (Railway)

Backend als Container (`backend/Dockerfile`, Build-Kontext `backend/`), Datenbank Postgres mit pgvector,
Frontend auf Vercel (Projekt `stromlauf-ai`, Root Directory `frontend`). Railway-Service:

1. Service aus dem GitHub-Repo, **Root Directory `backend`** (dann greift `backend/railway.toml`:
   Dockerfile-Build, Healthcheck `/api/health`).
2. **Volume auf `/data`** (Uploads, Bilder, Flow-Cache, HF-Modellcache). Eine Instanz; fuer mehrere
   Instanzen waere ein Bucket noetig (siehe `docs/product/architecture.md`).
3. Datenbank-Service mit pgvector (Image `pgvector/pgvector:pg17` oder Railway-Postgres mit
   `CREATE EXTENSION vector`), Variable `DATABASE_URL=postgresql+psycopg://...`.
4. Variablen: `ANTHROPIC_API_KEY`, `API_KEY` (Zugriffsschutz), `CORS_ORIGINS=https://<vercel-domain>`,
   `CHECKPOINTER=postgres`, `EMBEDDING_PROVIDER=voyage` + `VOYAGE_API_KEY` (oder `local`, dann
   mindestens 3 GB RAM fuer bge-m3), optional `LANGFUSE_*`, `OCR_ENABLED`.
5. Vercel: `NEXT_PUBLIC_API_URL=https://<railway-domain>`, `NEXT_PUBLIC_API_KEY=<API_KEY>`.

Beim Start laeuft `alembic upgrade head`; mit `CHECKPOINTER=postgres` legt der Agent seine
Verlaufstabellen selbst an. `EMBEDDING_PROVIDER` wechseln heisst: alle Dokumente neu verarbeiten
(„Neu verarbeiten“ im Quellen-Panel oder `POST /api/documents/{id}/reingest`), sonst passen die
Vektoren nicht zusammen. CI baut das Image bei jedem PR (`docker build backend`).

## Zugriffsschutz

Ohne `API_KEY` in `.env` läuft das Backend offen (nur lokal sinnvoll). Mit `API_KEY` verlangt jede
Route unter `/api/` den Schlüssel, nur `/api/health` bleibt frei:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # Schlüssel erzeugen
# .env: API_KEY=<Schlüssel>  NEXT_PUBLIC_API_KEY=<Schlüssel>  STROMLAUF_API_KEY=<Schlüssel>
```

Frontend, Skripte (`scripts/`, `eval/`) und MCP-Server schicken ihn als Header `X-API-Key`; auch
`Authorization: Bearer` gilt. Bilder lädt der Browser ohne Header, dafür hängt das Frontend
`?api_key=` an Bild-URLs. Es ist ein gemeinsamer Schlüssel je Installation, keine Benutzerverwaltung.

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

## Testdokumentation: Umroller UR-01 und Aufrollung PM1-AR

Zwei größere Maschinen des Testwerks haben eine vollständige Elektrodokumentation, frei erfunden und
in sich stimmig: Stromlaufplan (16 bzw. 13 Blätter), Stückliste, Klemmenplan, AWL (FB mit 13 bzw.
16 Netzwerken, Schrittkette), Symboltabelle und Betriebsanleitung mit Fehlertabelle. Sie liegen in
[`examples/umroller/`](examples/umroller/) und [`examples/aufrollung/`](examples/aufrollung/) und
entstehen aus einem datengetriebenen Generator (`scripts/testdoku/`, Maschinenmodell → alle sechs
Dokumente, Blatt/Spalten-Verweise werden beim Zeichnen erfasst):

```bash
pip install -e "backend[examples]"                 # reportlab, openpyxl
python scripts/testdoku/build.py all               # erzeugt beide Sätze neu
python scripts/load_testwerk.py --docs             # lädt sie hoch und verknüpft L1-UR und PM1-S6
```

Der Lader übernimmt die Fehlertabellen in die Fehlerlisten der Maschinen; Signalweg, Befundkarte
und Fehlersuche funktionieren damit an beiden Maschinen. Tests (`backend/tests/test_testdoku.py`)
prüfen jeden Verweis gegen den Plan und lassen alle Parser über die Dateien laufen.

## Werk: Maschinen, Standortplan, Halle, Schaltschrank

Reiter **Maschinen** (`/werk/maschinen`) ist der Einstieg: alle Maschinen des Werks in einer Tabelle
mit Typ, Linie, Halle, Stand der Dokumentation (keine / n von m fertig / fertig), Zahl der
Fehlereinträge, offenen Fehlersuchen und erster Kennzahl; Filter über Name, Linie, Halle, Typ und
Wissensquelle. Rot ist nur die Zahl offener Fehlersuchen. Daten: `GET /api/machines`.

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

## Dokumenttyp aus dem Inhalt

Beim Hochladen mit „Automatisch erkennen“ liest das Backend eine Textprobe (erste drei PDF-Seiten,
erste Zeilen einer Tabelle oder Textdatei) und schlägt den Typ mit Begründung vor, etwa
„Kopfzeile Klemmleiste;Klemme;Ziel“ oder „Schriftfeld Blatt n / m; Spaltenkopf 1 … 8“. Der Dialog
zeigt den Vorschlag je Datei; du bestätigst oder änderst ihn, dann wird hochgeladen. Reihenfolge:
Endung (.awl, .sdf) vor Inhalt vor Dateiname. Regeln in `backend/app/ingestion/doctype.py`, Vorschau
`POST /api/documents/detect`. Alle 18 Beispieldateien werden allein aus dem Inhalt richtig erkannt.

## Ablauf-Visualisierung: Schrittkette aus der Doku (kostet Tokens, einmal je Dokument)

Zwei Phasen, strikt getrennt. **(A) Extraktion** liest Funktionsbeschreibung, Symboltabelle, Stückliste
und AWL und schreibt ein JSON nach `schemas/machine_flow.json`. **(B) Anzeige** liest nur dieses JSON,
ohne Modellaufruf. Gleiche Dateien und gleiche Prompt-Version kommen aus dem Cache
(`backend/data/flow_cache/<sha256>.json`), also null Kosten beim zweiten Mal.

```bash
python scripts/extract_flow.py examples/foerderband/06_Betriebsanleitung_FB-01.md \
  --awl examples/foerderband/04_SPS_Programm_FB-01.awl \
  --extra examples/foerderband/05_Symboltabelle_FB-01.sdf \
  --extra examples/foerderband/02_Stueckliste_FB-01.xlsx \
  --out backend/data/flows/fb01.flow.json          # oder: pip install -e backend && extract-flow ...
```

- **Modelle** über `.env`: `FLOW_MODEL_SMALL` (I/O-Liste und Sensoren/Aktoren, zwei Aufrufe parallel)
  und `FLOW_MODEL_STRONG` (nur Schrittkette), `FLOW_EFFORT` für die Schrittkette. Layout der Draufsicht
  entsteht deterministisch aus den I/O-Punkten, ohne Modell.
- **Belege:** jedes Objekt trägt `source` (Datei, Seite oder Abschnitt, Zitat bis 15 Wörter), `confidence`
  und `assumption`. Verweise auf unbekannte Adressen landen in `open_questions`, werden nicht geraten.
- **Trace:** mit `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` (Paket `langfuse`, Extra `backend[trace]`) wird jede
  Extraktion ein Trace mit Spans `phase_a`, `phase_b`, `layout` und einer Generation je Modellaufruf
  (Tokens, Kosten, Latenz, Prompt-Version). Die Trace-ID steht in `meta.trace_id`. JSON-Logs auf stderr
  tragen dieselbe Trace-ID. Ohne Langfuse: lokale ID, gleiche Logs.
- **Kosten** stehen in `meta.total.cost_usd` (Preistabelle in `app/flow/pricing.py`) und in Langfuse.
  Messwert je Extraktion: noch nicht erhoben, dieser Container hat keinen API-Schlüssel. Nach dem ersten
  Lauf hier eintragen.
- Latenzbudget 30 s: Phase A parallel, `meta.total.latency_ms` und Log-Feld `over_budget` zeigen Verstöße.

**Anzeige** (Tab **Ablauf** auf der Maschinenseite): eine eigenständige Seite `frontend/public/ablauf/index.html`,
SVG plus Vanilla JS ohne Bibliotheken, per iframe eingebettet. Sie lädt nur das JSON (`GET /api/machines/{id}/flow`
aus dem Cache, in der Regel unter 30 ms) und simuliert die Schrittkette: Draufsicht mit aktiven Aktoren grün,
ausgelösten Sensoren gelb, unterbrochenem Sicherheitskreis rot; GRAFCET-Leiste mit aktuellem Schritt und
Bedingungen; Abspielen, Pause, Einzelschritt, Geschwindigkeit; DI/DO-Tabelle, Klick auf eine DI-Zeile schaltet
den Eingang (Störung von Hand auslösen). Klick auf Sensor, Aktor, Schritt oder Transition zeigt das Zitat mit
Datei und Seite. Gestrichelt = Lage geschätzt. Der Knopf „Ablauf extrahieren“ ruft `POST
/api/machines/{id}/flow/extract` (kostet Tokens, einmal je Dokumentstand). Simulationskern
`public/ablauf/sim.js`, Tests `src/lib/ablauf.test.ts`. Demo ohne Backend: `/ablauf/index.html?src=/ablauf/example.json`.

## Steckbrief je Wissensquelle (ohne KI-Kosten)

Nach dem Upload zeigt `/quelle/{id}` (Link im Quellen-Panel, im Tab „Dokumente“ der Maschine und in
der Maschinenübersicht), was die Dokumente hergeben: welche der sechs Dokumenttypen da sind, eine
Abdeckungsmatrix (jedes Betriebsmittel, jede Klemme, jede SPS-Adresse mit Fundstellen je Dokumenttyp)
und eine Lückenliste aus Regeln zwischen zwei Dokumenttypen, etwa „Betriebsmittel im Plan, aber nicht in
der Stückliste“, „Klemme im Plan, aber nicht im Klemmenplan“, „SPS-Adresse im Programm ohne Symbol“ oder
„Blattverweis auf ein Blatt, das der Plan nicht hat“. Eine Regel greift nur, wenn beide Dokumenttypen
vorhanden sind. Rechenkern `backend/app/ingestion/profile.py`, Daten `GET /api/sources/{id}/profile`.
Die Beispielanlage FB-01 hat genau eine Lücke: Symbol `M10.1` ohne Verwendung im AWL.

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

## Planung: Vorkalkulation (Nebenmodul, ohne KI-Kosten)

Nebenmodul im Feature-Freeze: wird gepflegt, aber nicht erweitert. Der Kern des Projekts ist die Maschine mit ihrer Dokumentation.

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

## Leitstand: Durchlauf-Simulation (Nebenmodul, ohne KI-Kosten)

Nebenmodul im Feature-Freeze, siehe Planung.

Reiter **Leitstand** (`/leitstand`): alle Aufträge des Auftragsbuchs laufen deterministisch durch
das Werk. Eine **Simulationsuhr** (Abspielen, 1 h / 6 h / 1 Tag je Sekunde, Schieberegler) zeigt zu
jeder Uhrzeit den Zustand von **Büro** (Kundenservice, Finanzen mit Kreditklärung, Arbeitsvorbereitung,
Geschäftsführung ab 100 Paletten; Personen belegt/frei, Warteschlange), **Fertigung** (PM1 und
Linien mit Fortschritt), **Lager** (Bestand je Artikel, „heute raus“) und **Versand** (8 Tore, LKW,
wartende LKW). Klick auf einen Auftrag zeigt seinen Weg (Warten hell, Arbeiten blau). Kennzahlen:
Termintreue, Ø Durchlauf, Auslastung, Ø Wartezeit Finanzen.

Regeln: Büro und PM1 nach Ankunft, Linien nach Wunschtermin, Tore nach Ankunft; vorhandener Bestand
wird von der Arbeitsvorbereitung reserviert, der Rest gefertigt; übersteigen offene Aufträge eines
Kunden sein Kreditlimit, folgt ein Arbeitstag Klärung. Simulationskern `backend/app/werk/sim.py`
(Ereignisschleife, rein, getestet), API `POST /api/simulation`, Auftragsbuch `GET/POST /api/orders`,
Bestand `GET /api/stock`. In der Planung legt „Als Auftrag anlegen“ die kalkulierte Bestellung ins
Auftragsbuch. Testwerk: 6 Kunden, 14 Aufträge in KW 40, Anfangsbestand (`python scripts/load_testwerk.py`).
Kreditlimits, Personenzahl und Klärungsdauer sind Richtwerte. Nicht enthalten: Maschinenausfälle,
Schichtpläne, Nachproduktion aufs Lager, Teillieferungen.

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

## Fehler markieren

Tab **Fehler**, Knopf **Zeigen** an einem Eintrag: ein roter Balken über allen Tabs nennt den Fehler und seine
Kennzeichen. Gleichzeitig werden die betroffenen Teile in der **Draufsicht**, die Bauteile im
**Schaltschrankfoto** und die I/O-Punkte samt Schritten im **Ablauf** rot markiert. Der Balken zählt die
Treffer je Ansicht, springt per Klick dorthin, nennt nicht platzierte Kennzeichen und startet die geführte
Fehlersuche. Rein aus Daten, kein Modellaufruf. Logik in `frontend/src/lib/faults.ts`.

## Chat je Maschine

Tab **Chat** auf der Maschinenseite: der Scope ist fest die Wissensquelle der Maschine. Das Backend erzwingt
das über `machine_id` im Chat-Aufruf, die Auswahl anderer Quellen ist dort nicht möglich; der Agent bekommt
den Maschinenkontext (Name, Halle) in den Systemprompt. Ausnahme, bewusst: die handgepflegten
**Fehlerlisten** aller Maschinen bleiben werksweit durchsuchbar (Werkzeug `search_faults`), Treffer an anderen
Maschinen kennzeichnet der Agent als Erfahrung, nicht als Beleg. Die Chats einer Maschine sind die
Konversationen, deren Scope genau ihre Quelle ist (`GET /api/conversations?source_id=…`, keine neue Spalte).
Der Reiter **Chat** in der Navigation bleibt der werksweite Chat mit freier Quellenwahl.

## Chat-Antworten

Antworten sind fest gegliedert: **Kurzantwort** (max. 2 Saetze), **Pruefen** (max. 5 Schritte,
je ein Beleg), **Sicherheit** (nur wenn relevant), **Details** (eingeklappt). Belege schreibt das
Modell als `[[Dateiname|Ort]]`; die Oberflaeche macht daraus Chips und listet nur zitierte Stellen.
Ein Klick auf einen Stromlaufplan-Verweis wie `/3.8` oeffnet rechts Blatt 3 und markiert Spalte 8.
Blatt und Spalten liest das Backend aus der PDF-Textebene (`GET /api/documents/{id}/locate`),
ohne Vision. Nennt die Frage ein Betriebsmittel (-K1), zeigt eine **Befundkarte** Einbauort,
Stromlaufplan-Verweise, Klemmen und SPS-Adressen aus dem Kennzeichen-Index (`GET /api/facts`), nicht
vom Modell. Der **Einbauort** kommt aus der Einbauort-Spalte der Stückliste (`+ST1`, `+FE1`), den
Klartext („Schaltschrank +ST1") liefert die Kopfzeile derselben Datei; Leitungen tragen beide Orte.
Ohne Kopfzeile steht nur das Kennzeichen da — geraten wird nichts.

## Architektur

```
frontend/   Next.js + TypeScript: Wissensquellen, Upload, Chat (SSE-Streaming), Seiten-Viewer,
            Werk (Standortplan, Hallen-Baukasten, Maschinenseite, Draufsicht-Editor mit React Flow,
            Planung/Vorkalkulation, Leitstand (Simulationsuhr),
            Schaltschrank-Editor), shadcn/ui im Blaupause-Design, Strg+K-Suche
backend/    FastAPI
  app/ingestion/   Docling (PDF/Office -> Markdown je Seite), AWL-Parser, Kennzeichen-Index,
                   optionale Vision-Analyse der Schaltplanseiten (Claude)
  app/agent/       LangGraph-Agent (Claude) mit Werkzeugen: search_knowledge, find_tag,
                   keyword_search, get_page, view_page, get_plc_block, list_documents
  app/retrieval.py Hybrid-Suche: Vektor (pgvector, HNSW) + Volltext (tsvector 'german', GIN),
                   Fusion per Reciprocal Rank Fusion; search_knowledge und /api/search?mode=semantic
  app/api/         REST + SSE; plant.py: Hallen, Maschinen, Fehlerliste, Schaltschrank-Hotspots,
                   Tag-Suche; layout.py: Draufsicht (Grundflaeche, Teile in mm, Vision-Vorschlaege);
                   site.py: Standortplan, Fluesse zwischen Hallen, Kennzahlen
  app/werk/        Werk-Logik ohne DB und ohne Modell (Standortlage, Kennzahlen, Kalender,
                   Vorkalkulation, Durchlauf-Simulation)
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

## Tracing: was in Langfuse landet (optional)

Mit `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY` in der `.env` und dem Extra
`pip install -e "backend[trace]"` schicken drei Stellen Traces:

| Was | Session in Langfuse | Tags | Woher |
| --- | --- | --- | --- |
| Chat: Agent, Werkzeugaufrufe, Tokens, Kosten | Konversations-ID | `stromlauf-ai`, `model:…`, dazu `ChatRequest.trace_tags` | `app/tracing.py` als LangChain-Callback in `graph.astream` |
| Vision: Seitenanalyse beim Upload, Draufsicht, Schaltschrank | Dokument- bzw. Bild-ID | `ingestion` plus `seitenanalyse`, `draufsicht` oder `schaltschrank` | derselbe Callback über `app/tracing.py: vision_trace` |
| Ablauf-Extraktion | ein Trace je Lauf | Spans `phase_a`, `phase_b`, `layout` | `app/flow/tracing.py`, setzt Tokens und Kosten selbst |

Ohne Schlüssel ist alles ein No-op: `trace_config` liefert ein leeres Dict, die Extraktion vergibt eine
lokale Trace-ID und loggt weiter als JSON. Die Schlüssel- und Paketprüfung steht nur in `app/tracing.py`.

**Nicht** getrackt, weil ohne Modell und ohne Kosten: hybride Suche (`app/retrieval.py`), Embeddings
(bge-m3 lokal) und die deterministischen Parser (Signalweg, Fehlersuche, Steckbrief).

Im Chat-Strom kommt je Modellaufruf ein SSE-Ereignis `usage` mit Input-/Output-Tokens und Modell —
unabhängig von Langfuse, daraus rechnet der Eval-Lauf seine Kosten (`app/flow/pricing.py`).

Live gegen Langfuse noch ungeprüft (hier ohne Schlüssel gelaufen); abgedeckt sind Konfiguration und
Weitergabe durch `backend/tests/test_tracing.py`.

## Antwortqualitaet messen

`eval/questions.jsonl` enthaelt 51 Fragen mit Erwartungen (Pflichtangaben, verbotene Angaben, zu
zitierende Quellen) zu FB-01, UR-01, PM1-AR, Festo, AWL und Testwerk, darunter fuenf Fallen ohne Antwort
im Material. Drei Schichten, bewertet ohne LLM-Richter:

```bash
python eval/run_retrieval.py     # kostenlos: liefern die Werkzeuge die Belege? (Sekunden)
python eval/rescore.py eval/results/referenz_2026-09-26.json   # kostenlos: gespeicherten Lauf neu bewerten
python eval/run_eval.py          # Agentenlauf, kostet API-Tokens je Frage
```

Details in [`eval/README.md`](eval/README.md).

## Tests

Alle Prüfungen auf einmal, wie sie eine CI ausführen würde (ohne Cloud-Kosten, etwa 1 Minute):

```bash
backend/.venv/Scripts/python scripts/check.py                 # ruff, pytest, eslint, tsc, vitest
backend/.venv/Scripts/python scripts/check.py --install-hook  # dasselbe automatisch vor jedem Push
```

Der GitHub-Workflow `.github/workflows/ci.yml` ist nur von Hand startbar, weil das private Repo kein
Actions-Guthaben hat. Wird das Repo öffentlich, `push`/`pull_request` wieder als Auslöser eintragen.

```bash
cd backend && .venv/Scripts/python -m pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```
