"""Ground Truth fuer den Ingest-Benchmark: Kennzeichen je Seite, beim Zeichnen der Stromlaufplaene mitgeschrieben.

Aufruf:  python scripts/example_docs/make_gold.py --write   |   python scripts/example_docs/make_gold.py --check

Jede gezeichnete Zeichenkette wird einzeln ausgewertet, nicht der Seitentext. Dazu kommen die BMK
aus den Symbolen (Sheet.device/contact/coil, in der Testdokumentation auch lamp/motor) direkt, ohne
Kennzeichen-Grammatik. So misst eval/run_ingest.py das Lesen des PDFs (Reihenfolge, Zusammenziehen,
Trennen von Text), nicht die Grammatik in tags.py.
Ausgabe (Seite = PDF-Seite; bei allen Plaenen ist Seite n = Blatt n): eval/ingest_gold/fb01.json aus dem
Beispielplan (make_pdf.py), ur01.json und pm1_ar.json aus der Testdokumentation (scripts/testdoku/render_pdf.py,
Issue #68).
"""

import importlib
import io
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
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


class RecordingCanvas(canvas.Canvas):
    """reportlab-Zeichenflaeche, die jede Zeichenkette je Seite festhaelt."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_no = 1
        self.strings: dict[int, list[str]] = {}
        self.bmk: dict[int, set[str]] = {}
        self.pins: dict[int, set[str]] = {}  # Anschlussnummern am Symbol als "-K1:A1" (Issue #102)
        self.last_bmk: dict[int, str] = {}

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

    def showPage(self):  # noqa: N802
        super().showPage()
        self.page_no += 1


class _RecordsSymbols:
    """Schreibt die BMK aus Geraeten, Kontakten und Spulen ohne Grammatik mit (vor dem Sheet des Generators erben)."""

    def _bmk(self, bmk: str) -> None:
        if bmk:
            self.c.bmk.setdefault(self.c.page_no, set()).add(bmk)

    def _pins(self, bmk: str, pins) -> None:
        """Nummern am Symbol gehoeren zu dessen Geraet; ein Kontakt ohne eigenes BMK (zweiter Kanal einer
        Reihenschaltung) zum Geraet derselben Zeile, also zum zuletzt gezeichneten. Nur Schaltgeraete, wie in
        tags.pin_kind."""
        from app.ingestion.tags import pin_kind

        owner = bmk or self.c.last_bmk.get(self.c.page_no, "")
        if bmk:
            self.c.last_bmk[self.c.page_no] = bmk
        for pin in pins or ():
            tag = f"{owner}:{str(pin).upper()}"
            if owner and pin_kind(tag):
                self.c.pins.setdefault(self.c.page_no, set()).add(tag)

    def device(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        return super().device(x, y, bmk, *args, **kwargs)

    def contact(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        self._pins(bmk, args[0] if args else kwargs.get("pins"))
        return super().contact(x, y, bmk, *args, **kwargs)

    def coil(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        self._pins(bmk, args[0] if args else kwargs.get("pins", ("A1", "A2")))
        return super().coil(x, y, bmk, *args, **kwargs)


class RecordingSheet(_RecordsSymbols, make_pdf.Sheet):
    """Blatt des Beispielplans FB-01."""


class RecordingTestdokuSheet(_RecordsSymbols, render_pdf.Sheet):
    """Blatt der Testdokumentation; zeichnet Leuchten und Motoren als eigene Symbole mit BMK."""

    def lamp(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        return super().lamp(x, y, bmk, *args, **kwargs)

    def motor(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        return super().motor(x, y, bmk, *args, **kwargs)


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
