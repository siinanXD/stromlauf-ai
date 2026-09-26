"""Stromlaufplan als text-basiertes PDF (A4 quer, 8 Spalten) aus dem Maschinenmodell.

Blaetter: Deckblatt, Einspeisung, Antriebe (je 3), Sicherheitskreise, Bedienpult, Digitaleingaenge,
Digitalausgaenge, Klemmenplan. Jede gezeichnete Beschriftung registriert ihre Kennzeichen in `Refs`.
"""

from pathlib import Path

from model import TAG, Machine, Refs, Signal
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

W, H = landscape(A4)
MARGIN = 28
FRAME_TOP = H - MARGIN
FRAME_BOTTOM = MARGIN + 60
COLS = 8
COL_W = (W - 2 * MARGIN) / COLS
DI_PER_PAGE = 12
DO_PER_PAGE = 11  # mehr passt nicht neben die Baugruppe
MAX_SAFETY_DEVICES = 5  # sonst kreuzt das Relais die 0-V-Schiene
DRIVES_PER_PAGE = 2
DRIVE_COLUMNS = (2, 6)
TERMINAL_ROWS_PER_PAGE = 26


def col_x(col: float) -> float:
    return MARGIN + (col - 0.5) * COL_W


def col_of(x: float) -> int:
    return max(1, min(COLS, int((x - MARGIN) // COL_W) + 1))


class Sheet:
    def __init__(self, c: canvas.Canvas, machine: Machine, refs: Refs, page: int, total: int, title: str):
        self.c, self.m, self.refs, self.page, self.total, self.title = c, machine, refs, page, total, title
        self._frame()

    def _frame(self) -> None:
        c, m = self.c, self.m
        c.setLineWidth(0.8)
        c.rect(MARGIN, MARGIN, W - 2 * MARGIN, H - 2 * MARGIN)
        c.setFont("Helvetica", 8)
        for i in range(COLS):
            x = MARGIN + i * COL_W
            c.line(x, FRAME_TOP, x, FRAME_TOP - 12)
            c.drawCentredString(x + COL_W / 2, FRAME_TOP - 9, str(i + 1))
        c.line(MARGIN, FRAME_TOP - 12, W - MARGIN, FRAME_TOP - 12)
        c.line(MARGIN, FRAME_BOTTOM, W - MARGIN, FRAME_BOTTOM)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(MARGIN + 6, FRAME_BOTTOM - 16, f"{m.title}  {m.plant}{m.loc_cabinet}")
        c.setFont("Helvetica", 9)
        c.drawString(MARGIN + 6, FRAME_BOTTOM - 30, self.title)
        c.drawString(MARGIN + 6, FRAME_BOTTOM - 44, "Testdokumentation fuer Stromlauf AI. Frei erfunden, keine reale Anlage.")
        c.drawRightString(W - MARGIN - 6, FRAME_BOTTOM - 16, f"Blatt {self.page} / {self.total}")
        c.drawRightString(W - MARGIN - 6, FRAME_BOTTOM - 30, "Stand: 2026-09  Rev. A")
        c.drawRightString(W - MARGIN - 6, FRAME_BOTTOM - 44, f"Zeichnungs-Nr. {m.drawing_no}")

    # --- Text mit Registrierung der Kennzeichen ---------------------------------------------
    def text(self, x, y, s, size=8, bold=False, align="l", primary=False) -> None:
        font = "Helvetica-Bold" if bold else "Helvetica"
        self.c.setFont(font, size)
        width = stringWidth(s, font, size)
        start = x if align == "l" else x - width / 2 if align == "c" else x - width
        if align == "c":
            self.c.drawCentredString(x, y, s)
        elif align == "r":
            self.c.drawRightString(x, y, s)
        else:
            self.c.drawString(x, y, s)
        for match in TAG.finditer(s):
            left = start + stringWidth(s[: match.start()], font, size)
            self.refs.add(match.group(0), self.page, col_of(left + 1), primary)

    def wire(self, x1, y1, x2, y2) -> None:
        self.c.setLineWidth(0.9)
        self.c.line(x1, y1, x2, y2)

    def rail(self, y, label, x1=None, x2=None) -> None:
        x1 = MARGIN + 10 if x1 is None else x1
        x2 = W - MARGIN - 10 if x2 is None else x2
        self.c.setLineWidth(1.4)
        self.c.line(x1, y, x2, y)
        self.text(x1, y + 3, label, 8, bold=True)

    def device(self, x, y, bmk, label, w=26, h=26, extra="") -> None:
        self.c.setLineWidth(0.9)
        self.c.rect(x - w / 2, y - h / 2, w, h)
        self.text(x - w / 2 - 3, y - 3, bmk, 8, bold=True, align="r", primary=True)
        if label:
            self.text(x + w / 2 + 3, y + 2, label, 7)
        if extra:
            self.text(x + w / 2 + 3, y - 8, extra, 7)

    def contact(self, x, y, bmk, pins, kind="NO") -> None:
        self.wire(x, y + 18, x, y + 6)
        self.wire(x, y - 18, x, y - 6)
        self.wire(x, y - 6, x - 8, y + 8)
        if kind == "NC":
            self.wire(x - 6, y + 6, x + 5, y + 6)
        if bmk:
            self.text(x + 5, y - 2, bmk, 8, bold=True, primary=True)
        self.text(x + 5, y + 9, pins[0], 6)
        self.text(x + 5, y - 13, pins[1], 6)

    def coil(self, x, y, bmk, pins=("A1", "A2")) -> None:
        self.wire(x, y + 18, x, y + 8)
        self.wire(x, y - 18, x, y - 8)
        self.c.rect(x - 9, y - 8, 18, 16)
        self.text(x + 12, y - 2, bmk, 8, bold=True, primary=True)
        self.text(x + 12, y + 9, pins[0], 6)
        self.text(x + 12, y - 13, pins[1], 6)

    def lamp(self, x, y, bmk, label="") -> None:
        self.c.circle(x, y, 9)
        self.wire(x - 6, y - 6, x + 6, y + 6)
        self.wire(x - 6, y + 6, x + 6, y - 6)
        self.text(x + 12, y - 2, bmk, 8, bold=True, primary=True)
        if label:
            self.text(x + 12, y - 12, label, 6)

    def terminal(self, x, y, label, primary=True, align="l") -> None:
        self.c.circle(x, y, 3.2)
        if label and align == "r":
            self.text(x - 6, y + 3, label, 7, primary=primary, align="r")
        elif label:
            self.text(x + 6, y + 3, label, 7, primary=primary)  # ueber dem Draht, nicht durchgestrichen

    def motor(self, x, y, bmk, label, extra="") -> None:
        self.c.circle(x, y, 22)
        self.text(x, y - 4, "M", 11, bold=True, align="c")
        self.text(x, y - 14, "3~", 8, align="c")
        self.text(x + 28, y + 4, f"{bmk}  {label}", 8, bold=True, primary=True)
        if extra:
            self.text(x + 28, y - 8, extra, 7)


# --- Blaetter ---------------------------------------------------------------------------------


def page_cover(s: Sheet, pages: list[tuple[int, str]]) -> None:
    m = s.m
    s.text(W / 2, H - 110, f"Stromlaufplan {m.title}", 20, bold=True, align="c")
    s.text(W / 2, H - 135, f"Anlage {m.plant}   Schaltschrank {m.loc_cabinet}   Feld {m.loc_field}", 11, align="c")
    s.text(W / 2, H - 153, "Testdokumentation fuer Stromlauf AI: frei erfunden, ohne Herstellerbezug, frei verwendbar.", 9, align="c")
    y = H - 190
    s.text(MARGIN + 40, y, "Inhaltsverzeichnis", 11, bold=True)
    y -= 15
    for page, title in pages:
        s.text(MARGIN + 40, y, f"Blatt {page}", 8, bold=True)
        s.text(MARGIN + 100, y, title, 8)
        y -= 12
    y -= 8
    s.text(MARGIN + 40, y, "Funktionsbeschreibung", 11, bold=True)
    y -= 15
    for line in m.function:
        s.text(MARGIN + 40, y, line, 8)
        y -= 12


def page_supply(s: Sheet) -> None:
    m = s.m
    x1, x2 = m.supply_strips
    ys = {"L1": H - 90, "L2": H - 105, "L3": H - 120, "N": H - 135, "PE": H - 150}
    for name, y in ys.items():
        s.rail(y, name, x1=col_x(1) - 30, x2=col_x(8) + 30)
    s.text(col_x(1) - 30, ys["L1"] + 14, m.supply_text, 8)
    for k, y in zip(["1", "2", "3", "N", "PE"], ys.values(), strict=True):
        s.terminal(col_x(1), y, f"{x1}:{k}")
    x = col_x(2)
    for y in (ys["L1"], ys["L2"], ys["L3"]):
        s.wire(x - 40, y, x - 10, y)
        s.wire(x + 10, y, x + 40, y)
    q1 = m.device("-Q1")
    s.device(x, ys["L2"], "-Q1", q1.name if q1 else "Hauptschalter", w=20, h=50, extra="1/2 3/4 5/6")
    s.text(x - 10, ys["L3"] - 22, "-> Blatt 3 ff. (L1 L2 L3 zu den Antrieben)", 7)
    xf = col_x(4)
    yF = H - 200
    s.wire(xf, ys["L1"], xf, yF + 18)
    s.contact(xf, yF, "-F1", ("1", "2"))
    s.text(xf + 5, yF - 24, "Steuerspannung 230 V, B6 A", 7)
    yT = H - 270
    s.wire(xf, yF - 18, xf, yT + 20)
    t1 = m.device("-T1")
    s.device(xf, yT, "-T1", t1.name if t1 else "Netzteil 24 V DC", w=60, h=40, extra="L N   -   +")
    s.wire(xf + 20, yT + 20, xf + 20, ys["N"])
    y24, y0 = H - 330, H - 345
    s.rail(y24, "+24 V DC (L+)", x1=col_x(4) - 40, x2=col_x(8) + 30)
    s.rail(y0, "0 V DC (M)", x1=col_x(4) - 40, x2=col_x(8) + 30)
    s.wire(xf + 10, yT - 20, xf + 10, y24)
    s.wire(xf - 10, yT - 20, xf - 10, y0)
    s.terminal(col_x(5), y24, f"{x2}:1  +24 V Sensoren")
    s.terminal(col_x(5), y0, f"{x2}:2  0 V")
    s.terminal(col_x(6), y24, f"{x2}:3  +24 V Sicherheitskreise")
    s.terminal(col_x(6), y0, f"{x2}:4  0 V Sicherheitskreise")
    s.terminal(col_x(7), y24, f"{x2}:5  +24 V SPS und Umrichter")
    s.terminal(col_x(7), y0, f"{x2}:6  0 V SPS und Umrichter")
    s.text(col_x(4) - 40, y0 - 22, "Steuerspannung 24 V DC, elektronisch abgesichert im Netzteil -T1. Freigegebene +24 V siehe Sicherheitskreise.", 8)


def page_drives(s: Sheet, drives) -> None:
    ys = [H - 90, H - 105, H - 120]
    for name, y in zip(["L1", "L2", "L3"], ys, strict=True):
        s.rail(y, name, x1=col_x(1) - 30, x2=col_x(8) + 30)
    s.text(col_x(1) - 30, ys[0] + 14, "von Blatt 2 (-Q1)", 7)
    for drive, col in zip(drives, DRIVE_COLUMNS[: len(drives)], strict=True):
        x = col_x(col)
        yF, yK, yX, yM = H - 185, H - 265, H - 345, H - 415
        for dx, y in zip((-8, 0, 8), ys, strict=True):
            s.wire(x + dx, y, x + dx, yF + 22)
        s.device(x, yF, drive.breaker, drive.breaker_name, w=40, h=44, extra=drive.setting)
        for dx in (-8, 0, 8):
            s.wire(x + dx, yF - 22, x + dx, yK + 25)
            s.wire(x + dx, yK - 25, x + dx, yX + 4)
        extra = f"{drive.kw:g} kW, PROFIBUS DP Adr. {drive.bus_address}, STO" if drive.kind == "vfd" else "Leistungsschuetz, Spule 24 V DC"
        s.device(x, yK, drive.switch, drive.switch_name, w=46, h=50, extra=extra)
        for dx in (-8, 0, 8):
            s.terminal(x + dx, yX, "", primary=False)
        s.text(x - 30, yX - 12, f"{drive.strip}:U {drive.strip}:V {drive.strip}:W", 7, primary=True)
        s.terminal(x + 22, yX, "", primary=False)
        s.text(x + 14, yX + 8, f"{drive.strip}:PE", 6, primary=True)
        for dx in (-8, 0, 8):
            s.wire(x + dx, yX - 4, x + dx, yM + 22)
        s.motor(x, yM, drive.motor, drive.name, f"{drive.kw:g} kW  400 V  {drive.amps:g} A  {drive.rpm} 1/min")
    s.text(col_x(1) - 30, H - 470, "Umrichter: Sollwert und Istwert ueber PROFIBUS DP von der SPS -A1; Freigabe ueber Digitalausgang, Bereitmeldung ueber Digitaleingang (siehe DI/DO-Blaetter).", 7)


def page_safety(s: Sheet, circuits) -> None:
    m = s.m
    y24, y0 = H - 90, H - 430
    s.rail(y24, f"+24 V DC von {m.supply_strips[1]}:3 (Blatt 2)", x1=col_x(1) - 30, x2=col_x(8) + 30)
    s.rail(y0, f"0 V DC von {m.supply_strips[1]}:4 (Blatt 2)", x1=col_x(1) - 30, x2=col_x(8) + 30)
    for circuit, base in zip(circuits, (2, 5), strict=False):
        assert len(circuit.devices) <= MAX_SAFETY_DEVICES, f"{circuit.relay}: hoechstens {MAX_SAFETY_DEVICES} Geraete je Kreis"
        x1, x2 = col_x(base) - 15, col_x(base) + 15
        y = H - 150
        top = y
        # Klemmen der Reihenschaltung: Beginn zwischen Schiene und erstem Kontakt, Ende vor dem Relais
        t = m.safety_terminals
        s.terminal(x1, top + 30, t[(circuit.relay, 1, "start")], align="r")
        s.terminal(x2, top + 30, t[(circuit.relay, 2, "start")])
        for bmk, pins1, pins2 in circuit.devices:
            s.wire(x1, y + 18 if y == top else y + 22, x1, y + 18)
            s.wire(x2, y + 18 if y == top else y + 22, x2, y + 18)
            s.contact(x1, y, bmk, tuple(pins1.split("/")), kind="NC")
            s.contact(x2, y, "", tuple(pins2.split("/")), kind="NC")
            y -= 40
        s.wire(x1, y24, x1, top + 18)
        s.wire(x2, y24, x2, top + 18)
        yK = y - 30
        s.terminal(x1, y + 9, t[(circuit.relay, 1, "end")], align="r")
        s.terminal(x2, y + 9, t[(circuit.relay, 2, "end")])
        s.device(col_x(base), yK, circuit.relay, circuit.name, w=70, h=50, extra="S11 S12 S21 S22 / 13-14 23-24")
        s.wire(x1, y + 22, x1, yK + 25)
        s.wire(x2, y + 22, x2, yK + 25)
        s.wire(col_x(base), yK - 25, col_x(base), y0)
        # Freigabekontakte
        xr, xr2 = col_x(base + 1), col_x(base + 2)
        yR = H - 160
        for x, pins, label1, label2 in (
            (xr, ("13", "14"), circuit.release_terminal, circuit.release_text),
            (xr2, ("23", "24"), circuit.feedback_input and _terminal_of(m, circuit.feedback_input), f"{circuit.feedback_input} Rueckmeldung SPS"),
        ):
            s.wire(x, y24, x, yR + 18)
            s.contact(x, yR, circuit.relay, pins, kind="NO")
            s.wire(x, yR - 18, x, yR - 60)
            s.terminal(x, yR - 66, "", primary=False)
            s.text(x, yR - 80, label1, 7, bold=True, align="c")
            s.text(x, yR - 90, label2, 6, align="c")
    s.text(col_x(1) - 30, y0 - 22, "Sicherheitsfunktionen Kat. 3 / PL d. Ruecksetzen nur nach Entriegeln und Quittierung; Wiederanlaufsperre im SPS-Programm.", 8)


def _terminal_of(m: Machine, address: str) -> str:
    return next((s.terminal for s in m.inputs if s.address == address), "")


def page_commands(s: Sheet, commands: list[Signal]) -> None:
    m = s.m
    y24 = H - 90
    s.rail(y24, f"+24 V DC von {m.supply_strips[1]}:1 (Blatt 2)", x1=col_x(1) - 30, x2=col_x(8) + 30)
    for signal, col in zip(commands, range(2, 8), strict=False):
        x = col_x(col)
        yT = H - 170
        s.wire(x, y24, x, yT + 18)
        s.contact(x, yT, signal.device, signal.pins, kind="NC" if signal.kind == "cmd_nc" else "NO")
        s.wire(x, yT - 18, x, yT - 60)
        s.terminal(x, yT - 66, "", primary=False)
        s.text(x, yT - 80, signal.terminal, 7, bold=True, align="c")
        s.text(x, yT - 90, f"{signal.address} {signal.symbol}", 6, align="c")
        s.text(x, yT - 100, signal.comment[:34], 6, align="c")
    s.text(col_x(1) - 30, H - 320, f"Bedienpult {m.loc_field}: Taster und Wahlschalter, Leitung -W1 zum Schaltschrank {m.loc_cabinet}, Klemmleiste {m.field_strip}.", 8)


def page_inputs(s: Sheet, signals: list[Signal], card: str, first: bool, offset: int = 0) -> None:
    m = s.m
    addr_from, addr_to = signals[0].address, signals[-1].address
    s.text(col_x(1) - 30, H - 80, f"SPS -A1, Digitaleingabe {card}, 16 x DC 24 V, Kanaele {addr_from} bis {addr_to}. Versorgung L+ von {m.supply_strips[1]}:5, M von {m.supply_strips[1]}:6.", 8)
    xcard = col_x(2)
    s.c.rect(xcard - 45, H - 440, 90, 330)
    s.text(xcard, H - 128, card, 10, bold=True, align="c")
    s.text(xcard, H - 140, "DI 16 x 24 V DC", 7, align="c")
    if first:  # CPU einmal als Symbol, damit -A1 einen Blattverweis hat
        s.device(col_x(1) - 10, H - 160, "-A1", "SPS CPU", w=30, h=40, extra="DP")
    for i, signal in enumerate(signals):
        y = H - 165 - i * 24
        s.text(xcard - 40, y - 2, str(offset + i + 1), 7)
        s.text(xcard - 25, y - 2, signal.address, 9, bold=True)
        s.wire(xcard + 45, y, col_x(3) - 4, y)
        s.terminal(col_x(3), y, signal.terminal)
        s.wire(col_x(3) + 4, y, col_x(5), y)
        s.text(col_x(5) + 6, y + 3, signal.symbol, 8, bold=True)
        s.text(col_x(5) + 6, y - 7, signal.comment[:52], 6)
        s.text(col_x(7) + 10, y - 2, f"von {signal.device}", 8)
    if first:
        a, b = m.sensor_supply
        s.text(col_x(3) - 10, H - 460, f"{a} (+24 V) und {b} (0 V) versorgen die Sensoren (BN/BU), Schaltausgang BK auf die Signalklemmen.", 8, primary=True)
        s.text(col_x(3) - 10, H - 472, f"Programm: OB1 ruft FB{m.fb_number} \"{m.fb_title}\" mit Instanz DB{m.db_number}. Symbole siehe Symboltabelle {m.code}.", 8)


def page_outputs(s: Sheet, signals: list[Signal], card: str, first: bool, offset: int = 0) -> None:
    m = s.m
    s.text(col_x(1) - 30, H - 80, f"SPS -A1, Digitalausgabe {card}, 16 x DC 24 V / 0,5 A, Kanaele {signals[0].address} bis {signals[-1].address}. Spulenversorgung ueber Freigabe der Sicherheitsrelais.", 8)
    xcard = col_x(2)
    s.c.rect(xcard - 45, H - 440, 90, 330)
    s.text(xcard, H - 128, card, 10, bold=True, align="c")
    s.text(xcard, H - 140, "DO 16 x 24 V DC", 7, align="c")
    for i, signal in enumerate(signals):
        y = H - 170 - i * 26
        s.text(xcard - 40, y - 2, str(offset + i + 1), 7)
        s.text(xcard - 25, y - 2, signal.address, 9, bold=True)
        s.wire(xcard + 45, y, col_x(3) - 4, y)
        s.terminal(col_x(3), y, signal.terminal)
        s.wire(col_x(3) + 4, y, col_x(5) - 20, y)
        x5 = col_x(5)
        if signal.kind == "coil":
            s.wire(x5 - 20, y, x5, y)
            s.coil(x5, y, signal.device)
            s.text(x5 + 30, y + 8, f"Spule A1/A2, 0 V ueber {m.coil_return}", 6)
        elif signal.kind == "vfd":
            s.wire(x5 - 20, y, x5 - 14, y)
            s.c.rect(x5 - 14, y - 9, 28, 18)
            s.text(x5 + 17, y - 2, signal.device, 8, bold=True, primary=True)
            s.text(x5 + 17, y - 12, f"Klemme {signal.pins[0]}/{signal.pins[1]}", 6)
        else:
            s.wire(x5 - 20, y, x5 - 9, y)
            s.lamp(x5, y, signal.device, f"X1/X2, 0 V ueber {m.lamp_return}")
        s.text(col_x(6) + 20, y - 2, f"{signal.symbol}: {signal.comment[:40]}", 6)
    if first:
        s.text(col_x(3) - 10, H - 460, f"{m.coil_return} und {m.lamp_return}: 0 V Rueckleiter fuer Schuetzspulen bzw. Meldeleuchten und Hupe.", 8, primary=True)


def page_terminals(s: Sheet, rows: list[tuple[str, str, str, str, str]], first: bool) -> None:
    s.text(col_x(1) - 30, H - 80, f"Klemmenplan Schaltschrank {s.m.loc_cabinet}" + (" (Fortsetzung)" if not first else ""), 10, bold=True)
    cols = [col_x(1) - 30, col_x(1) + 40, col_x(3) - 20, col_x(5) - 30, col_x(7) - 30]
    y = H - 105
    for x, head in zip(cols, ["Klemme", "intern", "extern (Feld)", "Funktion", "Blatt"], strict=True):
        s.text(x, y, head, 8, bold=True)
    s.wire(cols[0], y - 4, W - MARGIN - 10, y - 4)
    for row in rows:
        y -= 14
        for x, cell in zip(cols, row, strict=True):
            s.text(x, y, cell, 7, primary=False)


# --- Zusammenbau ------------------------------------------------------------------------------


def plan_pages(m: Machine) -> list[tuple[str, str, object]]:
    """(Titel, Art, Nutzlast) je Blatt in Reihenfolge."""
    pages: list[tuple[str, str, object]] = [("Deckblatt und Inhaltsverzeichnis", "cover", None), ("Netzeinspeisung 400 V und Steuerspannung 24 V DC", "supply", None)]
    for i in range(0, len(m.drives), DRIVES_PER_PAGE):
        chunk = m.drives[i : i + DRIVES_PER_PAGE]
        pages.append((f"Antriebe {', '.join(d.motor for d in chunk)}", "drives", chunk))
    for i in range(0, len(m.safety), 2):
        chunk = m.safety[i : i + 2]
        pages.append((f"Sicherheitskreise {', '.join(c.relay for c in chunk)}", "safety", chunk))
    commands = m.commands
    for i in range(0, len(commands), 6):
        pages.append(("Bedienpult, Taster und Wahlschalter", "commands", commands[i : i + 6]))
    # Ein Blatt zeigt nur Kanaele einer Baugruppe (16 Kanaele), hoechstens DI_PER_PAGE je Blatt
    first = True
    for card_index in range(0, len(m.inputs), 16):
        card = f"-A1.{1 + card_index // 16}"
        card_signals = m.inputs[card_index : card_index + 16]
        for i in range(0, len(card_signals), DI_PER_PAGE):
            chunk = card_signals[i : i + DI_PER_PAGE]
            pages.append((f"SPS -A1 Digitaleingaenge {card} ({chunk[0].address} bis {chunk[-1].address})", "inputs", (chunk, card, first, i)))
            first = False
    do_cards = 1 + (len(m.inputs) - 1) // 16
    first = True
    for card_index in range(0, len(m.outputs), 16):
        card = f"-A1.{do_cards + 1 + card_index // 16}"
        card_signals = m.outputs[card_index : card_index + 16]
        for i in range(0, len(card_signals), DO_PER_PAGE):
            chunk = card_signals[i : i + DO_PER_PAGE]
            pages.append((f"SPS -A1 Digitalausgaenge {card} ({chunk[0].address} bis {chunk[-1].address})", "outputs", (chunk, card, first, i)))
            first = False
    return pages


def render(m: Machine, out: Path, terminal_rows_fn) -> Refs:
    """Zeichnet den Plan; Klemmenplan-Blaetter kommen zuletzt (brauchen die Verweise der anderen)."""
    refs = Refs()
    pages = plan_pages(m)
    # Klemmenplan-Blaetter: Zeilenzahl kennen wir, Inhalt erst nach den anderen Blaettern
    probe_rows = terminal_rows_fn(m, refs, probe=True)
    n_terminal_pages = max(1, -(-len(probe_rows) // TERMINAL_ROWS_PER_PAGE))
    total = len(pages) + n_terminal_pages
    c = canvas.Canvas(str(out), pagesize=landscape(A4))
    c.setTitle(f"Stromlaufplan {m.title}")
    c.setAuthor("Stromlauf AI Testdokumentation")
    titles = [(i + 1, title) for i, (title, _, _) in enumerate(pages)]
    titles += [(len(pages) + 1 + i, "Klemmenplan" + (" (Fortsetzung)" if i else "")) for i in range(n_terminal_pages)]
    for number, (title, kind, payload) in enumerate(pages, start=1):
        s = Sheet(c, m, refs, number, total, title)
        if kind == "cover":
            page_cover(s, titles)
        elif kind == "supply":
            page_supply(s)
        elif kind == "drives":
            page_drives(s, payload)
        elif kind == "safety":
            page_safety(s, payload)
        elif kind == "commands":
            page_commands(s, payload)
        elif kind == "inputs":
            page_inputs(s, *payload)
        elif kind == "outputs":
            page_outputs(s, *payload)
        c.showPage()
    rows = terminal_rows_fn(m, refs, probe=False)
    for i in range(n_terminal_pages):
        number = len(pages) + 1 + i
        s = Sheet(c, m, refs, number, total, titles[number - 1][1])
        page_terminals(s, rows[i * TERMINAL_ROWS_PER_PAGE : (i + 1) * TERMINAL_ROWS_PER_PAGE], i == 0)
        c.showPage()
    c.save()
    return refs
