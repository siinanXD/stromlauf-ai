# Schriftfeld-Varianten für die Blatt-Map

Kleine Plan-PDFs einer frei erfundenen Anlage (Muster-Band MB-02) mit je einem anderen Schriftfeld. Damit lässt sich
messen, ob Verweise wie `/3.8` auch bei fremden Schriftfeldern auf das richtige Blatt zeigen (Issue #67). Jede Datei
hat vorne ein Deckblatt und ein Inhaltsverzeichnis ohne Blattnummer, danach die Blätter 1 bis 5 mit Spaltenraster,
Betriebsmitteln und Querverweisen. Einige Querverweise und Hinweise wie „von Blatt 3“ stehen im unteren Viertel direkt
über dem Schriftfeld, dort, wo die Blatt-Map sucht. Blatt 1 liegt also auf Seite 3. Frei verwendbar (MIT-Lizenz des
Repos, siehe `LICENSE`).

| Datei | Schriftfeld |
| --- | --- |
| `blatt_schraegstrich.pdf` | „Blatt 3 / 5“ |
| `blatt_von.pdf` | „Blatt 3 von 5“ |
| `bl_punkt.pdf` | „Bl. 3“ |
| `sheet_of.pdf` | „Sheet 3 of 5“ |
| `getrennte_felder.pdf` | Feldname „Blatt“ klein oben, „3“ groß darunter, „von 5“ daneben |
| `eplan_seitenname.pdf` | EPLAN-Seitenname „=ANL+ORT/3“, Querverweise zusätzlich als „=ANL+ORT/4.7“ |
| `luecke.pdf` | wie „Blatt 3 / 5“, aber im Schriftfeld von Blatt 3 fehlt die Nummer |
| `ohne_blattnummer.pdf` | Schriftfeld ohne Blattnummer |

`gold.json` hält je Datei Seite → Blatt, so wie gezeichnet. Die ersten sechs Dateien liest die Blatt-Map vollständig.
Bei `luecke.pdf` nimmt sie Blatt 3 aus der Seitenfolge an (Seite 5), bei `ohne_blattnummer.pdf` Seite = Blatt. In
beiden Fällen steht „Blatt-Map unsicher“ am Dokument, und die Zitatprüfung meldet Belege auf diese Blätter als nicht
geprüft.

## Erzeugen und prüfen

```bash
python scripts/example_docs/make_titleblocks.py          # schreibt alle Dateien und gold.json neu, gleiche Bytes je Lauf
cd backend && .venv/Scripts/python -m pytest -q tests/test_pdf_layout.py tests/test_pipeline_sheets.py
```
