import json
import time
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.ingestion.awl_parser import read_text
from app.ingestion.plc_blocks import (
    SCHEMA_PATH,
    SymbolTable,
    absolute_address,
    parse_plc_source,
)

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures"
VALIDATOR = Draft202012Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))

# (Ordner, Bausteine als (Art, Netzwerke))
EXAMPLES = {
    "foerderband": [("FB", 7), ("DB", 0), ("OB", 2)],
    "umroller": None,
    "aufrollung": None,
}


def load(folder: str):
    base = ROOT / "examples" / folder
    symbols = SymbolTable.from_text(read_text(next(base.glob("05_*.sdf"))))
    return parse_plc_source(read_text(next(base.glob("04_*.awl"))), symbols), symbols


@pytest.mark.parametrize("folder", list(EXAMPLES))
def test_examples_validate_against_schema(folder):
    program, _ = load(folder)
    VALIDATOR.validate(program.to_dict())
    assert program.source_format == "awl"
    assert program.blocks
    assert all(b["networks"] or b["kind"] in {"DB", "UDT"} for b in program.blocks)


def test_foerderband_counts_and_operands():
    program, _ = load("foerderband")
    assert [(b["kind"], len(b["networks"])) for b in program.blocks] == EXAMPLES["foerderband"]
    fb = program.blocks[0]
    assert fb["name"] == "FB 10" and fb["number"] == 10
    assert fb["networks"][0]["title"] == "Selbsthaltung Betrieb"
    first = [o["display"] for o in fb["networks"][0]["operands"]]
    assert first == ["Start", "Freigabe", "Stop", "MSS_OK", "NotHalt_OK", "Stoerung"]
    freigabe = next(o for o in fb["networks"][0]["operands"] if o["name"] == "Freigabe")
    assert freigabe["roles"] == ["read", "write"]
    assert {m["name"] for m in fb["interface"]} >= {"Start", "Vorwaerts", "Freigabe", "Stueckzahl"}


def test_constants_jumps_and_timers():
    program, _ = load("foerderband")
    blockade = program.blocks[0]["networks"][4]["operands"]
    assert [o["display"] for o in blockade] == ["LS_Einlauf", "Vorwaerts", "T_Blockade", "LS_Auslauf", "Stoerung"]
    assert blockade[2]["address"] == "T5"
    count = program.blocks[0]["networks"][6]["operands"]
    shown = [o["display"] for o in count]
    assert "S5T#20S" not in shown and "ende" not in shown and "1" not in shown
    # MW100 hat in der Symboltabelle den Namen Stueckzahl, der lokale #Stueckzahl ist derselbe Eintrag
    assert "MW100" not in shown and shown.count("Stueckzahl") == 1


def test_symbol_replaces_absolute_address():
    program, symbols = load("foerderband")
    ob = program.blocks[-1]
    call = ob["networks"][0]["operands"]
    assert call[0]["roles"] == ["call"] and call[0]["display"] == "FB 10"
    by_address = {o["address"]: o for n in ob["networks"] for o in n["operands"] if o["address"]}
    for address, symbol in symbols.by_address.items():
        if address in by_address:
            op = by_address[address]
            assert op["display"] == symbol and op["name"] == symbol and op["scope"] == "global"
    assert "E0.0" in by_address and by_address["E0.0"]["display"] == "Start"
    # ohne Symbolzeile bleibt die Adresse
    assert by_address["M20.0"]["display"] in {symbols.by_address.get("M20.0"), "M20.0"}


def test_no_absolute_address_where_table_has_a_name():
    for folder in EXAMPLES:
        program, symbols = load(folder)
        for block in program.blocks:
            for network in block["networks"]:
                for op in network["operands"]:
                    if op["address"] in symbols.by_address:
                        assert op["display"] == symbols.by_address[op["address"]], (folder, op)


def test_scl_fixture():
    program = parse_plc_source(read_text(FIXTURES / "FB10_Foerderband.scl"), filename="FB10_Foerderband.scl")
    VALIDATOR.validate(program.to_dict())
    assert program.source_format == "scl"
    fb, ob = program.blocks
    assert (fb["kind"], fb["name"], len(fb["networks"])) == ("FB", "FB_Foerderband", 1)
    assert [m["name"] for m in fb["interface"]] == ["Start", "Stop", "MSS_OK", "K1_Vorwaerts"]
    roles = {o["name"]: o["roles"] for o in fb["networks"][0]["operands"]}
    assert roles == {"Start": ["read"], "Stop": ["read"], "MSS_OK": ["read"], "K1_Vorwaerts": ["write"]}
    assert fb["networks"][0]["statements"] == 4
    calls = {o["display"]: o["roles"] for o in ob["networks"][0]["operands"]}
    assert calls["FB_Foerderband_DB"] == ["call"]
    assert calls["K1_Vorwaerts"] == ["write"] and calls["Start"] == ["param"]


def test_scl_with_symbol_table():
    symbols = SymbolTable.from_text('"Start","E 0.0","BOOL",""\n')
    text = 'ORGANIZATION_BLOCK "Main"\nBEGIN\n   "Start" := %E0.1;\nEND_ORGANIZATION_BLOCK\n'
    ops = parse_plc_source(text, symbols, "x.scl").blocks[0]["networks"][0]["operands"]
    assert ops[0]["display"] == "Start" and ops[0]["address"] == "E0.0"
    assert ops[1]["display"] == "E0.1" and ops[1]["roles"] == ["read"]


TIA_XML = """<?xml version="1.0" encoding="utf-8"?>
<Document><Engineering version="V17"/>
<SW.Blocks.FC ID="0"><AttributeList><Name>Motor</Name><Number>3</Number></AttributeList>
<ObjectList>
<SW.Blocks.CompileUnit ID="3" CompositionName="CompileUnits">
 <AttributeList><NetworkSource><StatementList>
  <StlStatement><StlToken Text="A"/><Access Scope="GlobalVariable"><Symbol><Component Name="Start"/></Symbol></Access></StlStatement>
  <StlStatement><StlToken Text="AN"/><Access Scope="Address"><Address Area="Input" Type="Bool" BlockNumber="0" BitOffset="9" Informational="false"/></Access></StlStatement>
  <StlStatement><StlToken Text="L"/><Access Scope="LiteralConstant"><Constant><ConstantValue>5</ConstantValue></Constant></Access></StlStatement>
  <StlStatement><StlToken Text="="/><Access Scope="LocalVariable"><Symbol><Component Name="Motor"/></Symbol></Access></StlStatement>
 </StatementList></NetworkSource></AttributeList>
 <ObjectList>
  <MultilingualText ID="4" CompositionName="Title"><ObjectList><MultilingualTextItem ID="5"><AttributeList><Culture>de-DE</Culture><Text>Motor ein</Text></AttributeList></MultilingualTextItem></ObjectList></MultilingualText>
 </ObjectList>
</SW.Blocks.CompileUnit>
</ObjectList></SW.Blocks.FC></Document>"""


def test_tia_xml():
    symbols = SymbolTable.from_text('"Start","E 0.0","BOOL",""\n"Taster2","E 1.1","BOOL",""\n')
    program = parse_plc_source(TIA_XML, symbols)
    VALIDATOR.validate(program.to_dict())
    block = program.blocks[0]
    assert (program.source_format, block["kind"], block["name"], block["number"]) == ("xml", "FC", "Motor", 3)
    network = block["networks"][0]
    assert network["title"] == "Motor ein" and network["statements"] == 4
    assert [(o["display"], o["roles"]) for o in network["operands"]] == [
        ("Start", ["read"]), ("Taster2", ["read"]), ("Motor", ["write"])]
    assert network["operands"][1]["address"] == "E1.1"


@pytest.mark.parametrize("raw, expected", [
    ("E 0.0", "E0.0"), ("E       0.0", "E0.0"), ("I0.1", "E0.1"), ("Q4.0", "A4.0"), ("MW 100", "MW100"),
    ("T 5", "T5"), ("C 3", "Z3"), ("%E0.2", "E0.2"), ("DB10.DBX0.0", "DB10.DBX0.0"), ("Start", None),
])
def test_absolute_address(raw, expected):
    assert absolute_address(raw) == expected


def test_parse_time_for_2000_lines():
    base = read_text(ROOT / "examples" / "foerderband" / "04_SPS_Programm_FB-01.awl")
    symbols = SymbolTable.from_text(read_text(ROOT / "examples" / "foerderband" / "05_Symboltabelle_FB-01.sdf"))
    text = "\n".join([base] * (2000 // len(base.splitlines()) + 1))
    assert len(text.splitlines()) >= 2000
    start = time.perf_counter()
    program = parse_plc_source(text, symbols)
    assert time.perf_counter() - start < 5
    assert len(program.blocks) > 3
