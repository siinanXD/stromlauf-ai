# Recherche: Leitungen aus Stromlaufplänen lesen, lokale Modelle, Anzeige im Frontend

Stand: 2026-10-01. Alle Angaben wurden an diesem Tag abgerufen. Es wurde nichts heruntergeladen und nichts installiert.
Grundlage für das Konzept `docs/superpowers/specs/2026-10-01-stoerfall-arbeitsflaeche-design.md`.

```yaml
problem:
  summary: >
    Für Maschinen, deren Dokumentation nur aus PDFs besteht, gibt es keinen Signalweg. Der Graph entsteht heute nur aus
    Klemmenplan (CSV), Stückliste (XLSX), Symboltabelle und AWL. Gesucht sind Wege, die gezeichneten Verbindungen
    deterministisch und lokal zu lesen, sowie Bausteine für eine schnelle Anzeige.
  components: [Vektorlinien aus PDF, Konnektivität, Wahrheit zum Messen, lokales Modell, Chat-UI, Graph-Layout, Planseite]
solutions:
  official: [pypdfium2 raw API (FPDFPath_*, FPDFPageObj_*), next/dynamic (Next 16.3.5), React Flow 12 Edge-Labels]
  github: [schematic-pdf-to-json (nur Regeln als Vorbild), Azure-Samples P&ID (nur Vorbild)]
  hugging_face: [qwen3.5:4b, qwen3-vl:4b, CGHD-Datensatz (nur Evaluation)]
  packages: [networkx, scipy oder shapely, react-zoom-pan-pinch, use-stick-to-bottom]
  services: [OpenAI und Anthropic nur als Lehrer in der Entwicklung, auf öffentlichen Plänen]
comparison:
  criteria: [maintenance, security, cost, license, scalability, integration]
recommendation:
  selected_option: "Hybrid: pypdfium2-Rohschnittstelle + eigener Leitungsleser mit networkx; Modell nur für Zweifel"
  reason: >
    Keine neue PDF-Abhängigkeit, alle Bausteine sind grün lizenziert und schnell. Ein fertiges Werkzeug für
    IEC-Stromlaufpläne gibt es weder auf GitHub noch auf Hugging Face.
  custom_build_required: true
risks:
  - pypdfium2 hat praktisch einen Maintainer; der Leser wird in einem Modul gekapselt
  - Ob EPLAN-PDFs Leiter als eigene Pfade mit eigener Strichstärke ausgeben, ist ungeprüft
  - Generierte Beispielpläne können zu freundlich sein; daher Stichproben an QElectroTech-Plänen
next_steps: [Konzept freigeben, Umsetzungsplan schreiben]
```

## 1. Linien aus Vektor-PDFs

| Fund | Was | Lizenz | Pflege | Bewertung |
| --- | --- | --- | --- | --- |
| pypdfium2 5.13.0 | Rohzugriff auf Pfadsegmente, Matrix, Strichstärke, Farbe, Strichmuster | BSD-3 / Apache-2.0, grün | aktiv, praktisch ein Maintainer | **gewählt**, ist schon Abhängigkeit |
| pdfplumber 0.11.10 / pdfminer.six | `.lines`, `.curves` mit angewandter Matrix | MIT, grün | aktiv | nur zum Debuggen, beim Text etwa 100-mal langsamer |
| PLAYA-PDF 1.1.0 | Pfadsegmente roh und im Geräteraum | MIT laut PyPI, auf GitHub unklar | ein Autor | Ersatz, falls pypdfium2 ausfällt |
| PyMuPDF `get_drawings` | bequemes Auslesen | AGPL, rot | aktiv | verworfen |

Gemessen mit pypdfium2, nur Pfade und Segmente gezählt, Form-XObjects eingeschlossen:

| Dokument | Seiten | Segmente | Zeit |
| --- | --- | --- | --- |
| FB-01 | 7 | 957 | 0,00 s |
| UR-01 | 16 | 2.568 | 0,01 s |
| PM1-AR | 13 | 2.083 | 0,00 s |
| QElectroTech-Beispiel „industrial“ | 50 | 205.873 | 0,15 s |
| echtes Fremddokument, lokal, nicht im Repo | 11 | 10.066 | 0,01 s |

Wichtig für den Leser: Die Punkte liegen im Objektraum. Jede Pfadmatrix muss angewendet werden, und bei
Form-XObjects sind die Matrizen verschachtelt.

## 2. Projekte, die Schaltpläne digitalisieren

| Fund | Was | Lizenz | Bewertung |
| --- | --- | --- | --- |
| schematic-pdf-to-json 0.2.0 | Vektor-PDF zu Netzliste. Regeln: Endpunkt, T-Abzweig, Verbindungspunkt; Kreuzung ohne Punkt ist keine Verbindung; Unklares wird als Hinweis ausgegeben | MIT, hängt aber an PyMuPDF | Regeln als Vorbild, Code nicht |
| MEPdetect | Leiter über die Strichstärke erkennen | AGPL, rot | nur die Idee; QElectroTech zeichnet Leiter mit 1,0 und 0,7 |
| Azure-Samples P&ID | Raster: Symbole, OCR, Hough-Linien, Graph | MIT | Vorbild für „Linienende zum nächsten Text“ |
| CGHD, PID2Graph | Machine Learning auf Rasterbildern | Code-Lizenz nicht geprüft | Forschung, für Vektor-PDFs unnötig |

## 3. Formate, in denen die Verdrahtung direkt steht

- **QElectroTech `.qet`:** `<conductor>` mit `terminal1` und `terminal2`. Zusammen mit dem PDF-Export ergibt das eine
  echte Wahrheit für Leitungen. Lokal liegen nur die PDFs, die `.qet`-Quellen müssten geladen werden.
- **EPLAN-Verbindungsexport** als TXT, XLSX oder XML, „Quelle → Ziel“ mit Anschluss: exakte Netzliste als optionaler
  Upload. Der Export braucht beim Kunden eine EPLAN-Lizenz.
- **AutomationML AR APC aus EPLAN:** Zuordnung von Symbol und Hardwareadresse, aber keine Feldverdrahtung.
- **IEC 61355** ist kein Verdrahtungsformat.

## 4. Hugging Face

- **Kein produktionsreifes Modell** übersetzt IEC-Stromlaufpläne in einen Graphen. Die Detektoren auf YOLO-Basis sind AGPL.
- **Datensätze:** CGHD hat 3.269 handgezeichnete Schaltungen und steht unter CC-BY, das taugt nur zur Evaluation.
  Für Steuerstromläufe mit Schütz und SPS gibt es keinen offenen Datensatz.
- **Lokales Bildmodell für 8 GB VRAM:** `qwen3.5:4b` belegt 3,4 GB in Ollama, steht unter Apache-2.0, OCRBench 85,0.
  Den „Thinking“-Modus abschalten und das JSON-Schema über das Ollama-Feld `format` vorgeben. Gegenprobe ist
  `qwen3-vl:4b` mit 3,3 GB, ebenfalls Apache-2.0.
- **Verworfen:** Qwen2.5-VL-3B wegen der Qwen Research License, die keine kommerzielle Nutzung erlaubt. Florence-2 liefert
  kein JSON nach Anweisung, SmolVLM2 kann nur Englisch, granite-vision ist nur auf Englisch trainiert.
- **Lokale Textmodelle mit Deutsch** für einen späteren Chat ohne Cloud: Ministral-3 8B mit 6,0 GB und Qwen3.5-4B/9B,
  beide Apache-2.0. Die tatsächliche Qualität im Deutschen ist nicht geprüft.

## 5. Frontend

Installiert: Next 16.3.5, React 19.2.8, `@xyflow/react` 12.12.0.

| Baustein | Entscheidung | Grund |
| --- | --- | --- |
| Chat | eigener Chat bleibt, zwei Muster kommen dazu: `use-stick-to-bottom` 1.1.6 (MIT, 2,5 kB) und Markdown, das je Absatz zwischengespeichert wird | assistant-ui (0.x, 225 kB), AI SDK + Elements und CopilotKit verlangen ein fremdes Protokoll |
| Signalweg-Layout | eigenes Spaltenlayout, `layout()` in `SignalPath.tsx` erweitern, Kantenlabels über `label` | elkjs: gelbe Lizenz, 1,6 MB |
| Laden bei Bedarf | `next/dynamic` mit `ssr: false` aus einer Client Component | wird im Projekt noch nicht genutzt |
| Planseite | PNG vom Server, `react-zoom-pan-pinch` 4.2.0 (MIT, 15,5 kB) | pdf.js kostet rund 1,7 MB |
| lange Verläufe | `@tanstack/react-virtual` mit `anchorTo: 'end'` erst bei Bedarf | vorher mit `next experimental-analyze` und Lighthouse messen |

**Regeln für Bedienoberflächen in der Industrie**, nach einer frei verfügbaren Zusammenfassung von ISA-101: Rockwell
PROCES-WP023A. Die Norm selbst ist kostenpflichtig und wurde nicht gelesen.
- Grau ist der Normalzustand, Farbe gibt es nur bei einer Abweichung.
- Ein Zustand wird nie nur über die Farbe gezeigt.
- Die Anzeigen sind in vier Ebenen gegliedert: Übersicht, Maschine, Detail, Dokument.
- Zielgröße 48 px für die Bedienung mit Handschuh. Das ist eine Annahme, gemessen wird am Tablet.

## Weg zurück

- Erweist sich der Leitungsleser als unzuverlässig, bleibt der Graph aus Spalten und Anschlüssen aus #90 und #102.
- Die Herkunft je Kante erlaubt es, „Leitung im Plan“ abzuschalten, ohne dass der Rest des Signalwegs verloren geht.
- Ein Chat-Framework wie assistant-ui bleibt Plan B, falls Nachrichten später verzweigt oder bearbeitet werden sollen.

## Quellen

pypdfium2 Releases und `pypdfium2_raw/bindings.py`; vmiklos.hu/blog/pdfium-pathsegment.html; pypi.org/project/pdfplumber;
github.com/py-pdf/benchmarks; pypi.org/project/playa-pdf; pypi.org/project/PyMuPDF; github.com/ght123247/schematic-pdf-to-json;
github.com/DynMEP/MEPdetect; github.com/Azure-Samples/digitization-of-piping-and-instrument-diagrams;
zenodo.org/records/17469897 (CGHD); github.com/qelectrotech/qelectrotech-source-mirror; eplan.help (Verbindungsexport,
AutomationML); hf.co/Qwen/Qwen3.5-4B; ollama.com/library/qwen3.5; ollama.com/library/qwen3-vl;
hf.co/Qwen/Qwen2.5-VL-3B-Instruct (LICENSE); github.com/assistant-ui/assistant-ui; elements.ai-sdk.dev;
npmjs.com/package/elkjs; github.com/BetterTyped/react-zoom-pan-pinch; tanstack.com/virtual/latest/docs/chat;
literature.rockwellautomation.com PROCES-WP023A; w3.org/WAI/WCAG22/Understanding/target-size-minimum.html.
