# Testdokumentation Umroller UR-01

Frei erfundener, in sich stimmiger Dokumentensatz für die Maschine **L1-UR** des Testwerks (Linie L1
Toilettenpapier). Erzeugt aus `scripts/testdoku/machines/ur01.py` mit
`python scripts/testdoku/build.py ur01`. Kein Herstellerbezug, frei verwendbar.

| Datei | Inhalt |
|---|---|
| `01_Stromlaufplan_UR-01.pdf` | 16 Blätter: Einspeisung, 7 Antriebe (5 Umrichter am PROFIBUS, 2 Schütze), Sicherheitskreise -K1/-K2, Bedienpult, DI/DO, Klemmenplan |
| `02_Stueckliste_UR-01.xlsx` | 65 Betriebsmittel mit Blatt/Spalte, dazu Leitungen |
| `03_Klemmenplan_UR-01.csv` | -X1 Netz, -X2 24 V, -X3 Feld (46 Klemmen), -X4 bis -X10 Motorabgänge |
| `04_SPS_Programm_UR-01.awl` | FB20 mit 13 Netzwerken (Freigabe, Bahnriss, Umrichter, Hülsenzufuhr, Logabschub, Logzählung), DB20, OB1 |
| `05_Symboltabelle_UR-01.sdf` | E0.0 bis E2.6, A4.0 bis A5.2, Merker, Timer |
| `06_Betriebsanleitung_UR-01.md` | Bedienung, SPS-Belegung, Fehlertabelle (12 Zeilen) mit Blattverweisen |

Laden und mit der Maschine verknüpfen: `python scripts/load_testwerk.py --docs`.

Fragen zum Ausprobieren: „Warum läuft die Hülsenzufuhr nicht?“ · „Was hängt an E1.2?“ ·
„Signalweg von -S4“ · „Welche Umrichter sitzen am PROFIBUS?“ · „Wo ist -K3 im Plan?“
