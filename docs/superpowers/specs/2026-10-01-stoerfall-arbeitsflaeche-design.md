# Störfall-Arbeitsfläche: Daten aus der Doku strukturiert zeigen

Stand: 2026-10-01 · Konzept mit dem Owner abgestimmt, in 5 Abschnitten und einer Ergänzung nach der Recherche
Recherche: `.ai/research/2026-10-01-planleser-und-anzeige.md` · Ist-Zustand des Frontends: Figma-Session
„Enterprise-Frontend in Figma“ (60 Seiten, 41 Mängel, Figma-Plan in 6 Phasen)

## Ziel

Ein Instandhalter steht an einer gestörten Maschine. Er tippt eine Meldung vom Bedienpanel oder ein Symptom ein und
kommt in wenigen Schritten zur Ursache, zum Signalweg, zur Stelle im Plan und zum Bauteil im Schrank. Das funktioniert
auch dann, wenn es für die Maschine nur PDFs gibt.

**Erfolg**
- Gegen FB-01 liefert „Störung Motorschutz Förderband“ zuerst den Treffer aus der Fehlerliste, in unter 1 s. Danach
  folgen Antwort, Bauteile, Signalweg, Planseite und Belege als Blöcke.
- Für eine Maschine, deren Dokumentation nur aus einem Stromlaufplan-PDF besteht, zeigt der Signalweg den Weg
  Feldgerät → Klemme → SPS-Eingang mit der Herkunft „Leitung im Plan“.
- Das Handy zeigt den Signalweg als Kette, der PC als Grafik. Beide zeigen dieselben Daten.

## Entscheidungen des Owners

| Frage | Entscheidung |
| --- | --- |
| Für welche Situation zuerst? | Störung jetzt, an der Maschine |
| Womit fängt der Techniker an? | Meldung vom Bedienpanel oder Symptom; Kennzeichen sind das Ergebnis, nicht der Einstieg |
| Welches Gerät? | gemischt: Handy zum schnellen Nachschauen, PC zum genauen Untersuchen |
| Signalweg für reine PDF-Maschinen? | ja, aus dem Plan; ein bezahltes Modell bleibt zuschaltbar |
| Grundaufbau | die Antwort ist die Arbeitsfläche, jeder Chat ist ein Störfall |
| Rolle bezahlter Modelle | Lehrer in der Entwicklung: aus ihren Ergebnissen werden Regeln; das Produkt läuft mit Regeln und optional lokalem Modell |
| Kosten | vor jedem bezahlten Lauf fragen, mit Anbieter, Modell, Seitenzahl und geschätzten USD |

## Nicht im Umfang

- Laststromkreise wie -Q1 → -K1 → -M1 innerhalb einer Spalte. Zwei Geräte untereinander sind nicht immer verbunden.
- Lokaler Chat ohne Cloud. Das ist ein eigenes Folgeprojekt, siehe „Reihenfolge“.
- Import von EPLAN-Verbindungslisten und AutomationML. Das ist ein späterer Schritt, siehe Recherche.
- Visuelle Gestaltung: Farben, Typografie und Maße entstehen in Figma und werden dort vom Owner freigegeben.

## 1. Aufbau und Navigation

**Die Maschinenseite `/werk/maschine/[id]` hat zwei Bereiche:**
- **Störfälle** ist der Standard. Jeder Chat dieser Maschine ist ein Störfall.
- **Aufbau** erreicht man über die Kopfzeile. Dort liegen die heutigen Tabs: Modell, Schaltschrank, Draufsicht,
  Dokumente, Fehlerliste, Kennzahlen und Ablauf. Bestehende Links mit `?tab=…` öffnen weiter den passenden Tab, auch
  `?tab=signalweg` aus der Befundkarte.

**Am PC ab 1024 px:** drei Spalten nebeneinander, Störfälle | Chat | Detail. Die Detailspalte ist geschlossen, bis ein
Block angetippt wird.

**Unter 1024 px:** drei Ebenen hintereinander, Störfälle → Chat → Detail. Das Detail füllt den Bildschirm und hat
einen Zurück-Knopf. Die Zurück-Geste des Browsers führt eine Ebene zurück, deshalb steht die Ebene in der URL.

**Einen Störfall anlegen:** Oben in der Liste steht ein Eingabefeld. Mit Enter entsteht der Störfall sofort in der
Liste, noch bevor der Server antwortet. Gleichzeitig starten der Chat und die Abfrage der Fehlerliste. Es gibt keinen
Dialog und keine Pflichtfelder.

**Einen Störfall abschließen:** Der Knopf „Erledigt“ nimmt optional einen Satz zum Befund auf. Erledigte Störfälle
bleiben in der Liste, sortiert nach dem letzten Stand, und sind durchsuchbar.

**Datenmodell**, Migration in `backend/app/migrations.py` mit `ADD COLUMN IF NOT EXISTS`:
- `conversations.outcome` vom Typ `String(16)`, Standard `"open"`, sonst `"resolved"`. Die Werte heißen wie bei
  `DiagnosisSession.outcome`.
- `conversations.finding` vom Typ `Text`, Standard `""`.
- `PATCH /api/conversations/{id}` mit `{outcome, finding}`.
- `GET /api/conversations?source_id=` liefert beide Felder.

Ein Störfall bleibt eine Konversation mit `source_ids == [source_id]`, wie heute beim Chat je Maschine. Eine neue
Tabelle entsteht nicht.

**Globaler Chat `/`:** Er bleibt für Fragen über mehrere Maschinen. In der Navigation tritt er hinter die
Maschinenübersicht zurück.

## 2. Antwortblöcke

Eine Antwort besteht aus Blöcken in fester Reihenfolge. Blöcke ohne Inhalt fallen weg. Nur der Antworttext kommt vom
Modell. Alles andere stammt aus dem Index, also ohne weiteren Modellaufruf.

| Reihenfolge | Block | Daten | Antippen öffnet |
| --- | --- | --- | --- |
| sofort | Fehlerliste | `GET /api/machines/{id}/fault-hits?q=` | Fehlereintrag mit Ursache und Behebung |
| während des Streams | Antworttext | SSE `token` | bekannte Kennzeichen im Text öffnen das Bauteil-Detail |
| nach der Antwort | Bauteile | `meta.referenced_tags` + `meta.part_kinds` | Bauteil-Detail |
| nach der Antwort | Signalweg | `meta.signal_start`, bis zu 5 Schritte des Hauptwegs | Signalweg-Ansicht |
| nach der Antwort | Im Plan | `meta.plan_spots`: Dokument, Seite, Blatt, Blatttitel, Spalte | Planseite mit markierter Spalte |
| nach der Antwort | Im Schrank | `meta.evidence` vom Typ `cabinet` | Schrankfoto mit Rahmen |
| nach der Antwort | Belege | `meta.citation_checks`, `meta.citations_valid`, zugeklappt | Liste der Belege |

**Fehlerliste sofort:** `GET /api/machines/{id}/fault-hits?q=` liefert drei Listen.
- `faults`: Einträge der Fehlerliste dieser Maschine.
- `experience`: Treffer an anderen Maschinen. Sie stehen als „Erfahrung“ da, nicht als Beleg.
- `incidents`: erledigte Störfälle mit Befund, die zur Meldung passen. Verglichen werden Titel und Befund.

Die Trefferlogik ist `fault_matches` aus `agent/tools.py`, herausgelöst als reine Funktion. Werkzeug und Endpunkt nutzen
dieselbe. Ziel ist eine Antwort in unter 1 s.

**Neue Felder im `meta`-Ereignis**, alle deterministisch und in `api/answer_meta.py`:
- `part_kinds`: `{tag: Art}` aus `letter_codes.kind_of` mit der Lesart der Quelle.
- `signal_start`: das erste referenzierte Kennzeichen, das im Signalweg-Graphen der Quelle vorkommt, sonst `null`.
- `plan_spots`: je referenziertem Kennzeichen höchstens eine Fundstelle im Stromlaufplan mit Blatt, Blatttitel und
  Spalte. Höchstens 4.

**Laden bei Bedarf:** Die Antwort liefert nur Verweise. Ein Block lädt seinen Inhalt erst, wenn er ins Bild kommt.

**Gegenüber heute ändert sich:**
- Die Befundkarte erscheint nicht mehr im Chat. Sie gehört ins Bauteil-Detail, denn Meldungen enthalten selten ein
  Kennzeichen.
- Die Belegbilder gehen in den Blöcken „Im Plan“ und „Im Schrank“ auf.
- Jeder Block nennt seine Quelle, etwa „Fehlerliste“, „Klemmenplan“ oder „Blatt 3“.

## 3. Signalweg-Ansicht

**Hauptweg statt Nachbarschaft:** `GET /api/signal-path` bekommt den Parameter `view=main`.
- Rückwärts geht der Weg bis zu einem Knoten ohne Vorgänger, vorwärts bis zu einem ohne Nachfolger.
- Je Richtung zählt der kürzeste Weg. Bei Gleichstand gewinnt die alphabetische Reihenfolge der Knoten-IDs, damit das
  Ergebnis reproduzierbar ist.
- Nachbarn, die nicht auf dem Hauptweg liegen, erscheinen als `branches: n` am Knoten. Ein Tippen klappt sie auf.
- Ohne `view` liefert der Endpunkt das bisherige Ergebnis.

**Feste Spalten nach Art:** Feld · Klemme · SPS-Eingang · Programm · SPS-Ausgang · Klemme · Schaltgerät · Verbraucher.
- Ob eine Klemme vor oder nach der SPS liegt, ergibt sich aus ihrer Lage auf dem Hauptweg.
- Leere Spalten fallen weg. Ohne SPS bleiben Feld · Klemme · Schaltgerät · Verbraucher.
- Der Endpunkt liefert je Knoten `column`, das Frontend rechnet nur noch die Reihenfolge innerhalb der Spalte. Das
  geschieht in `layout()` in `SignalPath.tsx`, ohne Layout-Bibliothek.

**Anschlüsse an der Linie:** Knoten der Art `pin` gehen in ihrem Gerät auf. Die Kante trägt `pins: {from, to}`, etwa
„A1“ an der Kante zur Spule und „2“ an der Kante zum Verbraucher. Das spart etwa die Hälfte der Knoten.

**Herkunft je Kante:** `via` ist eine Liste aus `klemmenplan`, `awl`, `symboltabelle`, `stueckliste`, `leitung`, `lage`
und `modell`.
- Die Darstellung unterscheidet drei Stufen: Tabelle oder Programm, Leitung im Plan, Lage im Plan oder Modell.
- Die Stufen unterscheiden sich nicht nur über die Farbe.
- Eine Legende erklärt sie. Ein Schalter blendet alles außer „Tabelle oder Programm“ aus.

**Handy:** eine senkrechte Liste mit einem Schritt pro Zeile: Kennzeichen, Klartext, Blatt und Herkunft. Sie kommt ohne
`@xyflow/react` aus.

**PC:** Oben die Grafik, darunter die Planseite des gewählten Knotens mit markierter Spalte. Die Grafik lädt per
`next/dynamic` mit `ssr: false` aus einer Client Component.

**Bedienung**
- Ein Knoten öffnet Bauteil-Detail und Planseite.
- „Von hier weiter verfolgen“ macht den Knoten zur neuen Mitte. Das ersetzt den heutigen Doppelklick.
- Ein Netzwerk-Knoten zeigt den AWL-Code wie heute.

**Leerer Zustand** mit Grund statt 404-Text:
- „Keine Tabellen und keine Leitungen im Plan gefunden“
- „-Q1 kommt im Signalweg nicht vor“

Dazu kommen die Aktionen „Planseite öffnen“ und, wenn ein Modell eingerichtet ist, „Mit Modell lesen, ca. <Betrag> USD“.
Den Betrag rechnet das Backend aus Seitenzahl und Preis (`app/flow/pricing.py`).

## 4. Planleser im Backend

### 4.1 Leitungen lesen

Neues Modul `app/ingestion/plan_wires.py`, nur für Stromlaufplan-PDFs:

1. **Segmente:** Über die Rohschnittstelle von pypdfium2 (`FPDFPath_*`, `FPDFPageObj_GetMatrix`) werden Segmente
   gelesen.
   - Jede Pfadmatrix wird angewendet. Form-XObjects werden rekursiv durchlaufen, Bézierkurven werden in Sehnen zerlegt.
   - Strichstärke und Strichmuster bleiben am Segment.
2. **Filter:**
   - Rahmen, Spaltenkopf und Schriftfeld fallen weg, über dieselben Grenzen wie `page_columns` und `TITLE_BAND`.
   - Rechtecke und geschlossene Pfade gelten als Symbole, nicht als Leitungen.
   - Unterscheidet ein Dokument Leiter und Symbole über die Strichstärke, zählt nur die Leiterstärke. QElectroTech
     nutzt etwa 1,0 und 0,7.
3. **Netze:** Endpunkte, die näher als `SNAP` beieinander liegen, werden zusammengeführt, über `scipy.spatial.cKDTree`.
   Der Startwert für `SNAP` ist 1,0 pt. Der Vergleich mit dem Gold bestätigt oder korrigiert ihn.
   - Ein Endpunkt auf dem Inneren eines anderen Segments ist ein T-Abzweig.
   - Eine Kreuzung ohne Verbindungspunkt verbindet nicht. Ein Verbindungspunkt ist ein kleiner gefüllter Kreis.
   - Netze entstehen als Zusammenhangskomponenten mit `networkx`.
4. **Enden benennen:** Jedes Netzende sucht den nächsten Anschluss-Text: Geräteanschluss aus #102, Klemme oder
   SPS-Adresse. Es gilt dieselbe Eindeutigkeitsregel wie in #102: der Abstand höchstens `PIN_REACH`, das zweitnächste
   mindestens 1,5-mal so weit weg. Ein Ende ohne eindeutigen Text bleibt unbenannt und zählt als Hinweis.
5. **Kanten:** Ein Netz verbindet seine benannten Enden.
   - Die Richtung folgt den Regeln aus `_add_terminal_rows`: Netze mit E-Adresse laufen zur Adresse, Netze mit
     A-Adresse von ihr weg.
   - Bei Spule und Kontakt läuft der Weg wie seit #98 durch das Gerät.
   - Netze ohne eindeutige Richtung bleiben ungerichtet. Sie erscheinen nur als Abzweig, nie im Hauptweg.

**Über Blätter hinweg:** Spule und Kontakte teilen sich den Geräteknoten. Der Kontaktspiegel aus #102 nennt das Blatt
des Kontakts.

**Ohne Vektorlinien**, etwa bei Scans, gilt die Lage im Plan als Ersatz:
- Kanäle in Spalten aus #90 und dieselbe Logik für Kanäle in Zeilen: Feldgerät, Klemme und Adresse in einer Zeile.
- Die Herkunft heißt dann `lage`.

**Graph und Speicher**
- `Graph.edges` wird von `set[tuple]` zu `dict[tuple, set[str]]` mit der Herkunft.
- `graph_for_source` nimmt Stromlaufplan-PDFs dazu.
- Das Ergebnis des Planlesers je Datei liegt unter `data/plan_cache/<sha256>.json`, mit `PLAN_READER_VERSION` im
  Schlüssel, so wie `data/flow_cache/`.
- `ingest_document` rechnet es nach dem Einlesen eines Stromlaufplans vorab.
- Eine Schema-Migration ist nicht nötig.

### 4.2 Modell als Option

- **Einstellungen** in `config.py` und `.env.example`, im selben Commit: `PLAN_READER_MODEL` ist leer, also aus, oder
  etwa `openai:gpt-5-mini`. `PLAN_READER_BASE_URL` ist leer für den Anbieter, oder etwa `http://localhost:11434/v1`
  für Ollama.
- `llm.make_chat_model` bekommt dafür eine einstellbare Basis-URL für OpenAI-kompatible Endpunkte.
- **Eingabe je Seite:** das Seitenbild, die Wortliste mit Koordinaten und die Kennzeichen der Seite aus dem Index.
- **Ausgabe** ist JSON nach Schema: `edges: [{from, to, pins, reason}]`.
- **Prüfung:** Beide Enden müssen Kennzeichen dieser Seite im Index sein. Alles andere wird verworfen und gezählt.
- **Aufruf:** `POST /api/sources/{id}/plan-read` startet den Lauf. Er kostet Geld, außer bei einem lokalen Endpunkt. Mit
  `dry_run=true` liefert er nur Seitenzahl und Schätzung.
- **Speicher:** Das Ergebnis liegt unter `data/plan_cache/model/` mit Prompt-Version. Der Signalweg liest es mit
  `via: modell`.
- **Erster lokaler Kandidat:** `qwen3.5:4b` über Ollama, mit 3,4 GB und Apache-2.0. Der „Thinking“-Modus ist aus, das
  Schema wird über `format` vorgegeben. Gegenprobe ist `qwen3-vl:4b`.

### 4.3 Lehrer in der Entwicklung

- `eval/plan_teacher.py --model … --doc …` lässt ein bezahltes Modell öffentliche Pläne lesen und schreibt Kanten und
  Kosten nach `eval/results/`.
  - Erlaubte Pläne: FB-01, UR-01, PM1-AR und die QElectroTech-Beispiele.
  - Firmendokumente gehen nie an ein Cloud-Modell, außer der Owner gibt sie ausdrücklich frei.
- Vor jedem Lauf werden Guthaben, Anbieter, Modell, Seitenzahl und geschätzte Kosten genannt. Der Lauf startet erst nach
  dem OK. Er läuft nie in der CI.
- Der Vergleich Wahrheit / Regeln / Modell listet je Seite drei Fälle:
  - Das Modell findet eine echte Verbindung, die Regeln nicht. Daraus wird ein Kandidat für eine neue Regel.
  - Die Regeln finden eine falsche Verbindung. Das ist ein Fehler in einer Regel.
  - Das Modell findet eine falsche Verbindung. Sie wird ignoriert.
- Jede neue Regel kommt mit einem Test auf einer synthetischen Seite.

### 4.4 Messen

Gemessen wird auf zwei Ebenen, beide kostenlos und im Ingest-Job von `eval.yml`.
- **Leitungen gegen gezeichnetes Gold:** `make_gold.py` schreibt die Verbindungen mit, die die Generatoren zeichnen,
  je Seite als `wires`. Gemeint sind `make_pdf.py` für FB-01 und `scripts/testdoku/render_pdf.py` mit `wire()` für
  UR-01 und PM1-AR. Damit wird `plan_wires` gemessen.
- **Signalweg aus dem Plan gegen den Graphen aus den Tabellen** derselben Maschine, also Klemmenplan, Symboltabelle und
  AWL von FB-01, UR-01 und PM1-AR. Gemessen wird nur die Precision der Kanten, die der Plan überhaupt zeigen kann:
  Feldgerät, Klemme, Adresse und Gerät.

Die Schwellen:
- Das Gate verlangt eine Precision von mindestens 0,95, denn eine falsche Verbindung schadet mehr als eine fehlende.
- Der Recall wird berichtet. Sobald er dreimal hintereinander stabil gemessen ist, kommt eine Schwelle 0,05 unter dem
  Messwert dazu.
- Stichproben an QElectroTech-Plänen werden am Seitenbild geprüft und im PR mit Anzahl genannt.

## 5. Performance, Zustände, Tests

**Ziele**
- Störfall-Liste und Chat stehen in unter 1 s nach dem Klick auf die Maschine.
- Der Block „Fehlerliste“ steht in unter 1 s nach Enter.
- Ein Detail öffnet sich in unter 0,3 s, wenn seine Daten geladen sind.
- Lighthouse Performance mindestens 90 auf der Maschinenseite, mobil. `frontend/scripts/lighthouse-a11y.mjs` misst
  dafür auch die Kategorie Performance. In der CI wird der Wert zuerst nur berichtet und ab drei stabilen Läufen zum
  Gate.

**Wie**
- **Laden nur, was sichtbar ist:** Maschine und Störfälle zuerst, Aufbau-Tabs beim Öffnen, Blöcke beim Sichtbarwerden.
- **Bibliotheken bei Bedarf:** `@xyflow/react` nur in Signalweg-Grafik, Draufsicht und Werkplan, jeweils über
  `next/dynamic`.
- **Chat:**
  - Er lädt die letzten 30 Nachrichten, ältere beim Hochscrollen.
  - Dafür bekommt `GET /api/conversations/{id}/messages` die Parameter `before` und `limit`.
  - Die Ansicht bleibt beim Streamen unten stehen, über `use-stick-to-bottom`.
  - Markdown wird je Absatz zwischengespeichert.
  - `@tanstack/react-virtual` kommt erst dazu, wenn eine Messung lange Verläufe als Bremse zeigt.
- **Planseite:** PNG vom Server, Zoom und Verschieben über `react-zoom-pan-pinch`, die Spalte als Rahmen darüber.
- **Rückmeldung:** Ein neuer Störfall steht sofort in der Liste. Platzhalter haben die Form des Blocks. Enter legt an,
  Esc schließt das Detail.

**Zustände in jeder Ansicht und jedem Block**
- **Laden:** Platzhalter in Blockform.
- **Leer:** ein Satz mit Grund und nächster Aktion. Leer ist nie rot.
- **Fehler:** „Erneut versuchen“, ohne Entwicklertexte wie Port, Skriptname oder API-Pfad.
- **Beleg verschwunden:** „Quelle wurde entfernt“.

**Regeln für Bedienoberflächen in der Industrie**, nach der Recherche:
- Grau ist der Normalzustand, Farbe nur bei Abweichung.
- Ein Zustand wird nie nur über die Farbe gezeigt.
- Rot gilt nur für Fehler und Not-Halt.
- Arbeitswert für Zielgrößen: 48 px. Gemessen wird am Tablet mit Handschuh.

**Tests**
- **Planleser:**
  - Synthetische Seiten mit Leitungen: T-Abzweig, Kreuzung mit und ohne Punkt, gedrehte Seite, Form-XObject.
  - Kanäle in Zeilen und in Spalten.
  - Ein unbenanntes Ende ergibt keine Kante.
- **Gate:** die zwei Ebenen aus 4.4 im Ingest-Job.
- **Backend:**
  - Fehlerlisten-Treffer mit den drei Listen.
  - `meta.part_kinds`, `signal_start` und `plan_spots`.
  - `PATCH` auf Störfälle samt Migration.
  - `view=main` mit Spalten, Pins an Kanten und Herkunft.
- **Frontend (Vitest):** Blöcke mit und ohne Inhalt, Kette und Grafik aus denselben Daten, Spalten und Reihenfolge.
- **Ende zu Ende (Playwright, bestehender E2E-Job):** Meldung eingeben, der Störfall entsteht, der Block „Fehlerliste“
  erscheint, dann Signalweg und Planseite. Das läuft einmal mit 390 und einmal mit 1440 px Breite.

## Abhängigkeiten

| Paket | Wo | Lizenz | Grund |
| --- | --- | --- | --- |
| networkx | Backend | BSD-3 | Netze und Wege; liegt schon indirekt im venv, wird in `pyproject.toml` eingetragen |
| scipy | Backend | BSD-3 | `cKDTree` zum Einrasten; liegt schon indirekt im venv, die Version muss Python 3.11 unterstützen |
| react-zoom-pan-pinch | Frontend | MIT | Planseite zoomen, 15,5 kB |
| use-stick-to-bottom | Frontend | MIT | Chat bleibt beim Streamen unten, 2,5 kB |

## Datenschutz

- Standard im Produkt sind die Regeln. Ohne `PLAN_READER_MODEL` verlässt keine Seite den Rechner.
- Mit lokalem Endpunkt bleibt alles auf dem Rechner. Mit Cloud-Endpunkt startet jeder Lauf nur per Knopf, mit Preis
  davor.
- Bezahlte Lehrerläufe nutzen nur öffentliche oder synthetische Pläne.

## Reihenfolge der Umsetzung

Jeder Schritt bekommt ein eigenes Issue mit Akzeptanzkriterien und einen eigenen PR.

1. **Planleser: Leitungen, Herkunft, Gold und Gate.** Nur Backend, kostenlos. Abschnitte 4.1 und 4.4.
2. **Lehrerlauf** mit OpenAI auf FB-01 und UR-01, nach Freigabe der Kosten. Danach werden Regeln nachgezogen.
   Abschnitt 4.3.
3. **Störfall-Backend:** Migration, `fault-hits`, neue `meta`-Felder, `view=main`, Nachrichten in Stücken.
   Abschnitte 1 bis 3.
4. **Figma:** Komponenten und Screens für Störfälle, Blöcke und Signalweg, in der Figma-Session. Der Owner gibt das
   Design frei.
5. **Frontend nach Figma:** Aufbau, Blöcke, Signalweg-Ansicht, Performance-Ziele. Abschnitte 1, 2, 3 und 5.
6. **Folgeprojekte:** Modell als Option mit `qwen3.5:4b` (4.2), lokaler Chat, Import von EPLAN-Verbindungslisten.

Nach Schritt 3 werden `docs/product/ux-spec.md` und `docs/product/contract.md` angepasst. Bisher kommen Signalweg,
Steckbrief und Ablauf dort nicht vor.

## Offene Punkte außerhalb dieses Konzepts

- Designrichtung, Figma-Datei und Modus „Halle“: Diese Entscheidungen fallen in der Figma-Session.
- Zielgröße mit Handschuh: Sie wird am Tablet gemessen, bevor die Figma-Komponenten feststehen.
- `.qet`-Quellen der QElectroTech-Beispiele als zweite Wahrheit für Leitungen: Sie brauchen einen Download und damit
  eine Freigabe.
