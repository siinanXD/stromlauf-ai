# Betriebsanleitung Umroller UR-01

Anlage =L1, Schaltschrank +ST1, Feld +FE1. Testdokumentation fuer Stromlauf AI,
frei erfunden. Zugehoerige Dokumente: Stromlaufplan UR-01-E-001, Stueckliste UR-01, Klemmenplan UR-01,
SPS-Programm UR-01 (AWL, FB20/DB20/OB1), Symboltabelle UR-01.

## 1. Bestimmungsgemaesse Verwendung

Der Umroller UR-01 wickelt Tissue von zwei Mutterrollen (Abwickler -M1, -M2) zu Logs auf Huelsen. Die Bahn wird gepraegt (-M3), perforiert (-M4) und vom Wickler (-M5, Leitantrieb, 200 m/min) aufgewickelt. Die Huelsenzufuhr (-M6) legt Huelsen aus dem Magazin ein, der Logabschub (-M7) schiebt fertige Logs zur Saege. Alle Antriebe sitzen im Feld +FE1 (Antriebsblaetter ab /3.2). Zulaessige Bahnbreite 2,8 m, Logdurchmesser 90 bis 130 mm.

## 2. Antriebe

| Motor | Funktion | Kenndaten | Ansteuerung | Schutz | Blatt |
| --- | --- | --- | --- | --- | --- |
| -M1 | Abwickler 1 | 11 kW, 22 A, 1460 1/min | -U1 (Umrichter) | -F2 | /3.2 |
| -M2 | Abwickler 2 | 11 kW, 22 A, 1460 1/min | -U2 (Umrichter) | -F3 | /3.6 |
| -M3 | Praegewerk | 7.5 kW, 15.5 A, 1455 1/min | -U3 (Umrichter) | -F4 | /4.2 |
| -M4 | Perforation | 5.5 kW, 11.5 A, 1450 1/min | -U4 (Umrichter) | -F5 | /4.6 |
| -M5 | Wickler | 15 kW, 29 A, 1465 1/min | -U5 (Umrichter) | -F6 | /5.2 |
| -M6 | Huelsenzufuhr | 0.75 kW, 1.9 A, 1400 1/min | -K3 (Schuetz) | -F7 | /5.6 |
| -M7 | Logabschub | 1.1 kW, 2.6 A, 1400 1/min | -K4 (Schuetz) | -F8 | /6.2 |

## 3. Bedienelemente am Bedienpult (+FE1)

| Element | BMK | Funktion |
| --- | --- | --- |
| Taster gruen | -S4 | Start, setzt die Freigabe (E0.0, FB20 Netzwerk 1) |
| Taster rot | -S5 | Stop, Oeffner (E0.1) |
| Taster blau | -S6 | Stoerung quittieren (E0.2) |
| Wahlschalter | -S7 | Betriebsart Tippen fuer Praegewerk und Perforation (E0.3) |
| Taster schwarz | -S8 | Huelsenzufuhr Hand (E0.4) |
| Taster schwarz | -S9 | Logabschub Hand (E0.5) |
| Pilztaster rot | -S1, -S2, -S3 | Not-Halt, rastend, 2 Oeffner auf Sicherheitsrelais -K1 (Blatt /7.1) |
| Leuchte gruen | -H1 | Betrieb (A4.7) |
| Leuchte rot | -H2 | Stoerung (A5.0) |
| Leuchte gelb | -H3 | Huelsenmangel (A5.1) |
| Hupe | -H4 | Stoerung bis zur Quittierung (A5.2) |

## 4. Einschalten

1. Hauptschalter -Q1 im Schaltschrank einschalten (Blatt /2.2).
2. Netzteil -T1 liefert 24 V DC an -X2; SPS -A1 und Umrichter -U1 bis -U5 laufen hoch (Bereitmeldung E2.0 bis E2.4).
3. Not-Halt -S1, -S2, -S3 entriegeln und alle Schutztueren -S10 bis -S13 schliessen. -K1 und -K2 ziehen an (Blatt /7.1).
4. Mutterrollen einlegen, Bahn einfaedeln, Huelsenmagazin fuellen (-B5 frei).
5. Start -S4 druecken. FB20 Netzwerk 1 setzt die Freigabe, -U5 (Wickler) bekommt die Freigabe A4.4, -H1 leuchtet.

## 5. Ausschalten und Not-Halt

Stop -S5 druecken: die Freigabe faellt ab, alle Umrichter-Freigaben (A4.0 bis A4.4) werden zurueckgenommen, die Antriebe bremsen geregelt. Bei Gefahr Not-Halt druecken: -K1 faellt ab, die sicher abgeschaltete Umrichter-Freigabe (STO) und die Schuetzspulen -K3 / -K4 werden hardwareseitig getrennt, unabhaengig von der SPS.

## 6. SPS-Belegung

| Adresse | Symbol | Bedeutung | Geraet | Klemme |
| --- | --- | --- | --- | --- |
| E0.0 | Start | Taster -S4 Start, Schliesser | -S4 | -X3:1 |
| E0.1 | Stop | Taster -S5 Stop, Oeffner (1 = nicht betaetigt) | -S5 | -X3:2 |
| E0.2 | Quitt | Taster -S6 Stoerung quittieren | -S6 | -X3:3 |
| E0.3 | Tippen | Wahlschalter -S7 Betriebsart Tippen | -S7 | -X3:4 |
| E0.4 | Huelse_Hand | Taster -S8 Huelsenzufuhr Hand | -S8 | -X3:5 |
| E0.5 | Abschub_Hand | Taster -S9 Logabschub Hand | -S9 | -X3:6 |
| E0.6 | Bahnriss1 | Ultraschallsensor -B1 Bahnriss Abwickler 1 (1 = Bahn fehlt) | -B1 | -X3:7 |
| E0.7 | Bahnriss2 | Ultraschallsensor -B2 Bahnriss Abwickler 2 (1 = Bahn fehlt) | -B2 | -X3:8 |
| E1.0 | Rolle1_Min | Sensor -B3 Mutterrolle 1 Restdurchmesser erreicht | -B3 | -X3:9 |
| E1.1 | Rolle2_Min | Sensor -B4 Mutterrolle 2 Restdurchmesser erreicht | -B4 | -X3:10 |
| E1.2 | NotHalt_OK | Sicherheitsrelais -K1 Freigabe (1 = Not-Halt entriegelt) | -K1 | -X3:11 |
| E1.3 | Tuer_OK | Sicherheitsrelais -K2 Freigabe (1 = Schutztueren zu) | -K2 | -X3:12 |
| E1.4 | Huelse_Leer | Kapazitiver Sensor -B5 Huelsenmagazin leer | -B5 | -X3:13 |
| E1.5 | Log_Fertig | Lichtschranke -B6 Log fertig gewickelt | -B6 | -X3:14 |
| E1.6 | Abschub_Ende | Endschalter -B7 Logabschub Endlage | -B7 | -X3:15 |
| E1.7 | Huelse_Da | Lichtschranke -B8 Huelse eingelegt | -B8 | -X3:16 |
| E2.0 | U1_Bereit | Umrichter -U1 betriebsbereit (DO1) | -U1 | -X3:17 |
| E2.1 | U2_Bereit | Umrichter -U2 betriebsbereit (DO1) | -U2 | -X3:18 |
| E2.2 | U3_Bereit | Umrichter -U3 betriebsbereit (DO1) | -U3 | -X3:19 |
| E2.3 | U4_Bereit | Umrichter -U4 betriebsbereit (DO1) | -U4 | -X3:20 |
| E2.4 | U5_Bereit | Umrichter -U5 betriebsbereit (DO1) | -U5 | -X3:21 |
| E2.5 | MSS_Huelse_OK | Motorschutz -F7 Hilfskontakt (1 = ok) | -F7 | -X3:22 |
| E2.6 | MSS_Abschub_OK | Motorschutz -F8 Hilfskontakt (1 = ok) | -F8 | -X3:23 |
| A4.0 | U1_Frei | Freigabe Umrichter -U1 Abwickler 1 | -U1 | -X3:26 |
| A4.1 | U2_Frei | Freigabe Umrichter -U2 Abwickler 2 | -U2 | -X3:27 |
| A4.2 | U3_Frei | Freigabe Umrichter -U3 Praegewerk | -U3 | -X3:28 |
| A4.3 | U4_Frei | Freigabe Umrichter -U4 Perforation | -U4 | -X3:29 |
| A4.4 | U5_Frei | Freigabe Umrichter -U5 Wickler | -U5 | -X3:30 |
| A4.5 | K3_Huelse | Schuetz -K3 Huelsenzufuhr -M6 | -K3 | -X3:31 |
| A4.6 | K4_Abschub | Schuetz -K4 Logabschub -M7 | -K4 | -X3:32 |
| A4.7 | H1_Betrieb | Meldeleuchte -H1 Betrieb gruen | -H1 | -X3:33 |
| A5.0 | H2_Stoerung | Meldeleuchte -H2 Stoerung rot | -H2 | -X3:34 |
| A5.1 | H3_Huelsenmangel | Meldeleuchte -H3 Huelsenmangel gelb | -H3 | -X3:35 |
| A5.2 | H4_Hupe | Hupe -H4 Stoerung | -H4 | -X3:36 |

## 7. Stoerungen und Fehlersuche

| Symptom | Moegliche Ursache | Pruefung |
| --- | --- | --- |
| -H2 leuchtet, Hupe -H4, Anlage steht | Bahnriss an Abwickler 1 oder 2 (E0.6 / E0.7 = 1, FB20 Netzwerk 2) | Bahn an -B1 bzw. -B2 pruefen, Bahn neu einfaedeln. Sensor auf Verschmutzung und Abstand pruefen (Blatt /9.6). Mit -S6 quittieren. |
| -H2 leuchtet, ein Umrichter meldet Fehler | Umrichter -U1 bis -U5 nicht bereit (E2.0 bis E2.4 = 0, FB20 Netzwerk 3) | Fehlernummer am Umrichter lesen (Blatt /3.2 ff.). Ueberstrom: Antrieb mechanisch pruefen. Nach Beheben Umrichter quittieren, dann -S6. |
| Start ohne Wirkung, -H1 aus, -H2 aus | Not-Halt nicht entriegelt oder Sicherheitsrelais -K1 ohne Freigabe (E1.2 = 0) | -S1, -S2 und -S3 entriegeln. Beide Kanaele 11/12 und 21/22 pruefen (Blatt /7.1). An Klemme -X3:11 muessen 24 V anliegen. |
| Start ohne Wirkung, Schutztuer geschlossen | Schutztuerschalter -S10 bis -S13 nicht betaetigt oder -K2 ohne Freigabe (E1.3 = 0) | Tuerschalter und Betaetiger pruefen (Blatt /7.4). Klemme -X3:12 messen. Betaetiger auf Verschleiss pruefen. |
| Start ohne Wirkung, E1.2 und E1.3 = 1 | Stop-Kreis unterbrochen (E0.1 = 0) oder Stoerung nicht quittiert | Leitung -W1 Ader zu -S5:11/12 pruefen und Klemme -X3:2 messen; danach -H2 beobachten und mit -S6 quittieren. |
| Huelsenzufuhr laeuft nicht, -H3 gelb | Huelsenmagazin leer (-B5, E1.4 = 1) | Magazin fuellen. Sensor -B5 pruefen (Blatt /10.6). |
| Huelsenzufuhr laeuft nicht, -H3 aus | Motorschutz -F7 ausgeloest (E2.5 = 0) oder Huelse bereits eingelegt (-B8) | -F7 pruefen, Motorstrom -M6 messen (Nennstrom 1,9 A, Einstellung 2,0 A; Blatt /5.6). Lichtschranke -B8 pruefen. |
| Log wird nicht ausgeschoben | Motorschutz -F8 ausgeloest (E2.6 = 0) oder Endschalter -B7 haengt (E1.6 = 1) | -F8 pruefen (Blatt /6.2), Schuetz -K4 auf Ansteuerung A4.6 pruefen (Klemme -X3:32). Endschalter -B7 und Rollenhebel pruefen. |
| Abwickler 1 stoppt, Anlage laeuft weiter | Restdurchmesser Mutterrolle 1 erreicht (-B3, E1.0 = 1), Rollenwechsel angefordert (M10.1) | Mutterrolle wechseln. Steht die Rolle nicht am Ende: Sensor -B3 Abstand pruefen (Blatt /9.5). |
| Logzahl MW100 zaehlt nicht | Lichtschranke -B6 defekt, verschmutzt oder Versorgung fehlt | 24 V an -X3:24, 0 V an -X3:25 pruefen. Schaltausgang BK an -X3:14 (E1.5) beobachten (Blatt /10.5). |
| Praegewerk oder Perforation laufen im Tippbetrieb nicht | Wahlschalter -S7 nicht auf Tippen (E0.3 = 0) oder Schutztuer offen | -S7 auf Tippen stellen, Start -S4 gedrueckt halten, Tueren schliessen (FB20 Netzwerk 8). |
| Motor brummt, dreht nicht (Huelsenzufuhr oder Logabschub) | Phase fehlt am Motorabgang | Spannung an -X9:U/V/W bzw. -X10:U/V/W pruefen, Motorleitung und Klemmen -M6 / -M7 (Blatt /5.6). |

## 8. Wartung

- Taeglich: Sensoren -B1, -B2 (Bahnriss) und -B6, -B8 (Lichtschranken) reinigen.
- Woechentlich: Huelsenmagazin und Sensor -B5 reinigen, Logabschub -M7 auf Leichtgaengigkeit pruefen.
- Halbjaehrlich: Not-Halt-Funktion (-S1 bis -S3) und Schutztueren (-S10 bis -S13) pruefen: -K1 bzw. -K2 muss abfallen, Umrichter-Freigabe weg.
- Jaehrlich: Motorstroeme -M1 bis -M7 messen und mit den Einstellungen der Schutzorgane vergleichen; Klemmen -X4 bis -X10 nachziehen; Pruefung nach DGUV Vorschrift 3.
