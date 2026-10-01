"""Schema-Modell aus Stueckliste, Draufsicht und Index (app/ingestion/machine_map.py) - ohne Datenbank."""

from app.ingestion.machine_map import build_map, kind_of

LEGEND = "Anlage =FB1, Schaltschrank +ST1, Feld +FE1"
BOM = [
    ("-K1", "| -K1 | Schütz Hauptantrieb | 3RT2015 | +ST1 |"),
    ("-M1", "| -M1 | Getriebemotor 0,75 kW | 1LE1001 | +FE1 |"),
    ("-W3", "| -W3 | Motorleitung 4x1,5 | +ST1 -> +FE1 |"),
    ("-F2", "| -F2 | Motorschutzschalter | 3RV2011 | +ST1 |"),
    ("-B7", "| -B7 | Lichtschranke Einlauf |"),
    ("-K1", "| -K1 | nochmal, andere Seite | +ST1 |"),
]


def test_zonen_aus_einbauorten_mit_klartext():
    """Nur Einzelbuchstaben: Die Lesart bleibt offen (Issue #99), -K1 ist Schuetz oder Relais und bekommt keine Art."""
    result = build_map(BOM, legend=LEGEND).as_dict()
    zones = {z["code"]: z for z in result["zones"]}
    assert zones["+ST1"]["name"] == "Schaltschrank" and zones["+FE1"]["name"] == "Feld"
    assert [p["tag"] for p in zones["+ST1"]["parts"]] == ["-K1", "-F2"]  # nach Art sortiert (ohne Art vorn), -K1 nur einmal
    assert zones["+ST1"]["parts"][0] == {
        "tag": "-K1",
        "label": "Schütz Hauptantrieb",
        "kind": "",
        "source": "bom",
        "verb": "hängt an",
    }
    assert result["letter_codes"]["edition"] == "offen"
    assert [p["tag"] for p in zones["+FE1"]["parts"]] == ["-M1"]
    assert zones["?"]["name"] == "Ohne Einbauort" and [p["tag"] for p in zones["?"]["parts"]] == ["-B7"]
    assert result["part_count"] == 4


def test_leitung_mit_zwei_orten_wird_verbinder():
    result = build_map(BOM, legend=LEGEND).as_dict()
    assert result["connectors"] == [{"source": "+ST1", "target": "+FE1", "label": "-W3"}]
    assert all(p["tag"] != "-W3" for z in result["zones"] for p in z["parts"])


def test_draufsicht_und_index_fuellen_auf():
    result = build_map(
        BOM, layout_tags=[("-M1", "Motor"), ("-S3", "Not-Halt Einlauf")], known_tags={"-K1", "-Q1", "-X1", "-W9"}, legend=LEGEND
    ).as_dict()
    codes = [z["code"] for z in result["zones"]]
    assert codes == ["+FE1", "+ST1", "anlage", "?"]
    anlage = next(z for z in result["zones"] if z["code"] == "anlage")
    assert [p["tag"] for p in anlage["parts"]] == ["-S3"]  # -M1 hat schon einen Einbauort
    unplaced = next(z for z in result["zones"] if z["code"] == "?")
    assert [p["tag"] for p in unplaced["parts"]] == ["-Q1", "-B7"] or {p["tag"] for p in unplaced["parts"]} == {"-B7", "-Q1"}
    # Klemmen und Leitungen aus dem blossen Index werden nicht als Bauteile gezeigt
    assert all(p["tag"] not in {"-X1", "-W9"} for z in result["zones"] for p in z["parts"])


def test_leer_ohne_daten():
    result = build_map([]).as_dict()
    assert (result["zones"], result["connectors"], result["part_count"]) == ([], [], 0)
    assert result["letter_codes"]["edition"] == "offen"


def test_modell_liest_kennbuchstaben_in_der_lesart_der_quelle():
    """Issue #99: Unterklassen wie QA und KF zeigen IEC 81346-2:2019; -QA1 ist dann das Schuetz, -KF1 Relais/SPS."""
    bom = [
        ("-QA1", "| -QA1 | Schuetz Pumpe | +ST1 |"),
        ("-KF1", "| -KF1 | SPS | +ST1 |"),
        ("-BG1", "| -BG1 | Endschalter | +FE1 |"),
        ("-MB1", "| -MB1 | Ventilspule | +FE1 |"),
    ]
    result = build_map(bom, legend=LEGEND).as_dict()
    parts = {p["tag"]: (p["kind"], p["verb"]) for z in result["zones"] for p in z["parts"]}
    assert result["letter_codes"]["edition"] == "2019" and "-QA1" in result["letter_codes"]["reason"]
    assert parts == {
        "-QA1": ("Schütz/Leistungsschalter", "schaltet"),
        "-KF1": ("Relais/SPS", "steuert"),
        "-BG1": ("Sensor", "hängt an"),
        "-MB1": ("Elektromagnet", "hängt an"),
    }


def test_beispielmaschine_fb01_behaelt_ihre_arten():
    """Issue #99: FB-01 folgt der aelteren Lesart (SPS -A1); Schuetz, Hauptschalter und Meldeleuchte bleiben, was sie
    vorher waren."""
    from pathlib import Path

    from app.ingestion.docling_parser import pdf_raw_text
    from app.ingestion.tags import TagType, extract_tags

    pdf = Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
    hits = [
        (tag.tag, page, "", page)
        for page, text in sorted(pdf_raw_text(pdf).items())
        for tag in extract_tags(text)
        if tag.tag_type == TagType.DEVICE
    ]
    result = build_map([], index_hits=hits).as_dict()
    kinds = {p["tag"]: p["kind"] for z in result["zones"] for p in z["parts"]}
    assert result["letter_codes"]["edition"] == "alt"
    assert (kinds["-K1"], kinds["-Q1"], kinds["-H1"]) == ("Schuetz/Relais", "Schalter", "Meldung")


def test_art_aus_kennbuchstabe():
    assert kind_of("-K12") == "Schuetz/Relais"
    assert kind_of("+ST1-F3") == "Schutz"
    assert kind_of("-X1") == "Klemme"
    assert kind_of("Q") == "Schalter"
    assert kind_of("") == ""


LONG_BOM_TABLE = """| BMK | Bezeichnung | Typ / Kenndaten | Menge | Einbauort | Blatt |
|---|---|---|---|---|---|
| -B1 | Lichtschranke Einlauf, Reflexionslichtschranke mit Reflektor, Schaltabstand 2 m | Reflexionslichtschranke 24 V DC, PNP, M18 | 1 | +FE1 | /4.2 |
| -K1 | Schuetz Foerdermotor vorwaerts, Hauptstromkreis mit Hilfskontaktblock 1S1OE | Leistungsschuetz 4 kW, Spule 24 V DC, 3RT2015 | 1 | +ST1 | /3.2 |
| -M1 | Foerdermotor 3~ 1,5 kW, 1420 1/min | Drehstrommotor 1,5 kW, IE3 | 1 | +FE1 | /3.3 |
"""


def test_einbauort_aus_der_eigenen_zeile_auch_bei_langen_stuecklistenzeilen():
    """Issue #38: Kontext aus extract_tags, Zeilen laenger als das alte 80-Zeichen-Fenster."""
    from app.ingestion.tags import TagType, extract_tags

    bom_rows = [(t.tag, t.context) for t in extract_tags(LONG_BOM_TABLE) if t.tag_type == TagType.DEVICE]
    zones = {z["code"]: [p["tag"] for p in z["parts"]] for z in build_map(bom_rows, legend=LEGEND).as_dict()["zones"]}
    assert zones == {"+FE1": ["-M1", "-B1"], "+ST1": ["-K1"]}  # je Zone nach Art sortiert (Motor < Sensor)


def test_index_fallback_gruppiert_teile_nach_blatt_und_titel():
    """Issue #39: ohne Stueckliste entstehen die Zonen aus den Blaettern des Stromlaufplans."""
    hits = [
        ("9QF1", 9, "V1 Gate Control Circuit", 9),
        ("9K1", 9, "V1 Gate Control Circuit", 9),
        ("4Q1", 4, "Mains Power Supply", 4),
        ("6KE1", 6, "Emergency Stop Circuit", 6),
        ("9K1", 41, "Nomenclature", 41),  # zweite Fundstelle auf der Stuecklistenseite zaehlt nicht fuer die Zone
        ("5T1", 41, "Nomenclature", 41),  # nur auf der Stuecklistenseite: kein Blatt bekannt
    ]
    result = build_map([], index_hits=hits).as_dict()
    codes = [z["code"] for z in result["zones"]]
    assert codes == ["Blatt 4", "Blatt 6", "Blatt 9", "?"]
    zones = {z["code"]: z for z in result["zones"]}
    assert zones["Blatt 9"]["name"] == "V1 Gate Control Circuit" and zones["Blatt 9"]["id"] == "blatt-9"
    assert {p["tag"] for p in zones["Blatt 9"]["parts"]} == {"9K1", "9QF1"}
    assert all(p["source"] == "index" for z in result["zones"] for p in z["parts"])
    assert [p["tag"] for p in zones["?"]["parts"]] == ["5T1"]
    assert result["part_count"] == 5


def test_stuecklistenzeile_ohne_ort_gibt_bezeichnung_und_blatt_zone():
    """Stuecklistenseite in der PDF (freie Zeile statt Tabelle) liefert die Bezeichnung, das Blatt die Zone."""
    bom_rows = [("6KE1", "6 Emergency Stop Circuit 6KE1 Emergency Contactor Emergency Contactor 1 Schneider Electric")]
    result = build_map(bom_rows, index_hits=[("6KE1", 6, "Emergency Stop Circuit", 6)]).as_dict()
    (zone,) = result["zones"]
    assert zone["code"] == "Blatt 6"
    assert zone["parts"] == [{"tag": "6KE1", "label": "Emergency Contactor Emergency Contactor 1 Schneider Electric",
                              "kind": "Schuetz/Relais", "source": "bom", "verb": "schaltet"}]


def test_einbauort_schlaegt_blatt_zone():
    bom_rows = [("-K1", "| -K1 | Schuetz Hauptantrieb | 3RT2015 | +ST1 |")]
    result = build_map(bom_rows, index_hits=[("-K1", 3, "Hauptstromkreis", 3)], legend=LEGEND).as_dict()
    assert [z["code"] for z in result["zones"]] == ["+ST1"]


def test_blatt_zone_heisst_nach_dem_schriftfeld_nicht_nach_der_seite():
    """Issue #67: Hinter Deckblatt und Inhaltsverzeichnis liegt Blatt 1 auf Seite 3. Ohne gelesene Blattnummer heisst
    die Zone nach der Seite, statt ein Blatt zu behaupten."""
    hits = [("-Q1", 3, "Einspeisung 400 V", 1), ("-K1", 5, "Motorsteuerung Band", 3), ("-S1", 12, "Wartung", None)]
    zones = {z["code"]: z for z in build_map([], index_hits=hits).as_dict()["zones"]}
    assert list(zones) == ["Blatt 1", "Blatt 3", "Seite 12"]
    assert zones["Blatt 1"]["id"] == "blatt-1" and zones["Blatt 1"]["name"] == "Einspeisung 400 V"
    assert zones["Seite 12"]["id"] == "seite-12"


def test_kind_of_kennt_folio_stil_und_zweibuchstabige_kennbuchstaben():
    assert kind_of("9K1") == kind_of("-K1") == "Schuetz/Relais"
    assert kind_of("4Q1") == kind_of("-Q1") == "Schalter"
    assert kind_of("9QF1") == kind_of("-QF1") == "Schutz" and kind_of("-KM1") == "Schuetz/Relais"
    assert kind_of("9EV1") == "Ventil" and kind_of("24V1") == "" and kind_of("-E1") == "Heizung/Leuchte"


def test_index_fallback_laesst_leitungen_klemmen_und_potentiale_weg():
    """Leitungen (-W), Klemmen (-X) und Namen ohne Kennbuchstabe (24V1) sind keine Teile; Verbinder-Leitungen erst recht nicht."""
    bom_rows = [("-W3", "| -W3 | Motorleitung | +ST1 -> +FE1 |")]
    hits = [("-W3", 3, "Hauptstromkreis", 3), ("-W9", 3, "Hauptstromkreis", 3), ("24V1", 5, "Auxiliary Power Supply", 5),
            ("9EV1", 9, "V1 Gate Control Circuit", 9), ("9QF1", 9, "V1 Gate Control Circuit", 9), ("-X3", 7, "Klemmenplan", 7)]
    result = build_map(bom_rows, index_hits=hits, legend=LEGEND).as_dict()
    assert [z["code"] for z in result["zones"]] == ["+FE1", "+ST1", "Blatt 9"]  # +FE1/+ST1 nur wegen des Verbinders -W3
    assert {p["tag"]: p["kind"] for z in result["zones"] for p in z["parts"]} == {"9EV1": "Ventil", "9QF1": "Schutz"}


def test_bezeichnung_steht_hinter_dem_kennzeichen_auch_in_stuecklistenseiten_der_pdf():
    """QET-Nomenclature als Tabelle: Folio | Blatttitel | Kennzeichen | Bezeichnung | ... - nicht der Blatttitel davor."""
    rows = [
        ("6KE1", "| 6 | Emergency Stop Circuit | 6KE1 | Emergency Contactor | Emergency Contactor 1 | Schneider Electric |"),
        ("4Q1", "| 4 | Mains Power Supply | 4Q1 | 80A |"),
        ("-K1", "| -K1 | Schuetz Hauptantrieb | 3RT2015 | +ST1 |"),
        ("8F1", "| 8 | VX Gate Control Circuit | 8F1 |"),  # ohne Bezeichnung: der Blatttitel davor ist keine
    ]
    hits = [("6KE1", 6, "Emergency Stop Circuit", 6), ("4Q1", 4, "Mains Power Supply", 4), ("8F1", 8, "VX Gate Control Circuit", 8)]
    labels = {p["tag"]: p["label"] for z in build_map(rows, index_hits=hits, legend=LEGEND).as_dict()["zones"] for p in z["parts"]}
    assert labels == {"6KE1": "Emergency Contactor", "4Q1": "80A", "-K1": "Schuetz Hauptantrieb", "8F1": ""}
