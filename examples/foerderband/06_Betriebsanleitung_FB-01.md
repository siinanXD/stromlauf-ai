# Betriebsanleitung Förderband FB-01

Anlage =FB1: Schaltschrank +ST1, Bedienpult +BP1, Antrieb +AN1, Einlauf +SE1, Auslauf +SA1. Beispielanlage für Stromlauf AI,
frei erfunden. Zugehörige Dokumente: Stromlaufplan FB-01-E-001 (7 Blätter), Stückliste FB-01,
Klemmenplan FB-01, SPS-Programm FB-01 (AWL, FB10/DB10/OB1), Symboltabelle FB-01.

## 1. Bestimmungsgemäße Verwendung

Das Förderband FB-01 transportiert Werkstücke bis 25 kg vom Einlauf (+SE1) zum Auslauf (+SA1). Der
Fördermotor -M1 (1,5 kW, 400 V, 3,5 A) am Antrieb +AN1 läuft im Normalbetrieb vorwärts. Rückwärtsbetrieb
ist nur für Wartungsarbeiten vorgesehen (Merker M20.0 über Bedienpanel). Der Reparaturschalter -Q2 am
Antrieb trennt den Motor allpolig für Arbeiten am Band.

## 2. Bedienelemente am Bedienpult (+BP1)

| Element | BMK | Funktion |
| --- | --- | --- |
| Taster grün | -S1 | Start, setzt die Freigabe (E0.0) |
| Taster rot | -S2 | Stop, Öffner (E0.1) |
| Pilztaster rot | -S3 | Not-Halt, rastend, 2 Öffner auf Sicherheitsrelais -K3 |
| Leuchte grün | -H1 | Betrieb (A4.2) |
| Leuchte rot | -H2 | Störung (A4.3) |
| Leuchte gelb | -H3 | Not-Halt betätigt, Meldekontakt -K3 31/32 (Blatt /4.8), ohne SPS |
| Zählwerk | -P1 | Betriebsstundenzähler, läuft parallel zu -H1 (Blatt /6.6) |

## 3. Einschalten

1. Hauptschalter -Q1 im Schaltschrank +ST1 einschalten (Blatt /2.2). Reparaturschalter -Q2 am Antrieb +AN1
   muss eingeschaltet sein (Blatt /3.5).
2. Netzteil -T1 liefert 24 V DC an -X2 (Blatt /2.5); -F3 sichert den Steuerkreis zum Bedienpult (Blatt /2.6).
   SPS -A1 läuft hoch.
3. Not-Halt -S3 entriegeln. Sicherheitsrelais -K3 zieht an, Freigabekontakt 13/14 versorgt
   die Schützspulen, Kontakt 23/24 meldet E0.3 = 1 an die SPS (Blatt /4.4), -H3 erlischt.
4. Start -S1 drücken. FB10 Netzwerk 1 setzt die Freigabe, -K1 zieht an (A4.0), -H1 leuchtet, -P1 zählt.

## 4. Ausschalten

Stop -S2 drücken. Die Freigabe fällt ab, -K1 fällt ab, das Band steht. Bei Gefahr
Not-Halt -S3 drücken: -K3 fällt ab und trennt die Schützspulen hardwareseitig,
unabhängig von der SPS.

## 5. SPS-Belegung

Eingabebaugruppe -A1.1 (Blatt /5), Ausgabebaugruppe -A1.2 (Blatt /6):

| Adresse | Symbol | Bedeutung | Gerät | Klemme |
| --- | --- | --- | --- | --- |
| E0.0 | Start | Taster Start, Schließer | -S1 | -X3:1 |
| E0.1 | Stop | Taster Stop, Öffner (1 = nicht betätigt) | -S2 | -X3:2 |
| E0.2 | MSS_OK | Motorschutz -F2 Hilfskontakt (1 = ok) | -F2 | -X3:3 |
| E0.3 | NotHalt_OK | Sicherheitsrelais -K3 Freigabe (1 = Not-Halt entriegelt) | -K3 | -X3:4 |
| E0.4 | LS_Einlauf | Lichtschranke Einlauf -B1 (1 = Teil erkannt) | -B1 | -X3:5 |
| E0.5 | LS_Auslauf | Lichtschranke Auslauf -B2 (1 = Teil erkannt) | -B2 | -X3:6 |
| A4.0 | K1_Vorwaerts | Schütz -K1 Fördermotor vorwärts | -K1 | -X3:9 |
| A4.1 | K2_Rueckwaerts | Schütz -K2 Fördermotor rückwärts | -K2 | -X3:10 |
| A4.2 | H1_Betrieb | Meldeleuchte -H1 Betrieb grün | -H1 | -X3:11 |
| A4.3 | H2_Stoerung | Meldeleuchte -H2 Störung rot | -H2 | -X3:12 |

## 6. Störungen und Fehlersuche

| Symptom | Mögliche Ursache | Prüfung |
| --- | --- | --- |
| -H2 leuchtet, Band steht, Start ohne Wirkung | Motorschutz -F2 ausgelöst (E0.2 = 0) | -F2 am Schaltschrank prüfen, Motorstrom -M1 messen (Nennstrom 3,5 A, Einstellung 3,6 A). Nach Abkühlen -F2 einschalten, mit Start -S1 quittieren (FB10 Netzwerk 4). |
| -H2 leuchtet nach ca. 20 s Betrieb | Blockade: Teil am Einlauf -B1 erkannt, aber nicht am Auslauf -B2 (Timer T5, FB10 Netzwerk 5) | Band auf Verklemmung prüfen. Lichtschranke -B2 auf Verschmutzung und Ausrichtung prüfen (Klemme -X3:6, E0.5). |
| Start ohne Wirkung, -H1 aus, -H2 aus, -H3 leuchtet | Not-Halt nicht entriegelt oder -K3 ohne Freigabe (E0.3 = 0) | -S3 entriegeln. An -X3:4 müssen 24 V anliegen. Beide Kanäle -S3 11/12 und 21/22 prüfen (Blatt /4.2). |
| -K1 zieht an, -H1 leuchtet, Motor steht ohne Brummen | Reparaturschalter -Q2 am Antrieb ausgeschaltet | Stellung -Q2 prüfen (Blatt /3.5); nur einschalten, wenn niemand am Band arbeitet. |
| Start ohne Wirkung, E0.3 = 1 | Stop-Kreis unterbrochen (E0.1 = 0) | Leitung -W1 Ader zu -S2:11/12 prüfen, Klemme -X3:2. |
| Band läuft, Stückzahl MW100 zählt nicht | Lichtschranke -B1/-B2 defekt oder Versorgung fehlt | 24 V an -X3:7, 0 V an -X3:8 prüfen. Schaltausgang BK an -X3:5 bzw. -X3:6 (E0.4, E0.5) beobachten. |
| -K1 zieht an, Motor brummt, dreht nicht | Phase fehlt am Motorabgang | Spannung an -X4:U/V/W prüfen, Motorleitung -W4 und Klemmen -M1:U1/V1/W1 (Blatt /3.5). |
| Band läuft in falscher Richtung | -K2 statt -K1 angesteuert (M20.0 gesetzt) oder Phasenfolge vertauscht | M20.0 zurücksetzen. Bei Erstinbetriebnahme Phasenfolge an -X1 prüfen. |

## 7. Wartung

- Vor jeder Arbeit am Band: Reparaturschalter -Q2 am Antrieb +AN1 ausschalten und abschließen.
- Monatlich: Lichtschranken -B1 (+SE1) und -B2 (+SA1) reinigen, Reflektoren prüfen.
- Halbjährlich: Not-Halt-Funktion prüfen (-S3 betätigen, -K3 muss abfallen, -K1/-K2 stromlos).
- Jährlich: Motorstrom -M1 messen und mit Einstellung -F2 vergleichen, Klemmen -X4 nachziehen,
  Prüfung der elektrischen Anlage nach DGUV Vorschrift 3.
