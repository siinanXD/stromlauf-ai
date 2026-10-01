"""Ground Truth fuer den Ingest-Benchmark: Kennzeichen je Seite, beim Zeichnen der Stromlaufplaene mitgeschrieben.

Aufruf:  python scripts/example_docs/make_gold.py --write   |   python scripts/example_docs/make_gold.py --check

Jede gezeichnete Zeichenkette wird einzeln ausgewertet, nicht der Seitentext. Dazu kommen die BMK
aus den Symbolen (Sheet.device/contact/coil, in der Testdokumentation auch lamp/motor) direkt, ohne
Kennzeichen-Grammatik. So misst eval/run_ingest.py das Lesen des PDFs (Reihenfolge, Zusammenziehen,
Trennen von Text), nicht die Grammatik in tags.py.

Leitungen (Stoerfall-Arbeitsflaeche): "wires" nennt je Seite die Paare von Anschluessen, die gezeichnete Leitungen
(Sheet.wire ausserhalb der Symbole) verbinden. Ein Leitungsende gehoert zum Anschlusspunkt, den der Generator beim
Zeichnen kennt: Kontakt- und Spulenanschluss (pins), Klemme (Beschriftung am Symbol oder im direkt folgenden Text),
sonst das Symbol, an dessen Rand die Leitung endet, eine SPS-Karte mit der Adresse ihrer Zeile. Schienen (rail)
zaehlen nicht. Damit misst eval/run_plan_graph.py den Leitungsleser (backend/app/ingestion/plan_wires.py).

Ausgabe (Seite = PDF-Seite; bei allen Plaenen ist Seite n = Blatt n): eval/ingest_gold/fb01.json aus dem
Beispielplan (make_pdf.py), ur01.json und pm1_ar.json aus der Testdokumentation (scripts/testdoku/render_pdf.py,
Issue #68).
"""

import importlib
import io
import json
import math
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))  # data.py und make_pdf.py liegen neben diesem Skript
sys.path.insert(1, str(ROOT / "scripts" / "testdoku"))  # render_pdf.py, render_rest.py, machines/
sys.path.insert(0, str(ROOT / "backend"))

import make_pdf  # noqa: E402
import render_pdf  # noqa: E402

GOLD_DIR = ROOT / "eval" / "ingest_gold"
NOTE = (
    "Kennzeichen je gezeichneter Zeichenkette (tags.extract_tags) plus BMK aus {symbols}; "
    "misst das Lesen des PDFs, nicht die Kennzeichen-Grammatik. Erzeugt von scripts/example_docs/make_gold.py."
)
WIRES_NOTE = (
    "Je Seite die Anschluesse, die gezeichnete Leitungen verbinden (ohne Schienen), als ungerichtete Paare; "
    "misst den Leitungsleser plan_wires mit eval/run_plan_graph.py."
)
PIN_HIT = 1.0  # pt: Leitungen enden genau am Anschlusspunkt eines Kontakts oder einer Spule
TERMINAL_HIT = 4.0  # pt: Abstand einer Leitung zum Rand des Klemmenkreises
ROW_HIT = 4.0  # pt: Grundlinie einer Kanal-Beschriftung zur Hoehe ihrer Leitung
SAME = 0.5  # pt: Endpunkte zweier Leitungen fallen zusammen


@dataclass
class _Box:
    """Symbol als Rechteck in reportlab-Koordinaten; name ist der Anschluss einer Leitung, die an seinem Rand endet."""

    x0: float
    y0: float
    x1: float
    y1: float
    name: str = ""

    def touches(self, x: float, y: float) -> bool:
        return (
            self.x0 - PIN_HIT <= x <= self.x1 + PIN_HIT
            and self.y0 - PIN_HIT <= y <= self.y1 + PIN_HIT
        )


@dataclass
class _Drawn:
    """Was ein Blatt fuer die Leitungs-Wahrheit zeichnet."""

    wires: list[tuple[float, float, float, float]] = field(default_factory=list)
    points: list[list] = field(default_factory=list)  # [x, y, Reichweite, Name]
    boxes: list[_Box] = field(default_factory=list)
    # links, rechts, Grundlinie, Text
    texts: list[tuple[float, float, float, str]] = field(default_factory=list)


class RecordingCanvas(canvas.Canvas):
    """reportlab-Zeichenflaeche, die jede Zeichenkette je Seite festhaelt, dazu Leitungen und Symbole."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_no = 1
        self.strings: dict[int, list[str]] = {}
        self.bmk: dict[int, set[str]] = {}
        self.pins: dict[int, set[str]] = {}  # Anschlussnummern am Symbol als "-K1:A1" (Issue #102)
        self.last_bmk: dict[int, str] = {}
        self.wires: dict[int, list[list[str]]] = {}  # verbundene Anschluesse je Seite
        self.drawn = _Drawn()
        self.symbol = 0  # > 0: im Symbol, in einer Schiene oder im Rahmen gezeichnet
        # Klemmen, deren Kennzeichen der direkt folgende Text nennt; Symbole direkt auf der Zeichenflaeche, deren
        # Kennzeichen im naechsten Text mit einem Geraet steht
        self.unnamed_terminals: list[list] = []
        self.unnamed_boxes: list[_Box] = []

    def _keep(self, text) -> None:
        self.strings.setdefault(self.page_no, []).append(str(text))

    def drawString(self, x, y, text, *args, **kwargs):  # noqa: N802 (reportlab-Name)
        self._keep(text)
        return super().drawString(x, y, text, *args, **kwargs)

    def drawRightString(self, x, y, text, *args, **kwargs):  # noqa: N802
        self._keep(text)
        return super().drawRightString(x, y, text, *args, **kwargs)

    def drawCentredString(self, x, y, text, *args, **kwargs):  # noqa: N802
        self._keep(text)
        return super().drawCentredString(x, y, text, *args, **kwargs)

    def circle(self, x_cen, y_cen, r, *args, **kwargs):
        if not self.symbol:  # Leuchte oder Motor im Beispielplan FB-01, ohne eigene Zeichenhilfe
            self.unnamed_boxes.append(self.box(x_cen - r, y_cen - r, x_cen + r, y_cen + r))
        return super().circle(x_cen, y_cen, r, *args, **kwargs)

    def rect(self, x, y, width, height, *args, **kwargs):
        if not self.symbol:  # SPS-Karte, Umrichter
            self.unnamed_boxes.append(self.box(x, y, x + width, y + height))
        return super().rect(x, y, width, height, *args, **kwargs)

    def box(self, x0: float, y0: float, x1: float, y1: float, name: str = "") -> _Box:
        found = _Box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), name)
        self.drawn.boxes.append(found)
        return found

    def note_text(self, left: float, right: float, y: float, text: str) -> None:
        """Beschriftung eines Blatts. Der direkt folgende Text nennt die Kennzeichen unbeschrifteter Klemmen, von links
        nach rechts; der naechste Text mit einem Geraet das Kennzeichen eines Symbols ohne Zeichenhilfe."""
        from app.ingestion.tags import TagType, extract_tags

        if not text.strip():
            return  # die Klemme im Beispielplan zeichnet ihre leere Beschriftung selbst
        self.drawn.texts.append((left, right, y, text))
        tags = extract_tags(text)
        if self.unnamed_terminals:
            names = [t.tag for t in tags if t.tag_type == TagType.TERMINAL and ":" in t.tag]
            if len(names) == len(self.unnamed_terminals):
                ordered = sorted(self.unnamed_terminals, key=lambda point: point[0])
                for point, name in zip(ordered, names, strict=True):
                    point[3] = name
            self.unnamed_terminals = []
        devices = [t.tag for t in tags if t.tag_type == TagType.DEVICE]
        if devices and self.unnamed_boxes:
            if len(devices) == 1:
                for found in self.unnamed_boxes:
                    found.name = devices[0]
            self.unnamed_boxes = []

    def showPage(self):  # noqa: N802
        if pairs := wire_pairs(self.drawn):
            self.wires[self.page_no] = pairs
        self.drawn = _Drawn()
        self.unnamed_terminals, self.unnamed_boxes = [], []
        super().showPage()
        self.page_no += 1


def _on_wire(x: float, y: float, wire: tuple[float, float, float, float]) -> bool:
    """Liegt der Punkt auf der Leitung, auch in ihrem Inneren (T-Abzweig)?"""
    x1, y1, x2, y2 = wire
    dx, dy = x2 - x1, y2 - y1
    span = dx * dx + dy * dy
    t = 0.0 if span == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / span))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= SAME


def _end_name(x: float, y: float, drawn: _Drawn) -> str:
    """Anschluss am freien Ende einer Leitung: Kontakt- oder Spulenanschluss, Klemme, sonst das kleinste Symbol, an
    dessen Rand sie endet; eine SPS-Karte nennt die Adresse ihrer Zeile."""
    from app.ingestion.tags import TagType, extract_tags

    for px, py, reach, name in drawn.points:
        if name and math.hypot(x - px, y - py) <= reach:
            return name
    for box in sorted(drawn.boxes, key=lambda b: (b.x1 - b.x0) * (b.y1 - b.y0)):
        if not box.touches(x, y):
            continue
        row = {
            t.tag
            for left, right, base, text in drawn.texts
            if box.x0 <= left and right <= box.x1 and abs(base - y) <= ROW_HIT
            for t in extract_tags(text)
            if t.tag_type == TagType.PLC_ADDRESS
        }
        return row.pop() if len(row) == 1 else box.name
    return ""


def wire_pairs(drawn: _Drawn) -> list[list[str]]:
    """Verbundene Anschluesse eines Blatts: Leitungen bilden Netze (gemeinsamer Endpunkt oder T-Abzweig), je Netz
    jedes Paar verschieden benannter freier Enden."""
    wires = [w for w in drawn.wires if (w[0], w[1]) != (w[2], w[3])]
    parent = list(range(len(wires)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    free: list[tuple[int, float, float]] = []
    for i, wire in enumerate(wires):
        for x, y in ((wire[0], wire[1]), (wire[2], wire[3])):
            joined = [j for j, other in enumerate(wires) if j != i and _on_wire(x, y, other)]
            for j in joined:
                parent[root(j)] = root(i)
            if not joined:
                free.append((i, x, y))
    nets: dict[int, set[str]] = {}
    for i, x, y in free:
        if name := _end_name(x, y, drawn):
            nets.setdefault(root(i), set()).add(name)
    pairs = {pair for names in nets.values() for pair in combinations(sorted(names), 2)}
    return [list(pair) for pair in sorted(pairs)]


class _RecordsSymbols:
    """Schreibt die BMK aus Geraeten, Kontakten und Spulen ohne Grammatik mit (vor dem Sheet des Generators erben),
    dazu Leitungen und die Anschlusspunkte der Symbole fuer die Leitungs-Wahrheit."""

    def _bmk(self, bmk: str) -> None:
        if bmk:
            self.c.bmk.setdefault(self.c.page_no, set()).add(bmk)

    def _pins(self, bmk: str, pins) -> str:
        """Nummern am Symbol gehoeren zu dessen Geraet; ein Kontakt ohne eigenes BMK (zweiter Kanal einer
        Reihenschaltung) zum Geraet derselben Zeile, also zum zuletzt gezeichneten. Nur Schaltgeraete, wie in
        tags.pin_kind. Gibt das Geraet zurueck."""
        from app.ingestion.tags import pin_kind

        owner = bmk or self.c.last_bmk.get(self.c.page_no, "")
        if bmk:
            self.c.last_bmk[self.c.page_no] = bmk
        for pin in pins or ():
            tag = f"{owner}:{str(pin).upper()}"
            if owner and pin_kind(tag):
                self.c.pins.setdefault(self.c.page_no, set()).add(tag)
        return owner

    @staticmethod
    def _pin_name(owner: str, pin) -> str:
        """Knoten wie im Signalgraphen: Anschluss eines Schaltgeraets, sonst das Geraet selbst."""
        from app.ingestion.tags import pin_kind

        tag = f"{owner}:{str(pin).upper()}"
        return tag if owner and pin_kind(tag) else owner

    def _symbol(self, draw, *args, **kwargs):
        self.c.symbol += 1
        try:
            return draw(*args, **kwargs)
        finally:
            self.c.symbol -= 1

    def _frame(self):
        return self._symbol(super()._frame)

    def text(self, x, y, s, size=8, bold=False, align="l", *args, **kwargs):
        from reportlab.pdfbase.pdfmetrics import stringWidth

        width = stringWidth(s, "Helvetica-Bold" if bold else "Helvetica", size)
        left = x if align == "l" else x - width / 2 if align == "c" else x - width
        self.c.note_text(left, left + width, y, s)
        return super().text(x, y, s, size, bold, align, *args, **kwargs)

    def wire(self, x1, y1, x2, y2):
        if not self.c.symbol:
            self.c.drawn.wires.append((x1, y1, x2, y2))
        return super().wire(x1, y1, x2, y2)

    def rail(self, *args, **kwargs):
        return self._symbol(super().rail, *args, **kwargs)

    def device(self, x, y, bmk, label, w=26, h=26, *args, **kwargs):
        self._bmk(bmk)
        self.c.box(x - w / 2, y - h / 2, x + w / 2, y + h / 2, bmk)
        return self._symbol(super().device, x, y, bmk, label, w, h, *args, **kwargs)

    def _pin_points(self, x, y, owner: str, pins) -> None:
        for pin, py in zip(pins, (y + 18, y - 18), strict=True):
            self.c.drawn.points.append([x, py, PIN_HIT, self._pin_name(owner, pin)])

    def contact(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        pins = args[0] if args else kwargs.get("pins")
        self._pin_points(x, y, self._pins(bmk, pins), pins)
        return self._symbol(super().contact, x, y, bmk, *args, **kwargs)

    def coil(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        pins = args[0] if args else kwargs.get("pins", ("A1", "A2"))
        owner = self._pins(bmk, pins)
        self._pin_points(x, y, owner, pins)
        # Eine Leitung in den Spulenkoerper (Ausgangsblaetter) speist die Spule: Anschluss pins[0]
        self.c.box(x - 9, y - 8, x + 9, y + 8, self._pin_name(owner, pins[0]))
        return self._symbol(super().coil, x, y, bmk, *args, **kwargs)

    def terminal(self, x, y, label, *args, **kwargs):
        from app.ingestion.tags import TagType, extract_tags

        names = [
            t.tag for t in extract_tags(label) if t.tag_type == TagType.TERMINAL and ":" in t.tag
        ]
        point = [x, y, 3.2 + TERMINAL_HIT, names[0] if len(names) == 1 else ""]
        self.c.drawn.points.append(point)
        if not label:
            self.c.unnamed_terminals.append(point)
        return self._symbol(super().terminal, x, y, label, *args, **kwargs)


class RecordingSheet(_RecordsSymbols, make_pdf.Sheet):
    """Blatt des Beispielplans FB-01."""


class RecordingTestdokuSheet(_RecordsSymbols, render_pdf.Sheet):
    """Blatt der Testdokumentation; zeichnet Leuchten und Motoren als eigene Symbole mit BMK."""

    def lamp(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        self.c.box(x - 9, y - 9, x + 9, y + 9, bmk)
        return self._symbol(super().lamp, x, y, bmk, *args, **kwargs)

    def motor(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        self.c.box(x - 22, y - 22, x + 22, y + 22, bmk)
        return self._symbol(super().motor, x, y, bmk, *args, **kwargs)


def testdoku_machine(name: str):
    """Maschinenmodell der Testdokumentation, z. B. ur01 -> scripts/testdoku/machines/ur01.py."""
    return importlib.import_module(f"machines.{name}").MACHINE


def _draw_fb01() -> RecordingCanvas:
    return make_pdf.build(
        io.BytesIO(), canvas_factory=RecordingCanvas, sheet_factory=RecordingSheet
    )


def _draw_testdoku(name: str) -> RecordingCanvas:
    from render_rest import terminal_rows

    drawn: list[RecordingCanvas] = []

    def recording_canvas(*args, **kwargs) -> RecordingCanvas:
        drawn.append(RecordingCanvas(*args, **kwargs))
        return drawn[-1]

    render_pdf.render(
        testdoku_machine(name),
        io.BytesIO(),
        terminal_rows,
        canvas_factory=recording_canvas,
        sheet_factory=RecordingTestdokuSheet,
    )
    return drawn[0]


@dataclass(frozen=True)
class Target:
    document: str
    generator: str
    symbols: str
    draw: Callable[[], RecordingCanvas]


TARGETS = {
    "fb01": Target(
        "examples/foerderband/01_Stromlaufplan_FB-01.pdf",
        "scripts/example_docs/make_pdf.py",
        "Sheet.device/contact/coil",
        _draw_fb01,
    ),
    "ur01": Target(
        "examples/umroller/01_Stromlaufplan_UR-01.pdf",
        "scripts/testdoku/render_pdf.py",
        "Sheet.device/contact/coil/lamp/motor",
        lambda: _draw_testdoku("ur01"),
    ),
    "pm1_ar": Target(
        "examples/aufrollung/01_Stromlaufplan_PM1-AR.pdf",
        "scripts/testdoku/render_pdf.py",
        "Sheet.device/contact/coil/lamp/motor",
        lambda: _draw_testdoku("pm1_ar"),
    ),
}


def gold(name: str) -> dict:
    # erst hier importiert: app liegt nur ueber sys.path vor, und ruff sortiert es je nach Startordner anders
    from app.ingestion.tags import extract_tags

    target = TARGETS[name]
    drawn = target.draw()
    pages: dict[str, dict[str, list[str]]] = {}
    for page in sorted(set(drawn.strings) | set(drawn.bmk)):
        by_type: dict[str, set[str]] = {}
        for text in drawn.strings.get(page, []):
            for tag in extract_tags(text):
                by_type.setdefault(str(tag.tag_type), set()).add(tag.tag)
        for bmk in drawn.bmk.get(page, set()):
            by_type.setdefault("terminal" if bmk[1:].startswith("X") else "device", set()).add(bmk)
        if drawn.pins.get(page):
            by_type.setdefault("device_pin", set()).update(drawn.pins[page])
        pages[str(page)] = {kind: sorted(tags) for kind, tags in sorted(by_type.items())}
    return {
        "dokument": target.document,
        "doc_type": "schematic",
        "generator": target.generator,
        "hinweis": NOTE.format(symbols=target.symbols),
        "seiten": pages,
        "hinweis_wires": WIRES_NOTE,
        "wires": {str(page): pairs for page, pairs in sorted(drawn.wires.items())},
    }


def render(name: str) -> str:
    return json.dumps(gold(name), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str]) -> int:
    outdated = []
    for name in TARGETS:
        path = GOLD_DIR / f"{name}.json"
        text = render(name)
        if "--write" in argv:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"geschrieben: {path.relative_to(ROOT).as_posix()}")
        elif not path.exists() or path.read_text(encoding="utf-8") != text:
            outdated.append(path.relative_to(ROOT).as_posix())
    if outdated:
        print(
            f"Gold veraltet: {', '.join(outdated)}. python scripts/example_docs/make_gold.py --write"
        )
        return 1
    if "--write" not in argv:
        print("Gold aktuell")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
