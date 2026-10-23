"""Stueckliste aus der Schrankerkennung (SIN-732): Mengen, eindeutige BMK, Export. Ohne Datenbank und Modell.

Die 15 Fixtures sind synthetisch (Seed je Schrank): bekannte Bauteilmengen werden gestreut, die Zaehlung muss sie
zurueckgeben. Echte Schrankfotos mit Erwartung liegen noch nicht im Repo."""

import csv
import io
import random
import re
import time
import zipfile

import pytest
from openpyxl import load_workbook
from PIL import Image

from app.werk import bom_export
from app.werk.bom import UNSURE_BELOW, BomItem, assign_bmk, build_bom, letter_for, reading_order

PARTS = [
    ("Schütz", "3RT2026-1BB40", "Siemens"),
    ("Schütz", "3RT2015-1BB41", "Siemens"),
    ("LS-Schalter", "5SL6106-7", "Siemens"),
    ("Sicherung", "FU-10A", "Phoenix Contact"),
    ("Netzteil", "2904598", "Phoenix Contact"),
    ("Klemme", "3044076", "Phoenix Contact"),
    ("Motorschutzschalter", "3RV2011-1GA10", "Siemens"),
    ("Koppelrelais", "2961105", "Phoenix Contact"),
]


def fixture(seed: int) -> tuple[list[BomItem], dict[tuple[str, str], int]]:
    """Ein Schrank: 4 bis 8 Teilearten mit je 1 bis 6 Stueck auf nicht ueberlappenden Rasterplaetzen."""
    rng = random.Random(seed)
    kinds = rng.sample(PARTS, rng.randint(4, 8))
    expected = {(kind, order): rng.randint(1, 6) for kind, order, _ in kinds}
    maker = {(kind, order): m for kind, order, m in kinds}
    slots = [(col * 0.1, row * 0.12) for row in range(8) for col in range(10)]
    rng.shuffle(slots)
    items, number = [], 0
    for key, count in expected.items():
        for _ in range(count):
            x, y = slots.pop()
            number += 1
            items.append(
                BomItem(
                    id=f"h{number}",
                    kind=key[0],
                    x=x,
                    y=y,
                    w=0.08,
                    h=0.1,
                    confidence=rng.choice([0.95, 0.9, 0.5]),
                    manufacturer=maker[key],
                    order_number=key[1] if rng.random() < 0.5 else key[1].lower().replace("-", " "),
                )
            )
    return items, expected


@pytest.mark.parametrize("seed", range(15))
def test_quantities_match_expectation(seed):
    items, expected = fixture(seed)
    bom = build_bom(items)
    counted = {(row.part, row.order_number.upper().replace(" ", "-")): row.quantity for row in bom.rows}
    assert len(bom.rows) == len(expected)
    for key, count in expected.items():
        assert any(row.part == key[0] and row.quantity == count and _same(row.order_number, key[1]) for row in bom.rows), (
            key,
            counted,
        )
    assert bom.total == len(items)


def _same(a: str, b: str) -> bool:
    clean = lambda t: "".join(ch for ch in t.upper() if ch.isalnum())  # noqa: E731
    return clean(a) == clean(b)


@pytest.mark.parametrize("seed", range(15))
def test_bmk_unique_and_complete(seed):
    items, _ = fixture(seed)
    bmk = assign_bmk(items)
    assert set(bmk) == {i.id for i in items}
    assert len(set(bmk.values())) == len(items)
    rows = build_bom(items).rows
    flat = [tag for row in rows for tag in row.bmk]
    assert len(flat) == len(set(flat)) == len(items)
    assert all(row.quantity == len(row.bmk) for row in rows)


def test_existing_tags_kept_duplicates_renumbered():
    items = [
        BomItem(id="a", kind="Schütz", tag="-K1", x=0.1, y=0.1),
        BomItem(id="b", kind="Schütz", tag="-k1", x=0.5, y=0.1),  # gleiches Kennzeichen, zweites bekommt ein neues
        BomItem(id="c", kind="Schütz", x=0.7, y=0.1),
        BomItem(id="d", kind="Sicherung", x=0.2, y=0.5),
    ]
    bmk = assign_bmk(items)
    assert bmk["a"] == "-K1"
    assert bmk["b"] == "-K2"
    assert bmk["c"] == "-K3"
    assert bmk["d"] == "-F1"


def test_bmk_numbered_in_reading_order():
    items = [
        BomItem(id="unten", kind="Schütz", x=0.1, y=0.8),
        BomItem(id="rechts", kind="Schütz", x=0.7, y=0.1),
        BomItem(id="links", kind="Schütz", x=0.1, y=0.11),  # fast gleiche Zeile wie "rechts"
    ]
    assert [i.id for i in reading_order(items)] == ["links", "rechts", "unten"]
    bmk = assign_bmk(items)
    assert (bmk["links"], bmk["rechts"], bmk["unten"]) == ("-K1", "-K2", "-K3")


def test_letters():
    assert letter_for("Schütz") == "K"
    assert letter_for("LS-Schalter") == "F"
    assert letter_for("Sicherung") == "F"
    assert letter_for("Motorschutzschalter") == "Q"
    assert letter_for("Frequenzumrichter") == "T"  # „FI“ steckt als Teilstueck darin, ist aber kein Wort
    assert letter_for("Unbekannt") == "A"


def test_unsure_rows_flagged():
    items = [
        BomItem(id="a", kind="Schütz", order_number="X1", confidence=0.95, x=0.1, y=0.1),
        BomItem(id="b", kind="Schütz", order_number="X1", confidence=UNSURE_BELOW - 0.01, x=0.3, y=0.1),
        BomItem(id="c", kind="Sicherung", order_number="Y1", confidence=0.7, x=0.5, y=0.1),
        BomItem(id="d", kind="Netzteil", x=0.7, y=0.1),  # manuell, keine Sicherheit
    ]
    rows = {row.part: row for row in build_bom(items).rows}
    assert rows["Schütz"].review and rows["Schütz"].quantity == 2
    assert not rows["Sicherung"].review
    assert not rows["Netzteil"].review


def test_group_without_order_number_uses_type():
    items = [
        BomItem(id="a", kind="Klemme", type="UK 5 N", x=0.1, y=0.1),
        BomItem(id="b", kind="Klemme", type="uk5n", x=0.2, y=0.1),
        BomItem(id="c", kind="Klemme", type="UK 10", x=0.3, y=0.1),
    ]
    assert sorted(row.quantity for row in build_bom(items).rows) == [1, 2]


def _pages(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


def _photo(tmp_path):
    path = tmp_path / "schrank.png"
    Image.new("RGB", (1200, 800), (200, 200, 200)).save(path)
    return path


def test_csv_xlsx_pdf_roundtrip(tmp_path):
    items, _ = fixture(3)
    items.append(BomItem(id="evil", kind="Schütz", type="=HYPERLINK(1)", x=0.0, y=0.95, confidence=0.4))
    bom = build_bom(items)

    rows = list(csv.reader(io.StringIO(bom_export.to_csv(bom).decode("utf-8-sig")), delimiter=";"))
    assert rows[0] == bom_export.HEADERS and len(rows) == len(bom.rows) + 1
    assert all(not cell.startswith("=") for r in rows for cell in r)

    data = bom_export.to_xlsx(bom)
    assert zipfile.is_zipfile(io.BytesIO(data))
    sheet = load_workbook(io.BytesIO(data)).active
    assert sheet.auto_filter.ref.startswith("A1:")
    last = sheet.max_row
    assert sheet.cell(last, 2).value == "Summe"
    assert sheet.cell(last, 3).value == f"=SUM(C2:C{last - 1})"
    assert sum(sheet.cell(r, 3).value for r in range(2, last)) == len(items)
    flagged = [r for r in range(2, last) if sheet.cell(r, 10).value == "ja"]
    assert flagged and all(sheet.cell(r, 1).fill.start_color.rgb.endswith("FFF2CC") for r in flagged)

    photo = bom_export.annotated_photo(_photo(tmp_path), items, bom.number_by_item)
    pdf = bom_export.to_pdf(bom, "Schrank 1", photo)
    assert pdf.startswith(b"%PDF")
    assert 1 <= _pages(pdf) <= 3


def test_pdf_max_three_pages_and_fast(tmp_path):
    items = []
    for i in range(60):
        items.append(
            BomItem(
                id=f"h{i}",
                kind="Klemme",
                order_number=f"30440{i:02d}",
                manufacturer="Phoenix Contact",
                type=f"UT 2,5 Variante {i}",
                rating="800 V, 24 A",
                x=(i % 10) * 0.1,
                y=(i // 10) * 0.15,
                w=0.08,
                h=0.1,
                confidence=0.5 if i % 7 == 0 else 0.9,
            )
        )
    bom = build_bom(items)
    start = time.perf_counter()
    photo = bom_export.annotated_photo(_photo(tmp_path), items, bom.number_by_item)
    pdf = bom_export.to_pdf(bom, "Schrank", photo)
    bom_export.to_xlsx(bom)
    bom_export.to_csv(bom)
    assert time.perf_counter() - start < 5
    assert 1 <= _pages(pdf) <= 3


def test_pdf_refuses_oversized_table():
    items = [BomItem(id=str(i), kind="Klemme", order_number=str(i), x=0.0, y=0.0) for i in range(200)]
    with pytest.raises(ValueError):
        bom_export.to_pdf(build_bom(items), "zu lang", None)
