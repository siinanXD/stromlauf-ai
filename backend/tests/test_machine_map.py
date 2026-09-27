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
    result = build_map(BOM, legend=LEGEND).as_dict()
    zones = {z["code"]: z for z in result["zones"]}
    assert zones["+ST1"]["name"] == "Schaltschrank" and zones["+FE1"]["name"] == "Feld"
    assert [p["tag"] for p in zones["+ST1"]["parts"]] == ["-K1", "-F2"]  # nach Art sortiert (Schuetz < Schutz), -K1 nur einmal
    assert zones["+ST1"]["parts"][0] == {"tag": "-K1", "label": "Schütz Hauptantrieb", "kind": "Schuetz/Relais", "source": "bom"}
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
    assert build_map([]).as_dict() == {"zones": [], "connectors": [], "part_count": 0}


def test_art_aus_kennbuchstabe():
    assert kind_of("-K12") == "Schuetz/Relais"
    assert kind_of("+ST1-F3") == "Schutz"
    assert kind_of("-X1") == "Klemme"
    assert kind_of("Q") == "Schalter"
    assert kind_of("") == ""
