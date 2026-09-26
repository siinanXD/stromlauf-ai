"""Stueckliste (xlsx), Klemmenplan (csv), AWL, Symboltabelle (sdf), Betriebsanleitung (md)."""

import csv
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font

from data import DEVICES, INPUTS, LOC_CABINET, LOC_FIELD, MERKER, OUTPUTS, PLANT, TERMINALS_X3, TERMINALS_X4

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

FIELD_DEVICES = {"-M1", "-S1", "-S2", "-S3", "-B1", "-B2", "-H1", "-H2"}


def stueckliste():
    wb = Workbook()
    ws = wb.active
    ws.title = "Stueckliste"
    ws.append(["Stueckliste Foerderband FB-01", "", "", "", "", ""])
    ws.append([f"Anlage {PLANT}, Schaltschrank {LOC_CABINET}, Feld {LOC_FIELD}. Beispielanlage, frei erfunden, ohne Herstellerbezug.", "", "", "", "", ""])
    ws.append([])
    head = ["BMK", "Bezeichnung", "Typ / Kenndaten", "Menge", "Einbauort", "Blatt"]
    ws.append(head)
    for cell in ws[4]:
        cell.font = Font(bold=True)
    for bmk, name, typ, qty, page in DEVICES:
        ort = LOC_FIELD if bmk in FIELD_DEVICES else LOC_CABINET
        ws.append([bmk, name, typ, qty, ort, page])
    ws.append([])
    ws.append(["-W1", "Steuerleitung Bedienpult", "12 x 0,75 mm2, 8 m", 1, f"{LOC_CABINET} -> {LOC_FIELD}", "/4.6"])
    ws.append(["-W2", "Sensorleitung Lichtschranke Einlauf", "4 x 0,5 mm2, 6 m", 1, f"{LOC_CABINET} -> {LOC_FIELD}", "/5.5"])
    ws.append(["-W3", "Sensorleitung Lichtschranke Auslauf", "4 x 0,5 mm2, 9 m", 1, f"{LOC_CABINET} -> {LOC_FIELD}", "/5.5"])
    ws.append(["-W4", "Motorleitung", "4G2,5 mm2, 7 m", 1, f"{LOC_CABINET} -> {LOC_FIELD}", "/3.5"])
    widths = [10, 44, 40, 8, 16, 8]
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
    wb.save(OUT / "02_Stueckliste_FB-01.xlsx")


def klemmenplan():
    with (OUT / "03_Klemmenplan_FB-01.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Klemmleiste", "Klemme", "Ziel intern", "Ziel extern", "Funktion", "Blatt"])
        for row in TERMINALS_X3:
            w.writerow(["-X3"] + list(row))
        for row in TERMINALS_X4:
            w.writerow(["-X4"] + list(row))
        w.writerow(["-X1", "-X1:1", "-Q1:1", "Netz L1", "Einspeisung L1", "/2.1"])
        w.writerow(["-X1", "-X1:2", "-Q1:3", "Netz L2", "Einspeisung L2", "/2.1"])
        w.writerow(["-X1", "-X1:3", "-Q1:5", "Netz L3", "Einspeisung L3", "/2.1"])
        w.writerow(["-X1", "-X1:N", "-T1:N", "Netz N", "Neutralleiter", "/2.1"])
        w.writerow(["-X1", "-X1:PE", "PE-Schiene", "Netz PE", "Schutzleiter", "/2.1"])
        w.writerow(["-X2", "-X2:1", "-T1:+", "-X3:7", "+24 V Sensoren", "/2.5"])
        w.writerow(["-X2", "-X2:2", "-T1:-", "-X3:8, -X3:13, -X3:14", "0 V", "/2.5"])
        w.writerow(["-X2", "-X2:3", "-T1:+", "-S3:11, -S3:21", "+24 V Not-Halt-Kreis", "/2.6"])
        w.writerow(["-X2", "-X2:3a", "-K3:14", "-K1:A1 / -K2:A1 (ueber -A1.2)", "+24 V freigegeben", "/4.4"])
        w.writerow(["-X2", "-X2:4", "-T1:-", "-K3:A2", "0 V Not-Halt-Kreis", "/2.6"])
        w.writerow(["-X2", "-X2:5", "-T1:+", "-A1:L+", "+24 V SPS", "/2.7"])
        w.writerow(["-X2", "-X2:6", "-T1:-", "-A1:M", "0 V SPS", "/2.7"])


def awl():
    text = '''FUNCTION_BLOCK FB 10
TITLE =Foerderband FB-01 Steuerung
//Ansteuerung Foerdermotor -M1 ueber Wendeschuetze -K1 / -K2,
//Stoerungsauswertung, Stueckzaehlung. Anlage =FB1, Schaltschrank +ST1.
AUTHOR : Beispiel
FAMILY : FB01
NAME : Foerder
VERSION : 1.0

VAR_INPUT
  Start : BOOL ;	//Taster -S1 Start (E0.0)
  Stop : BOOL ;	//Taster -S2 Stop, Oeffner (E0.1)
  MSS_OK : BOOL ;	//Motorschutz -F2 Hilfskontakt (E0.2)
  NotHalt_OK : BOOL ;	//Sicherheitsrelais -K3 Freigabe (E0.3)
  LS_Einlauf : BOOL ;	//Lichtschranke -B1 (E0.4)
  LS_Auslauf : BOOL ;	//Lichtschranke -B2 (E0.5)
  Richtung_Rueck : BOOL ;	//1 = Rueckwaertsbetrieb (Wartung)
END_VAR
VAR_OUTPUT
  Vorwaerts : BOOL ;	//Schuetz -K1 (A4.0)
  Rueckwaerts : BOOL ;	//Schuetz -K2 (A4.1)
  Betrieb : BOOL ;	//Meldeleuchte -H1 (A4.2)
  Stoerung : BOOL ;	//Meldeleuchte -H2 (A4.3)
END_VAR
VAR
  Freigabe : BOOL ;	//Selbsthaltung Betrieb
  Flanke_Start : BOOL ;	//Flankenmerker Start
  Flanke_Auslauf : BOOL ;	//Flankenmerker Lichtschranke Auslauf
  Stueckzahl : INT ;	//Teile seit Quittierung
  Timer_Blockade : S5TIME ;	//Ueberwachung Einlauf -> Auslauf
END_VAR
BEGIN
NETWORK
TITLE =Selbsthaltung Betrieb
//Start setzt die Freigabe, Stop (Oeffner), Motorschutz oder Not-Halt setzen zurueck.
//Wiederanlaufsperre: nach Not-Halt ist ein neuer Start noetig.
      U(    ;
      O     #Start;
      O     #Freigabe;
      )     ;
      U     #Stop;
      U     #MSS_OK;
      U     #NotHalt_OK;
      UN    #Stoerung;
      =     #Freigabe;
NETWORK
TITLE =Schuetz vorwaerts -K1
//Verriegelung gegen -K2: vorwaerts nur, wenn rueckwaerts nicht angesteuert.
      U     #Freigabe;
      UN    #Richtung_Rueck;
      UN    #Rueckwaerts;
      =     #Vorwaerts;
NETWORK
TITLE =Schuetz rueckwaerts -K2
//Verriegelung gegen -K1.
      U     #Freigabe;
      U     #Richtung_Rueck;
      UN    #Vorwaerts;
      =     #Rueckwaerts;
NETWORK
TITLE =Stoerung Motorschutz
//Motorschutz -F2 ausgeloest: Sammelstoerung setzen. Quittierung mit Start bei stehendem Band.
      UN    #MSS_OK;
      S     #Stoerung;
      U     #Start;
      UN    #Freigabe;
      U     #MSS_OK;
      R     #Stoerung;
NETWORK
TITLE =Stoerung Blockade Band
//Teil am Einlauf erkannt, aber innerhalb von 20 s nicht am Auslauf: Blockade.
      U     #LS_Einlauf;
      U     #Vorwaerts;
      L     S5T#20S;
      SE    T     5;
      U     #LS_Auslauf;
      R     T     5;
      U     T     5;
      S     #Stoerung;
NETWORK
TITLE =Meldeleuchte Betrieb -H1
      U     #Freigabe;
      =     #Betrieb;
NETWORK
TITLE =Stueckzaehlung
//Steigende Flanke Lichtschranke Auslauf -B2 zaehlt ein Teil.
      U     #LS_Auslauf;
      FP    #Flanke_Auslauf;
      SPBN  ende;
      L     #Stueckzahl;
      L     1;
      +I    ;
      T     #Stueckzahl;
      T     MW   100;
ende: NOP   0;
END_FUNCTION_BLOCK

DATA_BLOCK DB 10
TITLE =Instanz Foerderband FB-01
VERSION : 1.0
 FB 10
BEGIN
END_DATA_BLOCK

ORGANIZATION_BLOCK OB 1
TITLE = "Main Program Sweep (Cycle)"
VERSION : 1.0

VAR_TEMP
  OB1_EV_CLASS : BYTE ;
  OB1_SCAN_1 : BYTE ;
  OB1_PRIORITY : BYTE ;
  OB1_OB_NUMBR : BYTE ;
  OB1_RESERVED_1 : BYTE ;
  OB1_RESERVED_2 : BYTE ;
  OB1_PREV_CYCLE : INT ;
  OB1_MIN_CYCLE : INT ;
  OB1_MAX_CYCLE : INT ;
  OB1_DATE_TIME : DATE_AND_TIME ;
END_VAR
BEGIN
NETWORK
TITLE =Aufruf Foerderband FB-01
//Eingaenge -A1.1 (EB0), Ausgaenge -A1.2 (AB4)
      CALL  FB    10 , DB    10
       Start                    :=E      0.0
       Stop                     :=E      0.1
       MSS_OK                   :=E      0.2
       NotHalt_OK               :=E      0.3
       LS_Einlauf               :=E      0.4
       LS_Auslauf               :=E      0.5
       Richtung_Rueck           :=M     20.0
       Vorwaerts                :=A      4.0
       Rueckwaerts              :=A      4.1
       Betrieb                  :=A      4.2
       Stoerung                 :=A      4.3
      NOP   0;
NETWORK
TITLE =Sammelstoerung Merker
//Stoerung fuer Visualisierung spiegeln
      U     A      4.3;
      =     M     10.0;
END_ORGANIZATION_BLOCK
'''
    (OUT / "04_SPS_Programm_FB-01.awl").write_text(text, encoding="utf-8", newline="\r\n")


def symbole():
    rows = []
    for addr, sym, comment, _dev, _term in INPUTS:
        rows.append((sym, addr.replace("E", "E ", 1), "BOOL", comment))
    for addr, sym, comment, _dev, _term in OUTPUTS:
        rows.append((sym, addr.replace("A", "A ", 1), "BOOL", comment))
    for addr, sym, comment in MERKER:
        a = addr.replace("MW", "MW ", 1) if addr.startswith("MW") else addr.replace("M", "M ", 1)
        rows.append((sym, a, "INT" if addr.startswith("MW") else "BOOL", comment))
    rows.append(("Richtung_Rueck", "M 20.0", "BOOL", "Rueckwaertsbetrieb Wartung (Bedienpanel)"))
    rows.append(("T_Blockade", "T 5", "TIMER", "Ueberwachung Einlauf -> Auslauf 20 s"))
    rows.append(("FB_Foerder", "FB 10", "FB 10", "Foerderband FB-01 Steuerung"))
    rows.append(("DB_Foerder", "DB 10", "FB 10", "Instanz Foerderband FB-01"))
    rows.append(("Zyklus", "OB 1", "OB 1", "Main Program Sweep (Cycle)"))
    with (OUT / "05_Symboltabelle_FB-01.sdf").open("w", newline="", encoding="latin-1") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        for r in rows:
            w.writerow(r)


def anleitung():
    inputs = "\n".join(f"| {a} | {s} | {c} | {d} | {t} |" for a, s, c, d, t in INPUTS)
    outputs = "\n".join(f"| {a} | {s} | {c} | {d} | {t} |" for a, s, c, d, t in OUTPUTS)
    text = f"""# Betriebsanleitung Foerderband FB-01

Anlage {PLANT}, Schaltschrank {LOC_CABINET}, Feld {LOC_FIELD}. Beispielanlage fuer Stromlauf AI,
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
{inputs}
{outputs}

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
"""
    (OUT / "06_Betriebsanleitung_FB-01.md").write_text(text, encoding="utf-8")


stueckliste()
klemmenplan()
awl()
symbole()
anleitung()
print(sorted(p.name for p in OUT.iterdir()))
