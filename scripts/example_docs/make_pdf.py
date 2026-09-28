"""Erzeugt den Stromlaufplan als text-basiertes PDF (A4 quer, EPLAN-aehnliches Blattraster)."""

from pathlib import Path

from data import (
    INPUTS,
    LOC_CABINET,
    LOCATIONS_TEXT,
    OUTPUTS,
    PAGES,
    PLANT,
    TERMINALS_X3,
    TERMINALS_X4,
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

W, H = landscape(A4)
MARGIN = 28
FRAME_TOP = H - MARGIN
FRAME_BOTTOM = MARGIN + 60  # Platz fuer Schriftfeld
COLS = 8
COL_W = (W - 2 * MARGIN) / COLS


def col_x(col: float) -> float:
    """x-Koordinate der Spaltenmitte (Spalte 1..8, auch 2.5 moeglich)."""
    return MARGIN + (col - 0.5) * COL_W


class Sheet:
    def __init__(self, c: canvas.Canvas, page: int, title: str):
        self.c = c
        self.page = page
        self.title = title
        self._frame()

    def _frame(self):
        c = self.c
        c.setLineWidth(0.8)
        c.rect(MARGIN, MARGIN, W - 2 * MARGIN, H - 2 * MARGIN)
        # Spaltenraster oben und unten
        c.setFont("Helvetica", 8)
        for i in range(COLS):
            x = MARGIN + i * COL_W
            c.line(x, FRAME_TOP, x, FRAME_TOP - 12)
            c.drawCentredString(x + COL_W / 2, FRAME_TOP - 9, str(i + 1))
        c.line(MARGIN, FRAME_TOP - 12, W - MARGIN, FRAME_TOP - 12)
        # Schriftfeld
        c.line(MARGIN, FRAME_BOTTOM, W - MARGIN, FRAME_BOTTOM)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(MARGIN + 6, FRAME_BOTTOM - 16, f"Foerderband FB-01  {PLANT}{LOC_CABINET}")
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN + 6, FRAME_BOTTOM - 30, self.title)
        c.drawString(MARGIN + 6, FRAME_BOTTOM - 44, "Beispielanlage fuer Stromlauf AI. Frei erfunden, keine reale Anlage.")
        c.drawRightString(W - MARGIN - 6, FRAME_BOTTOM - 16, f"Blatt {self.page} / {len(PAGES)}")
        c.drawRightString(W - MARGIN - 6, FRAME_BOTTOM - 30, "Stand: 2026-09  Rev. A")
        c.drawRightString(W - MARGIN - 6, FRAME_BOTTOM - 44, "Zeichnungs-Nr. FB-01-E-001")

    # --- Zeichenhilfen -------------------------------------------------
    def text(self, x, y, s, size=8, bold=False, align="l"):
        self.c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        if align == "c":
            self.c.drawCentredString(x, y, s)
        elif align == "r":
            self.c.drawRightString(x, y, s)
        else:
            self.c.drawString(x, y, s)

    def wire(self, x1, y1, x2, y2):
        self.c.setLineWidth(0.9)
        self.c.line(x1, y1, x2, y2)

    def rail(self, y, label, x1=None, x2=None):
        x1 = MARGIN + 10 if x1 is None else x1
        x2 = W - MARGIN - 10 if x2 is None else x2
        self.c.setLineWidth(1.4)
        self.c.line(x1, y, x2, y)
        self.text(x1, y + 3, label, 8, bold=True)

    def device(self, x, y, bmk, label, w=26, h=26, extra=""):
        """Rechteck-Symbol mit BMK links und Beschreibung rechts."""
        self.c.setLineWidth(0.9)
        self.c.rect(x - w / 2, y - h / 2, w, h)
        self.text(x - w / 2 - 3, y - 3, bmk, 8, bold=True, align="r")
        if label:
            self.text(x + w / 2 + 3, y + 2, label, 7)
        if extra:
            self.text(x + w / 2 + 3, y - 8, extra, 7)

    def contact(self, x, y, bmk, pins, kind="NO"):
        """Schaltkontakt senkrecht: Schliesser (NO) oder Oeffner (NC)."""
        self.wire(x, y + 18, x, y + 6)
        self.wire(x, y - 18, x, y - 6)
        if kind == "NO":
            self.wire(x, y - 6, x - 8, y + 8)
        else:
            self.wire(x, y - 6, x - 8, y + 8)
            self.wire(x - 6, y + 6, x + 5, y + 6)
        self.text(x + 5, y - 2, bmk, 8, bold=True)
        self.text(x + 5, y + 9, pins[0], 6)
        self.text(x + 5, y - 13, pins[1], 6)

    def coil(self, x, y, bmk, pins=("A1", "A2")):
        self.wire(x, y + 18, x, y + 8)
        self.wire(x, y - 18, x, y - 8)
        self.c.rect(x - 9, y - 8, 18, 16)
        self.text(x + 12, y - 2, bmk, 8, bold=True)
        self.text(x + 12, y + 9, pins[0], 6)
        self.text(x + 12, y - 13, pins[1], 6)

    def terminal(self, x, y, label):
        self.c.circle(x, y, 3.2)
        self.text(x + 6, y - 2, label, 7)

    def xref(self, x, y, ref):
        self.text(x, y, ref, 7)


def page_1(s: Sheet):
    s.text(W / 2, H - 120, "Stromlaufplan Foerderband FB-01", 20, bold=True, align="c")
    s.text(W / 2, H - 145, f"Anlage {PLANT}: {LOCATIONS_TEXT}", 11, align="c")
    s.text(W / 2, H - 165, "Beispielanlage fuer Stromlauf AI: frei erfunden, ohne Herstellerbezug, frei verwendbar.", 9, align="c")
    y = H - 210
    s.text(MARGIN + 40, y, "Inhaltsverzeichnis", 11, bold=True)
    y -= 18
    for page, title in PAGES:
        s.text(MARGIN + 40, y, f"Blatt {page}", 9, bold=True)
        s.text(MARGIN + 100, y, title, 9)
        y -= 14
    y -= 10
    s.text(MARGIN + 40, y, "Funktionsbeschreibung", 11, bold=True)
    y -= 16
    lines = [
        "Das Foerderband FB-01 transportiert Werkstuecke vom Einlauf (Lichtschranke -B1) zum Auslauf (Lichtschranke -B2).",
        "Der Foerdermotor -M1 (1,5 kW) wird ueber die Wendeschuetze -K1 (vorwaerts) und -K2 (rueckwaerts) geschaltet.",
        "Die Steuerung uebernimmt die SPS -A1 mit der Eingabebaugruppe -A1.1 (E0.0 bis E0.5) und der Ausgabebaugruppe -A1.2 (A4.0 bis A4.3).",
        "Der Not-Halt -S3 wirkt zweikanalig auf das Sicherheitsrelais -K3, dessen Freigabekontakt die Schuetzspulen -K1/-K2 versorgt",
        "und ueber E0.3 an die SPS gemeldet wird. Motorschutz -F2 meldet ueber Hilfskontakt 13/14 an E0.2.",
        "Der Reparaturschalter -Q2 am Antrieb +AN1 trennt den Motor fuer Wartungsarbeiten. Am Bedienpult +BP1 zeigt -H3 einen betaetigten",
        "Not-Halt (Meldekontakt -K3 31/32), -P1 zaehlt die Betriebsstunden parallel zu -H1. -F3 sichert den 24-V-Steuerkreis zum Bedienpult.",
        "Zugehoerige Dokumente: Stueckliste FB-01, Klemmenplan FB-01, SPS-Programm FB-01 (AWL), Betriebsanleitung FB-01.",
    ]
    for line in lines:
        s.text(MARGIN + 40, y, line, 9)
        y -= 13


def page_2(s: Sheet):
    # Netz L1 L2 L3 N PE oben, Steuerspannung unten
    ys = {"L1": H - 90, "L2": H - 105, "L3": H - 120, "N": H - 135, "PE": H - 150}
    for name, y in ys.items():
        s.rail(y, name, x1=col_x(1) - 30, x2=col_x(8) + 30)
    s.text(col_x(1) - 30, ys["L1"] + 14, "Netzeinspeisung 3/N/PE AC 400/230 V 50 Hz, Vorsicherung bauseits 25 A", 8)
    # -X1 Klemmen
    for i, k in enumerate(["1", "2", "3", "N", "PE"]):
        y = list(ys.values())[i]
        s.terminal(col_x(1), y, f"-X1:{k}")
    # -Q1 Hauptschalter
    x = col_x(2)
    for y in (ys["L1"], ys["L2"], ys["L3"]):
        s.wire(x - 40, y, x - 10, y)
        s.wire(x + 10, y, x + 40, y)
    s.device(x, ys["L2"], "-Q1", "Hauptschalter 25 A", w=20, h=50, extra="1/2 3/4 5/6")
    s.xref(x - 10, ys["L3"] - 22, "-> /3.1 (L1 L2 L3 zum Motorabgang)")
    # Steuerspannung: -F1 von L1 nach -T1
    xf = col_x(4)
    yF = H - 200
    s.wire(xf, ys["L1"], xf, yF + 18)
    s.contact(xf, yF, "-F1", ("1", "2"))
    s.text(xf + 5, yF - 24, "B6 A", 7)
    yT = H - 270
    s.wire(xf, yF - 18, xf, yT + 20)
    s.device(xf, yT, "-T1", "Netzteil 230 V AC / 24 V DC 5 A", w=60, h=40, extra="L N   -   +")
    s.wire(xf + 20, yT + 20, xf + 20, ys["N"])
    s.text(xf + 22, ys["N"] - 12, "N", 6)
    # 24V Rails
    y24 = H - 330
    y0 = H - 345
    s.rail(y24, "+24 V DC (L+)", x1=col_x(4) - 40, x2=col_x(8) + 30)
    s.rail(y0, "0 V DC (M)", x1=col_x(4) - 40, x2=col_x(8) + 30)
    s.wire(xf + 10, yT - 20, xf + 10, y24)
    s.wire(xf - 10, yT - 20, xf - 10, y0)
    s.terminal(col_x(5), y24, "-X2:1  +24 V")
    s.terminal(col_x(5), y0, "-X2:2  0 V")
    # -F3 sichert den Abgang zum Bedienpult (Not-Halt-Kreis, Taster, Leuchten): Abzweig nach oben von der 24-V-Schiene
    xf3 = col_x(6)
    s.wire(xf3, y24, xf3, y24 + 10)
    s.contact(xf3, y24 + 28, "-F3", ("1", "2"))
    s.text(xf3 + 5, y24 + 52, "B4 A, Steuerkreis Bedienpult +BP1", 6)
    s.wire(xf3, y24 + 46, xf3, y24 + 62)
    s.terminal(xf3, y24 + 66, "-X2:3  +24 V -> /4.1 Not-Halt")
    s.terminal(col_x(6), y0, "-X2:4  0 V")
    s.terminal(col_x(7), y24, "-X2:5  +24 V -> /5.1 SPS")
    s.terminal(col_x(7), y0, "-X2:6  0 V -> /5.1 SPS")
    s.text(col_x(4) - 40, y0 - 22, "Steuerspannung 24 V DC. Absicherung sekundaer im Netzteil -T1 (elektronisch).", 8)


def page_3(s: Sheet):
    ys = [H - 90, H - 105, H - 120]
    for name, y in zip(["L1", "L2", "L3"], ys, strict=True):
        s.rail(y, name, x1=col_x(1) - 30, x2=col_x(3))
    s.xref(col_x(1) - 30, ys[0] + 14, "von /2.2 (-Q1)")
    # -F2 Motorschutz
    xf = col_x(2)
    yF = H - 180
    for dx in (-8, 0, 8):
        s.wire(xf + dx, ys[0] - 0 if dx == -8 else ys[1] if dx == 0 else ys[2], xf + dx, yF + 22)
    s.device(xf, yF, "-F2", "Motorschutzschalter 2,5-4 A", w=40, h=44, extra="Einstellung 3,6 A")
    s.text(xf + 23, yF - 18, "Hilfskontakt 13/14 -> /5.3 (E0.2)", 7)
    # Wendeschuetz K1 / K2
    yK = H - 260
    xk1, xk2 = col_x(4), col_x(6)
    for x, bmk, lbl in ((xk1, "-K1", "vorwaerts  /6.4"), (xk2, "-K2", "rueckwaerts  /6.5")):
        for dx in (-8, 0, 8):
            s.wire(x + dx, yK + 40, x + dx, yK + 22)
            s.wire(x + dx, yK - 22, x + dx, yK - 40)
        s.device(x, yK, bmk, f"Schuetz {lbl}", w=40, h=44, extra="1/2 3/4 5/6")
    s.wire(xf - 8, yF - 22, xf - 8, yK + 40)
    s.wire(xf - 8, yK + 40, xk2 + 8, yK + 40)
    s.wire(xf, yF - 22, xf, yK + 46)
    s.wire(xf, yK + 46, xk2, yK + 46)
    s.wire(xk2, yK + 46, xk2, yK + 40)
    s.wire(xf + 8, yF - 22, xf + 8, yK + 52)
    s.wire(xf + 8, yK + 52, xk2 - 8, yK + 52)
    s.wire(xk2 - 8, yK + 52, xk2 - 8, yK + 40)
    s.text(xk1 - 60, yK + 60, "Drehrichtungsumkehr: -K2 tauscht L1 und L3 (Phasen U/W).", 7)
    # -X4 Klemmen und Motor
    yX = H - 340
    xm = col_x(5)
    for dx in (-12, 0, 12):  # Phasen U, V, W
        s.wire(xm + dx, yK - 40, xm + dx, yX + 4)
        s.terminal(xm + dx, yX, "")
    s.text(xm + 20, yX - 3, "-X4:U  -X4:V  -X4:W  (Leitung -W4 4G2,5 zum Antrieb +AN1)", 7)
    s.terminal(xm + 26, yX, "")
    s.text(xm + 26 + 6, yX - 12, "-X4:PE", 6)
    # -Q2 Reparaturschalter am Antrieb, zwischen -X4 und Motor
    yQ = H - 372
    for dx in (-12, 0, 12):
        s.wire(xm + dx, yX - 4, xm + dx, yQ + 14)
    s.device(xm, yQ, "-Q2", "Reparaturschalter 3-polig, abschliessbar", w=40, h=28, extra="Ort +AN1, 1/2 3/4 5/6")
    yM = H - 420
    for dx in (-12, 0, 12):
        s.wire(xm + dx, yQ - 14, xm + dx, yM + 22)
    s.c.circle(xm, yM, 22)
    s.text(xm, yM - 4, "M", 11, bold=True, align="c")
    s.text(xm, yM - 14, "3~", 8, align="c")
    s.text(xm + 28, yM + 4, "-M1  Foerdermotor 1,5 kW  400 V  3,5 A  1420 1/min", 8, bold=True)
    s.text(xm + 28, yM - 8, "Anschluss U1 V1 W1 PE, Schaltung Stern, Ort +AN1", 7)
    s.text(col_x(1) - 30, H - 470, "Hinweis: Motorschutz -F2 loest bei Ueberlast aus, Hilfskontakt 13/14 oeffnet, SPS meldet Stoerung -H2 (siehe Betriebsanleitung Kap. 6).", 8)


def page_4(s: Sheet):
    y24 = H - 90
    y0 = H - 400
    s.rail(y24, "+24 V DC von -X2:3 (/2.6)", x1=col_x(1) - 30, x2=col_x(8) + 30)
    s.rail(y0, "0 V DC von -X2:4 (/2.6)", x1=col_x(1) - 30, x2=col_x(8) + 30)
    # Not-Halt zwei Kanaele -> -K3
    x1, x2 = col_x(2) - 15, col_x(2) + 15
    yS = H - 160
    for x, pins in ((x1, ("11", "12")), (x2, ("21", "22"))):
        s.wire(x, y24, x, yS + 18)
        s.contact(x, yS, "-S3" if x == x1 else "", pins, kind="NC")
    s.text(col_x(2) - 40, yS - 30, "-S3 Not-Halt, 2 Oeffner, Ort +BP1 Bedienpult", 7)
    yK3 = H - 260
    s.device(col_x(2), yK3, "-K3", "Sicherheitsrelais 2-kanalig", w=70, h=50, extra="S11 S12 S21 S22 / 13-14 23-24")
    s.wire(x1, yS - 18, x1, yK3 + 25)
    s.wire(x2, yS - 18, x2, yK3 + 25)
    s.wire(col_x(2), yK3 - 25, col_x(2), y0)
    s.text(col_x(2) + 40, yK3 - 40, "A1/A2 Spule 24 V DC", 7)
    # Freigabekontakt K3 13/14 -> Schuetzspulen-Versorgung, 23/24 -> E0.3
    xr = col_x(4)
    yR = H - 160
    s.wire(xr, y24, xr, yR + 18)
    s.contact(xr, yR, "-K3", ("13", "14"), kind="NO")
    s.wire(xr, yR - 18, xr, yR - 60)
    s.text(xr + 5, yR - 40, "Freigabe Schuetzspulen /6.4", 6)
    s.terminal(xr, yR - 66, "")
    s.text(xr, yR - 80, "-X2:3a", 7, bold=True, align="c")
    s.text(xr, yR - 90, "+24 V freigegeben", 6, align="c")
    xr2 = col_x(5)
    s.wire(xr2, y24, xr2, yR + 18)
    s.contact(xr2, yR, "-K3", ("23", "24"), kind="NO")
    s.wire(xr2, yR - 18, xr2, yR - 60)
    s.terminal(xr2, yR - 66, "")
    s.text(xr2, yR - 80, "-X3:4", 7, bold=True, align="c")
    s.text(xr2, yR - 90, "E0.3 NotHalt_OK /5.5", 6, align="c")
    # Meldekontakt -K3 31/32 (Oeffner) in Spalte 8: -H3 leuchtet, solange der Not-Halt nicht entriegelt ist
    xh = col_x(8)
    s.wire(xh, y24, xh, yR + 18)
    s.contact(xh, yR, "-K3", ("31", "32"), kind="NC")
    s.wire(xh, yR - 18, xh, yR - 60)
    s.terminal(xh, yR - 66, "")
    s.text(xh, yR - 80, "-X3:15", 7, bold=True, align="c")
    s.wire(xh, yR - 70, xh, yR - 111)
    s.c.circle(xh, yR - 120, 9)
    s.text(xh - 12, yR - 122, "-H3", 8, bold=True, align="r")
    s.text(xh - 12, yR - 132, "Not-Halt betaetigt (gelb)", 6, align="r")
    s.text(xh - 12, yR - 141, "0 V ueber -X3:14", 6, align="r")
    s.wire(xh, yR - 129, xh, y0)
    # Taster S1 S2 an SPS
    xs1, xs2 = col_x(6), col_x(7)
    yT = H - 160
    s.wire(xs1, y24, xs1, yT + 18)
    s.contact(xs1, yT, "-S1", ("13", "14"), kind="NO")
    s.wire(xs1, yT - 18, xs1, yT - 60)
    s.terminal(xs1, yT - 66, "")
    s.text(xs1, yT - 80, "-X3:1", 7, bold=True, align="c")
    s.text(xs1, yT - 90, "E0.0 Start /5.4", 6, align="c")
    s.wire(xs2, y24, xs2, yT + 18)
    s.contact(xs2, yT, "-S2", ("11", "12"), kind="NC")
    s.wire(xs2, yT - 18, xs2, yT - 60)
    s.terminal(xs2, yT - 66, "")
    s.text(xs2, yT - 80, "-X3:2", 7, bold=True, align="c")
    s.text(xs2, yT - 90, "E0.1 Stop /5.4", 6, align="c")
    s.text(col_x(4) - 30, H - 300, "Taster, Leuchten -H1/-H2/-H3, Zaehler -P1 und Not-Halt: Bedienpult +BP1.", 8)
    s.text(col_x(4) - 30, H - 314, "Leitung -W1 12x0,75 mm2 zur Klemmleiste -X3 im Schaltschrank +ST1.", 8)
    s.text(col_x(4) - 30, H - 328, "Sicherheitsfunktion: Not-Halt Kat. 3 / PL d.", 8)
    s.text(col_x(4) - 30, H - 342, "Ruecksetzen nur durch Entriegeln von -S3 und Start -S1 (Wiederanlaufsperre im Programm FB10).", 8)


def page_5(s: Sheet):
    s.text(col_x(1) - 30, H - 80, "SPS -A1, Digitaleingabe -A1.1, 16 x DC 24 V, Adressbereich EB0 (E0.0 bis E1.7). Versorgung L+ von -X2:5, M von -X2:6 (/2.7).", 8)
    xcard = col_x(2)
    s.c.rect(xcard - 45, H - 470, 90, 350)
    s.text(xcard, H - 135, "-A1.1", 10, bold=True, align="c")
    s.text(xcard, H - 147, "DI 16 x 24 V DC", 7, align="c")
    for i, (addr, sym, comment, dev, term) in enumerate(INPUTS):
        y = H - 180 - i * 40
        s.text(xcard - 40, y - 2, f"{i + 1}", 7)
        s.text(xcard - 25, y - 2, addr, 9, bold=True)
        s.wire(xcard + 45, y, col_x(3) - 4, y)
        s.terminal(col_x(3), y, term)
        s.wire(col_x(3) + 4, y, col_x(5), y)
        s.text(col_x(5) + 6, y + 3, f"{sym}", 8, bold=True)
        s.text(col_x(5) + 6, y - 8, f"{comment}", 7)
        s.text(col_x(7) + 10, y - 2, f"von {dev}", 8)
    yo = H - 180 - 6 * 40
    s.text(xcard - 25, yo - 2, "E0.6 .. E1.7", 8)
    s.text(xcard + 50, yo - 2, "Reserve", 7)
    s.text(col_x(3) - 10, H - 460, "-X3:7 (+24 V) und -X3:8 (0 V) versorgen die Lichtschranken -B1/-B2 (BN/BU) am Einlauf +SE1 / Auslauf +SA1, Schaltausgang BK auf -X3:5 bzw. -X3:6.", 8)
    s.text(col_x(3) - 10, H - 474, "Programm: OB1 ruft FB10 \"Foerderband\" mit Instanz DB10. Symbole siehe Symboltabelle FB-01.", 8)


def page_6(s: Sheet):
    s.text(col_x(1) - 30, H - 80, "SPS -A1, Digitalausgabe -A1.2, 16 x DC 24 V / 0,5 A, Adressbereich AB4 (A4.0 bis A5.7). Spulenversorgung ueber -K3 Freigabe (/4.4).", 8)
    xcard = col_x(2)
    s.c.rect(xcard - 45, H - 400, 90, 280)
    s.text(xcard, H - 135, "-A1.2", 10, bold=True, align="c")
    s.text(xcard, H - 147, "DO 16 x 24 V DC", 7, align="c")
    for i, (addr, sym, comment, dev, term) in enumerate(OUTPUTS):
        y = H - 180 - i * 45
        s.text(xcard - 40, y - 2, f"{i + 1}", 7)
        s.text(xcard - 25, y - 2, addr, 9, bold=True)
        s.wire(xcard + 45, y, col_x(3) - 4, y)
        s.terminal(col_x(3), y, term)
        s.wire(col_x(3) + 4, y, col_x(5) - 20, y)
        if dev.startswith("-K"):
            s.coil(col_x(5), y, dev)
            s.wire(col_x(5) - 20, y, col_x(5), y)
            s.text(col_x(5) + 30, y + 8, "Spule A1/A2, 0 V ueber -X3:13", 7)
        else:
            s.c.circle(col_x(5), y, 9)
            s.wire(col_x(5) - 20, y, col_x(5) - 9, y)
            s.text(col_x(5) + 12, y - 2, dev, 8, bold=True)
            s.text(col_x(5) + 30, y + 8, "X1/X2, 0 V ueber -X3:14", 7)
        s.text(col_x(6) + 10, y - 2, f"{sym}: {comment}", 7)
        if dev == "-H1":  # Betriebsstundenzaehler -P1 haengt parallel zur Betriebsleuchte
            yp = y - 24
            s.wire(col_x(5) - 20, y, col_x(5) - 20, yp)
            s.wire(col_x(5) - 20, yp, col_x(6) - 9, yp)
            s.c.circle(col_x(6), yp, 9)
            s.text(col_x(6) + 12, yp - 2, "-P1", 8, bold=True)
            s.text(col_x(6) + 12, yp + 8, "Betriebsstundenzaehler parallel zu -H1, 0 V ueber -X3:14", 6)
    yo = H - 180 - 4 * 45
    s.text(xcard - 25, yo - 2, "A4.4 .. A5.7", 8)
    s.text(xcard + 50, yo - 2, "Reserve", 7)
    s.text(col_x(3) - 10, H - 430, "Verriegelung: -K1 und -K2 duerfen nie gleichzeitig anziehen. Software-Verriegelung in FB10 Netzwerk 2 und 3,", 8)
    s.text(col_x(3) - 10, H - 444, "zusaetzlich Hilfskontakt 21/22 des jeweils anderen Schuetzes in Reihe zur Spule (nicht dargestellt, siehe Klemmenplan -X3:9/-X3:10).", 8)


def page_7(s: Sheet):
    s.text(col_x(1) - 30, H - 80, "Klemmenplan -X3 (Feldgeraete) und -X4 (Motorabgang), Schaltschrank +ST1", 10, bold=True)
    cols = [col_x(1) - 30, col_x(1) + 40, col_x(3) - 20, col_x(5) - 30, col_x(7) - 30]
    heads = ["Klemme", "intern", "extern (Feld)", "Funktion", "Blatt"]
    y = H - 105
    for x, h in zip(cols, heads, strict=True):
        s.text(x, y, h, 8, bold=True)
    s.wire(cols[0], y - 4, W - MARGIN - 10, y - 4)
    for row in TERMINALS_X3 + TERMINALS_X4:
        y -= 14
        for x, cell in zip(cols, row, strict=True):
            s.text(x, y, cell, 8)
    s.text(col_x(1) - 30, y - 30, "Leitungen: -W1 -X3 -> Bedienpult +BP1 12x0,75 mm2, -W2/-W3 -X3 -> Lichtschranken +SE1/+SA1 4x0,5 mm2, -W4 -X4 -> Antrieb +AN1 4G2,5 mm2.", 8)


def build(out: Path):
    c = canvas.Canvas(str(out), pagesize=landscape(A4))
    c.setTitle("Stromlaufplan Foerderband FB-01")
    c.setAuthor("Stromlauf AI Beispielanlage")
    builders = [page_1, page_2, page_3, page_4, page_5, page_6, page_7]
    for (page, title), fn in zip(PAGES, builders, strict=True):
        fn(Sheet(c, page, title))
        c.showPage()
    c.save()


if __name__ == "__main__":
    import sys

    build(Path(sys.argv[1]))
