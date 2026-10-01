# Störfall-Arbeitsfläche: Umsetzungsplan

> **Für ausführende Agenten:** Die Spuren A, B, C1, C2 und D laufen parallel, jede in einer eigenen Arbeitskopie auf
> einem eigenen Branch von `master`. Gemeinsame Typen liegen schon im Basis-Commit. Wer eine Schnittstelle einer anderen
> Spur braucht, hält sich an den Abschnitt „Verträge“ und erfindet keine eigene.

**Ziel:** Störfälle je Maschine mit Antwortblöcken, einem Signalweg als Hauptweg in festen Spalten und einem
Planleser, der die Leitungen aus Stromlaufplan-PDFs liest.

**Architektur:**
- Das Backend bekommt zwei Bausteine: einen Planleser für Kanten aus dem PDF, mit Herkunft und Cache, und eine
  Hauptweg-Sicht auf den Signalgraphen.
- Störfälle sind Konversationen mit den neuen Feldern `outcome` und `finding`.
- Das Frontend baut die Maschinenseite um, mit Störfällen, Chat und Detail, und zeigt Antworten als Blöcke. Die
  Signalweg-Ansicht gibt es als Kette und als Grafik.

**Tech-Stack:** FastAPI, SQLAlchemy, pypdfium2-Rohschnittstelle, networkx, scipy, Next.js 16.3.5, React 19.2,
`@xyflow/react` 12, `react-zoom-pan-pinch`, `use-stick-to-bottom`.

**Spec:** `docs/superpowers/specs/2026-10-01-stoerfall-arbeitsflaeche-design.md`.
**Recherche:** `.ai/research/2026-10-01-planleser-und-anzeige.md`.

## Globale Vorgaben

- **Reihenfolge laut Owner (2026-10-01):** Erst wird jede Spur vollständig umgesetzt, dann getestet. Jede Spur
  schreibt ihre Tests aus „Tests am Ende“, bevor sie meldet. Bestehende Tests und `ruff` bleiben grün.
- **Kein bezahlter Modellaufruf und kein Download** außer `npm ci` und `npm install` der zwei genehmigten Pakete.
- **Firmendokumente:** das private Elektroschema unter `testdata/` und alles unter `testdata/private/` bleiben
  lokal. Daraus kommen keine Namen, Räume, Adressen oder Blatttitel in Code, Tests, Commits oder PR-Texte, nur Zahlen.
- **Keine Secrets lesen:** Inhalte von `.env`, `*.pem`, `*.key`, `credentials*`, `secrets*` sind tabu.
- **Datenbank:**
  - Tests teilen sich die lokale Entwicklungsdatenbank auf Port 5433.
  - Spur B wendet die neue Migration auf diese Datenbank erst an, wenn der Lead die Freigabe weitergibt.
  - Bis dahin laufen in Spur B nur Tests ohne Datenbank.
- **Imports in Arbeitskopien:**
  - pytest wird aus `<arbeitskopie>/backend` gestartet.
  - Neue Module prüfst du mit `python -c "import app.<modul> as m; print(m.__file__)"`. Die geteilte venv kann sonst
    eine fremde Arbeitskopie laden.
- **Commits:** deutsch, Conventional Commits, eine Änderung je Commit, Abschluss
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Kein Push und kein PR, das macht der Lead.
- **Sprache:** Nutzertexte deutsch und ohne Entwicklertexte wie Port, Skriptname oder API-Pfad. Rot nur für Fehler
  und Not-Halt.
- **Neue Abhängigkeiten:**
  - Genehmigt sind nur `networkx` und `scipy` für das Backend, in `pyproject.toml` mit einer Version, die
    Python 3.11 unterstützt.
  - Für das Frontend sind `react-zoom-pan-pinch` und `use-stick-to-bottom` genehmigt.

## Review-Fokus

1. **Seite ohne Vektorlinien, etwa ein Scan:** Der Planleser liefert keine Leitungs-Kanten und fällt still auf `lage`
   zurück, ohne Fehler. Test in A1.
2. **Gedrehte Seite oder Form-XObject mit verschachtelter Matrix:** Die Endpunkte liegen trotzdem an der richtigen
   Stelle. Test in A1.
3. **Störfall ohne Treffer und Maschine ohne Fehlerliste:** `fault-hits` liefert drei leere Listen, das Frontend zeigt
   keinen Block. Tests in B2 und C2.
4. **Altes Gespräch ohne die neuen `meta`-Felder:** Das Frontend zeigt die Antwort ohne die neuen Blöcke und stürzt
   nicht ab. Test in C2.
5. **Kennzeichen kommt im Graphen nicht vor:** Signalweg-Block und Ansicht zeigen den leeren Zustand mit Grund, nicht
   den 404-Text. Test in C1.

## Verträge

### Planleser-Kanten (Basis-Commit: `backend/app/ingestion/plan_edges.py`)

```python
@dataclass(frozen=True)
class PlanEdge:
    source: str      # Knoten-ID wie im Signalgraphen: "-S1", "-K1:A1", "-X1:3", "E0.3"
    target: str
    page: int        # PDF-Seite, 1-basiert
    via: str         # "leitung" | "lage" | "modell"
    directed: bool = True  # False: Richtung unklar -> nur Abzweig, nie Hauptweg

def file_key(path: Path) -> str                         # sha256 der Dateibytes
def read_edges(path: Path) -> list[PlanEdge] | None     # data_dir/plan_cache/<key>-v<VERSION>.json; None = ungerechnet
def write_edges(path: Path, edges: list[PlanEdge]) -> None
def read_model_edges(path: Path) -> list[PlanEdge]      # data_dir/plan_cache/model/<key>-*.json, neueste Datei, sonst []
def write_model_edges(path: Path, prompt_version: str, edges: list[PlanEdge], meta: dict) -> None
def read_model_meta(path: Path) -> dict | None          # meta: model, pages, dropped, cost_usd
PLAN_READER_VERSION = 1
```

### Signalweg-API (Spur A), `GET /api/signal-path?tag&source_id[&view=main]`

- **Ohne `view`:** die bisherige Antwort. Jede Kante hat zusätzlich `via: string[]` und `directed: bool`.
- **Mit `view=main`:**

```json
{
  "start": "-K1",
  "view": "main",
  "columns": ["feld", "klemme_vor", "sps_eingang", "programm", "sps_ausgang", "klemme_nach", "schaltgeraet", "verbraucher"],
  "nodes": [{"id": "-K1", "kind": "device", "label": "", "ref": "/3.5", "detail": "",
             "main": true, "column": "schaltgeraet", "order": 5, "branches": 2, "parent": null}],
  "edges": [{"source": "-X3:9", "target": "-K1", "via": ["klemmenplan"], "directed": true,
             "pins": {"from": null, "to": "A1"}}],
  "schematic": {"document_id": "…", "filename": "…"}
}
```

- `columns` enthält nur die belegten Spalten, in dieser Reihenfolge.
- Auf dem Hauptweg gilt `main: true`, und `order` ist die Position auf dem Hauptweg ab 0.
- Nachbarn abseits des Hauptwegs, eine Stufe tief, haben `main: false`, `parent` ist der Knoten auf dem Hauptweg und
  `column` ist `null`.
- Knoten der Art `pin` gehen in ihrem Gerät auf. Ihre Nummer steht in `pins.from` oder `pins.to` der Kante.
- 404 mit `detail.reason` aus `no_sources` oder `unknown_tag`, dazu ein deutscher Text in `detail.message`.

### Störfälle (Spur B)

- `ConversationOut` bekommt `outcome: "open" | "resolved"` und `finding: string`.
- `PATCH /api/conversations/{id}` mit dem Body `{outcome?, finding?}`. `finding` hat höchstens 2000 Zeichen. Antwort ist
  `ConversationOut`, 404 für eine unbekannte ID, 422 für einen ungültigen `outcome`.
- `GET /api/conversations/{id}/messages?limit=&before=`:
  - Jede `MessageOut` hat `index: int`.
  - Ohne Parameter kommen alle Nachrichten, wie bisher.
  - `before` ist exklusiv, das Ergebnis sind höchstens `limit` Nachrichten vor `before` in zeitlicher Reihenfolge.
- `GET /api/machines/{machine_id}/fault-hits?q=` liefert:

```json
{"faults": [Fault], "experience": [{"machine_id": "…", "machine_name": "…", "fault": Fault}],
 "incidents": [{"conversation_id": "…", "title": "…", "finding": "…", "updated_at": "…"}]}
```

  Jede Liste hat höchstens 5 Einträge. Die Trefferlogik ist `app/werk/faults.py::fault_matches(fault: dict, query: str)
  -> bool`, verschoben aus `agent/tools.py`, das sie dann importiert.
- **Neue Felder in `meta`**, im Stream und in `MessageOut.meta`:
  - `part_kinds: {tag: str}`
  - `signal_start: str | null`
  - `plan_spots: [{tag, document_id, filename, page, sheet: int | null, title: str, column: int | null}]`, höchstens 4

### Modell-Option (Spur D)

- `POST /api/sources/{source_id}/plan-read?dry_run=true|false` liefert
  `{model, pages, estimate_usd, edges: int|null, dropped: int|null, cost_usd: float|null}`.
  Ist `PLAN_READER_MODEL` leer, antwortet der Endpunkt mit 409 und `detail.message` = „Kein Modell eingerichtet“.
- `GET /api/sources/{source_id}/plan-read` liefert `{configured: bool, model: str, cached: bool, edges: int, dropped: int,
  cost_usd: float|null}`.

### Frontend (Basis-Commit)

- `frontend/src/lib/detail.ts` legt fest, welches Detail offen ist:

```ts
export type DetailRef =
  | { kind: "signal"; tag: string }
  | { kind: "plan"; target: PageTarget }
  | { kind: "part"; tag: string }
  | { kind: "cabinet"; cabinetId: string; hotspotId?: string }
  | { kind: "fault"; faultId: string };
export function detailToParam(d: DetailRef): string;
export function detailFromParam(s: string | null): DetailRef | null;
```

- `frontend/src/lib/api.ts` enthält die Typen und Abrufe für alle Verträge oben:
  `signalPathMain`, `patchConversation`, `getMessagesPage`, `faultHits`, `planReadStatus`, `planRead`, dazu die Felder
  in `AnswerMeta` und `Conversation`.
- `frontend/src/components/signal/SignalView.tsx`:

```ts
export function SignalView(props: {
  sourceId: string; tag: string;
  variant: "compact" | "auto";
  onOpenDetail: (d: DetailRef) => void;
}): JSX.Element
```

  Im Basis-Commit umhüllt die Komponente nur `SignalPath`. Spur C1 ersetzt den Inhalt, die Props bleiben gleich.

---

## Spur A: Planleser und Signalweg-API (Backend)

**Arbeitskopie:** `.claude/worktrees/stoerfall-a`, Branch `feat/planleser-leitungen`

### A1: Leitungsleser `app/ingestion/plan_wires.py`

**Funktionen**
- `page_segments(path: Path, page: int) -> list[Segment]`
  - `Segment(x1, y1, x2, y2, width, dashed)` in pt, Ursprung oben links.
  - Jede Matrix wird angewendet, Form-XObjects rekursiv durchlaufen, Bézierkurven in 4 Sehnen zerlegt.
  - Rahmen, Spaltenkopf und Schriftfeld werden gefiltert, über dieselben Grenzen wie `pdf_layout.page_columns` und
    `TITLE_BAND`.
  - Geschlossene Pfade und Rechtecke gelten als Symbole.
  - Hat eine Seite mindestens zwei Strichstärken mit je mindestens 20 Segmenten, gilt die häufigste lange Stärke als
    Leiter.
- `page_nets(segments) -> list[Net]`
  - `SNAP = 1.0` pt, Einrasten mit `scipy.spatial.cKDTree`.
  - Ein T-Abzweig liegt vor, wenn ein Endpunkt höchstens `SNAP` von einem Segment-Inneren entfernt ist.
  - Eine Kreuzung ohne Punkt verbindet nicht. Ein Punkt ist ein gefüllter Pfad mit einem Durchmesser von höchstens 4 pt.
  - Komponenten über `networkx`.
- `page_wire_edges(path: Path, page: int) -> list[PlanEdge]`
  - Jedes Netzende sucht den nächsten Anschluss-Text aus den Wortpositionen von `pdf_layout._spots`: Pin wie in #102,
    Klemme (`-X1:3`, `X420 3`) oder SPS-Adresse.
  - Es gilt `PIN_REACH` und die Regel, dass das zweitnächste Ziel 1,5-mal so weit weg sein muss.
  - Kanten verbinden die benannten Enden eines Netzes.
  - Richtung: Ein Netz mit E-Adresse läuft zur Adresse, eins mit A-Adresse von ihr weg. Für Spule und Kontakt gelten
    die Regeln aus `signal_graph._add_terminal_rows`. Alles andere ist `directed=False`.
- `plan_edges(path: Path) -> list[PlanEdge]`
  - Erst wird der Cache über `read_edges` gelesen, sonst werden alle Seiten berechnet und mit `write_edges`
    gespeichert.
  - Seiten ohne Leiter-Segmente nutzen den Ersatz `lage`: Kanäle in Spalten aus #90 und Kanäle in Zeilen, also
    Feldgerät, Klemme und Adresse auf gleicher Höhe ±3 pt. Das gilt nur, wenn auf der Seite mindestens 3 Adressen in
    dieser Anordnung stehen.

**Tests am Ende** in `backend/tests/test_plan_wires.py`, mit synthetischen Seiten über reportlab:
- `test_t_abzweig_verbindet`
- `test_kreuzung_ohne_punkt_verbindet_nicht`
- `test_kreuzung_mit_punkt_verbindet`
- `test_form_xobject_mit_matrix`
- `test_gedrehte_seite`
- `test_unbenanntes_ende_ergibt_keine_kante`
- `test_eingang_richtung_zur_adresse`
- `test_scan_ohne_linien_faellt_auf_lage_zurueck`
- `test_kanaele_in_zeilen`
- `test_cache_wird_genutzt`, mit Patch auf `page_segments` und gezähltem Aufruf

### A2: Gold und Gate

- `scripts/example_docs/make_gold.py`: Die protokollierende Zeichenfläche schreibt je Seite `wires` mit, als Liste von
  `[source, target]` mit Knoten-IDs.
  - Quelle sind die Aufrufe von `wire()` in `scripts/testdoku/render_pdf.py` und die Leitungen in
    `scripts/example_docs/make_pdf.py`.
  - Ein Leitungsende wird der Anschlussposition des Symbols zugeordnet, die beim Zeichnen bekannt ist.
- Danach werden die Golds mit `--write` neu erzeugt. `test_run_ingest.py` prüft weiter die Gleichheit.
- `eval/run_plan_graph.py --gold … --doc …` misst zwei Ebenen:
  - `plan_edges` gegen `wires`, als Precision und Recall über ungerichtete Paare.
  - Den Graphen aus dem Plan gegen den Graphen aus den Tabellen derselben Quelle, Precision der Kanten zwischen
    Feldgerät, Klemme, Adresse und Gerät.
  - `--min-precision 0.95` lässt den Lauf mit Exit 1 enden, wenn die Precision darunter liegt.
- In `eval.yml` läuft das im Ingest-Job für FB-01, UR-01 und PM1-AR. Recall wird nur berichtet.

**Tests am Ende:** `test_run_plan_graph.py` mit einem Mini-Gold, das die Zahlen exakt prüft.

### A3: Graph mit Herkunft

- In `signal_graph.Graph` werden die Kanten zu `dict[tuple[str, str], set[str]]`.
  - `edge(source, target, via)` mit dem Standard `"klemmenplan"`. Die AWL-Kanten bekommen `"awl"`.
  - Neu ist `undirected: set[tuple[str, str]]` mit sortierten Paaren.
- `signal_path()` gibt je Kante `via` (sortiert) und `directed` aus. Ungerichtete Kanten beeinflussen die Ebenen nicht.
- `api/signal.py::graph_for_source` nimmt Stromlaufplan-PDFs dazu, über `plan_edges` und `read_model_edges`.
  - Der LRU-Schlüssel enthält ihre mtime.
  - Ohne Tabellen, aber mit Plan-Kanten gibt es keinen 404 mehr.
- `ingest_document` ruft nach einem Stromlaufplan `plan_edges(path)` auf. Ein Fehler wird geloggt und bricht nichts ab.

**Tests am Ende:**
- `test_signal_graph.py`: `via` für Klemmenplan und AWL; eine Plan-Kante macht eine reine PDF-Quelle verfolgbar.
- `test_signal_api.py`: 404-Grund `no_sources`.

### A4: Hauptweg `app/ingestion/signal_view.py`

- `main_view(graph: Graph, tag: str) -> dict | None` nach dem Vertrag oben.
- **Hauptweg:**
  - Rückwärts der kürzeste Weg über gerichtete Kanten bis zu einem Knoten ohne Vorgänger, vorwärts bis zu einem ohne
    Nachfolger.
  - Bei Gleichstand gewinnt die lexikografisch kleinste Folge der Knoten-IDs.
  - Es gelten `MAX_DEPTH` und `HUB_DEGREE` wie bei `signal_path`.
- **Spalten:**
  - Eine Adresse mit E ist `sps_eingang`, mit A `sps_ausgang`. Netzwerke und übrige Adressen oder Variablen sind
    `programm`.
  - Eine Klemme vor dem ersten SPS-Knoten des Hauptwegs ist `klemme_vor`, sonst `klemme_nach`. Ohne SPS-Knoten
    entscheidet die Lage vor oder nach dem Start.
  - Ein Gerät vor dem ersten SPS-Knoten ist `feld`, ohne SPS gilt dasselbe vor dem Start.
  - Ein Gerät danach ist `schaltgeraet`, wenn es auf dem Hauptweg einen Nachfolger hat, sonst `verbraucher`.
- `branches` zählt die Nachbarn außerhalb des Hauptwegs, auch ungerichtete.
- `api/signal.py`: `view=main` ruft `main_view` auf.

**Tests am Ende** in `test_signal_view.py`, gegen FB-01:
- -K1 ergibt die Spalten in Vertragsreihenfolge.
- Die Pins A1 und 2 stehen an Kanten, kein Knoten hat die Art `pin`.
- Der Gleichstand wird reproduzierbar aufgelöst.
- `branches` zählt richtig.

---

## Spur B: Störfall-Backend

**Arbeitskopie:** `.claude/worktrees/stoerfall-b`, Branch `feat/stoerfall-backend`

### B1: Störfall-Felder und Nachrichten in Stücken

- `models.Conversation`: `outcome = String(16), default "open"`, `finding = Text, default ""`.
- `migrations.py`: `ADD COLUMN IF NOT EXISTS` für beide, mit dem Standard auch für bestehende Zeilen.
- `schemas.ConversationOut` bekommt die beiden Felder. Neu ist `ConversationPatch` mit `outcome: Literal["open",
  "resolved"] | None` und `finding: str | None = Field(max_length=2000)`.
- `api/chat.py`: `PATCH /conversations/{id}`. `GET …/messages` bekommt `limit: int | None` (1 bis 200) und
  `before: int | None`, dazu `MessageOut.index`.

**Tests am Ende:** `PATCH`-Rundlauf, 422 und 404, Seiten von Nachrichten mit `before` und `limit` sowie ohne beide.
Die Tests laufen mit Datenbank erst nach der Freigabe der Migration.

### B2: `fault-hits`

- `app/werk/faults.py`: `fault_matches` aus `agent/tools.py` dorthin verschieben. Das Werkzeug importiert sie.
- `GET /api/machines/{machine_id}/fault-hits?q=` in `api/plant.py` nach dem Vertrag.
  - `incidents` sind erledigte Störfälle der Quelle der Maschine mit nicht leerem `finding`. Geprüft wird
    `fault_matches({"symptom": title, "cause": finding}, q)`.

**Tests am Ende:**
- Unit-Tests für `fault_matches` ohne Datenbank.
- API-Tests mit Datenbank: drei Listen, leere Maschine und das Höchstmaß von 5.

### B3: neue `meta`-Felder

- `app/ingestion/tag_columns.py`: `tag_columns(path: Path, page: int) -> dict[str, int]`, also Gerätekennzeichen und
  ihre Spalte über `pdf_layout.page_columns` und die Wortpositionen. Gecacht je (Pfad, mtime, Seite).
- `api/answer_meta.py::build_meta` bekommt drei Felder:
  - `part_kinds`: `letter_codes.kind_of` mit der Lesart der Quelle, so wie es `machine_map` bestimmt.
  - `signal_start`: das erste referenzierte Kennzeichen, für das `signal_path(graph_for_source(...)[0], tag)` nicht
    `None` ist.
  - `plan_spots`: je Kennzeichen die erste `TagOccurrence` in einem PDF vom Typ `schematic`, mit Blatt aus
    `pdf_layout.sheet_page`, Titel aus `section` und Spalte aus `tag_columns`. Höchstens 4.
- Die Felder gelten auch in `MessageOut.meta`.

**Tests am Ende:**
- `test_answer_meta.py`: die drei Felder für eine FB-01-Antwort, die -K1 nennt; leere Werte, wenn kein Kennzeichen
  genannt wird.
- `tag_columns` auf einer synthetischen Seite.

---

## Spur C1: Signalweg-Ansicht und Planseite (Frontend)

**Arbeitskopie:** `.claude/worktrees/stoerfall-c1`, Branch `feat/signalweg-ansicht`

- **`components/signal/signalColumns.ts`**, rein:
  - `COLUMN_LABELS` mit Feld, Klemme, SPS-Eingang, Programm, SPS-Ausgang, Klemme, Schaltgerät, Verbraucher.
  - `orderInColumns(data: SignalMainData) -> Map<string, {x: number, y: number}>`: Die Spalte bestimmt x, das
    Baryzentrum der Nachbarn bestimmt y.
- **`SignalChain.tsx`:** eine Liste ohne xyflow, je Hauptwegknoten eine Zeile mit Kennzeichen, Klartext, Blatt und
  Herkunft. Der Abzweig-Zähler klappt die Abzweige inline auf.
- **`SignalGraph.tsx`:** xyflow mit festen Spalten.
  - Spaltenköpfe, Pins als Kantenlabel.
  - Drei Herkunftsstufen, unterscheidbar über Strichart: Tabelle oder Programm durchgezogen, `leitung` lang
    gestrichelt, `lage` und `modell` gepunktet.
  - Legende und ein Schalter „nur Belegtes“.
  - Ein Knoten-Klick ruft `onOpenDetail({kind: "part"})`. „Von hier verfolgen“ macht den Knoten zur neuen Mitte.
  - Netzwerk-Knoten zeigen den AWL-Code wie heute.
- **`SignalView.tsx`:**
  - `compact` zeigt höchstens 5 Hauptwegknoten als Kette und den Link „ganz zeigen“.
  - `auto` zeigt unter 1024 px die Kette. Ab 1024 px lädt es `SignalGraph` per `next/dynamic` mit `ssr: false` und
    zeigt darunter die Planseite des gewählten Knotens.
  - Der leere Zustand nennt den Grund aus `detail.reason`. Dazu kommt „Planseite öffnen“ und, wenn `planReadStatus`
    `configured` meldet, „Mit Modell lesen, ca. X USD“ nach `dry_run`, mit Bestätigung.
- **`PageViewer.tsx`:** Zoom und Verschieben über `react-zoom-pan-pinch`. Die Spaltenbox liegt im Zoom-Inhalt, die
  Props bleiben gleich.
- **`SignalPath.tsx`:** Der Tab „Signalweg“ im Bereich Aufbau nutzt `SignalView` mit `auto`.

**Tests am Ende (Vitest):**
- `signalColumns.test.ts`: Reihenfolge, leere Spalten fallen weg, Baryzentrum.
- `SignalChain.test.tsx`: Abzweige aufklappen, Herkunft als Text.
- `SignalView.test.tsx`: leerer Zustand mit `unknown_tag`; `compact` zeigt höchstens 5 Knoten.

## Spur C2: Maschinenseite, Störfälle und Antwortblöcke (Frontend)

**Arbeitskopie:** `.claude/worktrees/stoerfall-c2`, Branch `feat/stoerfall-frontend`

- **`app/werk/maschine/[id]/page.tsx`:**
  - Bereiche `?bereich=stoerfaelle` als Standard und `?bereich=aufbau&tab=…`.
  - Ein alter Link mit `?tab=…` ohne `bereich` öffnet Aufbau mit diesem Tab.
  - Ab 1024 px drei Spalten. Darunter eine Ebene aus `?fall=` und `?detail=`, über `detailToParam` und
    `detailFromParam`. Die Zurück-Geste des Browsers wechselt die Ebene.
  - Beim Öffnen werden nur Maschine und Störfälle geladen. Aufbau-Tabs laden beim Öffnen.
- **`components/incident/IncidentList.tsx`:**
  - Eingabefeld „Meldung oder Frage“. Enter legt sofort einen Eintrag in der Liste an, mit vorläufiger ID, die nach
    dem Ereignis `conversation` ersetzt wird.
  - Filter offen und erledigt, sortiert nach `updated_at`.
- **`components/incident/IncidentHeader.tsx`:** „Erledigt“ mit optionalem Befund über `patchConversation`, dazu
  „Wieder öffnen“.
- **`components/incident/DetailPane.tsx`** zeigt je nach `DetailRef`:
  - `SignalView auto`
  - `PageViewer docked`
  - `PartSheet`-Inhalt mit Befundkarte
  - Schrankfoto
  - Fehlereintrag
- **Chat:**
  - `use-stick-to-bottom` hält die Ansicht beim Streamen unten.
  - Markdown wird je Absatz mit `React.memo` und dem Absatztext als Schlüssel zwischengespeichert.
  - Die letzten 30 Nachrichten über `getMessagesPage`, ältere beim Hochscrollen.
  - Beim Senden startet `faultHits` parallel.
- **`components/answer/blocks/`:** `FaultHitsBlock`, `PartsBlock`, `SignalBlock` (`SignalView compact`), `PlanBlock`,
  `CabinetBlock`, `CitationsBlock`.
  - Die Reihenfolge folgt der Spec, Blöcke ohne Inhalt fallen weg.
  - Inhalte laden erst bei Sichtbarkeit, über `useInView` mit `IntersectionObserver`.
- **`AnswerView`:**
  - Bekannte Kennzeichen aus `referenced_tags` werden im Text zu Knöpfen, die `onOpenDetail({kind: "part"})` aufrufen.
  - Die Befundkarte fällt im Chat weg.
  - Fehlen die neuen `meta`-Felder, gibt es keine neuen Blöcke.
- **`xyflow` erst bei Bedarf:** `LayoutCanvas`, `SiteCanvas` und `HallCanvas` laden per `next/dynamic`.
- **Lighthouse:** `frontend/scripts/lighthouse-a11y.mjs` misst mit `--performance` auch die Kategorie Performance und
  berichtet sie.

**Tests am Ende (Vitest):**
- `detail.test.ts`: Rundlauf aller fünf Arten.
- `blocks.test.tsx`: Reihenfolge und Wegfall; alte `meta` ohne neue Felder.
- `IncidentList.test.tsx`: Enter legt sofort an.
- `page`-Routing für `?tab=` ohne `bereich`.

## Spur D: Modell-Option und Lehrer

**Arbeitskopie:** `.claude/worktrees/stoerfall-d`, Branch `feat/planleser-modell`

- **`config.py`:** `plan_reader_model: str = ""` und `plan_reader_base_url: str = ""`. Dazu `.env.example` im selben
  Commit, ohne Werte.
- **`llm.make_chat_model(name, base_url: str | None = None)`:** Bei `openai:` und gesetzter `base_url` wird die URL
  durchgereicht. Der Schlüssel darf dann leer sein, etwa für Ollama.
- **`app/ingestion/plan_model.py`:**
  - `PROMPT_VERSION = "1"`.
  - `page_payload(path, page) -> dict` mit PNG-Bytes, Wortliste mit Koordinaten aus `pdf_layout._spots` und den
    Kennzeichen der Seite.
  - `read_page_with_model(model, payload) -> list[PlanEdge]` mit JSON-Schema-Ausgabe.
  - `validate(edges, page_tags) -> (kept, dropped)` behält nur Enden aus `page_tags`.
  - `estimate_usd(model, pages) -> float` nimmt 3000 Eingabe- und 2000 Ausgabe-Token je Seite und rechnet über
    `pricing.cost_usd`.
- **`api/plan_read.py`:** die zwei Endpunkte nach dem Vertrag. Das Ergebnis geht über `write_model_edges`.
- **`eval/plan_teacher.py --model … --doc … --gold …`:**
  - Ruft nur nach `--yes` ein Modell auf.
  - Schreibt `eval/results/plan_teacher_<datum>.json` mit Kanten, Kosten und einem Vergleich gegen `wires`.
  - Der Vergleich nennt drei Gruppen: „Modell richtig, Regeln fehlen“, „Regeln falsch“ und „Modell falsch“.
  - Ohne `--yes` gibt es nur die Schätzung.
  - Firmendokumente lehnt das Skript ab: Pfade unter `testdata/private/` und das private Elektroschema unter
    `testdata/`.

**Tests am Ende:**
- `test_plan_model.py`: `validate`, `estimate_usd` und `page_payload` ohne Modell.
- Ein Modell-Fake über die Schnittstelle von `make_chat_model`.
- `plan_teacher` verweigert Firmendokumente und ruft ohne `--yes` nichts auf.

---

## Danach: Durchspielen und gezielt testen (Lead)

1. Die Branches A, B, D, C1 und C2 werden lokal in einen Integrationsbranch gemergt. Er wird nie gepusht.
2. Durchspielen mit Freigabe für Container und Migration:
   - FB-01: Meldung „Störung Motorschutz Förderband“ → Fehlerliste, Blöcke, Signalweg, Planseite.
   - Reine PDF-Quelle: Signalweg aus Leitungen.
   - Handy mit 390 px und PC mit 1440 px.
   - Lighthouse.
3. Wo es hakt, kommt der Fix mit Test in den Branch der jeweiligen Spur.
4. Mit Freigabe der Kosten: Lehrerlauf mit OpenAI `gpt-5-mini` auf FB-01 und UR-01. Daraus werden Regeln mit Tests in
   Spur A.
5. Je Spur ein PR mit Issue und Nachweisen. Gemergt wird in der Reihenfolge A, B, D, C1, C2.
