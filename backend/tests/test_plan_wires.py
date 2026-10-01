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


def test_klemmenbeschriftung_gehoert_zur_naechsten_klemme(tmp_path):
    """Die Beschriftung "-X4:PE" steht zwischen zwei Klemmen, naeher an der PE-Klemme: Sie benennt die Leitung an der
    PE-Klemme, aber nicht die an der Nachbarklemme, auch wenn deren Ende kein anderer Text naeher ist."""

    def draw(c):
        c.circle(300, 300, 3.2)
        c.line(300, 304, 300, 360)  # von der Nachbarklemme nach oben
        c.drawString(304, 362, "-X1:1")
        c.circle(314, 300, 3.2)
        c.line(314, 296, 314, 250)  # von der PE-Klemme nach unten
        c.drawString(318, 246, "-X1:2")
        c.setFont("Helvetica", 6)
        c.drawString(306, 308, "-X4:PE")

    path = _plan(tmp_path, draw)
    assert _pairs(plan_wires.page_wire_edges(path, 1)) == {frozenset(("-X1:2", "-X4:PE"))}


def test_symbol_ohne_anschlussnummern_heisst_wie_sein_kennzeichen(tmp_path):
    """Leitungen enden am Rand von Schutzschalter und Motor; deren Kennzeichen stehen daneben, nicht am Ende. Die
    Klemme oben benennt ihr Ende wie bisher; Schalter und Motor heissen nach dem Kennzeichen neben dem Symbol."""

    def draw(c):
        c.line(200, 500, 200, 420)
        c.drawString(204, 502, "-X1:1")
        c.rect(180, 380, 40, 40)
        c.drawRightString(177, 397, "-F2")  # links neben dem Schalter, 3 pt vom Rand
        c.line(200, 380, 200, 322)
        c.circle(200, 300, 22)
        c.drawString(228, 302, "-M1  Motor 1,5 kW")  # rechts neben dem Motor, 6 pt vom Rand

    path = _plan(tmp_path, draw)
    assert _pairs(plan_wires.page_wire_edges(path, 1)) == {
        frozenset(("-X1:1", "-F2")),
        frozenset(("-F2", "-M1")),
    }


def test_kennzeichen_zwischen_zwei_symbolen_benennt_keins(tmp_path):
    """Steht ein Kennzeichen gleich nah an zwei Symbolen, ist offen, zu welchem es gehoert: keine Kante."""

    def draw(c):
        c.line(200, 500, 200, 420)
        c.drawString(204, 502, "-X1:1")
        c.rect(180, 380, 40, 40)
        c.drawString(224, 397, "-F2")  # rechts neben dem ersten Symbol ...
        c.rect(240, 380, 40, 40)  # ... und links neben dem zweiten

    path = _plan(tmp_path, draw)
    assert plan_wires.page_wire_edges(path, 1) == []


def test_spule_mit_anschlussnummern_benennt_kein_nachbarende(tmp_path):
    """Am Spulenkoerper stehen A1/A2: Nur sie benennen seine Zuleitungen. Die Leuchte darunter beruehrt die untere
    Zuleitung (Symbole zu dicht gezeichnet), haengt aber nicht an -K1."""

    def draw(c):
        c.line(470, 318, 470, 308)  # Zuleitung A1 bis an den Spulenkoerper
        c.rect(461, 292, 18, 16)
        c.drawString(482, 298, "-K1")
        c.drawString(482, 309, "A1")
        c.drawString(482, 287, "A2")
        c.line(470, 292, 470, 283)  # untere Zuleitung, endet auf der Leuchte darunter
        c.circle(470, 274, 9)
        c.drawString(482, 272, "-H1")

    path = _plan(tmp_path, draw)
    geometry = plan_wires._geometry(path, 1)
    assert set(plan_wires._box_labels(geometry.boxes, list(geometry.spots)).values()) == {"-H1"}
    assert plan_wires.page_wire_edges(path, 1) == []


def test_anschluss_schlaegt_sein_geraet(tmp_path):
    """Die Leitung von A1 endet am Rand von -K2: Das ist der Anschluss selbst, keine Verbindung -K2:A1 mit -K2. Unten
    fuehrt die Leitung vom Rand von -K2 zur Klemme."""

    def draw(c):
        c.line(200, 440, 200, 410)
        # mehr als 2 * LABEL_GAP ueber dem Symbol: kein Anschluss am Koerper
        c.drawString(204, 432, "A1")
        c.rect(180, 380, 40, 30)
        c.drawString(223, 402, "-K2")
        c.line(200, 380, 200, 340)
        c.drawString(204, 336, "-X1:1")

    path = _plan(tmp_path, draw)
    assert _pairs(plan_wires.page_wire_edges(path, 1)) == {frozenset(("-K2", "-X1:1"))}


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
    row = [(0.0, "-A1.1"), (1.0, "E0.0"), (2.0, "-X3:1"), (3.0, "von"), (4.0, "-S1")]
    assert plan_wires._channel(row, False) == ("E0.0", "-X3:1", "-S1")


def test_kanal_feldgeraet_steht_jenseits_der_klemme():
    """Spalte von oben: Taster, Leitung (-W), Klemme, Eingang, SPS-Baugruppe. Die Baugruppe bei der Adresse und die
    Leitung sind kein Feldgeraet; eine Adresse in Klammern verweist auf eine Spule und ist keine Kanal-Adresse."""
    column = [(0.0, "-S7"), (1.0, "-W7"), (2.0, "X420 3"), (3.0, "E0.0"), (4.0, "-D1")]
    assert plan_wires._channel(column, True) == ("E0.0", "-X420:3", "-S7")
    assert (
        plan_wires._channel([(0.0, "-K5"), (1.0, "(A20.2)"), (2.0, "-X9:1"), (3.0, "-M5")], False)
        is None
    )
    assert plan_wires._channel([(0.0, "A20.2"), (1.0, "-X9:1"), (2.0, "-M5")], False) == (
        "A20.2",
        "-X9:1",
        "-M5",
    )


def _column_sheet(c) -> None:
    """Kanaele in Spalten mit Spaltenkopf. Die Leitung laeuft nur von der Klemme zum Eingang; der Taster darueber ist
    nicht angeschlossen gezeichnet und steht nur in derselben Spalte."""
    for n in range(1, 9):
        c.drawCentredString(W * 0.1 * n, H - 30, str(n))
    for i in range(1, 5):
        x = W * 0.1 * (i + 1)
        c.drawCentredString(x, H - 150, f"-S{i}")
        c.drawString(x + 3, H - 300, f"-X1:{i}")
        c.line(x, H - 305, x, H - 440)
        c.drawString(x + 3, H - 452, f"E0.{i - 1}")


def test_kanal_in_spalten_ergaenzt_lage_auch_auf_blatt_mit_leitungen(tmp_path, cache):
    """Die Leitung verbindet Klemme und Eingang; den Taster in derselben Spalte ergaenzt die Lage im Plan. Fuer das
    Paar, das die Leitung schon zeigt, entsteht keine zweite Kante."""
    path = _plan(tmp_path, _column_sheet)
    assert plan_wires.page_segments(path, 1)
    edges = set(plan_wires.plan_edges(path))
    for i in range(1, 5):
        assert PlanEdge(f"-X1:{i}", f"E0.{i - 1}", 1, "leitung", True) in edges
        assert PlanEdge(f"-S{i}", f"-X1:{i}", 1, "lage", True) in edges
    assert {edge.via for edge in edges if edge.target.startswith("E")} == {"leitung"}
    assert len(edges) == 8


def test_lage_nur_wo_keine_leitung_das_paar_schon_zeigt(tmp_path, monkeypatch):
    """Auch ueber Blaetter und fuer Anschluss wie Geraet: -S1:14 -> -X1:1 als Leitung deckt -S1 -> -X1:1 aus der Lage."""
    monkeypatch.setattr(
        plan_wires, "_wire_edges", lambda *args: [PlanEdge("-S1:14", "-X1:1", 2, "leitung")]
    )
    monkeypatch.setattr(
        plan_wires,
        "_layout_page",
        lambda path, page, spots, spaced: [
            PlanEdge("-S1", "-X1:1", page, "lage"),
            PlanEdge("-X1:1", "E0.0", page, "lage"),
        ],
    )
    path = _plan(tmp_path, lambda c: c.line(100, 100, 200, 100))
    assert plan_wires.compute_edges(path) == [
        PlanEdge("-X1:1", "E0.0", 1, "lage"),
        PlanEdge("-S1:14", "-X1:1", 2, "leitung"),
    ]


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
