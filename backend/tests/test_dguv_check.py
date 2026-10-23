"""DGUV-V3-Pruefvorlage (SIN-733): jedes Betriebsmittel einmal, Hinweis da, Ergebnis- und Messfelder leer.

Nutzt die 15 synthetischen Schrank-Fixtures aus test_bom."""


import pytest

from app.werk import dguv_check
from app.werk.bom import BomItem, build_bom
from tests.test_bom import fixture


def _pdf_text(template) -> str:
    """Text der Inhaltsstroeme: ohne Kompression und ASCII85 baut reportlab lesbare Stroeme."""
    from reportlab import rl_config

    saved = rl_config.pageCompression, rl_config.useA85
    rl_config.pageCompression, rl_config.useA85 = 0, 0
    try:
        pdf = dguv_check.to_pdf(template)
    finally:
        rl_config.pageCompression, rl_config.useA85 = saved
    return pdf.decode("latin-1")


@pytest.mark.parametrize("seed", range(15))
def test_every_equipment_once_and_pdf_builds(seed):
    items, _ = fixture(seed)
    bom = build_bom(items)
    template = dguv_check.build_template(bom, f"Schrank {seed}")
    tags = [row.bmk for row in template.rows]
    assert sorted(tags) == sorted(bom.bmk_by_item.values())
    assert len(tags) == len(set(tags)) == len(items)
    pdf = dguv_check.to_pdf(template)
    assert pdf.startswith(b"%PDF")


@pytest.mark.parametrize("seed", range(15))
def test_no_result_prefilled_and_notice_present(seed):
    items, _ = fixture(seed)
    template = dguv_check.build_template(build_bom(items), "Schrank")
    assert template.rows
    assert all(row.result == "" for row in template.rows)
    text = _pdf_text(template).lower()
    assert "bestanden" not in text
    assert "elektrofachkraft" in text
    assert dguv_check.NOTICE.startswith("Vorausgefüllt durch Software, Prüfung und Bewertung durch Elektrofachkraft.")


def test_checks_by_part_kind():
    rcd_points, rcd_measures = dguv_check.checks_for("FI-Schalter", "5SM3")
    assert any("Auslöseprüfung" in p for p in rcd_points)
    assert "rcd" in rcd_measures
    _, ls_measures = dguv_check.checks_for("LS-Schalter", "5SL6106-7")
    assert ls_measures == ()
    terminal_points, _ = dguv_check.checks_for("Klemme", "3044076")
    assert any("Sitz" in p for p in terminal_points) and any("Beschriftung" in p for p in terminal_points)


def test_equal_bmk_not_duplicated():
    items = [BomItem(id="a", kind="Schütz", tag="-K1", x=0.1, y=0.1), BomItem(id="b", kind="Schütz", tag="-K1", x=0.5, y=0.1)]
    template = dguv_check.build_template(build_bom(items), "Doppelt")
    assert sorted(r.bmk for r in template.rows) == ["-K1", "-K2"]
