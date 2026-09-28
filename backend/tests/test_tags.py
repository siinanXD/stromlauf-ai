from app.ingestion.tags import detect_folio_style, extract_tags, normalize_tag, search_prefixes
from app.models import TagType


def _tags(text: str, **kwargs) -> set[tuple[str, str]]:
    return {(t.tag, str(t.tag_type)) for t in extract_tags(text, **kwargs)}


def test_device_tags_with_and_without_prefix():
    tags = _tags("Schuetz =A1+S1-K12 schaltet -M1, abgesichert ueber -Q3.")
    assert ("-K12", TagType.DEVICE) in tags
    assert ("=A1+S1-K12", TagType.DEVICE) in tags
    assert ("-M1", TagType.DEVICE) in tags
    assert ("-Q3", TagType.DEVICE) in tags


def test_terminals():
    tags = _tags("Ader 3 auf -X1:5, Bruecke nach -X1:6")
    assert ("-X1", TagType.TERMINAL) in tags
    assert ("-X1:5", TagType.TERMINAL) in tags
    assert ("-X1:6", TagType.TERMINAL) in tags


def test_no_device_tag_inside_words():
    assert _tags("E-Mail an Service-Team, Typ 3RT2016-1BB41") == set()


def test_plc_addresses_german_and_international():
    tags = _tags("Eingang E0.0 / %I0.1 / %QX4.0, Merkerwort MW100, DB10.DBX2.0, PEW 256")
    for expected in ["E0.0", "E0.1", "A4.0", "MW100", "DB10.DBX2.0", "DB10", "PEW256"]:
        assert (expected, TagType.PLC_ADDRESS) in tags


def test_awl_spacing_needs_loose_mode_for_outputs():
    line = "      =     A      4.0;"
    assert ("A4.0", TagType.PLC_ADDRESS) not in _tags(line)
    assert ("A4.0", TagType.PLC_ADDRESS) in _tags(line, plc_loose=True)
    # Eingaenge mit Leerzeichen sind auch im Plan eindeutig
    assert ("E0.0", TagType.PLC_ADDRESS) in _tags("U     E      0.0")


def test_current_rating_is_not_an_output():
    assert _tags("Sicherung 10 A 1.5 mm2") == set()


def test_cross_refs():
    tags = _tags("Kontakt 13-14 siehe /12.3 und =A1+S1/7.0")
    assert ("/12.3", TagType.CROSS_REF) in tags
    assert ("/7.0", TagType.CROSS_REF) in tags


def test_normalize_user_input():
    assert normalize_tag("k12") == "-K12"
    assert normalize_tag("-x1:5") == "-X1:5"
    assert normalize_tag("e 0.0") == "E0.0"
    assert normalize_tag("%I0.0") == "E0.0"
    assert normalize_tag("=A1+S1-K12") == "=A1+S1-K12"
    assert normalize_tag("db10.dbx2.0") == "DB10.DBX2.0"


def test_search_key_normalizes():
    from app.ingestion.tags import search_key

    assert search_key("k1") == "-K1"
    assert search_key(" -x1:5 ") == "-X1:5"
    assert search_key("%I0.0") == "E0.0"


def test_search_key_rejects_empty():
    from app.ingestion.tags import search_key

    assert search_key("") is None
    assert search_key("  - ") is None


def test_search_prefixes_cover_partial_input():
    from app.ingestion.tags import search_prefixes

    assert "E0" in search_prefixes("e0")
    assert "M10" in search_prefixes("M10")
    assert "-K" in search_prefixes("k")
    assert "-K1" in search_prefixes("k1")
    assert search_prefixes("  - ") == []


BOM_TABLE = """| BMK | Bezeichnung | Typ / Kenndaten | Menge | Einbauort | Blatt |
|---|---|---|---|---|---|
| -B1 | Lichtschranke Einlauf, Reflexionslichtschranke mit Reflektor, Schaltabstand 2 m | Reflexionslichtschranke 24 V DC, PNP, M18 | 1 | +FE1 | /4.2 |
| -K1 | Schuetz Foerdermotor vorwaerts, Hauptstromkreis mit Hilfskontaktblock 1S1OE | Leistungsschuetz 4 kW, Spule 24 V DC, 3RT2015 | 1 | +ST1 | /3.2 |
| -M1 | Foerdermotor 3~ 1,5 kW, 1420 1/min | Drehstrommotor 1,5 kW, IE3 | 1 | +FE1 | /3.3 |
"""


def test_kontext_einer_tabellenzeile_ist_die_ganze_eigene_zeile():
    """Issue #38: das 80-Zeichen-Fenster schnitt die Einbauort-Zelle der eigenen Zeile ab und zeigte die Vorgaengerzeile."""
    by_tag = {t.tag: t for t in extract_tags(BOM_TABLE) if t.tag_type == TagType.DEVICE}
    k1 = by_tag["-K1"].context
    assert k1.startswith("| -K1 |") and k1.endswith("| /3.2 |")
    assert "+ST1" in k1 and "+FE1" not in k1
    assert "+FE1" in by_tag["-M1"].context and "+ST1" not in by_tag["-M1"].context


def test_kontext_im_fliesstext_bleibt_ein_fenster():
    text = "x" * 300 + " Schuetz -K1 zieht an " + "y" * 300
    (k1,) = [t for t in extract_tags(text) if t.tag == "-K1"]
    assert "-K1" in k1.context and len(k1.context) <= 80 + len("-K1") + 80 + 2


QET_TEXT = """1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18
DATE 01/09/2018
V1 Gate Control Circuit
9QF1
21K1
(21-H2)
19-C8
A1
9K2
A2
V1R2 Closed
XV1:7
10-A1
X2:2
7-H18
AT50+SB-V3M GATE VALVE V1
9EV1
9K1
9K3
-W1
-W2
5F31 2A Schneider Electric
6KEP1 Emergency Power Contactor
TM3DM24R
4Q1 80A
4Q2 63A 300mA
C16 30mA 230VAC 24VDC / 10A
"""


def test_folio_kennzeichen_ohne_minus_nur_im_folio_stil():
    """QET/franzoesischer Stil: Blattnummer + Kennbuchstabe + Zaehler (4Q1, 9K1, 6KEP1), Issue #39."""
    plain = {t.tag for t in extract_tags(QET_TEXT)}
    assert "9K1" not in plain and "-W1" in plain
    folio = {t.tag: t for t in extract_tags(QET_TEXT, folio_style=True)}
    for tag in ("9QF1", "21K1", "9K2", "9EV1", "9K1", "9K3", "5F31", "6KEP1", "4Q1", "4Q2"):
        assert tag in folio and folio[tag].tag_type == TagType.DEVICE, tag
    assert "-W1" in folio
    for wrong in ("3DM24", "-H18", "-A1", "-H2", "H2", "A1", "C16", "10A", "-C8"):
        assert wrong not in folio, wrong


def test_folio_stil_wird_erkannt_wenn_er_dominiert():
    assert detect_folio_style(QET_TEXT) is True
    german = BOM_TABLE + chr(10).join([
        "| -T1 | Netzteil | 6ES7 214 | 1 | +ST1 | /2.6 |",
        "| -K9 | Schuetz | 3RT2015 | 1 | +ST1 | /3.4 |",
    ])
    assert detect_folio_style(german) is False  # Bestellnummern wie 6ES7 zaehlen nicht gegen Minus-Kennzeichen
    assert detect_folio_style("4Q1 4Q2 5F3 -K1") is False  # zu wenige Treffer fuer eine Stilentscheidung

def test_normalize_laesst_folio_kennzeichen_stehen():
    assert normalize_tag("9k1") == "9K1"
    assert normalize_tag(" 6KEP1 ") == "6KEP1"
    assert "9K1" in search_prefixes("9k1")


def test_tabellenzeile_wird_bereinigt_leere_und_verdoppelte_zellen():
    """Docling wiederholt verbundene Zellen und laesst leere stehen; der Kontext soll eine saubere Zeile sein."""
    row = "| 6 | 6 | Emergency Stop Circuit | Emergency Stop Circuit | 6KE1 | 6KE1 | | | Emergency Contactor | Schneider Electric |"
    (tag,) = [t for t in extract_tags(row, folio_style=True) if t.tag == "6KE1"]
    assert tag.context == "| 6 | Emergency Stop Circuit | 6KE1 | Emergency Contactor | Schneider Electric |"
