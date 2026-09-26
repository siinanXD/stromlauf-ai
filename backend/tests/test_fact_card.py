from app.ingestion.fact_card import build_fact_card


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
    [ref] = card["rows"][0]["values"]
    assert ref["page"] is None and ref["document_id"] == "id-schematic"


def test_line_based_sources_only_use_lines_with_the_device():
    awl = hit("plc_program", "NETWORK 2\nU E 0.0 // Start -S1\n= A 4.0 // Schuetz -K1 vorwaerts\nU E 0.4 // -B1\n= M 10.0")
    card = build_fact_card("-K1", [awl])
    assert rows(card)["SPS"] == ["A4.0"]


def test_pages_dropped_when_sheet_refs_exist():
    toc = hit("schematic", "Blatt 3 Hauptstromkreis Foerdermotor -M1", page=1)
    card = build_fact_card("-M1", [BOM, toc])
    assert rows(card)["Stromlaufplan"] == ["/3.8"]
