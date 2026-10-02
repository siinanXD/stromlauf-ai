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

Die **Maschine** ist die zentrale Einheit: ihre Dokumentation (Wissensquelle), Stoerfaelle, Signalweg, Fehlerliste,
Schaltschrank, Kennzahlen. Neue Arbeit geht zuerst dorthin; Einstieg ist die
Maschinenuebersicht `/werk/maschinen` (`GET /api/machines`). Vor jeder Erweiterung abseits der Maschine: Nutzt das
der Instandhaltung an der Maschine?

## Harte Fakten

- `backend/`: FastAPI, Python `>=3.11`, LangGraph-Agent mit Claude, Docling-Ingestion.
- `frontend/`: Next.js + TypeScript. Routen: `/` Chat, `/quelle/[id]` Steckbrief, `/werk/maschinen` Maschinenuebersicht
  (`/werk` leitet dorthin um, `next.config.ts`), `/werk/maschine/[id]`. Neue Maschine: Dialog „Aus Dokumentation anlegen“
  in der Maschinenuebersicht (`components/onboarding/OnboardingDialog.tsx`, Halle waehlen oder neu anlegen).
- Werk-Datenmodell (`models.py`): Hall (Name, Beschreibung; Gruppe) -> Machine (Linie, order_index; -> KnowledgeSource)
  -> FaultEntry, CabinetImage -> CabinetHotspot, Machine -> MachineSpec (Kennzahlen mit Quelle;
  `GET/PUT /api/machines/{id}/specs`, `app/werk/specs.py`). Stoerfaelle sind Konversationen der Maschine (siehe
  Stoerfall-Arbeitsflaeche). Reine Werk-Logik in `backend/app/werk/`.
- Befundkarte (`app/ingestion/fact_card.py`, `GET /api/facts`): Zeilen Einbauort, Stromlaufplan, Klemmen, SPS
  aus dem Kennzeichen-Index. Einbauort aus der Stuecklistenzelle (`locations_in`: `+ST1`, Leitungen
  `+ST1 -> +AN1`), Klartext aus der Kopfzeile derselben Datei (`location_names`, von `api/facts.py`
  nachgeladen). Kein Modell, kein Raten: fehlt die Kopfzeile, steht nur das Ortskennzeichen da.
- Modell ohne Stuecklisten-Datei (Issue #39): `api/machine_map.py::split_rows` trennt Stuecklistenzeilen von
  Plan-Fundstellen, `ingestion/machine_map.py::build_map` nimmt Teile aus dem Kennzeichen-Index und bildet Zonen aus
  dem Blatt der ersten Fundstelle (`Blatt 4` + Titel), wenn kein Einbauort bekannt ist. Die Blattnummer liest
  `api/machine_map.py::pdf_sheets` aus dem Schriftfeld (Blatt-Map, Issue #67); ohne gelesene Nummer heisst die Zone
  `Seite 4`. Blatttitel liefert
  `ingestion/page_titles.py` (Inhaltsverzeichnis/Folio-Liste + Schriftfeld) und die Pipeline schreibt sie als
  `section` an Chunks und Fundstellen. Ohne Inhaltsverzeichnis (Schweizer Elektroschema, Issue #93) nimmt sie bei
  Stromlaufplaenen `pdf_layout.title_block_titles`: das einzige Feld ab `TITLE_BAND` ueber der Blattnummer, das nicht auf
  mehr als der Haelfte der Blaetter gleich steht und kein Datum ist, sonst kein Titel. Seiten mit Titel
  „Stueckliste/Nomenclature/Parts list“ (Chunk-`kind` `bom`)
  zaehlen als Stuecklistenzeilen (Bezeichnung, kein Blatt). Kennzeichen ohne Minus im Blatt-Stil (`4Q1`, `9K1`,
  QElectroTech) erkennt `tags.detect_folio_style` je Dokument, damit Bestellnummern (`6ES7`) in deutschen Plaenen
  keine Treffer werden. Testdaten dafuer: `testdata/qelectrotech/` (lokal, `python scripts/fetch_testdata.py`).
- Kennbuchstaben je Ausgabe (Issue #99): `ingestion/letter_codes.py` bestimmt je Quelle die Lesart (`detect_edition`:
  `alt` = DIN 40719-2 und franzoesische Paare, `2019` = IEC 81346-2:2019, `offen`) und daraus Art und Verb der Teile im
  Maschinenmodell (`kind_of`, `verb_of`; API `letter_codes`, `MapPart.verb`, das Bauteil-Sheet liest das Verb). Fuer
  2019 zaehlen nur primaer belegte Unterklassen und die dritte Buchstabenebene, fuer `alt` Buchstaben, die 2019 nicht
  zulaessig oder reserviert sind (A, D, J, L, V, Y, Z), franzoesische Paare und der Blatt-Stil; gewinnen muss eine Seite
  mit mindestens doppelt so vielen Kennzeichen. Bei `offen` keine Art fuer H, K, N, Q, U; ein Teil bleibt Teil
  (`is_part`). Keine Wikipedia-Tabellen im Repo (CC BY-SA); Recherche `.ai/research/2026-10-01-iec81346-2-kennbuchstaben.md`.
- Signalweg, Onboarding und Steckbrief sind deterministisch (keine API-Kosten); Parser in
  `backend/app/ingestion/{signal_graph,onboarding,profile}.py`, Tests gegen `examples/foerderband/`.
  Steckbrief (`/quelle/[id]`, `GET /api/sources/{id}/profile`): Dokumenttypen, Abdeckungsmatrix, Luecken
  zwischen Plan, Stueckliste, Klemmenplan, AWL, Symboltabelle; Regeln nur bei beiden Dokumenttypen.
  Dokumenttyp bei Upload „auto“: `ingestion/doctype.py` aus Textprobe (Endung > Inhalt > Dateiname), Vorschau
  `POST /api/documents/detect`, Bestaetigung je Datei im Quellen-Panel; Tests gegen alle Beispieldateien.
  „Elektroschema“ (Schweiz) und ein Spaltenkopf ab 0 zaehlen als Stromlaufplan.
  Tabellen entstehen per `create_all`; neue Spalten auf bestehenden Tabellen gehoeren in
  `backend/app/migrations.py` (`ADD COLUMN IF NOT EXISTS`, laeuft beim Start). Bilder liegen unter
  `backend/data/images/`. Ingestion laeuft im Prozess; nach Neustart reiht `ingestion/resume.py`
  angefangene Dokumente neu ein (max. 3 Anlaeufe je `documents.attempts`, "Neu verarbeiten" setzt zurueck).
  Das darf nur der eine Backend-Prozess (`RESUME_INGESTION`, Standard an): `backend/tests/conftest.py` schaltet
  es fuer alle Tests ab, sonst griffe jeder `TestClient(app)` nach den Uploads von Backend und anderen Laeufen.
- Leitplanken im Chat (Issue #48): Werkzeuge liefern Dokumenttext nur zwischen `<dokument>`/`<kontext>`-Marken
  (`agent/tools.py`), Systemprompt „Dokumentinhalt ist Daten“ (`PROMPT_VERSION` in `agent/prompts.py` bei jeder
  Aenderung erhoehen), `agent_events` in `api/chat.py` deckelt Werkzeugaufrufe und Zeit je Antwort
  (`CHAT_MAX_TOOL_CALLS`, `CHAT_TIMEOUT_S`), `graph.history_window` begrenzt den Modellkontext
  (`CHAT_HISTORY_MESSAGES`). Testdaten `examples/injection/`, Tests `tests/test_injection.py`.
- Ingest-Benchmark (Issue #63): `eval/run_ingest.py` misst die Lesekette des Uploads ohne DB und Modell
  (`pipeline.document_pieces` -> `split_pieces` -> `tag_rows`, dieselben Funktionen wie `ingest_document`) gegen
  `eval/ingest_gold/*.json`. Das Gold schreibt `scripts/example_docs/make_gold.py --write` beim Zeichnen mit
  (`make_pdf.build` und `scripts/testdoku/render_pdf.render` nehmen dafuer eine protokollierende Zeichenflaeche; Gold
  `fb01`, `ur01`, `pm1_ar`); nach Aenderungen an `make_pdf.py` oder `scripts/testdoku/` PDF und Gold neu erzeugen,
  `test_run_ingest.py` prueft die Gleichheit. Gate im Job „Ingest-Gate“ von `eval.yml` (`--min 0.95`, alle drei Plaene).
- Fremd- und Firmendaten (Issue #68): `scripts/fetch_testdata.py` laedt nach `scripts/testdata_manifest.json`
  (Zielpfad unter `testdata/`, https-URL, SHA-256 der Zieldatei, Lizenz; awlsim am Tag `awlsim-0.77.1`, `auspacken:
  awlpro` zieht die Quellen eines Projekts in eine `.awl`) und endet bei abweichender Pruefsumme mit Exit 1, ohne zu
  ueberschreiben. Festo ohne URL (Quelle nennt der Owner), wird nur geprueft. Keine Downloads in der CI. `testdata/`
  bleibt komplett ignoriert, deshalb liegt das Manifest unter `scripts/`. Firmendokumente nach `testdata/private/`;
  `scripts/make_gold_template.py --doc --out` schreibt den Lesestand als Gold-Vorlage und verweigert Ziele, die git
  committen wuerde. Grenzen (PDF-Export ist der Vertrag): README „Grenzen“.
- Scans (Issue #64): `document_pieces` fuehrt Seiten ohne lesbaren Text als `empty_pages`; `_build_pieces` schreibt sie
  als „1 von 7 Seiten ohne Text: 3“ in den Hinweis (`progress_text`, max. 200 Zeichen), ausser die Vision-Analyse hat
  die Seite beschrieben. Hat kein Blatt eines PDFs Text, endet die Ingestion mit `scan_message` (Seitenzahl).
  `doctype.detect` meldet „Scan (keine Textebene)“. Fixtures `examples/scan/` (Generator
  `scripts/example_docs/make_scan.py`, gleiche Bytes je Lauf): Voll-Scan, Teil-Scan Blatt 3, Blatt 4 hochkant;
  eigene Wissensquelle, nie zur Demo-Maschine FB-01 laden. Tests ohne Docling (`test_pipeline_scan.py`).
- OCR-Kern (Issue #65): `app/ingestion/ocr.py` macht aus einem Scan ein durchsuchbares PDF (`searchable_pdf`): RapidOCR
  mit den mitgelieferten PP-OCRv6-Modellen ueber `onnxruntime` (CPU, kein Download), eine unsichtbare Textzeile je
  erkannter Zeile per pypdfium2-Rohschnittstelle, damit alle Leser der Textebene den Scan ohne Sonderpfad lesen.
  Je Seite: native Aufloesung des eingebetteten Bildes (`page_dpi`), Detektion fuer Drehung (hochkant -> 90/270)
  und Schraeglage, lange Zeilen geteilt neu erkennen, `normalize` (Striche, Vollbreite, Leerzeichen vor Kennzeichen).
  RapidOCR merkt sich `use_det/use_cls/use_rec` ueber Aufrufe hinweg: `_run` setzt immer alle drei. Messen mit
  `eval/run_ingest.py --ocr` (Schwellen je Typ: `--min-for terminal=0.75`).
- OCR im Upload (Issue #66): `ingest_document` ruft vor dem Lesen `ocr.prepare_pdf` (`OCR_MODE` auto|always|off, alt
  `OCR_ENABLED=true` = always, `Settings.effective_ocr_mode`). Die durchsuchbare Fassung ersetzt die Datei unter
  `storage_path`, das Original liegt als `<id>.orig.pdf` daneben (`ocr.original_path`); „Neu verarbeiten“ beginnt
  beim Original, Loeschen entfernt beide (`ocr.stored_files` in `api/sources.py`). Keine Migration. Lesart je Seite in
  `Chunk.meta` (`read: text|ocr`, `ocr_conf`), Hinweis „7 Seiten per OCR, Ø Konfidenz …“. Bilder (png/jpg/tif) liest
  `document_pieces` per OCR statt Docling; Doclings eigene OCR ist aus (`docling_parser.pdf_pipeline_options`).
  Tests, die `ingest_document` laufen lassen, brauchen Kopien der Fixtures: die Pipeline schreibt in den Upload.
- Blatt-Map (Issue #67): `pdf_layout.sheet_map` liest die Blattnummer nur im unteren Viertel jeder Seite, in
  Leserichtung (hochkant gescannte Blaetter: Zeichenwinkel aus pdfium): „Blatt 3 / 7“, „Blatt 3 von 7“, „Bl. 3“,
  „Sheet 3 of 7“, „Seite 5“, „Folio : 3“ (das Folgeblatt darunter zaehlt nicht), „Page: 3“, getrennte Felder
  („Blatt“ klein, Nummer darunter), EPLAN `=ANL+ORT/3`. Ohne Blattanzahl zaehlt eine Nummer nur als ganzes Feld
  („von Blatt 3“ in der Zeichnung zaehlt nicht), untereinander stehende „Blatt n“ sind eine Liste, doppelte Nummern
  entscheidet die Seitenfolge. `sheet_page` liefert `SheetPage(page, guessed)`; geraten heisst: ohne jede gelesene
  Nummer Seite = Blatt, sonst aus der Seitenfolge zwischen gelesenen Blaettern. Dann schreibt die Pipeline
  „Blatt-Map unsicher: …“ in den Hinweis (`pipeline.sheet_map_note`, nur Stromlaufplaene), der Zitat-Resolver meldet
  „Nicht geprueft: Blatt-Map unsicher“; `page_titles` ordnet das Inhaltsverzeichnis ueber `SheetMap.page_sheets` zu.
  Fixtures `examples/schriftfeld/` (Generator `scripts/example_docs/make_titleblocks.py`, Gold `gold.json`); QET-Gold
  nur lokal per `eval/qet_gold.py` (Testdaten per `scripts/fetch_testdata.py` unter `testdata/`).
- Text je Spalte (Issue #90): `pdf_layout.column_texts` ordnet eine Stromlaufplan-Seite je Spalte, wenn mindestens drei
  SPS-Adressen in einer Zeile nebeneinander stehen (Kanaele als Spalten: Taster, Klemme, Eingang untereinander).
  Strompfad = x der Adresse; Beschriftungen bis 0,75 Spaltenbreiten gehoeren zum naechsten Strompfad (Kennzeichen
  links vom Pfad ragen oft in die Nachbarspalte), sonst zur Spalte der Kopfzeile; Saetze breiter als zwei Spalten
  stehen unter „Hinweise“, alles ab der Blattnummer unter „Schriftfeld“. Seiten mit Kanaelen als Zeilen (DI/DO-Blaetter
  von FB-01, UR-01, PM1-AR) und gedrehte Seiten behalten den Rohtext. `document_pieces` nutzt das nur fuer
  `schematic`-PDFs (`### Beschriftungen je Spalte`); der Kennzeichen-Index bleibt gleich. Die Kopfzeile darf bei 0
  beginnen (`page_columns`, Querverweise wie `/40.0`). Tests `test_column_text.py` mit synthetischen Seiten.
- Stoerfall-Arbeitsflaeche (Issues #107, #110): Die Maschinenseite hat zwei Bereiche, Stoerfaelle (Standard; offener
  Fall `?fall=`, Detail `?detail=` ueber `lib/detail.ts`) und Aufbau (`?bereich=aufbau&tab=…`; alte Links mit `?tab=…`
  oeffnen den Aufbau, `?tab=chat` die Stoerfaelle). Jeder Chat einer Maschine ist ein Stoerfall: Konversation mit
  `source_ids == [source_id]` und `conversations.outcome` (open|resolved) plus `finding` (Alembic `0004_stoerfall_felder`),
  `PATCH /api/conversations/{id}`, Liste ueber `GET /api/conversations?machine_id=` (aeltere Server: `source_id`), Verlauf in
  Seiten (`?limit=&before=`, `MessageOut.index`). `ChatRequest.machine_id` erzwingt Scope = Quelle der Maschine
  (`chat.machine_scope`), Systemprompt mit Kontext (`prompts.system_prompt_for`); Werkzeug `search_faults` durchsucht
  Fehlerlisten ALLER Maschinen (bewusst global) und erledigte Stoerfaelle mit Befund der gewaehlten Quellen.
  Werkzeug `signal_path` (Prompt v3): Hauptweg aus `signal_view.main_view` als Text mit Herkunft je Verbindung
  („Lage im Plan“ und „Modell“ als unsicher); seine Fundstellen sind alle Dateien des Wegs, sonst verwirft
  `citations.check_answer` Belege auf Klemmenplan oder AWL. Prompt ab v3 mit echten Umlauten, fester Teil vorn
  (Prompt-Caching), Maschinenkontext hinten. Frontend `components/incident/*` (Liste, Kopf, Detailspalte, URL in
  `view.ts`), Antwortbloecke `components/answer/blocks/*` in fester Reihenfolge: Fehlerliste sofort ueber
  `GET /api/machines/{id}/fault-hits` (Trefferlogik `app/werk/faults.py`, dieselbe wie `search_faults`; andere Maschinen als
  „Erfahrung“), Text, Bauteile, Signalweg, Im Plan, Im Schrank, Belege; Bloecke ohne Inhalt entfallen, Inhalte laden erst
  bei Sichtbarkeit. `meta.part_kinds`, `signal_start` und `plan_spots` kommen aus `api/answer_meta.py` (Spalte je
  Kennzeichen `ingestion/tag_columns.py`); alte Antworten ohne diese Felder bekommen keine neuen Bloecke. Endnutzer sehen
  Fehler als Satz (`chat/chatError.tsx`), den Rohtext nur unter „Details“. Unter 1280 px mit offenem Detail wird die Liste
  zur Leiste `IncidentRail`.
- Planleser (Issue #106): `ingestion/plan_wires.py` liest Leiter aus der Vektorebene (pypdfium2-Rohschnittstelle samt
  Matrizen und Form-XObjects), rastet Endpunkte per scipy `cKDTree` ein und bildet Netze mit networkx; eine Kreuzung ohne
  Punkt verbindet nicht, Netzenden benennt der Anschlusstext wie in #102 (an einer Klemme nur der Text, der ihr am
  naechsten steht), am Rand eines Geraetesymbols ohne Anschlussnummern das Kennzeichen daneben, eine Zeile nur aus
  Klemmen einer Leiste ihre Klemmen von links nach rechts (Lernfaelle aus dem Lehrerlauf:
  `.ai/research/2026-10-02-planleser-lernfaelle.md`). Dazu `lage` aus Kanaelen in Spalten und Zeilen,
  auch auf Seiten mit Leitern. Kantenformat `ingestion/plan_edges.py` (`PlanEdge`, Cache
  `data/plan_cache/<sha256>-v<PLAN_READER_VERSION>.json`; bei geaenderten Regeln die Version erhoehen), vorab gerechnet in
  `ingest_document`. Der Signalgraph fuehrt je Kante die Herkunft (`via`: klemmenplan, awl, leitung, lage, modell), reine
  PDF-Quellen sind verfolgbar. `GET /api/signal-path?view=main` (`ingestion/signal_view.py`): Hauptweg in festen Spalten
  feld … verbraucher, Pins an den Kanten, Abzweige je Knoten (`branches`); 404 mit `detail.reason` no_sources|unknown_tag.
  Gate `eval/run_plan_graph.py` im Ingest-Job: Precision >= 0,95 gegen `wires` im Gold und gegen den Graphen aus den
  Tabellen, Recall nur berichtet.
- Planleser per Modell (Issue #108): `PLAN_READER_MODEL` (leer = aus), `PLAN_READER_BASE_URL` (OpenAI-kompatibel, auch
  lokal, etwa Ollama `qwen3.5:4b`), `ingestion/plan_model.py`, `POST/GET /api/sources/{id}/plan-read` (`dry_run` =
  Schaetzung). Lehrer `eval/plan_teacher.py`: nur oeffentliche Plaene (`examples/`, `testdata/qelectrotech/`), Modellaufruf
  nur mit `--yes`, `--from-result` rechnet ohne Aufruf neu; bezahlte Laeufe nur nach Freigabe des Owners.
- Signalweg-Ansicht (Issue #109): `components/signal/SignalView.tsx` mit `compact` im Antwortblock und `auto` (unter
  1024 px `SignalChain` ohne xyflow, sonst `SignalGraph` per `next/dynamic` mit Planseite darunter); Herkunft als
  Linienart; `PageViewer` zoomt und verschiebt mit `react-zoom-pan-pinch`.
- Fehler-Markierung: Fehlerliste „Zeigen“ -> `activeFault` auf der Maschinenseite, `FaultBanner.tsx`, Tags an
  `CabinetEditor.highlightTags`;
  Treffer per `lib/faults.ts` (`faultHits`). Rot nur fuer Fehler, wie im Design festgelegt.
- Tracing (optional, Langfuse): `app/tracing.py` liefert `trace_config`/`vision_trace` (LangChain-Callback)
  fuer Chat und die beiden Vision-Aufrufe (Seitenanalyse, Schaltschrank), `langfuse_client` fuer Skripte;
  Schluesselpruefung nur dort.
  Chat sendet je Modellaufruf ein SSE-Ereignis `usage`; `eval/run_eval.py` taggt `eval:<lauf>`/`q:<id>`,
  rechnet Kosten aus `app/pricing.py`, speichert nach jeder Frage (`--resume`) und schreibt Scores.
  Nicht getrackt: Retrieval und Embeddings (ohne Modellkosten).
- Modelle: drei Provider ueber `app/llm.py` (`make_chat_model`): Anthropic (Standard), OpenAI und Ollama (lokal,
  `ollama:qwen3.5:4b` ueber `OLLAMA_BASE_URL`, kein Schluessel, Kosten 0, Thinking aus); Name mit Praefix
  `openai:`/`anthropic:`/`ollama:` oder erkennbar (`claude-*`, `gpt-*`). Aufwand hinter `@` im Namen
  (`openai:gpt-5.4-mini@none`) wird `reasoning_effort`; GPT-5.5/5.6 rufen Werkzeuge in Chat Completions nur mit
  `@none`, GPT-6 Astra/6.1 Sol leitet langchain-openai mit Werkzeugen selbst ueber die Responses-API.
  `POST /api/chat` nimmt `model` je Anfrage (Evals: `run_eval.py --model`). Anthropic-Aufrufe tragen den
  Cache-Marker (`graph.model_kwargs_for`); Cache-Tokens stehen im `usage`-Ereignis und zaehlen in
  `pricing.cost_usd` (Treffer meist 0,1-fach, Tabelle kennt Ausnahmen, Schreiben 1,25-fach). Embeddings `local|voyage|openai` (`app/embeddings.py`), Wechsel = neu indexieren.
  `EMBEDDING_CACHE_DIR` (nur CI/Eval, leer = aus) legt `CachedEmbeddings` um den Provider: Dokument-Vektoren je
  SHA-256 aus Provider, Modell, Dimension, Passage-Praefix und Text auf Platte, Anfragen immer live. In `eval.yml`
  haelt `actions/cache` sie je Retrieval-Gruppe; ein aelterer Stand kommt nur bei gleichem `embeddings.py`,
  `pyproject.toml` und `MODELLCACHE_VERSION` zurueck.
  Bildbloecke im LangChain-Standardformat (`llm.image_block`).
  Preise beider Provider in `app/pricing.py` (laengster Praefix gewinnt bei datierten IDs). Fehlt der
  Schluessel des Providers, wirft `llm.MissingKeyError` (ein `RuntimeError`); „Bauteile erkennen“ antwortet
  dann 400 mit dem Namen der Variable, andere Vision-Fehler bleiben 502.
- Zugriff: Setting `API_KEY` (leer = offen). Middleware `app/auth.py` prueft `/api/*` ausser `/api/health`;
  Header `X-API-Key` oder `?api_key=` (Bild-URLs). Frontend `NEXT_PUBLIC_API_KEY`, Skripte/MCP `STROMLAUF_API_KEY`.
- Suche `search_knowledge` ist hybrid (`app/retrieval.py`): Vektor + Postgres-Volltext (`chunks.tsv`,
  generierte Spalte, Konfiguration `german`), Fusion per RRF. `keyword_search` bleibt woertlich (ILIKE).
- Kennzeichen-Index: Schluessel immer in der Schreibweise von `tags.normalize_tag` (gross), denn `find_tag`,
  `/api/tags/search`, `/api/facts` und die Hotspot-Suche vergleichen case-sensitiv (`==`, `LIKE`). Die Etage einer
  Mehrstockklemme `-X2:3a` steht als `-X2:3A` im Index, der Kontext behaelt die Schreibweise des Dokuments.
  Wo die Befundkarte den Schluessel mit Dokumenttext vergleicht (`fact_card._mentions`, Abschnitte in
  `api/facts.py`), gilt Gross/Klein nicht. Klemmen wie im Schweizer Elektroschema (`X420 3`, ohne Minus, Leerzeichen
  statt Doppelpunkt, Issue #91) erkennt `tags.detect_spaced_terminals` je Dokument: ab 5 verschiedenen und nur, wenn
  sie den Minus-Stil `-X1:5` ueberwiegen. Dann stehen `-X420` und `-X420:3` im Index (`Piece.spaced_terminals`);
  `normalize_tag("X420 3")` ergibt `-X420:3`, damit die Suche die Schreibweise des Dokuments versteht.
  Adressbereiche einer SPS-Karte wie `E8.0..E9.7` (`tags._PLC_RANGE_RE`, Issue #92) liefern beide Enden als
  `plc_address`, nie die Adressen dazwischen; mit Leerzeichen (`E0.6 .. E1.7`) fand sie schon `_PLC_BIT_RE`.
  Geraeteanschluesse wie `-K1:A1` oder `-K1:13` stehen als `device_pin` im Index (Issue #98). `tags.pin_kind` gibt
  die Art nach IEC 60947-1 Anhang L, nur fuer Schaltgeraete K, Q, S, F, B:
  Spule A1/A2, Funktionsziffer 1-2/5-6 Oeffner, 3-4/7-8 Schliesser, einstellig 1 bis 6 Hauptkontakt (K, Q, F).
  Im Signalweg laufen solche Anschluesse als Knoten `pin`: Klemme -> Spule -> Geraet -> Kontakt -> Klemme
  (`signal_graph._ends`, `MAX_DEPTH` 16); ein gesuchter Anschluss ohne eigenen Knoten startet beim Geraet.
  Nummern, die nur am Schaltzeichen stehen ("A1", "13"), ordnet `pdf_layout.pin_labels` ueber die Wortpositionen dem
  naechsten Kennzeichen zu (Issue #102): bis `PIN_REACH` 40 pt, das zweitnaechste mindestens 1,5-mal so weit weg,
  Klemmleisten ohne Minus (`X1041`) als Anker, nur Schaltgeraete; Kontaktspiegel "13 14 /5.3" unter einer Spule mit
  Verweis. `document_pieces` haengt sie als Block "Anschluesse am Schaltzeichen" an Stromlaufplan-Seiten (nicht an
  Stuecklistenseiten). `make_gold.py` schreibt die am Symbol gezeichneten Anschluesse mit; das Ingest-Gate prueft
  `device_pin` mit 0,90 (gemessen Precision 1,00, Recall 0,94 bis 1,00). Blatt-Stil (`9K1`, QElectroTech) noch nicht.
- PostgreSQL + pgvector im Docker-Container auf Port **5433**.
- LangGraph-Checkpointer: SQLite in `backend/data/checkpoints.sqlite`.
- Erster Upload lädt `BAAI/bge-m3` (ca. 2 GB) und Docling-Modelle von Hugging Face.
- **Kosten:** Die optionale Vision-Analyse schickt jede Schaltplanseite an Claude
  (API-Tokens pro Seite). Braucht `ANTHROPIC_API_KEY` in `.env`. Ebenso kostet
  „Bauteile erkennen“ (Schaltschrank) pro Aufruf.
- Design: „iOS clean“ (Figma `wtxajO1YC5HvtQG7CI44BC`, Seite „Vorlagen“; freigegeben 2026-10-01). Tokens in
  `frontend/src/app/globals.css` mit den Figma-Namen (`--color-*`, `--space-*`, `--radius-*`, Textstile `text-body`,
  `text-footnote` …), shadcn- und App-Namen zeigen darauf; Schriften Inter und JetBrains Mono. Wo ein Figma-Wert als
  Text unter 4,5:1 liegt, gilt die `-strong`-Variante. Blau = Auswahl/Aktion, Orange = „hier schauen“, Rot nur für Fehler
  und Not-Halt. Eigene Textstile in `cn()` stehen in `src/lib/utils.ts`. UI-Bausteine: shadcn/ui unter `src/components/ui/`.
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
ueber die ganze Historie (gitleaks selbst mit fester Version und Pruefsumme; gitleaks-action prueft bei PR und Push
nur neue Commits; Ausnahmen nur fuer feste Testwerte in `.gitleaks.toml`, Muster `…-test-secret-0123456789…`, und
einzelne begruendete Fehlalarme per Fingerprint in `.gitleaksignore`);
`eval.yml` faehrt je PR kostenlos das Ingest-Gate (eigener Job ohne DB) und das Retrieval-Gate in drei parallelen
Gruppen (Matrix FB-01, UR-01, PM1-AR; das Einlesen mit bge-m3 auf der CPU kostet die meiste Zeit) und woechentlich den
bezahlten Agentenlauf. `backend/tests/test_ci_laufzeit.py` haelt CPU-Torch, die Docker-Layer-Reihenfolge und die
Verteilung der Quellen fest. Vor jedem Push `scripts/check.py`; `--install-hook` legt dafuer einen pre-push-Hook an.

Ordner hieß bis 2026-09-25 `Stromlauf ai`. Die `.venv` im Backend stammt vom alten Pfad
und muss neu erstellt werden.

GitHub-Remote: `siinanXD/stromlauf-ai` (oeffentlich, angelegt 2026-09-25). Beispielanlage: `examples/foerderband/`, Laden mit `python scripts/load_example.py`.
MCP-Server: `backend/stromlauf_mcp/` (nur httpx + mcp 2.x, importiert nichts aus `app`), Start
`backend/.venv/Scripts/python scripts/mcp_server.py`; Werkzeuge nur lesend, Tests mit httpx.MockTransport.
Testdokumentation UR-01/PM1-AR: Generator `scripts/testdoku/` (model, render_pdf, render_rest, machines/*),
Ausgabe `examples/umroller/`, `examples/aufrollung/`; `scripts/load_testwerk.py --docs` laedt und verknuepft.
Testwerk Tissue (4 Hallen, 30 Maschinen): `examples/testwerk/testwerk.json`, Laden mit `python scripts/load_testwerk.py [--refresh]`.
