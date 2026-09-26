"""UR-01 Umroller Toilettenpapier (Linie L1 des Testwerks).

Zwei Abwickler, Praegewerk, Perforation und Wickler an Frequenzumrichtern (PROFIBUS DP),
Huelsenzufuhr und Logabschub ueber Schuetze, vier Schutztueren, drei Not-Halt, Bedienpult.
"""

from model import Device, Drive, Fault, Machine, SafetyCircuit, Signal

DRIVES = [
    Drive("-M1", "Abwickler 1", 11, 22, 1460, "-F2", "Leistungsschalter Abwickler 1", "In 25 A", "-U1", "Frequenzumrichter Abwickler 1", "vfd", "-X4", 3),
    Drive("-M2", "Abwickler 2", 11, 22, 1460, "-F3", "Leistungsschalter Abwickler 2", "In 25 A", "-U2", "Frequenzumrichter Abwickler 2", "vfd", "-X5", 4),
    Drive("-M3", "Praegewerk", 7.5, 15.5, 1455, "-F4", "Leistungsschalter Praegewerk", "In 20 A", "-U3", "Frequenzumrichter Praegewerk", "vfd", "-X6", 5),
    Drive("-M4", "Perforation", 5.5, 11.5, 1450, "-F5", "Leistungsschalter Perforation", "In 16 A", "-U4", "Frequenzumrichter Perforation", "vfd", "-X7", 6),
    Drive("-M5", "Wickler", 15, 29, 1465, "-F6", "Leistungsschalter Wickler", "In 32 A", "-U5", "Frequenzumrichter Wickler", "vfd", "-X8", 7),
    Drive("-M6", "Huelsenzufuhr", 0.75, 1.9, 1400, "-F7", "Motorschutzschalter Huelsenzufuhr", "Einstellung 2,0 A", "-K3", "Schuetz Huelsenzufuhr", "contactor", "-X9"),
    Drive("-M7", "Logabschub", 1.1, 2.6, 1400, "-F8", "Motorschutzschalter Logabschub", "Einstellung 2,8 A", "-K4", "Schuetz Logabschub", "contactor", "-X10"),
]

INPUTS = [
    Signal("E0.0", "Start", "Taster -S4 Start, Schliesser", "-S4", "cmd_no", ("13", "14")),
    Signal("E0.1", "Stop", "Taster -S5 Stop, Oeffner (1 = nicht betaetigt)", "-S5", "cmd_nc", ("11", "12")),
    Signal("E0.2", "Quitt", "Taster -S6 Stoerung quittieren", "-S6", "cmd_no", ("13", "14")),
    Signal("E0.3", "Tippen", "Wahlschalter -S7 Betriebsart Tippen", "-S7", "cmd_no", ("13", "14")),
    Signal("E0.4", "Huelse_Hand", "Taster -S8 Huelsenzufuhr Hand", "-S8", "cmd_no", ("13", "14")),
    Signal("E0.5", "Abschub_Hand", "Taster -S9 Logabschub Hand", "-S9", "cmd_no", ("13", "14")),
    Signal("E0.6", "Bahnriss1", "Ultraschallsensor -B1 Bahnriss Abwickler 1 (1 = Bahn fehlt)", "-B1", "sensor", ("1", "4")),
    Signal("E0.7", "Bahnriss2", "Ultraschallsensor -B2 Bahnriss Abwickler 2 (1 = Bahn fehlt)", "-B2", "sensor", ("1", "4")),
    Signal("E1.0", "Rolle1_Min", "Sensor -B3 Mutterrolle 1 Restdurchmesser erreicht", "-B3", "sensor", ("1", "4")),
    Signal("E1.1", "Rolle2_Min", "Sensor -B4 Mutterrolle 2 Restdurchmesser erreicht", "-B4", "sensor", ("1", "4")),
    Signal("E1.2", "NotHalt_OK", "Sicherheitsrelais -K1 Freigabe (1 = Not-Halt entriegelt)", "-K1", "aux", ("23", "24")),
    Signal("E1.3", "Tuer_OK", "Sicherheitsrelais -K2 Freigabe (1 = Schutztueren zu)", "-K2", "aux", ("23", "24")),
    Signal("E1.4", "Huelse_Leer", "Kapazitiver Sensor -B5 Huelsenmagazin leer", "-B5", "sensor", ("1", "4")),
    Signal("E1.5", "Log_Fertig", "Lichtschranke -B6 Log fertig gewickelt", "-B6", "sensor", ("1", "4")),
    Signal("E1.6", "Abschub_Ende", "Endschalter -B7 Logabschub Endlage", "-B7", "sensor", ("1", "4")),
    Signal("E1.7", "Huelse_Da", "Lichtschranke -B8 Huelse eingelegt", "-B8", "sensor", ("1", "4")),
    Signal("E2.0", "U1_Bereit", "Umrichter -U1 betriebsbereit (DO1)", "-U1", "aux", ("DO1", "COM")),
    Signal("E2.1", "U2_Bereit", "Umrichter -U2 betriebsbereit (DO1)", "-U2", "aux", ("DO1", "COM")),
    Signal("E2.2", "U3_Bereit", "Umrichter -U3 betriebsbereit (DO1)", "-U3", "aux", ("DO1", "COM")),
    Signal("E2.3", "U4_Bereit", "Umrichter -U4 betriebsbereit (DO1)", "-U4", "aux", ("DO1", "COM")),
    Signal("E2.4", "U5_Bereit", "Umrichter -U5 betriebsbereit (DO1)", "-U5", "aux", ("DO1", "COM")),
    Signal("E2.5", "MSS_Huelse_OK", "Motorschutz -F7 Hilfskontakt (1 = ok)", "-F7", "aux", ("13", "14")),
    Signal("E2.6", "MSS_Abschub_OK", "Motorschutz -F8 Hilfskontakt (1 = ok)", "-F8", "aux", ("13", "14")),
]

OUTPUTS = [
    Signal("A4.0", "U1_Frei", "Freigabe Umrichter -U1 Abwickler 1", "-U1", "vfd", ("DI1", "COM")),
    Signal("A4.1", "U2_Frei", "Freigabe Umrichter -U2 Abwickler 2", "-U2", "vfd", ("DI1", "COM")),
    Signal("A4.2", "U3_Frei", "Freigabe Umrichter -U3 Praegewerk", "-U3", "vfd", ("DI1", "COM")),
    Signal("A4.3", "U4_Frei", "Freigabe Umrichter -U4 Perforation", "-U4", "vfd", ("DI1", "COM")),
    Signal("A4.4", "U5_Frei", "Freigabe Umrichter -U5 Wickler", "-U5", "vfd", ("DI1", "COM")),
    Signal("A4.5", "K3_Huelse", "Schuetz -K3 Huelsenzufuhr -M6", "-K3", "coil", ("A1", "A2")),
    Signal("A4.6", "K4_Abschub", "Schuetz -K4 Logabschub -M7", "-K4", "coil", ("A1", "A2")),
    Signal("A4.7", "H1_Betrieb", "Meldeleuchte -H1 Betrieb gruen", "-H1", "lamp", ("X1", "X2")),
    Signal("A5.0", "H2_Stoerung", "Meldeleuchte -H2 Stoerung rot", "-H2", "lamp", ("X1", "X2")),
    Signal("A5.1", "H3_Huelsenmangel", "Meldeleuchte -H3 Huelsenmangel gelb", "-H3", "lamp", ("X1", "X2")),
    Signal("A5.2", "H4_Hupe", "Hupe -H4 Stoerung", "-H4", "horn", ("X1", "X2")),
]

FIELD = {d.motor for d in DRIVES} | {f"-S{i}" for i in range(1, 14)} | {f"-B{i}" for i in range(1, 9)} | {"-H1", "-H2", "-H3", "-H4"}

DEVICES = [
    Device("-Q1", "Hauptschalter 3-polig, 160 A", "Lasttrennschalter 3P 160A"),
    Device("-F1", "Leitungsschutzschalter Steuerspannung 230 V", "LS-Schalter 1P+N B6"),
    Device("-T1", "Netzteil 230 V AC / 24 V DC, 10 A", "Schaltnetzteil 24V/10A"),
] + [Device(d.breaker, d.breaker_name, "Motorschutzschalter 3P + Hilfskontakt 1S" if d.kind == "contactor" else "Leistungsschalter 3P, thermisch-magnetisch") for d in DRIVES] + [
    Device(d.switch, d.switch_name, f"Frequenzumrichter {d.kw:g} kW, 400 V, PROFIBUS DP, STO" if d.kind == "vfd" else "Leistungsschuetz 4 kW, Spule 24 V DC") for d in DRIVES
] + [
    Device("-K1", "Sicherheitsrelais Not-Halt, 2-kanalig", "Sicherheitsschaltgeraet Kat. 3 / PL d"),
    Device("-K2", "Sicherheitsrelais Schutztueren, 2-kanalig", "Sicherheitsschaltgeraet Kat. 3 / PL d"),
] + [Device(d.motor, f"Motor {d.name} 3~ {d.kw:g} kW, {d.rpm} 1/min", f"Drehstrommotor {d.kw:g} kW, IE3", in_field=True) for d in DRIVES] + [
    Device("-S1", "Not-Halt-Taster Bedienpult, 2 Oeffner, rastend", "Pilzdrucktaster 2OE", in_field=True),
    Device("-S2", "Not-Halt-Taster Abwickler, 2 Oeffner, rastend", "Pilzdrucktaster 2OE", in_field=True),
    Device("-S3", "Not-Halt-Taster Wickler, 2 Oeffner, rastend", "Pilzdrucktaster 2OE", in_field=True),
    Device("-S4", "Taster Start (Schliesser)", "Drucktaster gruen 1S", in_field=True),
    Device("-S5", "Taster Stop (Oeffner)", "Drucktaster rot 1OE", in_field=True),
    Device("-S6", "Taster Stoerung quittieren", "Drucktaster blau 1S", in_field=True),
    Device("-S7", "Wahlschalter Betriebsart Tippen", "Wahlschalter 2 Stellungen 1S", in_field=True),
    Device("-S8", "Taster Huelsenzufuhr Hand", "Drucktaster schwarz 1S", in_field=True),
    Device("-S9", "Taster Logabschub Hand", "Drucktaster schwarz 1S", in_field=True),
    Device("-S10", "Schutztuerschalter Abwickler 1, 2 Oeffner", "Sicherheitsschalter mit getrenntem Betaetiger 2OE", in_field=True),
    Device("-S11", "Schutztuerschalter Abwickler 2, 2 Oeffner", "Sicherheitsschalter mit getrenntem Betaetiger 2OE", in_field=True),
    Device("-S12", "Schutztuerschalter Praegewerk, 2 Oeffner", "Sicherheitsschalter mit getrenntem Betaetiger 2OE", in_field=True),
    Device("-S13", "Schutztuerschalter Wickler, 2 Oeffner", "Sicherheitsschalter mit getrenntem Betaetiger 2OE", in_field=True),
    Device("-B1", "Ultraschallsensor Bahnriss Abwickler 1", "Ultraschall-Reflexionstaster 24 V DC PNP", in_field=True),
    Device("-B2", "Ultraschallsensor Bahnriss Abwickler 2", "Ultraschall-Reflexionstaster 24 V DC PNP", in_field=True),
    Device("-B3", "Sensor Restdurchmesser Mutterrolle 1", "Induktiver Naeherungsschalter M18 PNP", in_field=True),
    Device("-B4", "Sensor Restdurchmesser Mutterrolle 2", "Induktiver Naeherungsschalter M18 PNP", in_field=True),
    Device("-B5", "Kapazitiver Sensor Huelsenmagazin leer", "Kapazitiver Sensor M30 PNP", in_field=True),
    Device("-B6", "Lichtschranke Log fertig", "Reflexionslichtschranke 24 V DC PNP", in_field=True),
    Device("-B7", "Endschalter Logabschub Endlage", "Positionsschalter Rollenhebel 1S", in_field=True),
    Device("-B8", "Lichtschranke Huelse eingelegt", "Einweglichtschranke 24 V DC PNP", in_field=True),
    Device("-H1", "Meldeleuchte Betrieb (gruen)", "LED-Leuchtmelder 24 V DC gruen", in_field=True),
    Device("-H2", "Meldeleuchte Stoerung (rot)", "LED-Leuchtmelder 24 V DC rot", in_field=True),
    Device("-H3", "Meldeleuchte Huelsenmangel (gelb)", "LED-Leuchtmelder 24 V DC gelb", in_field=True),
    Device("-H4", "Hupe Stoerung", "Summer 24 V DC 85 dB", in_field=True),
    Device("-A1", "SPS CPU, PROFIBUS DP Master", "SPS-Zentralbaugruppe"),
    Device("-A1.1", "Digitaleingabe 16 x 24 V DC (E0.0 bis E1.7)", "DI-Baugruppe 16 DI"),
    Device("-A1.2", "Digitaleingabe 16 x 24 V DC (E2.0 bis E3.7)", "DI-Baugruppe 16 DI"),
    Device("-A1.3", "Digitalausgabe 16 x 24 V DC / 0,5 A (A4.0 bis A5.7)", "DO-Baugruppe 16 DO"),
    Device("-X1", "Klemmleiste Netzeinspeisung", "Reihenklemme 50 mm2", 5),
    Device("-X2", "Klemmleiste 24 V Steuerspannung", "Reihenklemme 2,5 mm2", 8),
    Device("-X3", "Klemmleiste Feldgeraete (Sensoren, Taster, Umrichter-Signale, Sicherheitskreise)", "Reihenklemme 2,5 mm2"),
] + [Device(d.strip, f"Klemmleiste Motorabgang {d.motor}", "Reihenklemme 6 mm2" if d.kw > 5 else "Reihenklemme 2,5 mm2", 4) for d in DRIVES]

NETWORKS = """NETWORK
TITLE =Freigabe Betrieb
//Start setzt die Freigabe; Stop (Oeffner), Not-Halt, offene Schutztuer oder Stoerung setzen zurueck.
//Wiederanlaufsperre: nach Not-Halt ist ein neuer Start noetig.
      U(    ;
      O     #Start;
      O     #Freigabe;
      )     ;
      U     #Stop;
      U     #NotHalt_OK;
      U     #Tuer_OK;
      UN    #Stoerung;
      =     #Freigabe;
NETWORK
TITLE =Bahnriss
//Ultraschallsensoren -B1 / -B2 melden fehlende Bahn: Stoerung setzen, Anlage stoppt.
      U     #Bahnriss1;
      O     #Bahnriss2;
      =     #Bahnriss;
      U     #Bahnriss;
      U     #Freigabe;
      S     #Stoerung;
NETWORK
TITLE =Stoerung Umrichter
//Ein Umrichter nicht bereit (Sammelstoerung des Geraets): Stoerung setzen.
      U     #Freigabe;
      U(    ;
      ON    #U1_Bereit;
      ON    #U2_Bereit;
      ON    #U3_Bereit;
      ON    #U4_Bereit;
      ON    #U5_Bereit;
      )     ;
      S     #Stoerung;
NETWORK
TITLE =Stoerung Motorschutz
//Motorschutz -F7 (Huelsenzufuhr) oder -F8 (Logabschub) ausgeloest.
      UN    #MSS_Huelse_OK;
      ON    #MSS_Abschub_OK;
      S     #Stoerung;
NETWORK
TITLE =Quittierung
//Quittieren nur bei stehender Anlage, behobenem Bahnriss und bereiten Umrichtern.
      U     #Quitt;
      UN    #Freigabe;
      UN    #Bahnriss;
      U     #U1_Bereit;
      U     #U2_Bereit;
      U     #U3_Bereit;
      U     #U4_Bereit;
      U     #U5_Bereit;
      U     #MSS_Huelse_OK;
      U     #MSS_Abschub_OK;
      R     #Stoerung;
NETWORK
TITLE =Freigabe Wickler -U5
//Leitantrieb der Linie. Sollwert (Bahngeschwindigkeit) ueber PROFIBUS.
      U     #Freigabe;
      UN    #Stoerung;
      =     #U5_Frei;
NETWORK
TITLE =Freigabe Abwickler -U1 / -U2
//Abwickler laufen mit dem Wickler; bei Restdurchmesser wird der jeweilige Abwickler gesperrt (Rollenwechsel).
      U     #U5_Frei;
      UN    #Rolle1_Min;
      =     #U1_Frei;
      U     #U5_Frei;
      UN    #Rolle2_Min;
      =     #U2_Frei;
NETWORK
TITLE =Freigabe Praegewerk -U3 und Perforation -U4
//Im Automatik mit dem Wickler; im Tippbetrieb (-S7) nur bei gedruecktem Start und geschlossenen Tueren.
      U     #U5_Frei;
      O     ;
      U     #Tippen;
      U     #Start;
      U     #Tuer_OK;
      =     #U3_Frei;
      =     #U4_Frei;
NETWORK
TITLE =Huelsenzufuhr -K3
//Neue Huelse einlegen, wenn ein Log fertig ist oder Hand-Taster -S8; nicht bei leerem Magazin oder eingelegter Huelse.
      U(    ;
      O     #Log_Fertig;
      O     #Huelse_Hand;
      )     ;
      UN    #Huelse_Leer;
      UN    #Huelse_Da;
      U     #MSS_Huelse_OK;
      U     #Freigabe;
      =     #K3_Huelse;
NETWORK
TITLE =Logabschub -K4
//Fertigen Log ausschieben: -K4 zieht 3 s nach Log fertig an (Saege raeumt), Hand-Taster -S9 moeglich; Endschalter -B7 beendet.
      U(    ;
      O     #Log_Fertig;
      O     #Abschub_Hand;
      )     ;
      U     #MSS_Abschub_OK;
      UN    #Abschub_Ende;
      L     S5T#3S;
      SE    T     20;
      U     T     20;
      =     #K4_Abschub;
NETWORK
TITLE =Logzaehlung
//Steigende Flanke Lichtschranke -B6 zaehlt einen Log (MW100 fuer die Visualisierung).
      U     #Log_Fertig;
      FP    #Flanke_Log;
      SPBN  m010;
      L     #Logzahl;
      L     1;
      +I    ;
      T     #Logzahl;
      T     MW   100;
m010: NOP   0;
NETWORK
TITLE =Rollenwechsel anfordern
//Restdurchmesser an einem Abwickler: Anforderung fuer den Bediener (M10.1).
      U     #Rolle1_Min;
      O     #Rolle2_Min;
      =     #Wechsel_Anf;
      =     M     10.1;
NETWORK
TITLE =Meldungen
//Betrieb gruen, Stoerung rot, Huelsenmangel gelb, Hupe bis zur Quittierung.
      U     #Freigabe;
      =     #H1_Betrieb;
      U     #Stoerung;
      =     #H2_Stoerung;
      U     #Huelse_Leer;
      =     #H3_Huelsenmangel;
      U     #Stoerung;
      UN    #Quitt;
      =     #H4_Hupe;
"""

OB_EXTRA = """NETWORK
TITLE =Merker fuer die Visualisierung
//Sammelstoerung und Betrieb spiegeln.
      U     A      5.0;
      =     M     10.0;
      U     A      4.7;
      =     M     10.2;
"""

FAULTS = [
    Fault("-H2 leuchtet, Hupe -H4, Anlage steht", "Bahnriss an Abwickler 1 oder 2 (E0.6 / E0.7 = 1, FB20 Netzwerk 2)", "Bahn an -B1 bzw. -B2 pruefen, Bahn neu einfaedeln. Sensor auf Verschmutzung und Abstand pruefen (Blatt {ref:-B1}). Mit -S6 quittieren."),
    Fault("-H2 leuchtet, ein Umrichter meldet Fehler", "Umrichter -U1 bis -U5 nicht bereit (E2.0 bis E2.4 = 0, FB20 Netzwerk 3)", "Fehlernummer am Umrichter lesen (Blatt {ref:-U1} ff.). Ueberstrom: Antrieb mechanisch pruefen. Nach Beheben Umrichter quittieren, dann -S6."),
    Fault("Start ohne Wirkung, -H1 aus, -H2 aus", "Not-Halt nicht entriegelt oder Sicherheitsrelais -K1 ohne Freigabe (E1.2 = 0)", "-S1, -S2 und -S3 entriegeln. Beide Kanaele 11/12 und 21/22 pruefen (Blatt {ref:-K1}). An Klemme {term:E1.2} muessen 24 V anliegen."),
    Fault("Start ohne Wirkung, Schutztuer geschlossen", "Schutztuerschalter -S10 bis -S13 nicht betaetigt oder -K2 ohne Freigabe (E1.3 = 0)", "Tuerschalter und Betaetiger pruefen (Blatt {ref:-K2}). Klemme {term:E1.3} messen. Betaetiger auf Verschleiss pruefen."),
    Fault("Start ohne Wirkung, E1.2 und E1.3 = 1", "Stop-Kreis unterbrochen (E0.1 = 0) oder Stoerung nicht quittiert", "Leitung -W1 Ader zu -S5:11/12 pruefen und Klemme {term:E0.1} messen; danach -H2 beobachten und mit -S6 quittieren."),
    Fault("Huelsenzufuhr laeuft nicht, -H3 gelb", "Huelsenmagazin leer (-B5, E1.4 = 1)", "Magazin fuellen. Sensor -B5 pruefen (Blatt {ref:-B5})."),
    Fault("Huelsenzufuhr laeuft nicht, -H3 aus", "Motorschutz -F7 ausgeloest (E2.5 = 0) oder Huelse bereits eingelegt (-B8)", "-F7 pruefen, Motorstrom -M6 messen (Nennstrom 1,9 A, Einstellung 2,0 A; Blatt {ref:-F7}). Lichtschranke -B8 pruefen."),
    Fault("Log wird nicht ausgeschoben", "Motorschutz -F8 ausgeloest (E2.6 = 0) oder Endschalter -B7 haengt (E1.6 = 1)", "-F8 pruefen (Blatt {ref:-F8}), Schuetz -K4 auf Ansteuerung A4.6 pruefen (Klemme {term:A4.6}). Endschalter -B7 und Rollenhebel pruefen."),
    Fault("Abwickler 1 stoppt, Anlage laeuft weiter", "Restdurchmesser Mutterrolle 1 erreicht (-B3, E1.0 = 1), Rollenwechsel angefordert (M10.1)", "Mutterrolle wechseln. Steht die Rolle nicht am Ende: Sensor -B3 Abstand pruefen (Blatt {ref:-B3})."),
    Fault("Logzahl MW100 zaehlt nicht", "Lichtschranke -B6 defekt, verschmutzt oder Versorgung fehlt", "24 V an {supply24}, 0 V an {supply0} pruefen. Schaltausgang BK an {term:E1.5} (E1.5) beobachten (Blatt {ref:-B6})."),
    Fault("Praegewerk oder Perforation laufen im Tippbetrieb nicht", "Wahlschalter -S7 nicht auf Tippen (E0.3 = 0) oder Schutztuer offen", "-S7 auf Tippen stellen, Start -S4 gedrueckt halten, Tueren schliessen (FB20 Netzwerk 8)."),
    Fault("Motor brummt, dreht nicht (Huelsenzufuhr oder Logabschub)", "Phase fehlt am Motorabgang", "Spannung an -X9:U/V/W bzw. -X10:U/V/W pruefen, Motorleitung und Klemmen -M6 / -M7 (Blatt {ref:-M6})."),
]

MANUAL = {
    "verwendung": (
        "Der Umroller UR-01 wickelt Tissue von zwei Mutterrollen (Abwickler -M1, -M2) zu Logs auf Huelsen. "
        "Die Bahn wird gepraegt (-M3), perforiert (-M4) und vom Wickler (-M5, Leitantrieb, 200 m/min) aufgewickelt. "
        "Die Huelsenzufuhr (-M6) legt Huelsen aus dem Magazin ein, der Logabschub (-M7) schiebt fertige Logs zur Saege. "
        "Alle Antriebe sitzen im Feld +FE1 (Antriebsblaetter ab {ref:-M1}). Zulaessige Bahnbreite 2,8 m, Logdurchmesser 90 bis 130 mm."
    ),
    "bedienelemente": [
        ("Taster gruen", "-S4", "Start, setzt die Freigabe (E0.0, FB20 Netzwerk 1)"),
        ("Taster rot", "-S5", "Stop, Oeffner (E0.1)"),
        ("Taster blau", "-S6", "Stoerung quittieren (E0.2)"),
        ("Wahlschalter", "-S7", "Betriebsart Tippen fuer Praegewerk und Perforation (E0.3)"),
        ("Taster schwarz", "-S8", "Huelsenzufuhr Hand (E0.4)"),
        ("Taster schwarz", "-S9", "Logabschub Hand (E0.5)"),
        ("Pilztaster rot", "-S1, -S2, -S3", "Not-Halt, rastend, 2 Oeffner auf Sicherheitsrelais -K1 (Blatt {ref:-K1})"),
        ("Leuchte gruen", "-H1", "Betrieb (A4.7)"),
        ("Leuchte rot", "-H2", "Stoerung (A5.0)"),
        ("Leuchte gelb", "-H3", "Huelsenmangel (A5.1)"),
        ("Hupe", "-H4", "Stoerung bis zur Quittierung (A5.2)"),
    ],
    "einschalten": [
        "Hauptschalter -Q1 im Schaltschrank einschalten (Blatt {ref:-Q1}).",
        "Netzteil -T1 liefert 24 V DC an -X2; SPS -A1 und Umrichter -U1 bis -U5 laufen hoch (Bereitmeldung E2.0 bis E2.4).",
        "Not-Halt -S1, -S2, -S3 entriegeln und alle Schutztueren -S10 bis -S13 schliessen. -K1 und -K2 ziehen an (Blatt {ref:-K1}).",
        "Mutterrollen einlegen, Bahn einfaedeln, Huelsenmagazin fuellen (-B5 frei).",
        "Start -S4 druecken. FB20 Netzwerk 1 setzt die Freigabe, -U5 (Wickler) bekommt die Freigabe A4.4, -H1 leuchtet.",
    ],
    "ausschalten": (
        "Stop -S5 druecken: die Freigabe faellt ab, alle Umrichter-Freigaben (A4.0 bis A4.4) werden zurueckgenommen, "
        "die Antriebe bremsen geregelt. Bei Gefahr Not-Halt druecken: -K1 faellt ab, die sicher abgeschaltete "
        "Umrichter-Freigabe (STO) und die Schuetzspulen -K3 / -K4 werden hardwareseitig getrennt, unabhaengig von der SPS."
    ),
    "wartung": [
        "Taeglich: Sensoren -B1, -B2 (Bahnriss) und -B6, -B8 (Lichtschranken) reinigen.",
        "Woechentlich: Huelsenmagazin und Sensor -B5 reinigen, Logabschub -M7 auf Leichtgaengigkeit pruefen.",
        "Halbjaehrlich: Not-Halt-Funktion (-S1 bis -S3) und Schutztueren (-S10 bis -S13) pruefen: -K1 bzw. -K2 muss abfallen, Umrichter-Freigabe weg.",
        "Jaehrlich: Motorstroeme -M1 bis -M7 messen und mit den Einstellungen der Schutzorgane vergleichen; Klemmen -X4 bis -X10 nachziehen; Pruefung nach DGUV Vorschrift 3.",
    ],
}

CABLES = [
    ("-W1", "Steuerleitung Bedienpult", "24 x 0,75 mm2, 12 m", "-S4"),
    ("-W2", "Sensorleitungen Bahnriss, Durchmesser, Huelse, Log (8 Stueck)", "4 x 0,5 mm2, 6 bis 15 m", "-B1"),
    ("-W3", "Leitungen Schutztuerschalter (4 Stueck)", "6 x 0,75 mm2, 8 bis 14 m", "-S10"),
    ("-W4", "PROFIBUS-DP-Leitung SPS -> Umrichter -U1 bis -U5", "2 x 0,64 mm2 geschirmt, 18 m", "-U1"),
] + [
    (f"-W1{i}", f"Motorleitung {d.motor} {d.name}", ("4G6 mm2" if d.kw > 10 else "4G4 mm2" if d.kw > 4 else "4G1,5 mm2") + ", geschirmt" if d.kind == "vfd" else "4G1,5 mm2", d.motor)
    for i, d in enumerate(DRIVES, start=1)
]

MACHINE = Machine(
    code="UR-01",
    title="Umroller UR-01",
    plant="=L1",
    loc_cabinet="+ST1",
    loc_field="+FE1",
    drawing_no="UR-01-E-001",
    supply_text="Netzeinspeisung 3/N/PE AC 400/230 V 50 Hz, Vorsicherung bauseits 160 A",
    function=[
        "Der Umroller UR-01 wickelt Tissue von zwei Mutterrollen (Abwickler -M1, -M2) ueber Praegewerk (-M3) und Perforation (-M4)",
        "zum Wickler (-M5, Leitantrieb) auf Huelsen. Die Huelsenzufuhr (-M6) und der Logabschub (-M7) laufen ueber Schuetze -K3 / -K4.",
        "Fuenf Frequenzumrichter -U1 bis -U5 haengen am PROFIBUS DP der SPS -A1; Freigabe und Bereitmeldung laufen ueber Digitalein-/ausgaenge.",
        "Not-Halt (-S1 bis -S3) wirkt zweikanalig auf -K1, die Schutztueren (-S10 bis -S13) auf -K2; beide schalten die Umrichter-Freigabe (STO)",
        "und die Schuetzspulen hardwareseitig ab. Bahnriss (-B1, -B2), Restdurchmesser (-B3, -B4), Huelsenmagazin (-B5), Log fertig (-B6),",
        "Logabschub Endlage (-B7) und Huelse eingelegt (-B8) werden von der SPS ausgewertet (FB20, Instanz DB20).",
        "Zugehoerige Dokumente: Stueckliste, Klemmenplan, SPS-Programm (AWL), Symboltabelle und Betriebsanleitung UR-01.",
    ],
    devices=DEVICES,
    drives=DRIVES,
    safety=[
        SafetyCircuit("-K1", "Sicherheitsrelais Not-Halt", [("-S1", "11/12", "21/22"), ("-S2", "11/12", "21/22"), ("-S3", "11/12", "21/22")],
                      "STO -U1..-U5, Spulen -K3/-K4", "-X2:3a", "E1.2"),
        SafetyCircuit("-K2", "Sicherheitsrelais Schutztueren", [("-S10", "11/12", "21/22"), ("-S11", "11/12", "21/22"), ("-S12", "11/12", "21/22"), ("-S13", "11/12", "21/22")],
                      "Freigabe -U3/-U4 Tippbetrieb", "-X2:3b", "E1.3"),
    ],
    inputs=INPUTS,
    outputs=OUTPUTS,
    merker=[
        ("M10.0", "Stoerung", "Sammelstoerung (Visualisierung)"),
        ("M10.1", "Rollenwechsel", "Rollenwechsel angefordert (Restdurchmesser)"),
        ("M10.2", "Betrieb", "Anlage in Betrieb (Visualisierung)"),
        ("MW100", "Logzahl", "Logs seit Schichtbeginn"),
    ],
    fb_number=20,
    db_number=20,
    fb_title="Umroller UR-01 Steuerung",
    fb_static=[
        ("Freigabe", "BOOL", "Selbsthaltung Betrieb"),
        ("Stoerung", "BOOL", "Sammelstoerung"),
        ("Bahnriss", "BOOL", "Bahnriss an einem Abwickler"),
        ("Wechsel_Anf", "BOOL", "Rollenwechsel angefordert"),
        ("Flanke_Log", "BOOL", "Flankenmerker Log fertig"),
        ("Logzahl", "INT", "Logs seit Quittierung"),
    ],
    networks=NETWORKS,
    ob_extra=OB_EXTRA,
    extra_symbols=[("T_Abschub", "T 20", "TIMER", "Logabschub 3 s")],
    manual=MANUAL,
    faults=FAULTS,
    cables=CABLES,
)
