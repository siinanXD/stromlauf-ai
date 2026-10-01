"""Kennbuchstaben je Ausgabe (Issue #99): aeltere Lesart, IEC 81346-2:2019 oder offen."""

from pathlib import Path

import pytest

from app.ingestion.docling_parser import pdf_raw_text
from app.ingestion.letter_codes import ALT, NEU, OFFEN, detect_edition, is_part, kind_of, verb_of
from app.ingestion.tags import extract_tags
from app.models import TagType

EXAMPLES = Path(__file__).resolve().parents[2] / "examples"
PLANS = [
    EXAMPLES / "foerderband" / "01_Stromlaufplan_FB-01.pdf",
    EXAMPLES / "umroller" / "01_Stromlaufplan_UR-01.pdf",
    EXAMPLES / "aufrollung" / "01_Stromlaufplan_PM1-AR.pdf",
]


def _devices(pdf: Path) -> list[str]:
    text = "\n".join(pdf_raw_text(pdf).values())
    return sorted({t.tag for t in extract_tags(text) if t.tag_type == TagType.DEVICE})


@pytest.mark.parametrize("pdf", PLANS, ids=[p.stem for p in PLANS])
def test_beispielplaene_folgen_der_aelteren_lesart(pdf):
    """Die SPS heisst dort -A1; A gibt es seit IEC 81346-2:2019 nicht mehr."""
    edition = detect_edition(_devices(pdf))
    assert edition.name == ALT, edition
    assert "-A1" in edition.reason


def test_unterklassen_der_ausgabe_2019_ergeben_2019():
    edition = detect_edition(["-QA1", "-QA2", "-KF1", "-BG1", "-BG2", "-SJ1", "-MB1", "-PF1", "-XD1", "-FC1"])
    assert edition.name == NEU, edition
    assert "-QA1" in edition.reason


def test_dritte_buchstabenebene_gibt_es_erst_2019():
    assert detect_edition(["-QAB1", "-GQA1", "-KFA2"]).name == NEU


def test_nur_einzelbuchstaben_ohne_weiteren_hinweis_bleiben_offen():
    edition = detect_edition(["-K1", "-Q1", "-M1", "-S1", "-B1", "-F1", "-H1"])
    assert edition.name == OFFEN and edition.reason


def test_franzoesische_paare_und_blatt_stil_ergeben_die_aeltere_lesart():
    assert detect_edition(["-QF1", "-KM1", "-KA2"]).name == ALT
    assert detect_edition(["9QF1", "9EV1", "4Q1", "6KEP1"]).name == ALT


def test_gemischte_hinweise_entscheidet_nur_eine_klare_mehrheit():
    assert detect_edition(["-QA1", "-QA2", "-KF1", "-KF2", "-BG1", "-A1"]).name == NEU
    assert detect_edition(["-QA1", "-KF1", "-A1", "-Y1"]).name == OFFEN


@pytest.mark.parametrize(
    ("tag", "kind"),
    [
        ("-Q1", "Schütz/Schalter"),
        ("-QA1", "Schütz/Leistungsschalter"),
        ("-QM1", "Ventil"),
        ("-K1", "Relais/SPS"),
        ("-KF1", "Relais/SPS"),
        ("-P1", "Anzeige"),
        ("-MB1", "Elektromagnet"),
        ("-MM1", "Zylinder"),
        ("-SJ1", "Taster"),
        ("-FC1", "Sicherung"),
        ("-B1", "Sensor"),
        ("-H1", "Stoffbehandlung"),
        ("-U1", "Halterung"),
        ("-X1", "Klemme"),
        ("-W1", "Leitung"),
    ],
)
def test_lesart_2019(tag, kind):
    assert kind_of(tag, NEU) == kind


def test_aeltere_lesart_bleibt_wie_bisher():
    assert kind_of("-K1", ALT) == kind_of("-K1") == "Schuetz/Relais"
    assert (kind_of("-Q1", ALT), kind_of("-H1", ALT), kind_of("-U1", ALT)) == ("Schalter", "Meldung", "Umrichter")
    assert kind_of("-QF1", ALT) == "Schutz" and kind_of("9EV1", ALT) == "Ventil"


def test_offen_setzt_keine_art_bei_widerspruechlicher_lesart():
    for tag in ("-H1", "-K1", "-Q1", "-U1", "-KE1", "-EV1", "-HL1"):
        assert kind_of(tag, OFFEN) == "", tag
    assert (kind_of("-M1", OFFEN), kind_of("-B1", OFFEN), kind_of("-F1", OFFEN)) == ("Motor", "Sensor", "Schutz")


def test_teil_des_modells_haengt_nicht_an_einer_bekannten_art():
    """Bei offener Lesart hat -K1 keine Art, bleibt aber ein Bauteil; Klemmen, Leitungen und Potentiale nie."""
    assert is_part("-K1", OFFEN) and is_part("-Q1", OFFEN)
    assert not is_part("-X1", NEU) and not is_part("-W1", ALT) and not is_part("24V1", OFFEN)
    assert is_part("-C1", NEU) and not is_part("-C1", ALT)


@pytest.mark.parametrize(
    ("kind", "verb"),
    [
        ("Schutz", "schützt"),
        ("Schalter", "schützt"),
        ("Sicherung", "schützt"),
        ("Schuetz/Relais", "schaltet"),
        ("Schütz/Schalter", "schaltet"),
        ("Schütz/Leistungsschalter", "schaltet"),
        ("Baugruppe", "steuert"),
        ("Relais/SPS", "steuert"),
        ("Versorgung", "versorgt"),
        ("Trafo", "versorgt"),
        ("Umrichter", "versorgt"),
        ("Umformer", "versorgt"),
        ("Klemme", "verbindet"),
        ("Motor", "hängt an"),
        ("", "hängt an"),
    ],
)
def test_verb_aus_der_art(kind, verb):
    """Fuer die aeltere Lesart dieselben Verben wie bisher aus dem Buchstaben (F/Q schuetzt, K schaltet, ...)."""
    assert verb_of(kind) == verb
