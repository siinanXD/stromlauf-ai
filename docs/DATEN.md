# Daten: Herkunft und Lizenz

Stand: 2026-10-28 · Linear SIN-1169 · `docs/FERTIG.md` Punkt 1.

Diese Liste beschreibt, was heute im Repo liegt. Ob FB-01 als öffentliche Demo reicht, entscheidet Sinan
(`docs/NAECHSTE-SCHRITTE.md` Schritt 1); das ändert die Liste nicht. Die Lizenz des Repos ist MIT (`LICENSE`).

## Demo-Maschine FB-01 (`examples/foerderband/`)

Der Satz ist laut `examples/foerderband/README.md` frei erfunden, ohne Herstellerbezug. Die Dateien 01 bis 06 entstehen mit
`python scripts/example_docs/build.py examples/foerderband` (`build.py` ruft `make_pdf.py` und `make_rest.py`), die Daten
stehen in `scripts/example_docs/data.py`. Die beiden Dateien 07 erzeugt `make_cabinet.py`.

| Datei | Herkunft | Lizenz |
| --- | --- | --- |
| `01_Stromlaufplan_FB-01.pdf` | erzeugt von `scripts/example_docs/make_pdf.py` (Aufruf in `build.py`) | MIT (Repo) |
| `02_Stueckliste_FB-01.xlsx` | erzeugt von `scripts/example_docs/make_rest.py`, Funktion `stueckliste()` | MIT (Repo) |
| `03_Klemmenplan_FB-01.csv` | erzeugt von `scripts/example_docs/make_rest.py`, Funktion `klemmenplan()` | MIT (Repo) |
| `04_SPS_Programm_FB-01.awl` | erzeugt von `scripts/example_docs/make_rest.py`, Funktion `awl()`; der Text steht im Skript, wer ihn geschrieben hat, ist im Repo nicht belegt: unbekannt | MIT (Repo) |
| `05_Symboltabelle_FB-01.sdf` | erzeugt von `scripts/example_docs/make_rest.py`, Funktion `symbole()` | MIT (Repo) |
| `06_Betriebsanleitung_FB-01.md` | erzeugt von `scripts/example_docs/make_rest.py`, Funktion `anleitung()` | MIT (Repo) |
| `07_Schaltschrank_Aufbauplan_FB-01.png` | `scripts/example_docs/make_cabinet.py` (Aufruf: `python scripts/example_docs/make_cabinet.py examples/foerderband`); `build.py` ruft es nicht auf, ob die eingecheckte Datei so entstand, ist nicht belegt: unbekannt | MIT (Repo) |
| `07_Schaltschrank_Hotspots_FB-01.json` | `scripts/example_docs/make_cabinet.py`, gleicher Lauf wie das PNG; gleiche Einschränkung | MIT (Repo) |
| `README.md` | von Hand geschrieben | MIT (Repo) |

Anmerkungen:

- „Erzeugt“ heißt: das Skript schreibt die Datei in dieser Form. Dass die eingecheckten Bytes mit einem frischen Lauf
  übereinstimmen, wurde für diese Liste nicht geprüft (nur für das PDF prüft `backend/tests/test_run_ingest.py` die
  Gleichheit mit dem Gold).
- Die Git-Historie dieses Checkouts enthält nur einen Commit (`fbe739d`); frühere Autoren lassen sich hier nicht nachprüfen.

## Nicht im Repo

Bewusst draußen bleibt:

- **Fremddaten unter `testdata/`** (komplett per `.gitignore` ausgeschlossen): Festo-MPS-Handbuch und -Stromlaufplan
  (Eigentum von Festo Didactic, nur lokal testen, Weitergabe verboten), QElectroTech-Beispielprojekte (Programm
  GPL-2.0-or-later, Lizenz der Projektdateien ungeklärt), AWL-Quellen aus awlsim (GPL-2.0-or-later). Quelle, Lizenz und
  SHA-256 je Datei: `scripts/testdata_manifest.json`; Laden mit `python scripts/fetch_testdata.py`.
- **Firmendaten unter `testdata/private/`**: nie committen. `scripts/make_gold_template.py` verweigert Ziele, die git
  committen würde.

Andere Beispielanlagen unter `examples/` (UR-01, PM1-AR, Testwerk, Injection) sind nicht Gegenstand dieser Liste.
