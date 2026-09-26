# Betriebsanleitung Foerderband FB-01

Anlage =FB1, Schaltschrank +ST1, Feld +FE1. Beispielanlage fuer Stromlauf AI,
frei erfunden. Zugehoerige Dokumente: Stromlaufplan FB-01-E-001 (7 Blaetter), Stueckliste FB-01,
Klemmenplan FB-01, SPS-Programm FB-01 (AWL, FB10/DB10/OB1), Symboltabelle FB-01.

## 1. Bestimmungsgemaesse Verwendung

Das Foerderband FB-01 transportiert Werkstuecke bis 25 kg vom Einlauf zum Auslauf. Der
Foerdermotor -M1 (1,5 kW, 400 V, 3,5 A) laeuft im Normalbetrieb vorwaerts. Rueckwaertsbetrieb
ist nur fuer Wartungsarbeiten vorgesehen (Merker M20.0 ueber Bedienpanel).

## 2. Bedienelemente am Bedienpult (+FE1)

| Element | BMK | Funktion |
| --- | --- | --- |
| Taster gruen | -S1 | Start, setzt die Freigabe (E0.0) |
| Taster rot | -S2 | Stop, Oeffner (E0.1) |
| Pilztaster rot | -S3 | Not-Halt, rastend, 2 Oeffner auf Sicherheitsrelais -K3 |
| Leuchte gruen | -H1 | Betrieb (A4.2) |
| Leuchte rot | -H2 | Stoerung (A4.3) |

## 3. Einschalten

1. Hauptschalter -Q1 im Schaltschrank +ST1 einschalten (Blatt /2.2).
2. Netzteil -T1 liefert 24 V DC an -X2 (Blatt /2.5). SPS -A1 laeuft hoch.
3. Not-Halt -S3 entriegeln. Sicherheitsrelais -K3 zieht an, Freigabekontakt 13/14 versorgt
   die Schuetzspulen, Kontakt 23/24 meldet E0.3 = 1 an die SPS (Blatt /4.4).
4. Start -S1 druecken. FB10 Netzwerk 1 setzt die Freigabe, -K1 zieht an (A4.0), -H1 leuchtet.

## 4. Ausschalten

Stop -S2 druecken. Die Freigabe faellt ab, -K1 faellt ab, das Band steht. Bei Gefahr
Not-Halt -S3 druecken: -K3 faellt ab und trennt die Schuetzspulen hardwareseitig,
unabhaengig von der SPS.

## 5. SPS-Belegung

Eingabebaugruppe -A1.1 (Blatt /5), Ausgabebaugruppe -A1.2 (Blatt /6):

| Adresse | Symbol | Bedeutung | Geraet | Klemme |
| --- | --- | --- | --- | --- |
| E0.0 | Start | Taster Start, Schliesser | -S1 | -X3:1 |
| E0.1 | Stop | Taster Stop, Oeffner (1 = nicht betaetigt) | -S2 | -X3:2 |
| E0.2 | MSS_OK | Motorschutz -F2 Hilfskontakt (1 = ok) | -F2 | -X3:3 |
| E0.3 | NotHalt_OK | Sicherheitsrelais -K3 Freigabe (1 = Not-Halt entriegelt) | -K3 | -X3:4 |
| E0.4 | LS_Einlauf | Lichtschranke Einlauf -B1 (1 = Teil erkannt) | -B1 | -X3:5 |
| E0.5 | LS_Auslauf | Lichtschranke Auslauf -B2 (1 = Teil erkannt) | -B2 | -X3:6 |
| A4.0 | K1_Vorwaerts | Schuetz -K1 Foerdermotor vorwaerts | -K1 | -X3:9 |
| A4.1 | K2_Rueckwaerts | Schuetz -K2 Foerdermotor rueckwaerts | -K2 | -X3:10 |
| A4.2 | H1_Betrieb | Meldeleuchte -H1 Betrieb gruen | -H1 | -X3:11 |
| A4.3 | H2_Stoerung | Meldeleuchte -H2 Stoerung rot | -H2 | -X3:12 |

## 6. Stoerungen und Fehlersuche

| Symptom | Moegliche Ursache | Pruefung |
| --- | --- | --- |
| -H2 leuchtet, Band steht, Start ohne Wirkung | Motorschutz -F2 ausgeloest (E0.2 = 0) | -F2 am Schaltschrank pruefen, Motorstrom -M1 messen (Nennstrom 3,5 A, Einstellung 3,6 A). Nach Abkuehlen -F2 einschalten, mit Start -S1 quittieren (FB10 Netzwerk 4). |
| -H2 leuchtet nach ca. 20 s Betrieb | Blockade: Teil am Einlauf -B1 erkannt, aber nicht am Auslauf -B2 (Timer T5, FB10 Netzwerk 5) | Band auf Verklemmung pruefen. Lichtschranke -B2 auf Verschmutzung und Ausrichtung pruefen (Klemme -X3:6, E0.5). |
| Start ohne Wirkung, -H1 aus, -H2 aus | Not-Halt nicht entriegelt oder -K3 ohne Freigabe (E0.3 = 0) | -S3 entriegeln. An -X3:4 muessen 24 V anliegen. Beide Kanaele -S3 11/12 und 21/22 pruefen (Blatt /4.2). |
| Start ohne Wirkung, E0.3 = 1 | Stop-Kreis unterbrochen (E0.1 = 0) | Leitung -W1 Ader zu -S2:11/12 pruefen, Klemme -X3:2. |
| Band laeuft, Stueckzahl MW100 zaehlt nicht | Lichtschranke -B1/-B2 defekt oder Versorgung fehlt | 24 V an -X3:7, 0 V an -X3:8 pruefen. Schaltausgang BK an -X3:5 bzw. -X3:6 (E0.4, E0.5) beobachten. |
| -K1 zieht an, Motor brummt, dreht nicht | Phase fehlt am Motorabgang | Spannung an -X4:U/V/W pruefen, Motorleitung -W4 und Klemmen -M1:U1/V1/W1 (Blatt /3.5). |
| Band laeuft in falscher Richtung | -K2 statt -K1 angesteuert (M20.0 gesetzt) oder Phasenfolge vertauscht | M20.0 zuruecksetzen. Bei Erstinbetriebnahme Phasenfolge an -X1 pruefen. |

## 7. Wartung

- Monatlich: Lichtschranken -B1, -B2 reinigen, Reflektoren pruefen.
- Halbjaehrlich: Not-Halt-Funktion pruefen (-S3 betaetigen, -K3 muss abfallen, -K1/-K2 stromlos).
- Jaehrlich: Motorstrom -M1 messen und mit Einstellung -F2 vergleichen, Klemmen -X4 nachziehen,
  Pruefung der elektrischen Anlage nach DGUV Vorschrift 3.
