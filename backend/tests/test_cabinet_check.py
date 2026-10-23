"""Abgleich Schrankfoto <-> Plan (app/werk/cabinet_check.py) gegen die Hotspots und den Kennzeichen-Index von FB-01."""

import csv
import json
from pathlib import Path

import pytest

from app.ingestion.machine_map import build_map
from app.ingestion.tags import extract_tags
from app.werk.cabinet_check import compare, device_of, placement

FB01 = Path(__file__).resolve().parents[2] / "examples" / "foerderband"
HOTSPOTS = [h["tag"] for h in json.loads((FB01 / "07_Schaltschrank_Hotspots_FB-01.json").read_text(encoding="utf-8"))]


def _index() -> tuple[list[str], dict[str, bool]]:
    """Plankennzeichen und Einbauorte wie aus dem Kennzeichen-Index von FB-01 (Stueckliste und Klemmenplan, ohne Docling)."""
    openpyxl = pytest.importorskip("openpyxl")
    sheet = openpyxl.load_workbook(FB01 / "02_Stueckliste_FB-01.xlsx", read_only=True)
    bom_lines = [
        "| " + " | ".join(str(c) for c in row if c is not None) + " |" for ws in sheet for row in ws.iter_rows(values_only=True)
    ]
    with (FB01 / "03_Klemmenplan_FB-01.csv").open(encoding="utf-8", newline="") as handle:
        terminal_lines = [" | ".join(row) for row in csv.reader(handle, delimiter=";")]
    tags = sorted({t.tag for t in extract_tags("\n".join(bom_lines + terminal_lines))})
    bom_rows = [
        (t.tag, line) for line in bom_lines for t in extract_tags(line) if t.tag_type == "device" and line.count("|") > 2
    ]
    legend = "\n".join(line for line in bom_lines if "Anlage" in line)
    zones = build_map(bom_rows, {t for t in tags if t.startswith("-")}, legend).as_dict()["zones"]
    return tags, placement(zones)


def test_drei_listen_gegen_erwartung():
    plan, placed = _index()
    check = compare(plan, HOTSPOTS, placed)
    # -Q2 (Reparaturschalter) und -P1 (Zaehler) sitzen laut Stueckliste am Antrieb, nicht im Schrank
    assert set(check.in_both) | set(check.missing_in_plan) == {device_of(t) for t in HOTSPOTS}
    assert not set(check.in_both) & set(check.missing_in_plan)
    assert {"-Q1", "-K1", "-K2", "-K3", "-F1", "-F2", "-X3"} <= set(check.in_both)
    assert check.missing_in_cabinet == [], check.missing_in_cabinet
    assert not {"-Q2", "-P1"} & set(check.missing_in_cabinet)


def test_entferntes_bauteil_fehlt_im_schrank():
    plan, placed = _index()
    check = compare(plan, [t for t in HOTSPOTS if t != "-K1"], placed)
    assert "-K1" in check.missing_in_cabinet
    assert "-K1" not in check.in_both


def test_unbekanntes_bauteil_fehlt_im_plan():
    check = compare(["-K1", "-X3:5"], ["-K1", "-Q99"])
    assert check.as_dict() == {"in_both": ["-K1"], "missing_in_cabinet": ["-X3"], "missing_in_plan": ["-Q99"]}


def test_feldgeraete_fehlen_nie_im_schrank():
    check = compare(["-M1", "-B1", "-S1:13", "-K1:A1"], [])
    assert check.missing_in_cabinet == ["-K1"]


def test_einbauort_schlaegt_kennbuchstabe():
    zones = [
        {"code": "+ST1", "name": "Schaltschrank", "parts": [{"tag": "-S9"}]},
        {"code": "+AN1", "name": "Antrieb", "parts": [{"tag": "-Q2"}]},
        {"code": "Blatt 3", "name": "", "parts": [{"tag": "-K7"}]},
    ]
    check = compare(["-S9", "-Q2", "-K7"], [], placement(zones))
    assert check.missing_in_cabinet == ["-K7", "-S9"]
