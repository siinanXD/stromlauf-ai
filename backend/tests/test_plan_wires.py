"""Leitungsleser (Stoerfall-Arbeitsflaeche, Spur A1): synthetische Seiten mit reportlab, ohne Datenbank und Modell.

Die Seiten zeichnen nur, worauf es ankommt: Leitungen, Anschluss-Texte und hier und da einen Verbindungspunkt.
Koordinaten im Test in reportlab-Punkten (Ursprung unten links); der Leser rechnet in pt mit Ursprung oben links.
"""

from pathlib import Path

import pypdfium2 as pdfium
import pytest

pytest.importorskip("reportlab")
from reportlab.pdfgen import canvas  # noqa: E402

from app.ingestion import plan_edges as plan_cache  # noqa: E402
from app.ingestion import plan_wires  # noqa: E402
from app.ingestion.ocr import OcrLine, write_text_layer  # noqa: E402
from app.ingestion.plan_edges import PlanEdge  # noqa: E402

W, H = 842, 595  # A4 quer
EXAMPLES = Path(__file__).resolve().parents[2] / "examples"


def _plan(tmp_path: Path, draw, name: str = "plan.pdf", size=(W, H)) -> Path:
    path = tmp_path / name
    c = canvas.Canvas(str(path), pagesize=size)
    c.setLineWidth(0.9)
    c.setFont("Helvetica", 7)
    draw(c)
    c.showPage()
    c.save()
    return path


def _pairs(edges: list[PlanEdge]) -> set[frozenset[str]]:
    return {frozenset((e.source, e.target)) for e in edges}


def _label(c, x: float, y: float, text: str) -> None:
    """Beschriftung links von x (rechtsbuendig) mit der Grundlinie knapp unter y."""
    c.drawRightString(x, y - 2, text)


def test_t_abzweig_verbindet(tmp_path):
    """Ein Endpunkt auf dem Inneren einer anderen Leitung verbindet: drei Enden, ein Netz."""

    def draw(c):
        c.line(100, 300, 300, 300)
        c.line(200, 300, 200, 200)  # endet mitten auf der waagerechten Leitung
        _label(c, 96, 300, "-X1:1")
        c.drawString(304, 298, "-X1:2")
        c.drawString(204, 196, "-X2:1")

    path = _plan(tmp_path, draw)
    nets = plan_wires.page_nets(plan_wires.page_segments(path, 1))
    assert len(nets) == 1 and len(nets[0].ends) == 3
    assert _pairs(plan_wires.page_wire_edges(path, 1)) == {
        frozenset(("-X1:1", "-X1:2")),
        frozenset(("-X1:1", "-X2:1")),
        frozenset(("-X1:2", "-X2:1")),
    }


def _crossing(c) -> None:
    c.line(100, 300, 300, 300)
    c.line(200, 400, 200, 200)
    _label(c, 96, 300, "-X1:1")
    c.drawString(304, 298, "-X1:2")
    c.drawString(204, 404, "-X2:1")
    c.drawString(204, 192, "-X2:2")


def test_kreuzung_ohne_punkt_verbindet_nicht(tmp_path):
    path = _plan(tmp_path, _crossing)
    assert len(plan_wires.page_nets(plan_wires.page_segments(path, 1))) == 2
    assert _pairs(plan_wires.page_wire_edges(path, 1)) == {
        frozenset(("-X1:1", "-X1:2")),
        frozenset(("-X2:1", "-X2:2")),
    }


def test_kreuzung_mit_punkt_verbindet(tmp_path):
    """Ein gefuellter Punkt (Durchmesser 3 pt) auf der Kreuzung verbindet beide Leitungen."""

    def draw(c):
        _crossing(c)
        c.circle(200, 300, 1.5, stroke=0, fill=1)

    path = _plan(tmp_path, draw)
    geometry = plan_wires._geometry(path, 1)
    assert len(geometry.dots) == 1
    nets = plan_wires.page_nets(list(geometry.segments), geometry.dots)
    assert len(nets) == 1
    assert frozenset(("-X1:1", "-X2:2")) in _pairs(plan_wires.page_wire_edges(path, 1))


def test_form_xobject_mit_matrix(tmp_path):
    """Leitung in einem Form-XObject in einem Form-XObject: beide Matrizen und die Seitenmatrix gelten."""

    def draw(c):
        c.beginForm("leitung")
        c.setLineWidth(0.5)
        c.line(0, 0, 60, 0)
        c.endForm()
        c.beginForm("symbol")
        c.translate(10, 0)
        c.doForm("leitung")
        c.endForm()
        c.saveState()
        c.translate(150, 300)
        c.scale(2, 2)
        c.doForm("symbol")  # (0, 0) -> (170, 300), (60, 0) -> (290, 300)
        c.restoreState()
        _label(c, 166, 300, "-X1:1")
        c.drawString(294, 298, "E0.0")

    path = _plan(tmp_path, draw)
    [segment] = plan_wires.page_segments(path, 1)
    assert (segment.x1, segment.y1, segment.x2, segment.y2) == pytest.approx(
        (170, H - 300, 290, H - 300), abs=0.01
    )
    assert segment.width == pytest.approx(1.0)  # 0,5 pt im Formular, doppelt skaliert
    assert plan_wires.page_wire_edges(path, 1) == [PlanEdge("-X1:1", "E0.0", 1, "leitung", True)]


def _rotate_page(path: Path) -> Path:
    """Dieselbe Seite mit /Rotate 90 (Blatt im Viewer gedreht, Inhalt unveraendert)."""
    pdf = pdfium.PdfDocument(str(path))
    pdf[0].set_rotation(90)
    out = path.with_name("gedreht.pdf")
    pdf.save(out)
    pdf.close()
    return out


@pytest.mark.parametrize("art", ["inhalt", "seitenattribut"])
def test_gedrehte_seite(tmp_path, art):
    """Hochkant eingelegtes Blatt: Text und Leitungen laufen gedreht (Inhalt) oder die Seite traegt /Rotate. Die
    Enden liegen in derselben Leserichtung wie die Woerter, die Kante entsteht trotzdem."""

    def plan(c):
        c.line(100, 300, 300, 300)
        _label(c, 96, 300, "-X1:1")
        c.drawString(304, 298, "E0.0")
        c.line(100, 200, 300, 200)
        _label(c, 96, 200, "A4.0")
        c.drawString(304, 198, "-X1:2")

    if art == "inhalt":

        def draw(c):
            c.translate(H, 0)
            c.rotate(90)  # Querformat-Plan auf einer Hochformat-Seite, Text laeuft nach oben
            plan(c)

        path = _plan(tmp_path, draw, size=(H, W))
    else:
        path = _rotate_page(_plan(tmp_path, plan))
    assert set(plan_wires.page_wire_edges(path, 1)) == {
        PlanEdge("-X1:1", "E0.0", 1, "leitung", True),
        PlanEdge("A4.0", "-X1:2", 1, "leitung", True),
    }


def test_unbenanntes_ende_ergibt_keine_kante(tmp_path):
    """Ein Ende ohne Text in Reichweite und ein Ende zwischen zwei gleich nahen Texten bleiben unbenannt."""

    def draw(c):
        c.line(100, 300, 300, 300)  # rechts steht nichts
        _label(c, 96, 300, "-X1:1")
        c.line(100, 200, 300, 200)
        _label(c, 96, 200, "-X1:2")
        c.drawString(310, 208, "-X1:3")  # gleich weit ueber und unter dem rechten Ende
        c.drawString(310, 188, "-X1:4")

    path = _plan(tmp_path, draw)
    assert len(plan_wires.page_nets(plan_wires.page_segments(path, 1))) == 2
    assert plan_wires.page_wire_edges(path, 1) == []


def test_eingang_richtung_zur_adresse(tmp_path):
    """Eingang: Klemme -> Adresse. Ausgang: Adresse -> Klemme. Spule: Klemme -> Spule (-K1:A1)."""

    def draw(c):
        c.line(100, 400, 300, 400)
        _label(c, 96, 400, "E0.0")
        c.drawString(304, 398, "-X1:1")
        c.line(100, 300, 300, 300)
        _label(c, 96, 300, "A4.0")
        c.drawString(304, 298, "-X1:2")
        c.line(100, 200, 300, 200)
        _label(c, 96, 200, "-X1:3")
        c.drawString(304, 202, "A1")  # Spulenanschluss am Ende, das Schuetz daneben
        c.drawString(304, 186, "-K1")

    path = _plan(tmp_path, draw)
    assert set(plan_wires.page_wire_edges(path, 1)) == {
        PlanEdge("-X1:1", "E0.0", 1, "leitung", True),
        PlanEdge("A4.0", "-X1:2", 1, "leitung", True),
        PlanEdge("-X1:3", "-K1:A1", 1, "leitung", True),
    }


@pytest.fixture
def cache(tmp_path, monkeypatch) -> Path:
    directory = tmp_path / "plan_cache"
    monkeypatch.setattr(plan_cache, "_cache_dir", lambda: directory)
    return directory


def _ocr_line(text: str, x: float, y: float, size: float = 8) -> OcrLine:
    """Zeile ab (x, y) in pt, Ursprung oben links, wie die OCR sie ablegt."""
    x0, x1, top = x / W, (x + 0.55 * size * len(text)) / W, y / H
    bottom = (y + size * 1.2) / H
    return OcrLine(text, ((x0, top), (x1, top), (x1, bottom), (x0, bottom)), 0.99)


def _channel_rows(count: int, skew: float = 0.0) -> list[OcrLine]:
    """Kanaele in Zeilen wie im FB-01-Eingangsblatt: Adresse, Klemme, Feldgeraet auf gleicher Hoehe; skew neigt die
    Zeilen wie ein schief eingelegtes Blatt (pt Hoehe je pt Breite)."""
    lines = []
    for row in range(count):
        y = 150 + 40 * row
        lines += [
            _ocr_line(f"E0.{row}", 120, y),
            _ocr_line(f"-X3:{row + 1}", 300, y + skew * 180),
            _ocr_line("von", 560, y + skew * 440),
            _ocr_line(f"-S{row + 1}", 590, y + skew * 470),
        ]
    return lines


def test_scan_ohne_linien_faellt_auf_lage_zurueck(tmp_path, cache):
    """Gescanntes Blatt: ein Bild mit unsichtbarer Textebene, keine Vektorlinien. Kein Fehler, Kanten aus der Lage."""
    from PIL import Image

    image = tmp_path / "scan.png"
    Image.new("L", (400, 280), 255).save(image)

    def draw(c):
        c.drawImage(str(image), 0, 0, W, H)

    scan = _plan(tmp_path, draw, name="scan.pdf")
    path = tmp_path / "scan_ocr.pdf"
    write_text_layer(scan, path, {1: _channel_rows(3)})
    assert plan_wires.page_segments(path, 1) == []
    assert plan_wires.page_wire_edges(path, 1) == []
    edges = plan_wires.plan_edges(path)
    assert {edge.via for edge in edges} == {"lage"}
    assert PlanEdge("-S1", "-X3:1", 1, "lage", True) in edges
    assert PlanEdge("-X3:1", "E0.0", 1, "lage", True) in edges


def test_kanaele_in_zeilen(tmp_path, cache):
    """Ab drei Kanaelen je Seite: Feldgeraet -> Klemme -> Eingang; weniger Zeilen sind kein Kanal-Blatt."""

    def text_only(rows: int) -> Path:
        blank = _plan(tmp_path, lambda c: None, name=f"leer{rows}.pdf")
        out = tmp_path / f"zeilen{rows}.pdf"
        write_text_layer(blank, out, {1: _channel_rows(rows)})
        return out

    edges = plan_wires.plan_edges(text_only(3))
    assert _pairs(edges) == {
        frozenset(pair)
        for row in range(3)
        for pair in ((f"-S{row + 1}", f"-X3:{row + 1}"), (f"-X3:{row + 1}", f"E0.{row}"))
    }
    assert all(edge.directed and edge.via == "lage" for edge in edges)
    assert plan_wires.plan_edges(text_only(2)) == []


def test_schief_eingescannte_zeilen_bleiben_kanaele(tmp_path, cache):
    """0,8 Grad Schraeglage: das Feldgeraet am Zeilenende liegt 6,6 pt tiefer als die Adresse."""
    blank = _plan(tmp_path, lambda c: None, name="leer.pdf")
    path = tmp_path / "schief.pdf"
    write_text_layer(blank, path, {1: _channel_rows(3, skew=0.014)})
    assert PlanEdge("-S3", "-X3:3", 1, "lage", True) in plan_wires.plan_edges(path)


def test_sps_karte_ist_keine_adresse():
    """In "-A1.1" findet extract_tags auch die Adresse A1.1; als Anschluss zaehlt nur die Karte nicht."""
    assert plan_wires._anchor_node("-A1.1,", False) is None
    assert plan_wires._anchor_node("(E0.0", False) == "E0.0"
    assert plan_wires._channel(["-A1.1 E0.0 -X3:1 von -S1"], False) == ("E0.0", "-X3:1", "-S1")


def test_cache_wird_genutzt(tmp_path, cache, monkeypatch):
    """Zweiter Aufruf liest data/plan_cache statt die Seiten neu zu lesen."""
    calls = []
    original = plan_wires.page_segments

    def counting(path, page):
        calls.append(page)
        return original(path, page)

    monkeypatch.setattr(plan_wires, "page_segments", counting)
    path = _plan(tmp_path, _crossing)
    first = plan_wires.plan_edges(path)
    assert calls == [1] and len(list(cache.glob("*.json"))) == 1
    assert plan_wires.plan_edges(path) == first
    assert calls == [1]


def test_beispielplan_fb01_signalkette_aus_den_leitungen():
    """FB-01: Taster -> Klemme (Blatt 4), Klemme -> Eingang (Blatt 5), Ausgang -> Klemme (Blatt 6). Der Hinweis
    "0 V ueber -X3:14" mitten im Satz unter -P1 ist kein Anschluss."""
    edges = plan_wires.compute_edges(EXAMPLES / "foerderband" / "01_Stromlaufplan_FB-01.pdf")
    assert {
        PlanEdge("-S1:14", "-X3:1", 4, "leitung", True),
        PlanEdge("-X3:1", "E0.0", 5, "leitung", True),
        PlanEdge("A4.0", "-X3:9", 6, "leitung", True),
    } <= set(edges)
    assert not any("-X3:14" in (edge.source, edge.target) for edge in edges)
