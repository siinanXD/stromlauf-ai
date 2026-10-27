from pathlib import Path

import pytest

from app.ablauf.gruppieren import gruppiere, kennung_aus_name

EX = Path(__file__).resolve().parents[2] / "examples"


def _namen(ordner: str) -> list[str]:
    # README.md hat keine Kennung und gehoert nicht zu den Anlagendateien.
    return sorted(p.name for p in (EX / ordner).iterdir() if p.is_file() and p.name != "README.md")


def test_kennung_aus_dateiname():
    assert kennung_aus_name("01_Stromlaufplan_FB-01.pdf") == "FB01"
    assert kennung_aus_name("04_SPS_Programm_PM1-AR.awl") == "PM1AR"
    assert kennung_aus_name("Betriebsanleitung.md") is None
    assert kennung_aus_name("FB-01_Handbuch_DE-EN.pdf") == "FB01"


@pytest.mark.parametrize(
    ("name", "erwartet"),
    [
        ("FB01_Stromlaufplan.pdf", "FB01"),
        ("=FB-01_Handbuch.pdf", "FB01"),
        ("=FB01_Handbuch.pdf", "FB01"),
        ("Stromlaufplan_UR01.pdf", "UR01"),
        ("01_Plan_fb01.pdf", None),
    ],
)
def test_kennung_ohne_bindestrich_und_mit_gleichheitszeichen(name, erwartet):
    assert kennung_aus_name(name) == erwartet


@pytest.mark.parametrize(
    "name",
    [
        "Handbuch_DE-EN.pdf",
        "Manual_EN-US.pdf",
        "Handbuch_UTF-8.txt",
        "Plan_REV-01.pdf",
        "IP-65.pdf",
        "PDF-A.pdf",
        "DIN-EN-60204.pdf",
        "SPS7_Programm.awl",
        "PDF1.pdf",
        "DIN1_Norm.pdf",
        "UTF8_liste.csv",
        "REV2_Plan.pdf",
        "ISO9001.pdf",
        "DIN01_Norm.pdf",
        "TIA17_Projekt.pdf",
    ],
)
def test_normen_und_sprachen_sind_keine_kennung(name):
    assert kennung_aus_name(name) is None


def test_gemischter_ordner_ergibt_drei_gruppen():
    dateien = [
        {"name": n, "pfad": n} for o in ("foerderband", "umroller", "aufrollung") for n in _namen(o)
    ]
    g = gruppiere(dateien)
    assert [x["name"] for x in g["gruppen"]] == ["FB-01", "PM1-AR", "UR-01"]
    assert all(x["quelle"] == "kennung" for x in g["gruppen"])
    # foerderband 8 (inkl. 07_ png/json) + umroller 6 + aufrollung 6
    assert sum(len(x["dateien"]) for x in g["gruppen"]) == 20 and g["unzugeordnet"] == []


def test_schreibweisen_einer_kennung_landen_in_einer_gruppe():
    g = gruppiere(
        [
            {"name": "FB01_x.pdf", "pfad": "FB01_x.pdf"},
            {"name": "FB-01_y.pdf", "pfad": "FB-01_y.pdf"},
            {"name": "=FB-01_z.pdf", "pfad": "=FB-01_z.pdf"},
        ]
    )
    assert len(g["gruppen"]) == 1 and g["unzugeordnet"] == []
    assert g["gruppen"][0]["dateien"] == ["FB01_x.pdf", "FB-01_y.pdf", "=FB-01_z.pdf"]


def test_unterordner_gewinnt_vor_kennung():
    dateien = [
        {"name": "01_Stromlaufplan_FB-01.pdf", "pfad": "a/01_Stromlaufplan_FB-01.pdf"},
        {"name": "02_Stueckliste_FB-01.xlsx", "pfad": "b/02_Stueckliste_FB-01.xlsx"},
    ]
    g = gruppiere(dateien)
    assert [(x["name"], x["quelle"]) for x in g["gruppen"]] == [("a", "ordner"), ("b", "ordner")]


def test_wurzeldateien_ohne_kennung_sind_unzugeordnet():
    g = gruppiere(
        [{"name": "notizen.md", "pfad": "notizen.md"}, {"name": "archiv.zip", "pfad": "archiv.zip"}]
    )
    assert (
        g["gruppen"] == []
        and g["unzugeordnet"] == ["notizen.md"]
        and g["ignoriert"] == ["archiv.zip"]
    )


def test_ordner_nur_mit_ignorierten_dateien_ergibt_keine_gruppe():
    g = gruppiere([{"name": "setup.exe", "pfad": "x/setup.exe"}])
    assert g["gruppen"] == [] and g["ignoriert"] == ["x/setup.exe"]
