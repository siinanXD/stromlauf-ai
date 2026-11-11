"""Belege als Ausschnitt (SIN-1236): Seitenbild-Route mit box und Spaltenbox im Beleg, ohne Datenbank und Modell."""

import io
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from app.api.answer_meta import column_box
from app.api.sources import page_image
from app.ingestion.pdf_layout import page_columns
from app.tenancy import reset_workspace, set_workspace

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
FB01 = EXAMPLES / "foerderband" / "01_Stromlaufplan_FB-01.pdf"


def _session(path: Path, workspace_id: str = "default"):
    document = SimpleNamespace(storage_path=str(path), workspace_id=workspace_id)
    return SimpleNamespace(get=lambda _model, _id: document)


def _size(response) -> tuple[int, int]:
    return Image.open(io.BytesIO(response.body)).size


def test_box_schneidet_den_anteil_der_seite_aus():
    full_w, full_h = _size(page_image("d1", 3, None, _session(FB01)))
    response = page_image("d1", 3, "0.25,0.5,0.75,1", _session(FB01))
    assert response.media_type == "image/png"
    width, height = _size(response)
    assert abs(width - full_w / 2) <= 1 and abs(height - full_h / 2) <= 1


def test_box_ausserhalb_wird_auf_die_seite_begrenzt():
    full = _size(page_image("d1", 3, None, _session(FB01)))
    assert _size(page_image("d1", 3, "-0.5,-1,1.5,2", _session(FB01))) == full


def test_winzige_box_liefert_mindestens_ein_pixel():
    assert _size(page_image("d1", 3, "0.5,0.5,0.50001,0.50001", _session(FB01))) == (1, 1)
    assert _size(page_image("d1", 3, "0.99999,0.99999,1,1", _session(FB01))) == (1, 1)


@pytest.mark.parametrize(
    "box",
    ["", "0.1,0.2,0.3", "0.1,0.2,0.3,0.4,0.5", "a,b,c,d", "0.5,0.1,0.5,0.9", "0.8,0.1,0.2,0.9", "nan,0,1,1", "1.2,0,1.5,1"],
)
def test_ungueltige_box_ist_400(box):
    with pytest.raises(HTTPException) as error:
        page_image("d1", 3, box, _session(FB01))
    assert error.value.status_code == 400


def test_fremder_workspace_bekommt_auch_mit_box_404():
    token = set_workspace("eigener")
    try:
        with pytest.raises(HTTPException) as error:
            page_image("d1", 3, "0,0,1,1", _session(FB01, workspace_id="fremd"))
    finally:
        reset_workspace(token)
    assert error.value.status_code == 404


def test_spaltenbox_aus_dem_raster_fuer_ein_blatt_von_fb01():
    column = next(c for c in page_columns(FB01, 3) if c.n == 8)
    box = column_box(FB01, 3, ["-K1", "/3.8"])
    assert box == {"x0": column.x0, "y0": column.y0, "x1": column.x1, "y1": column.y1}
    assert 0 <= box["x0"] < box["x1"] <= 1 and 0 <= box["y0"] < box["y1"] <= 1


def test_keine_box_ohne_spalte_fuer_anderes_blatt_oder_unbekannte_spalte():
    assert column_box(FB01, 3, ["/3", "S. 3", "-K1"]) is None
    assert column_box(FB01, 3, ["/4.8"]) is None
    assert column_box(FB01, 3, ["/3.99"]) is None


def test_keine_box_ohne_spaltenraster_und_bei_gedrehter_seite(tmp_path):
    pytest.importorskip("reportlab")
    from reportlab.pdfgen import canvas

    def plan(name: str, rotated: bool) -> Path:
        path = tmp_path / name
        c = canvas.Canvas(str(path), pagesize=(842, 595))
        c.setFont("Helvetica", 8)
        if rotated:  # Blatt hochkant: die Kopfzeile laeuft die Seite hinauf
            c.rotate(90)
            c.translate(0, -595)
        for n in range(1, 9):
            c.drawString(n * 60, 560, str(n))
        c.drawString(700, 20, "Blatt 1 / 1")
        c.showPage()
        c.save()
        return path

    assert column_box(plan("gerade.pdf", rotated=False), 1, ["/1.4"]) is not None
    assert column_box(plan("gedreht.pdf", rotated=True), 1, ["/1.4"]) is None
    scan = EXAMPLES / "scan" / "01_Stromlaufplan_FB-01_scan.pdf"
    assert column_box(scan, 3, ["/3.8"]) is None


def test_fehlende_datei_liefert_keine_box(tmp_path):
    assert column_box(tmp_path / "weg.pdf", 1, ["/1.4"]) is None


def test_meta_haengt_die_box_nur_an_den_beleg_der_zitierten_datei():
    from app.api.answer_meta import add_column_boxes

    session = SimpleNamespace(get=lambda _model, _id: SimpleNamespace(storage_path=str(FB01)))
    evidence = [
        {"kind": "page", "document_id": "d1", "filename": FB01.name, "page": 3},
        {"kind": "page", "document_id": "d1", "filename": FB01.name, "page": 4},
        {"kind": "page", "document_id": "d2", "filename": "Handbuch.pdf", "page": 3},
    ]
    checks = [{"file": "01_stromlaufplan_fb-01", "locator": "/3.8"}, {"file": "Handbuch.pdf", "locator": "S. 3"}]
    out = add_column_boxes(session, evidence, checks)
    assert "box" in out[0] and "box" not in out[1] and "box" not in out[2]
