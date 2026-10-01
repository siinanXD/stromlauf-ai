from app.ingestion.tags import (
    detect_folio_style,
    detect_spaced_terminals,
    extract_tags,
    normalize_tag,
    search_prefixes,
)
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


def test_satzzeichen_nach_der_klemme_gehoert_nicht_zum_anschluss():
    """Scan-Messung zu #64: "-X3:6." am Satzende landete so im Kennzeichen-Index; ein Anschluss endet nie auf "." oder "/"."""
    tags = _tags("Schaltausgang BK auf -X3:5 bzw. -X3:6. Bruecke -X1:7/ -X1:8")
    for tag in ("-X3:5", "-X3:6", "-X1:7", "-X1:8"):
        assert (tag, TagType.TERMINAL) in tags, tag
    assert [tag for tag, _ in tags if tag.endswith((".", "/"))] == []


def test_kennzeichen_nach_schraegstrich_beginnt_eine_neue_klemme():
    """Zwei Klemmen "-X3:9/-X3:10", nicht der Anschluss "9/-X3" und ein verlorenes -X3:10."""
    tags = _tags("(nicht dargestellt, siehe Klemmenplan -X3:9/-X3:10).")
    assert ("-X3:9", TagType.TERMINAL) in tags
    assert ("-X3:10", TagType.TERMINAL) in tags
    assert ("-X3:9/-X3", TagType.TERMINAL) not in tags


def test_anschluesse_mit_buchstaben_punkt_und_schraegstrich_bleiben_ganz():
    tags = _tags("PE auf -X1:PE, N auf -X1:N, Bruecke -X2:3A, Motor an -X4:U, Ebene -X5:1.2, Spannung an -X4:U/V/W pruefen")
    for tag in ("-X1:PE", "-X1:N", "-X2:3A", "-X4:U", "-X5:1.2", "-X4:U/V/W"):
        assert (tag, TagType.TERMINAL) in tags, tag
    assert ("-X2:3", TagType.TERMINAL) not in _tags("Bruecke -X2:3a")  # ganz oder gar nicht, nie abgeschnitten


def test_etage_einer_mehrstockklemme_in_kleinbuchstaben_wird_erkannt():
    """-X2:3a/-X2:3b stehen so in den Klemmenplaenen von FB-01, UR-01 und PM1-AR; bisher kam nur -X2 in den Index."""
    row = _tags("-X2;-X2:3a;-K3:14;-K1:A1 / -K2:A1 (ueber -A1.2);+24 V freigegeben;/4.4")  # 03_Klemmenplan_FB-01.csv
    assert ("-X2:3A", TagType.TERMINAL) in row
    prose = _tags("Freigabe ueber -X2:3a, Tippbetrieb ueber -X2:3b.")
    assert ("-X2:3A", TagType.TERMINAL) in prose and ("-X2:3B", TagType.TERMINAL) in prose
    assert [tag for tag, _ in row | prose if tag != tag.upper()] == []


def test_suche_findet_die_mehrstockklemme_in_jeder_schreibweise():
    """Die Suche vergleicht case-sensitiv (== und LIKE) mit normalize_tag(); der Index muss genauso lauten."""
    assert [t.tag for t in extract_tags("Bruecke -X2:3a") if ":" in t.tag] == ["-X2:3A"]
    for typed in ("-X2:3a", "-x2:3a", "x2:3a", "-X2:3A"):
        assert normalize_tag(typed) == "-X2:3A", typed
        assert "-X2:3A" in search_prefixes(typed), typed


def test_kleinbuchstaben_nur_als_etage_direkt_hinter_einer_ziffer():
    """Fliesstext hinter einer Klemmleiste wird kein Anschluss; "3ab" wird weder "3A" noch "3"."""
    for text in ("Schirm auf -X1:Schirm legen", "Leiste -X1:oben", "Ader -X1:Pe", "Klemme -X2:3ab"):
        assert [tag for tag, _ in _tags(text) if ":" in tag] == [], text


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


# Schweizer Elektroschema (Issue #91): Klemmleiste ohne Minus, Leerzeichen statt Doppelpunkt
SPACED_TEXT = """X420 1 X420 2
-S421 Taster oben links X420 3 DI b .3 E1.3 -D401
-S422 Taster oben rechts X420 4 DI a .1 E0.1 -D401
-S423 X420 5 E0.2   -S424 X420 6 E0.3
-H427 X420 9 A0.0 -W420 (10x4x0,5) PROFINET X1 P2 X1 P1
"""


def test_klemmen_mit_leerzeichen_nur_im_passenden_stil():
    assert not {t.tag for t in extract_tags(SPACED_TEXT)} & {"-X420", "-X420:3"}
    spaced = {t.tag: t for t in extract_tags(SPACED_TEXT, spaced_terminals=True)}
    for tag in ("-X420", "-X420:1", "-X420:3", "-X420:9"):
        assert tag in spaced and spaced[tag].tag_type == TagType.TERMINAL, tag
    # der Kontext behaelt die Schreibweise des Dokuments
    assert "X420 3" in spaced["-X420:3"].context
    # Profinet-Ports und Leitungsangaben sind keine Klemmen, Geraete bleiben Geraete
    for wrong in ("-X1", "-X1:P2", "-X10", "-X4"):
        assert wrong not in spaced, wrong
    assert spaced["-S421"].tag_type == TagType.DEVICE and "E1.3" in spaced


def test_keine_klemme_mit_leerzeichen_aus_dezimalzahl_oder_minus_kennzeichen():
    found = {t.tag for t in extract_tags("X2 2.5 mm X3 4,5 -X7 2", spaced_terminals=True)}
    assert not {"-X2:2", "-X3:4", "-X7:2"} & found


def test_stil_mit_leerzeichen_braucht_mehrere_klemmen_und_ueberwiegt_den_minus_stil():
    assert detect_spaced_terminals(SPACED_TEXT) is True
    # zu wenige Treffer fuer eine Stilentscheidung
    assert detect_spaced_terminals("X1 1 X1 2 X1 3 X1 4") is False
    dashed = " ".join(f"-X1:{n}" for n in range(1, 11))
    assert detect_spaced_terminals(SPACED_TEXT + dashed) is False  # Minus-Stil ueberwiegt


def test_normalize_versteht_klemmen_mit_leerzeichen():
    assert normalize_tag("X420 3") == "-X420:3"
    assert normalize_tag(" x7 12 ") == "-X7:12"
    assert "-X420:3" in search_prefixes("x420 3")


def test_adressbereich_einer_sps_karte_liefert_beide_enden():
    """Issue #92: "E8.0..E9.7" auf der SPS-Uebersicht; ohne Leerzeichen fielen beide Enden weg."""
    plc = TagType.PLC_ADDRESS
    assert {("E8.0", plc), ("E9.7", plc)} <= _tags("SM 1221 E8.0..E9.7 DI 16x24VDC")
    assert {("A16.0", plc), ("A17.7", plc)} <= _tags("SM 1222 A16.0..A17.7 DQ 16x24VDC")
    both = _tags("CPU 1215C E0.0..E1.5 / A0.0..A1.1")
    assert {("E0.0", plc), ("E1.5", plc), ("A0.0", plc), ("A1.1", plc)} <= both
    assert {("E0.0", plc), ("E1.5", plc)} <= _tags("%I0.0..%I1.5")  # internationale Mnemonik
    assert ("E8.1", plc) not in _tags("E8.0..E9.7")  # der Bereich wird nicht aufgeblaeht
    (start,) = [t for t in extract_tags("Karte -D403 E8.0..E9.7") if t.tag == "E8.0"]
    assert "E8.0..E9.7" in start.context


def test_kein_adressbereich_aus_versionsnummern():
    assert not [t for t in extract_tags("Firmware 1.0..2.0") if t.tag_type == TagType.PLC_ADDRESS]


def test_tabellenzeile_wird_bereinigt_leere_und_verdoppelte_zellen():
    """Docling wiederholt verbundene Zellen und laesst leere stehen; der Kontext soll eine saubere Zeile sein."""
    row = "| 6 | 6 | Emergency Stop Circuit | Emergency Stop Circuit | 6KE1 | 6KE1 | | | Emergency Contactor | Schneider Electric |"
    (tag,) = [t for t in extract_tags(row, folio_style=True) if t.tag == "6KE1"]
    assert tag.context == "| 6 | Emergency Stop Circuit | 6KE1 | Emergency Contactor | Schneider Electric |"
