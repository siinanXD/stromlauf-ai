"""Einzige Datenquelle fuer den Beispielsatz "Foerderband FB-01".

Alle Dokumente (Stromlaufplan, Stueckliste, Klemmenplan, AWL, Symboltabelle,
Betriebsanleitung) werden aus diesen Tabellen erzeugt, damit Betriebsmittel,
Klemmen und SPS-Adressen ueberall identisch sind.
"""

PLANT = "=FB1"
LOC_CABINET = "+ST1"  # Schaltschrank
LOC_FIELD = "+FE1"  # Feld / Anlage

# BMK, Bezeichnung, Typ (neutral, kein Hersteller), Menge, Blatt/Spalte im Plan
DEVICES = [
    ("-Q1", "Hauptschalter 3-polig, 25 A", "Lasttrennschalter 3P 25A", 1, "/2.2"),
    ("-F1", "Leitungsschutzschalter Steuerspannung 230 V", "LS-Schalter 1P+N B6", 1, "/2.4"),
    ("-F2", "Motorschutzschalter Foerdermotor 2,5-4 A", "MSS 3P 2,5-4A + Hilfskontakt 1S1OE", 1, "/3.2"),
    ("-T1", "Netzteil 230 V AC / 24 V DC, 5 A", "Schaltnetzteil 24V/5A", 1, "/2.6"),
    ("-K1", "Schuetz Foerdermotor vorwaerts", "Leistungsschuetz 4 kW, Spule 24 V DC", 1, "/3.4"),
    ("-K2", "Schuetz Foerdermotor rueckwaerts", "Leistungsschuetz 4 kW, Spule 24 V DC", 1, "/3.6"),
    ("-K3", "Sicherheitsrelais Not-Halt, 2-kanalig", "Sicherheitsschaltgeraet Kat. 3 / PL d", 1, "/4.2"),
    ("-M1", "Foerdermotor 3~ 1,5 kW, 1420 1/min", "Drehstrommotor 1,5 kW, IE3", 1, "/3.5"),
    ("-S1", "Taster Start (Schliesser)", "Drucktaster gruen 1S", 1, "/4.6"),
    ("-S2", "Taster Stop (Oeffner)", "Drucktaster rot 1OE", 1, "/4.7"),
    ("-S3", "Not-Halt-Taster, 2 Oeffner, rastend", "Pilzdrucktaster 2OE", 1, "/4.2"),
    ("-B1", "Lichtschranke Einlauf", "Reflexionslichtschranke 24 V DC PNP", 1, "/5.5"),
    ("-B2", "Lichtschranke Auslauf", "Reflexionslichtschranke 24 V DC PNP", 1, "/5.5"),
    ("-H1", "Meldeleuchte Betrieb (gruen)", "LED-Leuchtmelder 24 V DC gruen", 1, "/6.5"),
    ("-H2", "Meldeleuchte Stoerung (rot)", "LED-Leuchtmelder 24 V DC rot", 1, "/6.5"),
    ("-A1", "SPS CPU, kompakt, PROFIBUS DP", "SPS-Zentralbaugruppe", 1, "/5.1"),
    ("-A1.1", "Digitaleingabe 16 x 24 V DC", "DI-Baugruppe 16 DI", 1, "/5.2"),
    ("-A1.2", "Digitalausgabe 16 x 24 V DC / 0,5 A", "DO-Baugruppe 16 DO", 1, "/6.2"),
    ("-X1", "Klemmleiste Netzeinspeisung", "Reihenklemme 4 mm2", 5, "/2.1"),
    ("-X2", "Klemmleiste 24 V Steuerspannung", "Reihenklemme 2,5 mm2", 6, "/2.7"),
    ("-X3", "Klemmleiste Feldgeraete (Sensoren, Taster)", "Reihenklemme 2,5 mm2", 14, "/5.3"),
    ("-X4", "Klemmleiste Motorabgang", "Reihenklemme 4 mm2", 4, "/3.5"),
]

# SPS-Eingaenge: Adresse, Symbol, Kommentar, Feldgeraet, Klemme -X3
INPUTS = [
    ("E0.0", "Start", "Taster Start, Schliesser", "-S1", "-X3:1"),
    ("E0.1", "Stop", "Taster Stop, Oeffner (1 = nicht betaetigt)", "-S2", "-X3:2"),
    ("E0.2", "MSS_OK", "Motorschutz -F2 Hilfskontakt (1 = ok)", "-F2", "-X3:3"),
    ("E0.3", "NotHalt_OK", "Sicherheitsrelais -K3 Freigabe (1 = Not-Halt entriegelt)", "-K3", "-X3:4"),
    ("E0.4", "LS_Einlauf", "Lichtschranke Einlauf -B1 (1 = Teil erkannt)", "-B1", "-X3:5"),
    ("E0.5", "LS_Auslauf", "Lichtschranke Auslauf -B2 (1 = Teil erkannt)", "-B2", "-X3:6"),
]

# SPS-Ausgaenge: Adresse, Symbol, Kommentar, Zielgeraet, Klemme
OUTPUTS = [
    ("A4.0", "K1_Vorwaerts", "Schuetz -K1 Foerdermotor vorwaerts", "-K1", "-X3:9"),
    ("A4.1", "K2_Rueckwaerts", "Schuetz -K2 Foerdermotor rueckwaerts", "-K2", "-X3:10"),
    ("A4.2", "H1_Betrieb", "Meldeleuchte -H1 Betrieb gruen", "-H1", "-X3:11"),
    ("A4.3", "H2_Stoerung", "Meldeleuchte -H2 Stoerung rot", "-H2", "-X3:12"),
]

MERKER = [
    ("M10.0", "Stoerung", "Sammelstoerung (Motorschutz oder Lichtschranke)"),
    ("M10.1", "Stoer_Quitt", "Stoerung quittiert (Flanke Start)"),
    ("MW100", "Stueckzahl", "Teile seit Schichtbeginn"),
]

# Klemmenplan -X3 (Feldgeraete): Klemme, Ziel intern (Schrank), Ziel extern (Feld), Funktion, Blatt
TERMINALS_X3 = [
    ("-X3:1", "-A1.1:1 (E0.0)", "-S1:13", "Start", "/5.3"),
    ("-X3:2", "-A1.1:2 (E0.1)", "-S2:11", "Stop", "/5.3"),
    ("-X3:3", "-A1.1:3 (E0.2)", "-F2:13", "Motorschutz ok", "/5.3"),
    ("-X3:4", "-A1.1:4 (E0.3)", "-K3:24", "Not-Halt Freigabe", "/5.3"),
    ("-X3:5", "-A1.1:5 (E0.4)", "-B1:4 (BK)", "Lichtschranke Einlauf", "/5.3"),
    ("-X3:6", "-A1.1:6 (E0.5)", "-B2:4 (BK)", "Lichtschranke Auslauf", "/5.3"),
    ("-X3:7", "-X2:1 (+24V)", "-B1:1 (BN), -B2:1 (BN)", "+24 V Sensoren", "/5.3"),
    ("-X3:8", "-X2:2 (0V)", "-B1:3 (BU), -B2:3 (BU)", "0 V Sensoren", "/5.4"),
    ("-X3:9", "-A1.2:1 (A4.0)", "-K1:A1", "Schuetz vorwaerts", "/6.3"),
    ("-X3:10", "-A1.2:2 (A4.1)", "-K2:A1", "Schuetz rueckwaerts", "/6.3"),
    ("-X3:11", "-A1.2:3 (A4.2)", "-H1:X1", "Meldeleuchte Betrieb", "/6.3"),
    ("-X3:12", "-A1.2:4 (A4.3)", "-H2:X1", "Meldeleuchte Stoerung", "/6.3"),
    ("-X3:13", "-X2:2 (0V)", "-K1:A2, -K2:A2", "0 V Schuetzspulen", "/6.6"),
    ("-X3:14", "-X2:2 (0V)", "-H1:X2, -H2:X2", "0 V Meldeleuchten", "/6.6"),
]

TERMINALS_X4 = [
    ("-X4:U", "-K1:2 / -K2:6", "-M1:U1", "Motor Phase U", "/3.5"),
    ("-X4:V", "-K1:4 / -K2:4", "-M1:V1", "Motor Phase V", "/3.5"),
    ("-X4:W", "-K1:6 / -K2:2", "-M1:W1", "Motor Phase W", "/3.6"),
    ("-X4:PE", "PE-Schiene", "-M1:PE", "Schutzleiter", "/3.5"),
]

PAGES = [
    (1, "Deckblatt und Inhaltsverzeichnis"),
    (2, "Netzeinspeisung 400 V und Steuerspannung 24 V DC"),
    (3, "Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)"),
    (4, "Not-Halt-Kreis und Bedientaster"),
    (5, "SPS -A1 Digitaleingaenge -A1.1"),
    (6, "SPS -A1 Digitalausgaenge -A1.2"),
    (7, "Klemmenplan -X3 und -X4"),
]
