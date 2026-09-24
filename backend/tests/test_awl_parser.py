from pathlib import Path

from app.ingestion.awl_parser import parse_awl, parse_symbol_table, read_text

FIXTURE = Path(__file__).parent / "fixtures" / "motor.awl"


def test_blocks_and_networks():
    blocks = parse_awl(read_text(FIXTURE))

    assert [b.kind for b in blocks] == ["FB", "OB"]
    fb, ob = blocks
    assert fb.label == "FB 10 - Motorsteuerung Pumpe 1"
    assert "Start : BOOL" in fb.declaration
    assert [n.title for n in fb.networks] == ["Selbsthaltung Motor", "Stoermeldung"]
    assert "=     A      4.0" in fb.networks[0].code
    assert "//Start setzt" in fb.networks[0].code

    assert ob.label == "OB 1 - Main Program Sweep (Cycle)"
    assert len(ob.networks) == 1
    assert "CALL FB    10" in ob.networks[0].code


def test_block_without_end_is_kept():
    blocks = parse_awl("FUNCTION FC 1 : VOID\nBEGIN\nNETWORK\nTITLE =Test\n      U E 0.0;\n")
    assert len(blocks) == 1
    assert blocks[0].label == "FC 1"
    assert blocks[0].networks[0].title == "Test"


def test_symbol_table():
    rows = parse_symbol_table('"Taster_Start","E       0.0","BOOL","Start Pumpe 1"\n"Motor_P1","A 4.0","BOOL",""\n')
    assert rows[0] == {
        "symbol": "Taster_Start",
        "address": "E       0.0",
        "data_type": "BOOL",
        "comment": "Start Pumpe 1",
    }
    assert rows[1]["symbol"] == "Motor_P1"
