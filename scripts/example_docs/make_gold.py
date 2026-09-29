"""Ground Truth fuer den Ingest-Benchmark: Kennzeichen je Seite, beim Zeichnen des Stromlaufplans mitgeschrieben.

Aufruf:  python scripts/example_docs/make_gold.py --write   |   python scripts/example_docs/make_gold.py --check

Jede gezeichnete Zeichenkette wird einzeln ausgewertet, nicht der Seitentext. Dazu kommen die BMK
aus Sheet.device/contact/coil direkt, ohne Kennzeichen-Grammatik. So misst eval/run_ingest.py das
Lesen des PDFs (Reihenfolge, Zusammenziehen, Trennen von Text), nicht die Grammatik in tags.py.
Ausgabe: eval/ingest_gold/fb01.json (Seite = PDF-Seite; beim Beispiel ist Seite n = Blatt n).
"""

import io
import json
import sys
from pathlib import Path

from reportlab.pdfgen import canvas

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))  # data.py und make_pdf.py liegen neben diesem Skript
sys.path.insert(0, str(ROOT / "backend"))

import make_pdf  # noqa: E402

TARGET = ROOT / "eval" / "ingest_gold" / "fb01.json"
DOCUMENT = "examples/foerderband/01_Stromlaufplan_FB-01.pdf"
NOTE = (
    "Kennzeichen je gezeichneter Zeichenkette (tags.extract_tags) plus BMK aus Sheet.device/contact/coil; "
    "misst das Lesen des PDFs, nicht die Kennzeichen-Grammatik. Erzeugt von scripts/example_docs/make_gold.py."
)


class RecordingCanvas(canvas.Canvas):
    """reportlab-Zeichenflaeche, die jede Zeichenkette je Seite festhaelt."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_no = 1
        self.strings: dict[int, list[str]] = {}
        self.bmk: dict[int, set[str]] = {}

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


class RecordingSheet(make_pdf.Sheet):
    """Blatt, das die BMK aus Geraeten, Kontakten und Spulen ohne Grammatik mitschreibt."""

    def _bmk(self, bmk: str) -> None:
        if bmk:
            self.c.bmk.setdefault(self.c.page_no, set()).add(bmk)

    def device(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        return super().device(x, y, bmk, *args, **kwargs)

    def contact(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        return super().contact(x, y, bmk, *args, **kwargs)

    def coil(self, x, y, bmk, *args, **kwargs):
        self._bmk(bmk)
        return super().coil(x, y, bmk, *args, **kwargs)


def gold() -> dict:
    # erst hier importiert: app liegt nur ueber sys.path vor, und ruff sortiert es je nach Startordner anders
    from app.ingestion.tags import extract_tags

    drawn = make_pdf.build(
        io.BytesIO(), canvas_factory=RecordingCanvas, sheet_factory=RecordingSheet
    )
    pages: dict[str, dict[str, list[str]]] = {}
    for page in sorted(set(drawn.strings) | set(drawn.bmk)):
        by_type: dict[str, set[str]] = {}
        for text in drawn.strings.get(page, []):
            for tag in extract_tags(text):
                by_type.setdefault(str(tag.tag_type), set()).add(tag.tag)
        for bmk in drawn.bmk.get(page, set()):
            by_type.setdefault("terminal" if bmk[1:].startswith("X") else "device", set()).add(bmk)
        pages[str(page)] = {kind: sorted(tags) for kind, tags in sorted(by_type.items())}
    return {
        "dokument": DOCUMENT,
        "doc_type": "schematic",
        "generator": "scripts/example_docs/make_pdf.py",
        "hinweis": NOTE,
        "seiten": pages,
    }


def render() -> str:
    return json.dumps(gold(), ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str]) -> int:
    if "--write" in argv:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(render(), encoding="utf-8", newline="\n")
        print(f"geschrieben: {TARGET.relative_to(ROOT).as_posix()}")
        return 0
    if TARGET.exists() and TARGET.read_text(encoding="utf-8") == render():
        print("Gold aktuell")
        return 0
    print("Gold veraltet: python scripts/example_docs/make_gold.py --write")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
