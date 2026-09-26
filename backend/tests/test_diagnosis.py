from datetime import date

from app.ingestion.diagnosis import append_finding, build_steps

FIX = ("-F2 am Schaltschrank pruefen, Motorstrom -M1 messen (Nennstrom 3,5 A, Einstellung 3,6 A). "
       "Nach Abkuehlen -F2 einschalten, mit Start -S1 quittieren (FB10 Netzwerk 4).")
REFS = {"-F2": "/3.2", "-M1": "/3.5", "-S1": "/4.6", "-H2": "/6.5"}


def test_sentences_become_steps_with_first_tag_and_ref():
    steps = build_steps(FIX, ["-F2", "-M1", "-H2"], REFS)
    assert [s["text"][:10] for s in steps[:2]] == ["-F2 am Sch", "Nach Abkue"]
    assert steps[0]["tag"] == "-F2" and steps[0]["ref"] == "/3.2" and steps[0]["status"] == "open"


def test_tags_without_own_step_are_added():
    steps = build_steps(FIX, ["-F2", "-M1", "-H2"], REFS)
    assert steps[-1] == {"text": "-H2 pruefen", "tag": "-H2", "ref": "/6.5", "status": "open", "note": ""}


def test_abbreviations_do_not_split():
    steps = build_steps("Nach ca. 20 s Band pruefen, z. B. auf Verklemmung (Kap. 6). Danach -B2 reinigen.", [], {})
    assert len(steps) == 2


def test_semicolons_split_and_empty_fix_falls_back():
    assert len(build_steps("-X4:U messen; -X4:V messen", [], {})) == 2
    assert build_steps("", ["-K1"], {"-K1": "/3.4"}) == [
        {"text": "-K1 pruefen", "tag": "-K1", "ref": "/3.4", "status": "open", "note": ""}
    ]
    assert build_steps("", [], {})[0]["text"] == "Befund aufnehmen"


def test_append_finding_is_dated():
    assert append_finding("Alt.", "Kontakt -K1 3/4 verbrannt", date(2026, 9, 26)) == "Alt.\n[26.09.2026] Kontakt -K1 3/4 verbrannt"
    assert append_finding("", "neu", date(2026, 9, 26)) == "[26.09.2026] neu"
