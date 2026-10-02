from app.werk.specs import clean_specs, key_figure


def test_clean_specs_trims_and_drops_rows_without_label():
    specs = [
        {"label": " Leistung ", "value": " 10 ", "unit": "Logs/min", "source": " x "},
        {"label": "  ", "value": "1"},
    ]
    assert clean_specs(specs) == [
        {"label": "Leistung", "value": "10", "unit": "Logs/min", "source": "x", "position": 0}
    ]


def test_key_figure_is_first_value_with_unit():
    assert key_figure([{"value": "2.200", "unit": "m/min"}, {"value": "5", "unit": "m"}]) == "2.200 m/min"
    assert key_figure([{"value": "Dampf", "unit": ""}]) == "Dampf"
    assert key_figure([]) == ""
