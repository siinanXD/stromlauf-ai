"""PM1-AR Aufrollung der Papiermaschine PM1 (Sektor S6 des Testwerks).

Tragtrommel und Tambourantrieb an Frequenzumrichtern (PROFIBUS DP), Hydraulikpumpe fuer die
Wechselarme und Oelumlaufpumpe ueber Schuetze, Tambourwechsel als Schrittkette, Reissleine,
Bahnriss-, Druck-, Oelstands- und Temperaturueberwachung.
"""

from model import Device, Drive, Fault, Machine, SafetyCircuit, Signal

DRIVES = [
    Drive("-M1", "Tragtrommel", 75, 138, 1485, "-F2", "Leistungsschalter Tragtrommel", "In 160 A", "-U1", "Frequenzumrichter Tragtrommel", "vfd", "-X4", 10),
    Drive("-M2", "Tambourantrieb", 30, 56, 1475, "-F3", "Leistungsschalter Tambourantrieb", "In 63 A", "-U2", "Frequenzumrichter Tambourantrieb", "vfd", "-X5", 11),
    Drive("-M3", "Hydraulikpumpe Wechselarme", 11, 22, 1460, "-F4", "Motorschutzschalter Hydraulikpumpe", "Einstellung 23 A", "-K3", "Schuetz Hydraulikpumpe", "contactor", "-X6"),
    Drive("-M4", "Oelumlaufpumpe Lager", 3, 6.5, 1420, "-F5", "Motorschutzschalter Oelpumpe", "Einstellung 7 A", "-K4", "Schuetz Oelpumpe", "contactor", "-X7"),
]

INPUTS = [
    Signal("E0.0", "Start", "Taster -S5 Start, Schliesser", "-S5", "cmd_no", ("13", "14")),
    Signal("E0.1", "Stop", "Taster -S6 Stop, Oeffner (1 = nicht betaetigt)", "-S6", "cmd_nc", ("11", "12")),
    Signal("E0.2", "Quitt", "Taster -S7 Stoerung quittieren", "-S7", "cmd_no", ("13", "14")),
    Signal("E0.3", "Wechsel_Hand", "Taster -S8 Tambourwechsel Hand", "-S8", "cmd_no", ("13", "14")),
    Signal("E0.4", "Automatik", "Wahlschalter -S9 Betriebsart Automatik", "-S9", "cmd_no", ("13", "14")),
    Signal("E0.5", "Durchm_OK", "Laser-Distanzsensor -B1 Tambourdurchmesser erreicht", "-B1", "sensor", ("1", "4")),
    Signal("E0.6", "Bahnriss", "Ultraschallsensor -B2 Bahnriss vor Tragtrommel (1 = Bahn fehlt)", "-B2", "sensor", ("1", "4")),
    Signal("E0.7", "Druck_OK", "Druckschalter -B3 Hydraulikdruck 150 bar erreicht", "-B3", "sensor", ("1", "4")),
    Signal("E1.0", "Oel_OK", "Schwimmerschalter -B4 Oelstand Lagerschmierung ok", "-B4", "sensor", ("1", "4")),
    Signal("E1.1", "Arm_Aus", "Naeherungsschalter -B5 Wechselarm ausgefahren", "-B5", "sensor", ("1", "4")),
    Signal("E1.2", "Arm_Grund", "Naeherungsschalter -B6 Wechselarm Grundstellung", "-B6", "sensor", ("1", "4")),
    Signal("E1.3", "Tambour_Da", "Lichtschranke -B7 Leertambour eingelegt", "-B7", "sensor", ("1", "4")),
    Signal("E1.4", "NotHalt_OK", "Sicherheitsrelais -K1 Freigabe (1 = Not-Halt und Reissleine entriegelt)", "-K1", "aux", ("23", "24")),
    Signal("E1.5", "Tuer_OK", "Sicherheitsrelais -K2 Freigabe (1 = Schutztueren zu)", "-K2", "aux", ("23", "24")),
    Signal("E1.6", "U1_Bereit", "Umrichter -U1 Tragtrommel betriebsbereit (DO1)", "-U1", "aux", ("DO1", "COM")),
    Signal("E1.7", "U2_Bereit", "Umrichter -U2 Tambourantrieb betriebsbereit (DO1)", "-U2", "aux", ("DO1", "COM")),
    Signal("E2.0", "MSS_Hydr_OK", "Motorschutz -F4 Hilfskontakt (1 = ok)", "-F4", "aux", ("13", "14")),
    Signal("E2.1", "MSS_Oel_OK", "Motorschutz -F5 Hilfskontakt (1 = ok)", "-F5", "aux", ("13", "14")),
    Signal("E2.2", "Oeltemp_OK", "Thermostat -B8 Oeltemperatur unter 60 Grad", "-B8", "sensor", ("1", "4")),
]

OUTPUTS = [
    Signal("A4.0", "U1_Frei", "Freigabe Umrichter -U1 Tragtrommel", "-U1", "vfd", ("DI1", "COM")),
    Signal("A4.1", "U2_Frei", "Freigabe Umrichter -U2 Tambourantrieb", "-U2", "vfd", ("DI1", "COM")),
    Signal("A4.2", "K3_Hydr", "Schuetz -K3 Hydraulikpumpe -M3", "-K3", "coil", ("A1", "A2")),
    Signal("A4.3", "K4_Oel", "Schuetz -K4 Oelumlaufpumpe -M4", "-K4", "coil", ("A1", "A2")),
    Signal("A4.4", "Y1_Aus", "Magnetventil -Y1 Wechselarm ausfahren", "-Y1", "coil", ("A1", "A2")),
    Signal("A4.5", "Y2_Rueck", "Magnetventil -Y2 Wechselarm zurueck", "-Y2", "coil", ("A1", "A2")),
    Signal("A4.6", "Y3_Trenn", "Magnetventil -Y3 Trennmesser", "-Y3", "coil", ("A1", "A2")),
    Signal("A4.7", "H1_Betrieb", "Meldeleuchte -H1 Betrieb gruen", "-H1", "lamp", ("X1", "X2")),
    Signal("A5.0", "H2_Stoerung", "Meldeleuchte -H2 Stoerung rot", "-H2", "lamp", ("X1", "X2")),
    Signal("A5.1", "H3_Wechsel", "Meldeleuchte -H3 Tambourwechsel angefordert gelb", "-H3", "lamp", ("X1", "X2")),
    Signal("A5.2", "H4_Hupe", "Hupe -H4 Stoerung", "-H4", "horn", ("X1", "X2")),
]

DEVICES = [
    Device("-Q1", "Hauptschalter 3-polig, 250 A", "Lasttrennschalter 3P 250A"),
    Device("-F1", "Leitungsschutzschalter Steuerspannung 230 V", "LS-Schalter 1P+N B6"),
    Device("-T1", "Netzteil 230 V AC / 24 V DC, 10 A", "Schaltnetzteil 24V/10A"),
] + [Device(d.breaker, d.breaker_name, "Motorschutzschalter 3P + Hilfskontakt 1S" if d.kind == "contactor" else "Leistungsschalter 3P, thermisch-magnetisch") for d in DRIVES] + [
    Device(d.switch, d.switch_name, f"Frequenzumrichter {d.kw:g} kW, 400 V, PROFIBUS DP, STO" if d.kind == "vfd" else "Leistungsschuetz 11 kW, Spule 24 V DC") for d in DRIVES
] + [
    Device("-K1", "Sicherheitsrelais Not-Halt und Reissleine, 2-kanalig", "Sicherheitsschaltgeraet Kat. 3 / PL d"),
    Device("-K2", "Sicherheitsrelais Schutztueren, 2-kanalig", "Sicherheitsschaltgeraet Kat. 3 / PL d"),
] + [Device(d.motor, f"Motor {d.name} 3~ {d.kw:g} kW, {d.rpm} 1/min", f"Drehstrommotor {d.kw:g} kW, IE3", in_field=True) for d in DRIVES] + [
    Device("-S1", "Not-Halt-Taster Bedienpult, 2 Oeffner, rastend", "Pilzdrucktaster 2OE", in_field=True),
    Device("-S2", "Not-Halt-Taster Fuehrerseite, 2 Oeffner, rastend", "Pilzdrucktaster 2OE", in_field=True),
    Device("-S3", "Not-Halt-Taster Triebseite, 2 Oeffner, rastend", "Pilzdrucktaster 2OE", in_field=True),
    Device("-S4", "Reissleine Tragtrommel, 2 Oeffner, rastend", "Seilzug-Notschalter 2OE", in_field=True),
    Device("-S5", "Taster Start (Schliesser)", "Drucktaster gruen 1S", in_field=True),
    Device("-S6", "Taster Stop (Oeffner)", "Drucktaster rot 1OE", in_field=True),
    Device("-S7", "Taster Stoerung quittieren", "Drucktaster blau 1S", in_field=True),
    Device("-S8", "Taster Tambourwechsel Hand", "Drucktaster schwarz 1S", in_field=True),
    Device("-S9", "Wahlschalter Betriebsart Automatik", "Wahlschalter 2 Stellungen 1S", in_field=True),
    Device("-S10", "Schutztuerschalter Tragtrommel Fuehrerseite, 2 Oeffner", "Sicherheitsschalter mit getrenntem Betaetiger 2OE", in_field=True),
    Device("-S11", "Schutztuerschalter Tragtrommel Triebseite, 2 Oeffner", "Sicherheitsschalter mit getrenntem Betaetiger 2OE", in_field=True),
    Device("-B1", "Laser-Distanzsensor Tambourdurchmesser", "Laser-Distanzsensor 0,2 bis 3 m, Schaltausgang PNP", in_field=True),
    Device("-B2", "Ultraschallsensor Bahnriss", "Ultraschall-Reflexionstaster 24 V DC PNP", in_field=True),
    Device("-B3", "Druckschalter Hydraulik 150 bar", "Druckschalter 0 bis 250 bar, 1S", in_field=True),
    Device("-B4", "Schwimmerschalter Oelstand", "Schwimmerschalter 1S", in_field=True),
    Device("-B5", "Naeherungsschalter Wechselarm ausgefahren", "Induktiver Naeherungsschalter M18 PNP", in_field=True),
    Device("-B6", "Naeherungsschalter Wechselarm Grundstellung", "Induktiver Naeherungsschalter M18 PNP", in_field=True),
    Device("-B7", "Lichtschranke Leertambour eingelegt", "Reflexionslichtschranke 24 V DC PNP", in_field=True),
    Device("-B8", "Thermostat Oeltemperatur", "Temperaturschalter 60 Grad, 1OE", in_field=True),
    Device("-Y1", "Magnetventil Wechselarm ausfahren", "4/2-Wegeventil 24 V DC", in_field=True),
    Device("-Y2", "Magnetventil Wechselarm zurueck", "4/2-Wegeventil 24 V DC", in_field=True),
    Device("-Y3", "Magnetventil Trennmesser", "3/2-Wegeventil 24 V DC", in_field=True),
    Device("-H1", "Meldeleuchte Betrieb (gruen)", "LED-Leuchtmelder 24 V DC gruen", in_field=True),
    Device("-H2", "Meldeleuchte Stoerung (rot)", "LED-Leuchtmelder 24 V DC rot", in_field=True),
    Device("-H3", "Meldeleuchte Tambourwechsel (gelb)", "LED-Leuchtmelder 24 V DC gelb", in_field=True),
    Device("-H4", "Hupe Stoerung", "Summer 24 V DC 85 dB", in_field=True),
    Device("-A1", "SPS CPU, PROFIBUS DP Master", "SPS-Zentralbaugruppe"),
    Device("-A1.1", "Digitaleingabe 16 x 24 V DC (E0.0 bis E1.7)", "DI-Baugruppe 16 DI"),
    Device("-A1.2", "Digitaleingabe 16 x 24 V DC (E2.0 bis E3.7)", "DI-Baugruppe 16 DI"),
    Device("-A1.3", "Digitalausgabe 16 x 24 V DC / 0,5 A (A4.0 bis A5.7)", "DO-Baugruppe 16 DO"),
    Device("-X1", "Klemmleiste Netzeinspeisung", "Reihenklemme 95 mm2", 5),
    Device("-X2", "Klemmleiste 24 V Steuerspannung", "Reihenklemme 2,5 mm2", 8),
    Device("-X3", "Klemmleiste Feldgeraete (Sensoren, Taster, Ventile, Umrichter-Signale, Sicherheitskreise)", "Reihenklemme 2,5 mm2"),
] + [Device(d.strip, f"Klemmleiste Motorabgang {d.motor}", "Reihenklemme 50 mm2" if d.kw > 50 else "Reihenklemme 16 mm2" if d.kw > 20 else "Reihenklemme 6 mm2", 4) for d in DRIVES]

NETWORKS = """NETWORK
TITLE =Freigabe Betrieb
//Start setzt die Freigabe; Stop, Not-Halt/Reissleine, offene Schutztuer oder Stoerung setzen zurueck.
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
TITLE =Oelumlaufpumpe -K4
//Lagerschmierung laeuft, sobald Not-Halt frei ist; bleibt bei Stoerung an, solange Motorschutz ok.
      U     #NotHalt_OK;
      U     #MSS_Oel_OK;
      =     #K4_Oel;
NETWORK
TITLE =Oelmangel und Oeltemperatur
//10 s nach Pumpenstart muss der Oelstand ok sein; Uebertemperatur (-B8) ist sofort Stoerung.
      U     #K4_Oel;
      L     S5T#10S;
      SE    T     30;
      U     T     30;
      UN    #Oel_OK;
      S     #Stoerung;
      UN    #Oeltemp_OK;
      S     #Stoerung;
NETWORK
TITLE =Hydraulikpumpe -K3
//Hydraulik fuer die Wechselarme laeuft mit der Freigabe.
      U     #Freigabe;
      U     #MSS_Hydr_OK;
      =     #K3_Hydr;
NETWORK
TITLE =Hydraulikdruck
//5 s nach Pumpenstart muss der Druckschalter -B3 150 bar melden.
      U     #K3_Hydr;
      L     S5T#5S;
      SE    T     31;
      U     T     31;
      UN    #Druck_OK;
      S     #Stoerung;
NETWORK
TITLE =Bahnriss
//Ultraschallsensor -B2 meldet fehlende Bahn bei laufender Tragtrommel: Stoerung, Aufrollung stoppt geregelt.
      U     #Bahnriss;
      U     #U1_Frei;
      S     #Stoerung;
NETWORK
TITLE =Stoerung Umrichter
//Tragtrommel oder Tambourantrieb bei laufender Aufrollung nicht bereit.
      U     #U1_Frei;
      U(    ;
      ON    #U1_Bereit;
      ON    #U2_Bereit;
      )     ;
      S     #Stoerung;
NETWORK
TITLE =Quittierung
//Quittieren nur bei stehender Aufrollung, bereiten Umrichtern und Oelstand ok.
      U     #Quitt;
      UN    #Freigabe;
      U     #U1_Bereit;
      U     #U2_Bereit;
      U     #Oel_OK;
      U     #Oeltemp_OK;
      U     #MSS_Hydr_OK;
      U     #MSS_Oel_OK;
      R     #Stoerung;
NETWORK
TITLE =Freigabe Tragtrommel -U1
//Leitantrieb der Aufrollung, Sollwert Bahngeschwindigkeit ueber PROFIBUS.
      U     #Freigabe;
      UN    #Stoerung;
      =     #U1_Frei;
NETWORK
TITLE =Freigabe Tambourantrieb -U2
//Zentrumsantrieb des Tambours nur mit eingelegtem Tambour (-B7).
      U     #U1_Frei;
      U     #Tambour_Da;
      =     #U2_Frei;
NETWORK
TITLE =Tambourwechsel anfordern
//Durchmesser erreicht (-B1) im Automatik oder Hand-Taster -S8; Schrittkette startet nur in Grundstellung.
      U(    ;
      U     #Durchm_OK;
      U     #Automatik;
      O     #Wechsel_Hand;
      )     ;
      U     #Freigabe;
      U     #Tuer_OK;
      =     #Wechsel_Anf;
      =     #H3_Wechsel;
      U     #Wechsel_Anf;
      U     #Arm_Grund;
      UN    M     30.1;
      UN    M     30.2;
      UN    M     30.3;
      S     M     30.0;
NETWORK
TITLE =Schritt 2 Wechselarm ausfahren -Y1
//Mit Hydraulikdruck: Arm ausfahren bis Endlage -B5.
      U     M     30.0;
      U     #Druck_OK;
      S     M     30.1;
      R     M     30.0;
      U     M     30.1;
      =     #Y1_Aus;
NETWORK
TITLE =Schritt 3 Bahn trennen -Y3
//Trennmesser 2 s, dann weiter.
      U     M     30.1;
      U     #Arm_Aus;
      S     M     30.2;
      R     M     30.1;
      U     M     30.2;
      =     #Y3_Trenn;
      U     M     30.2;
      L     S5T#2S;
      SE    T     32;
      U     T     32;
      S     M     30.3;
      R     M     30.2;
NETWORK
TITLE =Schritt 4 Wechselarm zurueck -Y2
//Arm zurueck bis Grundstellung -B6, dann Schrittkette beenden.
      U     M     30.3;
      =     #Y2_Rueck;
      U     M     30.3;
      U     #Arm_Grund;
      R     M     30.3;
NETWORK
TITLE =Tambourzaehlung
//Steigende Flanke Grundstellung nach einem Wechsel zaehlt einen Tambour (MW102).
      U     #Arm_Grund;
      FP    #Flanke_Wechsel;
      SPBN  m015;
      L     #Tambourzahl;
      L     1;
      +I    ;
      T     #Tambourzahl;
      T     MW   102;
m015: NOP   0;
NETWORK
TITLE =Meldungen
//Betrieb gruen, Stoerung rot, Hupe bis zur Quittierung.
      U     #Freigabe;
      =     #H1_Betrieb;
      U     #Stoerung;
      =     #H2_Stoerung;
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
    Fault("-H2 leuchtet, Hupe -H4, Aufrollung steht", "Bahnriss vor der Tragtrommel (-B2, E0.6 = 1, FB30 Netzwerk 6)", "Bahn neu einfuehren. Sensor -B2 auf Verschmutzung und Abstand pruefen (Blatt {ref:-B2}). Mit -S7 quittieren."),
    Fault("-H2 leuchtet, Tragtrommel laeuft nicht an", "Umrichter -U1 nicht bereit (E1.6 = 0, FB30 Netzwerk 7)", "Fehlernummer an -U1 lesen (Blatt {ref:-U1}). Leistungsschalter -F2 pruefen. Nach Beheben Umrichter quittieren, dann -S7."),
    Fault("Start ohne Wirkung, -H1 aus, -H2 aus", "Not-Halt oder Reissleine nicht entriegelt, -K1 ohne Freigabe (E1.4 = 0)", "-S1, -S2, -S3 und Reissleine -S4 entriegeln. Beide Kanaele pruefen (Blatt {ref:-K1}). An Klemme {term:E1.4} muessen 24 V anliegen."),
    Fault("Start ohne Wirkung, Schutztuer geschlossen", "Schutztuerschalter -S10 / -S11 nicht betaetigt oder -K2 ohne Freigabe (E1.5 = 0)", "Tuerschalter und Betaetiger pruefen (Blatt {ref:-K2}). Klemme {term:E1.5} messen."),
    Fault("Stoerung 10 s nach dem Einschalten, Oelpumpe laeuft", "Oelstand zu niedrig (-B4, E1.0 = 0) oder Oel zu heiss (-B8, E2.2 = 0), FB30 Netzwerk 3", "Oelstand am Schauglas pruefen, Oel nachfuellen. Schwimmerschalter -B4 und Thermostat -B8 pruefen (Blatt {ref:-B4}). Oelkuehler pruefen."),
    Fault("Stoerung 5 s nach Start, Hydraulikpumpe laeuft", "Hydraulikdruck 150 bar nicht erreicht (-B3, E0.7 = 0), FB30 Netzwerk 5", "Druck am Manometer pruefen. Druckbegrenzungsventil und Pumpe -M3 pruefen. Druckschalter -B3 pruefen (Blatt {ref:-B3})."),
    Fault("Hydraulikpumpe laeuft nicht", "Motorschutz -F4 ausgeloest (E2.0 = 0)", "-F4 pruefen, Motorstrom -M3 messen (Nennstrom 22 A, Einstellung 23 A; Blatt {ref:-F4}). Schuetz -K3 auf Ansteuerung A4.2 pruefen."),
    Fault("Tambourwechsel startet nicht, -H3 leuchtet", "Wechselarm nicht in Grundstellung (-B6, E1.2 = 0) oder Schutztuer offen", "Arm mit der Hydraulik-Handsteuerung am Ventilblock in Grundstellung bringen. Naeherungsschalter -B6 pruefen (Blatt {ref:-B6}). Schrittkette M30.0 bis M30.3 in FB30 beobachten."),
    Fault("Wechselarm faehrt nicht aus (Schritt 2)", "Magnetventil -Y1 ohne Ansteuerung (A4.4) oder Hydraulikdruck fehlt", "Spannung an Klemme {term:A4.4} pruefen (Blatt {ref:-Y1}). Ventil -Y1 auf Verschmutzung pruefen. Druck -B3 pruefen."),
    Fault("Trennmesser schneidet nicht (Schritt 3)", "Magnetventil -Y3 ohne Ansteuerung (A4.6) oder Messer stumpf", "Spannung an Klemme {term:A4.6} pruefen (Blatt {ref:-Y3}). Messer pruefen. Endlage -B5 muss E1.1 = 1 melden."),
    Fault("Tambourantrieb -M2 laeuft nicht mit", "Leertambour nicht erkannt (-B7, E1.3 = 0) oder -U2 nicht bereit", "Lichtschranke -B7 pruefen (Blatt {ref:-B7}). Umrichter -U2 Fehlernummer lesen, -F3 pruefen."),
    Fault("Tambourzahl MW102 zaehlt nicht", "Naeherungsschalter -B6 Grundstellung ohne Flanke", "24 V an {supply24}, 0 V an {supply0} pruefen. Schaltausgang -B6 an {term:E1.2} (E1.2) beobachten (Blatt {ref:-B6})."),
]

MANUAL = {
    "verwendung": (
        "Die Aufrollung PM1-AR wickelt die Tissuebahn der Papiermaschine PM1 (2,8 m breit, bis 2.200 m/min) auf Tambours. "
        "Die Tragtrommel (-M1, Leitantrieb) treibt den Tambour, der Tambourantrieb (-M2) beschleunigt den Leertambour vor dem Wechsel. "
        "Die Wechselarme werden hydraulisch bewegt (Pumpe -M3, Ventile -Y1 bis -Y3), die Lager werden von der Oelumlaufpumpe -M4 versorgt. "
        "Der Tambourwechsel laeuft als Schrittkette in FB30 (M30.0 bis M30.3). Alle Antriebe sitzen im Feld +FE6 (Antriebsblaetter ab {ref:-M1})."
    ),
    "bedienelemente": [
        ("Taster gruen", "-S5", "Start, setzt die Freigabe (E0.0, FB30 Netzwerk 1)"),
        ("Taster rot", "-S6", "Stop, Oeffner (E0.1)"),
        ("Taster blau", "-S7", "Stoerung quittieren (E0.2)"),
        ("Taster schwarz", "-S8", "Tambourwechsel Hand (E0.3)"),
        ("Wahlschalter", "-S9", "Betriebsart Automatik: Wechsel bei Solldurchmesser -B1 (E0.4)"),
        ("Pilztaster rot", "-S1, -S2, -S3", "Not-Halt, rastend, 2 Oeffner auf Sicherheitsrelais -K1 (Blatt {ref:-K1})"),
        ("Reissleine", "-S4", "Not-Halt entlang der Tragtrommel, 2 Oeffner auf -K1"),
        ("Leuchte gruen", "-H1", "Betrieb (A4.7)"),
        ("Leuchte rot", "-H2", "Stoerung (A5.0)"),
        ("Leuchte gelb", "-H3", "Tambourwechsel angefordert (A5.1)"),
        ("Hupe", "-H4", "Stoerung bis zur Quittierung (A5.2)"),
    ],
    "einschalten": [
        "Hauptschalter -Q1 im Schaltschrank einschalten (Blatt {ref:-Q1}).",
        "Netzteil -T1 liefert 24 V DC an -X2; SPS -A1 und Umrichter -U1, -U2 laufen hoch (Bereitmeldung E1.6, E1.7).",
        "Not-Halt -S1 bis -S3 und Reissleine -S4 entriegeln, Schutztueren -S10, -S11 schliessen. -K1 und -K2 ziehen an (Blatt {ref:-K1}).",
        "Oelumlaufpumpe -M4 laeuft an (A4.3); nach 10 s muss der Oelstand -B4 ok melden.",
        "Leertambour einlegen (-B7), Start -S5 druecken. FB30 Netzwerk 1 setzt die Freigabe, Hydraulikpumpe -M3 laeuft an, -U1 bekommt A4.0, -H1 leuchtet.",
    ],
    "ausschalten": (
        "Stop -S6 druecken: die Freigabe faellt ab, die Umrichter-Freigaben A4.0 und A4.1 werden zurueckgenommen, "
        "Tragtrommel und Tambour bremsen geregelt; die Oelpumpe laeuft weiter. Bei Gefahr Not-Halt oder Reissleine "
        "betaetigen: -K1 faellt ab, STO der Umrichter und die Schuetzspulen -K3 / -K4 werden hardwareseitig getrennt."
    ),
    "wartung": [
        "Taeglich: Sensoren -B1 (Laser) und -B2 (Bahnriss) reinigen, Oelstand am Schauglas pruefen.",
        "Woechentlich: Hydraulikdruck am Manometer mit -B3 vergleichen (150 bar), Ventile -Y1 bis -Y3 auf Leckage pruefen.",
        "Halbjaehrlich: Not-Halt (-S1 bis -S3), Reissleine -S4 und Schutztueren (-S10, -S11) pruefen: -K1 bzw. -K2 muss abfallen.",
        "Jaehrlich: Motorstroeme -M1 bis -M4 messen und mit den Einstellungen vergleichen; Klemmen -X4 bis -X7 nachziehen; Pruefung nach DGUV Vorschrift 3.",
    ],
}

CABLES = [
    ("-W1", "Steuerleitung Bedienpult", "24 x 0,75 mm2, 15 m", "-S5"),
    ("-W2", "Sensorleitungen (8 Stueck)", "4 x 0,5 mm2, 8 bis 20 m", "-B1"),
    ("-W3", "Leitungen Schutztuerschalter und Reissleine (3 Stueck)", "6 x 0,75 mm2, 10 bis 25 m", "-S10"),
    ("-W4", "Ventilleitungen -Y1 bis -Y3", "3 x 0,75 mm2, 12 m", "-Y1"),
    ("-W5", "PROFIBUS-DP-Leitung SPS -> Umrichter -U1, -U2", "2 x 0,64 mm2 geschirmt, 8 m", "-U1"),
    ("-W11", "Motorleitung -M1 Tragtrommel", "4G50 mm2, geschirmt, 25 m", "-M1"),
    ("-W12", "Motorleitung -M2 Tambourantrieb", "4G16 mm2, geschirmt, 22 m", "-M2"),
    ("-W13", "Motorleitung -M3 Hydraulikpumpe", "4G6 mm2, 18 m", "-M3"),
    ("-W14", "Motorleitung -M4 Oelpumpe", "4G1,5 mm2, 14 m", "-M4"),
]

MACHINE = Machine(
    code="PM1-AR",
    title="Aufrollung PM1-AR",
    plant="=PM1",
    loc_cabinet="+ST6",
    loc_field="+FE6",
    drawing_no="PM1-AR-E-001",
    supply_text="Netzeinspeisung 3/N/PE AC 400/230 V 50 Hz, Vorsicherung bauseits 250 A",
    function=[
        "Die Aufrollung PM1-AR wickelt die Tissuebahn der Papiermaschine PM1 auf Tambours. Die Tragtrommel -M1 (75 kW, Leitantrieb)",
        "und der Tambourantrieb -M2 (30 kW) haengen an den Frequenzumrichtern -U1 / -U2 am PROFIBUS DP der SPS -A1.",
        "Die Hydraulikpumpe -M3 (Schuetz -K3) versorgt die Wechselarme (Ventile -Y1, -Y2) und das Trennmesser (-Y3); die Oelumlaufpumpe -M4",
        "(Schuetz -K4) schmiert die Lager. Der Tambourwechsel laeuft als Schrittkette in FB30 (M30.0 bis M30.3), ausgeloest vom",
        "Laser-Distanzsensor -B1 (Solldurchmesser) oder von Hand (-S8). Not-Halt (-S1 bis -S3) und Reissleine (-S4) wirken zweikanalig",
        "auf -K1, die Schutztueren (-S10, -S11) auf -K2. Bahnriss (-B2), Hydraulikdruck (-B3), Oelstand (-B4), Endlagen (-B5, -B6),",
        "Leertambour (-B7) und Oeltemperatur (-B8) werden von der SPS ausgewertet (FB30, Instanz DB30).",
    ],
    devices=DEVICES,
    drives=DRIVES,
    safety=[
        SafetyCircuit("-K1", "Sicherheitsrelais Not-Halt / Reissleine",
                      [("-S1", "11/12", "21/22"), ("-S2", "11/12", "21/22"), ("-S3", "11/12", "21/22"), ("-S4", "11/12", "21/22")],
                      "STO -U1/-U2, Spulen -K3/-K4", "-X2:3a", "E1.4"),
        SafetyCircuit("-K2", "Sicherheitsrelais Schutztueren", [("-S10", "11/12", "21/22"), ("-S11", "11/12", "21/22")],
                      "Freigabe Tambourwechsel -Y1..-Y3", "-X2:3b", "E1.5"),
    ],
    inputs=INPUTS,
    outputs=OUTPUTS,
    merker=[
        ("M10.0", "Stoerung", "Sammelstoerung (Visualisierung)"),
        ("M10.2", "Betrieb", "Anlage in Betrieb (Visualisierung)"),
        ("M30.0", "Schritt_Anf", "Tambourwechsel Schritt 1: angefordert"),
        ("M30.1", "Schritt_Aus", "Tambourwechsel Schritt 2: Arm ausfahren"),
        ("M30.2", "Schritt_Trenn", "Tambourwechsel Schritt 3: Bahn trennen"),
        ("M30.3", "Schritt_Rueck", "Tambourwechsel Schritt 4: Arm zurueck"),
        ("MW102", "Tambourzahl", "Tambours seit Schichtbeginn"),
    ],
    fb_number=30,
    db_number=30,
    fb_title="Aufrollung PM1-AR Steuerung",
    fb_static=[
        ("Freigabe", "BOOL", "Selbsthaltung Betrieb"),
        ("Stoerung", "BOOL", "Sammelstoerung"),
        ("Wechsel_Anf", "BOOL", "Tambourwechsel angefordert"),
        ("Flanke_Wechsel", "BOOL", "Flankenmerker Grundstellung"),
        ("Tambourzahl", "INT", "Tambours seit Quittierung"),
    ],
    networks=NETWORKS,
    ob_extra=OB_EXTRA,
    extra_symbols=[("T_Oelanlauf", "T 30", "TIMER", "Oelstand-Ueberwachung 10 s"), ("T_Druck", "T 31", "TIMER", "Druckaufbau 5 s"), ("T_Trenn", "T 32", "TIMER", "Trennmesser 2 s")],
    manual=MANUAL,
    faults=FAULTS,
    cables=CABLES,
)
