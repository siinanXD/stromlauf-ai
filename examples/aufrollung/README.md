# Testdokumentation Aufrollung PM1-AR

Frei erfundener, in sich stimmiger Dokumentensatz für die Maschine **PM1-S6 Aufrollung** der
Papiermaschine des Testwerks. Erzeugt aus `scripts/testdoku/machines/pm1_ar.py` mit
`python scripts/testdoku/build.py pm1_ar`. Kein Herstellerbezug, frei verwendbar.

| Datei | Inhalt |
|---|---|
| `01_Stromlaufplan_PM1-AR.pdf` | 13 Blätter: Einspeisung 250 A, Tragtrommel 75 kW und Tambourantrieb 30 kW an Umrichtern, Hydraulik- und Ölpumpe, Not-Halt mit Reißleine, Schutztüren, DI/DO, Klemmenplan |
| `02_Stueckliste_PM1-AR.xlsx` | Betriebsmittel mit Blatt/Spalte, Magnetventile -Y1 bis -Y3, Leitungen |
| `03_Klemmenplan_PM1-AR.csv` | -X1, -X2, -X3 Feld, -X4 bis -X7 Motorabgänge |
| `04_SPS_Programm_PM1-AR.awl` | FB30 mit 16 Netzwerken: Ölmangel- und Druckerwachung mit Timern, Tambourwechsel als Schrittkette M30.0 bis M30.3, Tambourzählung; DB30, OB1 |
| `05_Symboltabelle_PM1-AR.sdf` | E0.0 bis E2.2, A4.0 bis A5.2, Schrittmerker, Timer T30 bis T32 |
| `06_Betriebsanleitung_PM1-AR.md` | Bedienung, SPS-Belegung, Fehlertabelle (12 Zeilen) mit Blattverweisen |

Laden und mit der Maschine verknüpfen: `python scripts/load_testwerk.py --docs`.

Fragen zum Ausprobieren: „Warum startet der Tambourwechsel nicht?“ · „Was passiert bei Reißleine?“ ·
„Signalweg von -S5“ · „Welche Merker bilden die Schrittkette?“ · „Wo ist -Y3 im Plan?“
