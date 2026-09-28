from pathlib import Path

from app.ingestion.fact_card import build_fact_card, location_names, locations_in


def hit(doc_type, context, page=None, section="", filename=None):
    return {
        "doc_type": doc_type,
        "filename": filename or f"{doc_type}.x",
        "document_id": f"id-{doc_type}",
        "page": page,
        "section": section,
        "context": context,
    }


BOM = hit("bom", "| Sicherheitsschaltgeraet Kat. 3 / PL d | 1 | +ST1 | /4.3 | | -M1 | Foerdermotor 3~ 1,5 kW, "
          "1420 1/min | Drehstrommotor 1,5 kW, IE3 | 1 | +FE1 | /3.8 |")
TERMINAL_U = hit("terminal_plan", "0 V Meldeleuchten | /6.6 | | -X4 | -X4:U | -K1:2 / -K2:6 | -M1:U1 | Motor Phase U | /3.8 | | -X4 | -X")
TERMINAL_V = hit("terminal_plan", "| -X4 | -X4:V | -K1:4 / -K2:4 | -M1:V1 | Motor Phase V | /3.8 | | -X4 | -X4:W")
SCHEMATIC = hit("schematic", "## Foerderband FB-01 =FB1+ST1 Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)", page=3,
                filename="01_Stromlaufplan.pdf")
SYMBOLS = hit("plc_symbols", "| Band_vor | A 4.0 | BOOL | Schuetz -K1 Foerdermotor vorwaerts | | Band_rueck | A 4.1 |")


def rows(card):
    return {row["label"]: [v["text"] for v in row["values"]] for row in card["rows"]}


def test_title_and_bom_line_from_bom_row():
    card = build_fact_card("-M1", [BOM])
    assert card["title"] == "Foerdermotor 3~ 1,5 kW, 1420 1/min"
    assert "-M1" in card["bom_line"] and "Sicherheitsschaltgeraet" not in card["bom_line"]


def test_schematic_row_has_sheet_refs_first_then_pages():
    card = build_fact_card("-M1", [BOM, SCHEMATIC])
    assert rows(card)["Stromlaufplan"] == ["/3.8"]  # Seite 3 ist durch Blatt 3 abgedeckt
    card = build_fact_card("-M1", [SCHEMATIC])
    assert rows(card)["Stromlaufplan"] == ["S. 3"]


def test_terminals_from_rows_mentioning_the_device():
    card = build_fact_card("-M1", [TERMINAL_U, TERMINAL_V])
    assert rows(card)["Klemmen"] == ["-X4:U", "-X4:V"]


def test_plc_address_from_symbol_row():
    card = build_fact_card("-K1", [SYMBOLS])
    assert rows(card)["SPS"] == ["A4.0"]


def test_no_hits_gives_none():
    assert build_fact_card("-M1", []) is None


def test_full_table_chunk_yields_all_terminals():
    table = hit("terminal_plan", "| -X4 | -X4:U | -K1:2 | -M1:U1 | Motor Phase U | /3.8 |\n"
                "| -X4 | -X4:V | -K1:4 | -M1:V1 | Motor Phase V | /3.8 |\n"
                "| -X4 | -X4:W | -K1:6 | -M1:W1 | Motor Phase W | /3.8 |\n"
                "| -X3 | -X3:4 | -K3:13 | -S3:12 | Not-Halt | /4.4 |")
    card = build_fact_card("-M1", [table])
    assert rows(card)["Klemmen"] == ["-X4:U", "-X4:V", "-X4:W"]


def test_sheet_ref_value_has_no_page():
    card = build_fact_card("-M1", [BOM, SCHEMATIC])
    [ref] = next(row for row in card["rows"] if row["label"] == "Stromlaufplan")["values"]
    assert ref["page"] is None and ref["document_id"] == "id-schematic"


def test_line_based_sources_only_use_lines_with_the_device():
    awl = hit("plc_program", "NETWORK 2\nU E 0.0 // Start -S1\n= A 4.0 // Schuetz -K1 vorwaerts\nU E 0.4 // -B1\n= M 10.0")
    card = build_fact_card("-K1", [awl])
    assert rows(card)["SPS"] == ["A4.0"]


def test_pages_dropped_when_sheet_refs_exist():
    toc = hit("schematic", "Blatt 3 Hauptstromkreis Foerdermotor -M1", page=1)
    card = build_fact_card("-M1", [BOM, toc])
    assert rows(card)["Stromlaufplan"] == ["/3.8"]


def test_single_source_only():
    from app.ingestion.fact_card import hits_of_single_source

    a = {**BOM, "source_id": "A"}
    b = {**TERMINAL_U, "source_id": "B"}
    assert hits_of_single_source([a, {**SCHEMATIC, "source_id": "A"}]) == [a, {**SCHEMATIC, "source_id": "A"}]
    assert hits_of_single_source([a, b]) is None
    assert hits_of_single_source([]) == []


# --- Einbauort aus der Stueckliste ----------------------------------------------------------------

LEGEND = "Anlage =FB1, Schaltschrank +ST1, Feld +FE1. Beispielanlage, frei erfunden."


def test_einbauort_aus_der_stuecklistenzeile_steht_vorn():
    card = build_fact_card("-M1", [BOM, SCHEMATIC])
    assert rows(card)["Einbauort"] == ["+FE1"]  # Zeile von -M1, nicht die des Sicherheitsschaltgeraets
    assert card["rows"][0]["label"] == "Einbauort"  # erst der Ort, dann die Verweise


def test_einbauort_mit_klartext_aus_der_kopfzeile():
    card = build_fact_card("-M1", [BOM], legend=LEGEND)
    assert rows(card)["Einbauort"] == ["Feld +FE1"]
    assert card["rows"][0]["values"][0]["ref"] == "+FE1"


def test_klartext_auch_wenn_die_kopfzeile_im_kontext_der_stueckliste_steht():
    card = build_fact_card("-M1", [hit("bom", LEGEND), BOM])
    assert rows(card)["Einbauort"] == ["Feld +FE1"]


def test_ohne_einbauort_keine_zeile():
    card = build_fact_card("-M1", [TERMINAL_U])
    assert "Einbauort" not in rows(card)


def test_locations_in_nimmt_leitungen_mit_und_prosa_nicht():
    assert locations_in("+ST1") == ["+ST1"]
    assert locations_in("+ST1 -> +FE1") == ["+ST1", "+FE1"]  # Leitung liegt in beiden Orten
    assert locations_in("Leitung von +ST1 nach +FE1") == []
    assert locations_in("Drehstrommotor 1,5 kW, IE3") == []
    assert locations_in("") == []


def test_location_names_liest_nur_ortskennzeichen():
    assert location_names(LEGEND) == {"+ST1": "Schaltschrank", "+FE1": "Feld"}
    assert location_names("") == {}


def test_einbauort_und_kopfzeile_passen_zur_echten_stueckliste():
    """Muster gegen die erzeugte Stueckliste: aendert der Generator das Format, faellt es hier auf."""
    import openpyxl

    path = Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "02_Stueckliste_FB-01.xlsx"
    sheet = openpyxl.load_workbook(path).active
    table = [["" if cell is None else str(cell) for cell in row] for row in sheet.iter_rows(values_only=True)]

    legend = next(row[0] for row in table if row[0].startswith("Anlage"))
    assert location_names(legend) == {"+ST1": "Schaltschrank", "+BP1": "Bedienpult", "+AN1": "Antrieb", "+SE1": "Einlauf", "+SA1": "Auslauf"}

    column = next(row for row in table if row[0] == "BMK").index("Einbauort")
    cells = {row[column] for row in table if row[0].startswith("-") and row[column]}
    assert {"+ST1", "+BP1", "+AN1", "+SE1", "+SA1"} <= cells
    assert all(locations_in(cell) for cell in cells)  # jede Zelle ist als Ort erkennbar


LONG_BOM_TABLE = """| BMK | Bezeichnung | Typ / Kenndaten | Menge | Einbauort | Blatt |
|---|---|---|---|---|---|
| -B1 | Lichtschranke Einlauf, Reflexionslichtschranke mit Reflektor, Schaltabstand 2 m | Reflexionslichtschranke 24 V DC, PNP, M18 | 1 | +FE1 | /4.2 |
| -K1 | Schuetz Foerdermotor vorwaerts, Hauptstromkreis mit Hilfskontaktblock 1S1OE | Leistungsschuetz 4 kW, Spule 24 V DC, 3RT2015 | 1 | +ST1 | /3.2 |
| -M1 | Foerdermotor 3~ 1,5 kW, 1420 1/min | Drehstrommotor 1,5 kW, IE3 | 1 | +FE1 | /3.3 |
"""


def test_einbauort_kommt_aus_der_eigenen_zeile_auch_wenn_sie_lang_ist():
    """Issue #38: Kontext aus extract_tags; die Einbauort-Zelle steht weit hinter dem Kennzeichen."""
    from app.ingestion.tags import TagType, extract_tags

    (k1,) = [t for t in extract_tags(LONG_BOM_TABLE) if t.tag == "-K1" and t.tag_type == TagType.DEVICE]
    card = build_fact_card("-K1", [hit("bom", k1.context)], legend="Anlage =FB1, Schaltschrank +ST1, Feld +FE1")
    assert rows(card)["Einbauort"] == ["Schaltschrank +ST1"]  # Klartext aus der Kopfzeile, nicht +FE1 der Vorgaengerzeile
    assert card["title"] == "Schuetz Foerdermotor vorwaerts, Hauptstromkreis mit Hilfskontaktblock 1S1OE"
