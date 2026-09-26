from app.ingestion.tags import extract_tags, normalize_tag
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
