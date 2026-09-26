# Betriebsanleitung Aufrollung PM1-AR

Anlage =PM1, Schaltschrank +ST6, Feld +FE6. Testdokumentation fuer Stromlauf AI,
frei erfunden. Zugehoerige Dokumente: Stromlaufplan PM1-AR-E-001, Stueckliste PM1-AR, Klemmenplan PM1-AR,
SPS-Programm PM1-AR (AWL, FB30/DB30/OB1), Symboltabelle PM1-AR.

## 1. Bestimmungsgemaesse Verwendung

Die Aufrollung PM1-AR wickelt die Tissuebahn der Papiermaschine PM1 (2,8 m breit, bis 2.200 m/min) auf Tambours. Die Tragtrommel (-M1, Leitantrieb) treibt den Tambour, der Tambourantrieb (-M2) beschleunigt den Leertambour vor dem Wechsel. Die Wechselarme werden hydraulisch bewegt (Pumpe -M3, Ventile -Y1 bis -Y3), die Lager werden von der Oelumlaufpumpe -M4 versorgt. Der Tambourwechsel laeuft als Schrittkette in FB30 (M30.0 bis M30.3). Alle Antriebe sitzen im Feld /3.2.

## 2. Antriebe

| Motor | Funktion | Kenndaten | Ansteuerung | Schutz | Blatt |
| --- | --- | --- | --- | --- | --- |
| -M1 | Tragtrommel | 75 kW, 138 A, 1485 1/min | -U1 (Umrichter) | -F2 | /3.2 |
| -M2 | Tambourantrieb | 30 kW, 56 A, 1475 1/min | -U2 (Umrichter) | -F3 | /3.6 |
| -M3 | Hydraulikpumpe Wechselarme | 11 kW, 22 A, 1460 1/min | -K3 (Schuetz) | -F4 | /4.2 |
| -M4 | Oelumlaufpumpe Lager | 3 kW, 6.5 A, 1420 1/min | -K4 (Schuetz) | -F5 | /4.6 |

## 3. Bedienelemente am Bedienpult (+FE6)

| Element | BMK | Funktion |
| --- | --- | --- |
| Taster gruen | -S5 | Start, setzt die Freigabe (E0.0, FB30 Netzwerk 1) |
| Taster rot | -S6 | Stop, Oeffner (E0.1) |
| Taster blau | -S7 | Stoerung quittieren (E0.2) |
| Taster schwarz | -S8 | Tambourwechsel Hand (E0.3) |
| Wahlschalter | -S9 | Betriebsart Automatik: Wechsel bei Solldurchmesser -B1 (E0.4) |
| Pilztaster rot | -S1, -S2, -S3 | Not-Halt, rastend, 2 Oeffner auf Sicherheitsrelais -K1 (Blatt /5.1) |
| Reissleine | -S4 | Not-Halt entlang der Tragtrommel, 2 Oeffner auf -K1 |
| Leuchte gruen | -H1 | Betrieb (A4.7) |
| Leuchte rot | -H2 | Stoerung (A5.0) |
| Leuchte gelb | -H3 | Tambourwechsel angefordert (A5.1) |
| Hupe | -H4 | Stoerung bis zur Quittierung (A5.2) |

## 4. Einschalten

1. Hauptschalter -Q1 im Schaltschrank einschalten (Blatt /2.2).
2. Netzteil -T1 liefert 24 V DC an -X2; SPS -A1 und Umrichter -U1, -U2 laufen hoch (Bereitmeldung E1.6, E1.7).
3. Not-Halt -S1 bis -S3 und Reissleine -S4 entriegeln, Schutztueren -S10, -S11 schliessen. -K1 und -K2 ziehen an (Blatt /5.1).
4. Oelumlaufpumpe -M4 laeuft an (A4.3); nach 10 s muss der Oelstand -B4 ok melden.
5. Leertambour einlegen (-B7), Start -S5 druecken. FB30 Netzwerk 1 setzt die Freigabe, Hydraulikpumpe -M3 laeuft an, -U1 bekommt A4.0, -H1 leuchtet.

## 5. Ausschalten und Not-Halt

Stop -S6 druecken: die Freigabe faellt ab, die Umrichter-Freigaben A4.0 und A4.1 werden zurueckgenommen, Tragtrommel und Tambour bremsen geregelt; die Oelpumpe laeuft weiter. Bei Gefahr Not-Halt oder Reissleine betaetigen: -K1 faellt ab, STO der Umrichter und die Schuetzspulen -K3 / -K4 werden hardwareseitig getrennt.

## 6. SPS-Belegung

| Adresse | Symbol | Bedeutung | Geraet | Klemme |
| --- | --- | --- | --- | --- |
| E0.0 | Start | Taster -S5 Start, Schliesser | -S5 | -X3:1 |
| E0.1 | Stop | Taster -S6 Stop, Oeffner (1 = nicht betaetigt) | -S6 | -X3:2 |
| E0.2 | Quitt | Taster -S7 Stoerung quittieren | -S7 | -X3:3 |
| E0.3 | Wechsel_Hand | Taster -S8 Tambourwechsel Hand | -S8 | -X3:4 |
| E0.4 | Automatik | Wahlschalter -S9 Betriebsart Automatik | -S9 | -X3:5 |
| E0.5 | Durchm_OK | Laser-Distanzsensor -B1 Tambourdurchmesser erreicht | -B1 | -X3:6 |
| E0.6 | Bahnriss | Ultraschallsensor -B2 Bahnriss vor Tragtrommel (1 = Bahn fehlt) | -B2 | -X3:7 |
| E0.7 | Druck_OK | Druckschalter -B3 Hydraulikdruck 150 bar erreicht | -B3 | -X3:8 |
| E1.0 | Oel_OK | Schwimmerschalter -B4 Oelstand Lagerschmierung ok | -B4 | -X3:9 |
| E1.1 | Arm_Aus | Naeherungsschalter -B5 Wechselarm ausgefahren | -B5 | -X3:10 |
| E1.2 | Arm_Grund | Naeherungsschalter -B6 Wechselarm Grundstellung | -B6 | -X3:11 |
| E1.3 | Tambour_Da | Lichtschranke -B7 Leertambour eingelegt | -B7 | -X3:12 |
| E1.4 | NotHalt_OK | Sicherheitsrelais -K1 Freigabe (1 = Not-Halt und Reissleine entriegelt) | -K1 | -X3:13 |
| E1.5 | Tuer_OK | Sicherheitsrelais -K2 Freigabe (1 = Schutztueren zu) | -K2 | -X3:14 |
| E1.6 | U1_Bereit | Umrichter -U1 Tragtrommel betriebsbereit (DO1) | -U1 | -X3:15 |
| E1.7 | U2_Bereit | Umrichter -U2 Tambourantrieb betriebsbereit (DO1) | -U2 | -X3:16 |
| E2.0 | MSS_Hydr_OK | Motorschutz -F4 Hilfskontakt (1 = ok) | -F4 | -X3:17 |
| E2.1 | MSS_Oel_OK | Motorschutz -F5 Hilfskontakt (1 = ok) | -F5 | -X3:18 |
| E2.2 | Oeltemp_OK | Thermostat -B8 Oeltemperatur unter 60 Grad | -B8 | -X3:19 |
| A4.0 | U1_Frei | Freigabe Umrichter -U1 Tragtrommel | -U1 | -X3:22 |
| A4.1 | U2_Frei | Freigabe Umrichter -U2 Tambourantrieb | -U2 | -X3:23 |
| A4.2 | K3_Hydr | Schuetz -K3 Hydraulikpumpe -M3 | -K3 | -X3:24 |
| A4.3 | K4_Oel | Schuetz -K4 Oelumlaufpumpe -M4 | -K4 | -X3:25 |
| A4.4 | Y1_Aus | Magnetventil -Y1 Wechselarm ausfahren | -Y1 | -X3:26 |
| A4.5 | Y2_Rueck | Magnetventil -Y2 Wechselarm zurueck | -Y2 | -X3:27 |
| A4.6 | Y3_Trenn | Magnetventil -Y3 Trennmesser | -Y3 | -X3:28 |
| A4.7 | H1_Betrieb | Meldeleuchte -H1 Betrieb gruen | -H1 | -X3:29 |
| A5.0 | H2_Stoerung | Meldeleuchte -H2 Stoerung rot | -H2 | -X3:30 |
| A5.1 | H3_Wechsel | Meldeleuchte -H3 Tambourwechsel angefordert gelb | -H3 | -X3:31 |
| A5.2 | H4_Hupe | Hupe -H4 Stoerung | -H4 | -X3:32 |

## 7. Stoerungen und Fehlersuche

| Symptom | Moegliche Ursache | Pruefung |
| --- | --- | --- |
| -H2 leuchtet, Hupe -H4, Aufrollung steht | Bahnriss vor der Tragtrommel (-B2, E0.6 = 1, FB30 Netzwerk 6) | Bahn neu einfuehren. Sensor -B2 auf Verschmutzung und Abstand pruefen (Blatt /7.6). Mit -S7 quittieren. |
| -H2 leuchtet, Tragtrommel laeuft nicht an | Umrichter -U1 nicht bereit (E1.6 = 0, FB30 Netzwerk 7) | Fehlernummer an -U1 lesen (Blatt /3.2). Leistungsschalter -F2 pruefen. Nach Beheben Umrichter quittieren, dann -S7. |
| Start ohne Wirkung, -H1 aus, -H2 aus | Not-Halt oder Reissleine nicht entriegelt, -K1 ohne Freigabe (E1.4 = 0) | -S1, -S2, -S3 und Reissleine -S4 entriegeln. Beide Kanaele pruefen (Blatt /5.1). An Klemme -X3:13 muessen 24 V anliegen. |
| Start ohne Wirkung, Schutztuer geschlossen | Schutztuerschalter -S10 / -S11 nicht betaetigt oder -K2 ohne Freigabe (E1.5 = 0) | Tuerschalter und Betaetiger pruefen (Blatt /5.4). Klemme -X3:14 messen. |
| Stoerung 10 s nach dem Einschalten, Oelpumpe laeuft | Oelstand zu niedrig (-B4, E1.0 = 0) oder Oel zu heiss (-B8, E2.2 = 0), FB30 Netzwerk 3 | Oelstand am Schauglas pruefen, Oel nachfuellen. Schwimmerschalter -B4 und Thermostat -B8 pruefen (Blatt /7.6). Oelkuehler pruefen. |
| Stoerung 5 s nach Start, Hydraulikpumpe laeuft | Hydraulikdruck 150 bar nicht erreicht (-B3, E0.7 = 0), FB30 Netzwerk 5 | Druck am Manometer pruefen. Druckbegrenzungsventil und Pumpe -M3 pruefen. Druckschalter -B3 pruefen (Blatt /7.5). |
| Hydraulikpumpe laeuft nicht | Motorschutz -F4 ausgeloest (E2.0 = 0) | -F4 pruefen, Motorstrom -M3 messen (Nennstrom 22 A, Einstellung 23 A; Blatt /4.2). Schuetz -K3 auf Ansteuerung A4.2 pruefen. |
| Tambourwechsel startet nicht, -H3 leuchtet | Wechselarm nicht in Grundstellung (-B6, E1.2 = 0) oder Schutztuer offen | Arm mit -S8 in Grundstellung fahren. Naeherungsschalter -B6 pruefen (Blatt /7.6). Schrittkette M30.0 bis M30.3 in FB30 beobachten. |
| Wechselarm faehrt nicht aus (Schritt 2) | Magnetventil -Y1 ohne Ansteuerung (A4.4) oder Hydraulikdruck fehlt | Spannung an Klemme -X3:24 pruefen (Blatt /10.5). Ventil -Y1 auf Verschmutzung pruefen. Druck -B3 pruefen. |
| Trennmesser schneidet nicht (Schritt 3) | Magnetventil -Y3 ohne Ansteuerung (A4.6) oder Messer stumpf | Spannung an Klemme -X3:26 pruefen (Blatt /10.5). Messer pruefen. Endlage -B5 muss E1.1 = 1 melden. |
| Tambourantrieb -M2 laeuft nicht mit | Leertambour nicht erkannt (-B7, E1.3 = 0) oder -U2 nicht bereit | Lichtschranke -B7 pruefen (Blatt /7.5). Umrichter -U2 Fehlernummer lesen, -F3 pruefen. |
| Tambourzahl MW102 zaehlt nicht | Naeherungsschalter -B6 Grundstellung ohne Flanke | 24 V an -X3:20, 0 V an -X3:21 pruefen. Schaltausgang -B6 an -X3:11 (E1.2) beobachten (Blatt /7.6). |

## 8. Wartung

- Taeglich: Sensoren -B1 (Laser) und -B2 (Bahnriss) reinigen, Oelstand am Schauglas pruefen.
- Woechentlich: Hydraulikdruck am Manometer mit -B3 vergleichen (150 bar), Ventile -Y1 bis -Y3 auf Leckage pruefen.
- Halbjaehrlich: Not-Halt (-S1 bis -S3), Reissleine -S4 und Schutztueren (-S10, -S11) pruefen: -K1 bzw. -K2 muss abfallen.
- Jaehrlich: Motorstroeme -M1 bis -M4 messen und mit den Einstellungen vergleichen; Klemmen -X4 bis -X7 nachziehen; Pruefung nach DGUV Vorschrift 3.
