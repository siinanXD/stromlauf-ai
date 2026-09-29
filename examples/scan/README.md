# Scan-Fassungen des Beispielplans FB-01

Derselbe Stromlaufplan wie `examples/foerderband/01_Stromlaufplan_FB-01.pdf`, aber ganz oder teilweise als Bild
ohne Textebene, so wie ein eingescannter Plan aus dem Schaltschrank. Damit laesst sich messen, was die Lesekette
bei Scans verliert und was die Texterkennung zurueckholt (Issues #64 bis #66). Abgeleitet aus der frei erfundenen
Beispielanlage, frei verwendbar (MIT-Lizenz des Repos, siehe `LICENSE`).

| Datei | Inhalt |
| --- | --- |
| `01_Stromlaufplan_FB-01_scan.pdf` | alle 7 Blaetter als Bild, keine Textebene |
| `01_Stromlaufplan_FB-01_teilscan.pdf` | Text-PDF, nur Blatt 3 als Bild |
| `01_Stromlaufplan_FB-01_quer.pdf` | Text-PDF, Blatt 4 als Bild und um 90 Grad gedreht, wie ein hochkant gescanntes Blatt |

"Scan" heisst: 200 dpi, Graustufen, 0,5 Grad schief, grauer Papierton, Rauschen mit festem Seed, leicht unscharf,
JPEG. Seitenzahl und Blattfolge stimmen mit dem Text-PDF ueberein, deshalb gilt dieselbe Ground Truth
`eval/ingest_gold/fb01.json`.

## Erzeugen und messen

```bash
python scripts/example_docs/make_scan.py                    # schreibt die drei Dateien neu, gleiche Bytes
python eval/run_ingest.py --gold eval/ingest_gold/fb01.json --doc examples/scan/01_Stromlaufplan_FB-01_scan.pdf --label scan
```

Die Dateien gehoeren in eine eigene Wissensquelle, nicht zur Demo-Maschine FB-01. Sonst beantwortet der Chat
Fragen zum Scan aus dem Text-PDF, und der Test beweist nichts. Das Retrieval-Gate laedt nur den Voll-Scan als Quelle
„Scan FB-01“; der Upload liest ihn per OCR (Issue #66):

```bash
python scripts/load_folder.py examples/scan --pattern "*_scan.pdf" --name "Scan FB-01"
python eval/run_retrieval.py --only "Scan FB-01"
```
