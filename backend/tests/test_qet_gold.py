"""QElectroTech-Gold aus der Stueckliste (Issue #67): Zeilen lesen ohne Testdaten, das echte Gold nur lokal."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
QET = ROOT / "testdata" / "qelectrotech" / "QET_Beispielprojekt_industrial_50S.pdf"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "eval" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qet_gold = _load("qet_gold")


def test_stuecklistenzeilen_liefern_folio_und_kennzeichen():
    lines = [
        "1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18",
        "1 1st issue 22 CHKD AM %{machine} -IGCFolio : 41",
        "4 Mains Power Supply 4Q1 80A",
        "4 Mains Power Supply 4EH EC Led Lighting Cabinet Lighting Schneider Electric",
        "5 Auxiliary Power Supply",
        "5 Auxiliary Power Supply 5F31 2A Schneider Electric",
        "6 Emergency Stop Circuit 6KE1 Emergency Contactor Emergency Contactor 1 Schneider Electric",
        "9 V1 Gate Control Circuit 9HF Led 22mm2 Red H1RD Fault Schneider Electric",
    ]
    # nur Kennzeichen im Blatt-Stil mit dem Folio der Zeile vorne; 4EH und 9HF liest die Grammatik nicht
    assert qet_gold.nomenclature_rows(lines) == [(4, "4Q1"), (5, "5F31"), (6, "6KE1")]


@pytest.mark.skipif(not QET.exists(), reason="QElectroTech-Testdaten liegen nur lokal (testdata/qelectrotech)")
def test_gold_des_industrial_projekts_liegt_auf_den_planseiten():
    gold = qet_gold.build_gold(QET)
    pages = {int(page): set(entry["device"]) for page, entry in gold["seiten"].items()}
    assert {"4Q1", "4Q2", "4Q3"} <= pages[4] and "6KE1" in pages[6]
    assert max(pages) < 41  # Stuecklistenseiten 41 bis 50 gehoeren nicht ins Gold
    assert sum(len(tags) for tags in pages.values()) >= 100
    assert gold["dokument"] == "testdata/qelectrotech/QET_Beispielprojekt_industrial_50S.pdf"
