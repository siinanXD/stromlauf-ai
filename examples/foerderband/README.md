# Beispielanlage: Foerderband FB-01

Ein vollstaendiger, frei erfundener Dokumentensatz einer kleinen Foerderbandsteuerung. Alle
Betriebsmittel, Klemmen und SPS-Adressen sind ueber die sechs Dateien hinweg konsistent, so wie
in einer echten Anlagendokumentation. Ohne Herstellerbezug, frei verwendbar (MIT-Lizenz des Repos, siehe `LICENSE`).

| Datei | Inhalt |
| --- | --- |
| `01_Stromlaufplan_FB-01.pdf` | 7 Blaetter: Einspeisung, Motorabgang mit Wendeschuetz, Not-Halt, SPS-Ein-/Ausgaenge, Klemmenplan |
| `02_Stueckliste_FB-01.xlsx` | 26 Betriebsmittel (davon 4 Klemmleisten) und 4 Leitungen mit BMK, Typ, Einbauort, Blattverweis; fuenf Einbauorte: +ST1 Schaltschrank, +BP1 Bedienpult, +AN1 Antrieb, +SE1 Einlauf, +SA1 Auslauf |
| `03_Klemmenplan_FB-01.csv` | Klemmleisten -X1 bis -X4: Klemme, Ziel intern, Ziel extern, Funktion, Blatt |
| `04_SPS_Programm_FB-01.awl` | STEP 7 AWL: OB1, FB10 (7 Netzwerke), DB10 |
| `05_Symboltabelle_FB-01.sdf` | 18 Symbole (E0.0 bis A4.3, Merker, Timer, Bausteine) |
| `06_Betriebsanleitung_FB-01.md` | Bedienung, SPS-Belegung, Fehlersuche-Tabelle, Wartung |

## Laden

Backend und Datenbank laufen (siehe Haupt-README), dann:

```bash
python scripts/load_example.py
```

Das Skript legt die Wissensquelle „Foerderband FB-01“ an, laedt die sechs Dateien hoch und wartet,
bis die Ingestion fertig ist (erster Lauf: einige Minuten, weil Embedding- und Docling-Modelle
geladen werden). Vision-Analyse ist aus, es fallen keine API-Kosten fuer das Laden an.

## Fragen zum Ausprobieren

Die Antworten stehen verteilt ueber mehrere Dokumente, der Agent muss sie zusammenfuehren:

1. **Was haengt an E0.3 und wo ist das im Plan?**
   Symboltabelle (NotHalt_OK) + Klemmenplan (-X3:4, -K3:13) + Stromlaufplan Blatt /4.4 und /5.5.
2. **Warum leuchtet -H2 nach etwa 20 Sekunden Betrieb?**
   Betriebsanleitung Kap. 6 (Blockade) + FB10 Netzwerk 5 (Timer T5, S5T#20S).
3. **Welche Klemmen muss ich pruefen, wenn der Motor brummt, aber nicht dreht?**
   Betriebsanleitung + Klemmenplan -X4:U/V/W + Blatt /3.5.
4. **Wie ist -K1 gegen -K2 verriegelt?**
   FB10 Netzwerk 2 und 3 (Software) + Stromlaufplan Blatt 6 (Hilfskontakte).
5. **Welchen Typ hat -F2 und auf welchen Strom ist er eingestellt?**
   Stueckliste (2,5-4 A) + Stromlaufplan Blatt /3.2 (Einstellung 3,6 A) + Anleitung (Nennstrom 3,5 A).
6. **Was passiert beim Druecken von -S3?**
   Blatt 4 (zwei Kanaele auf -K3, Meldeleuchte -H3 ueber 31/32) + Anleitung Kap. 4 + FB10 Netzwerk 1 (Wiederanlaufsperre).
7. **-K1 zieht an, aber der Motor steht und brummt nicht. Woran kann es liegen?**
   Anleitung Kap. 6 (Reparaturschalter -Q2 am Antrieb +AN1) + Blatt /3.5.

## Erzeugung

Die Dateien werden aus einer Datentabelle generiert (`scripts/example_docs/`). Aenderungen dort,
dann `python scripts/example_docs/build.py examples/foerderband` ausfuehren.
