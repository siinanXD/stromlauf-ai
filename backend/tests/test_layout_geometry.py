from app.ingestion.layout_geometry import FALLBACK_MM, LAYOUT_KINDS, clamp_part, to_parts


def test_to_parts_converts_relative_to_mm():
    [p] = to_parts(
        [{"kind": "Motor", "tag": "m1", "x": 0.1, "y": 0.2, "w": 0.05, "h": 0.1, "confidence": 0.9}], 6000, 1000
    )
    assert (p["x_mm"], p["y_mm"], p["w_mm"], p["h_mm"]) == (600, 200, 300, 100)
    assert p["tag"] == "-M1" and p["kind"] == "Motor" and p["shape"] == "rect"
    assert p["confidence"] == 0.9


def test_to_parts_zero_size_uses_fallback():
    [p] = to_parts([{"kind": "Sensor", "x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}], 0, 0)
    assert FALLBACK_MM == 1000.0
    assert p["x_mm"] == 500 and p["w_mm"] == 100


def test_to_parts_unknown_kind_becomes_sonstiges_and_garbage_dropped():
    parts = to_parts(
        [{"kind": "Rakete", "x": 0.1, "y": 0.1, "w": 0.1, "h": 0.1}, {"kind": "Motor", "x": "abc"}], 1000, 1000
    )
    assert [p["kind"] for p in parts] == ["Sonstiges"]


def test_to_parts_circle_shape_and_clamped_to_bounds():
    [p] = to_parts(
        [{"kind": "Not-Halt", "shape": "circle", "x": 0.98, "y": -0.2, "w": 0.1, "h": 0.1}], 1000, 1000
    )
    assert p["shape"] == "circle" and p["x_mm"] + p["w_mm"] <= 1000 and p["y_mm"] == 0


def test_to_parts_empty_tag_stays_empty():
    [p] = to_parts([{"kind": "Rahmen", "tag": None, "x": 0, "y": 0, "w": 1, "h": 1}], 1000, 1000)
    assert p["tag"] == ""


def test_clamp_part_keeps_part_inside():
    assert clamp_part(-50, 900, 200, 200, 1000, 1000) == (0, 800, 200, 200)
    assert clamp_part(0, 0, 5000, 10, 1000, 1000) == (0, 0, 1000, 10)


def test_layout_kinds_fixed_list():
    assert LAYOUT_KINDS == (
        "Motor", "Sensor", "Taster", "Not-Halt", "Leuchte", "Schaltschrank",
        "Band/Förderer", "Rahmen", "Schutztür", "Sonstiges",
    )


def test_parse_vision_json_extracts_object():
    from app.ingestion.layout_vision import parse_vision_json

    assert parse_vision_json('bla {"items": [], "width_mm": 6000} bla') == {"items": [], "width_mm": 6000}


def test_parse_vision_json_without_json_raises():
    import pytest

    from app.ingestion.layout_vision import parse_vision_json

    with pytest.raises(ValueError):
        parse_vision_json("kein json")
