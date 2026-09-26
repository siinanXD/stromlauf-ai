from pathlib import Path

from app.ingestion.onboarding import fault_rows_from_markdown, guess_machine

MANUAL = (Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "06_Betriebsanleitung_FB-01.md").read_text(encoding="utf-8")


def test_fault_table_of_the_manual_becomes_fault_entries():
    faults = fault_rows_from_markdown(MANUAL, "Betriebsanleitung")
    assert len(faults) == 7
    first = faults[0]
    assert first["symptom"].startswith("-H2 leuchtet, Band steht")
    assert first["cause"].startswith("Motorschutz -F2 ausgeloest")
    assert first["fix"].startswith("-F2 am Schaltschrank pruefen")
    assert first["doc_ref"] == "Betriebsanleitung Kap. 6"
    assert "-F2" in first["tags"] and "-M1" in first["tags"]


def test_other_tables_are_ignored():
    markdown = "## 5. SPS\n\n| Adresse | Symbol |\n| --- | --- |\n| E0.0 | Start |\n"
    assert fault_rows_from_markdown(markdown, "Handbuch") == []


def test_heading_without_number_is_used_as_reference():
    markdown = "## Fehlersuche\n\n| Fehler | Abhilfe |\n| --- | --- |\n| Pumpe laeuft nicht | -Q2 einschalten |\n"
    [fault] = fault_rows_from_markdown(markdown, "Handbuch")
    assert fault["doc_ref"] == "Handbuch, Fehlersuche" and fault["fix"] == "-Q2 einschalten" and fault["cause"] == ""


def test_guess_machine_from_bom_title():
    assert guess_machine(["Stueckliste Foerderband FB-01", "Foerderband FB-01"]) == ("Foerderband FB-01", "conveyor")
    assert guess_machine(["Roboterzelle R3"]) == ("Roboterzelle R3", "robot")
    assert guess_machine(["Anlage 7"]) == ("Anlage 7", "other")


def test_code_column_is_not_taken_as_symptom():
    markdown = "## Fehler\n\n| Fehlercode | Störung | Ursache | Abhilfe |\n| --- | --- | --- | --- |\n| F01 | Pumpe steht | -F3 aus | -F3 einschalten |\n"
    [fault] = fault_rows_from_markdown(markdown, "Handbuch")
    assert fault["code"] == "F01" and fault["symptom"] == "Pumpe steht"
