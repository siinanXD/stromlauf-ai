from app.ablauf.schritte import (
    SCHRITTE,
    beende,
    dauer_s,
    lauf_status,
    neue_schritte,
    scheitere,
    starte,
)


def test_sieben_schritte_in_reihenfolge():
    assert [k for k, _ in SCHRITTE] == [
        "hochladen",
        "lesen",
        "maschine",
        "steckbrief",
        "modell",
        "zusammenfassung",
        "fertig",
    ]
    assert all(s["status"] == "wartet" for s in neue_schritte())


def test_starte_und_beende_setzen_zeiten_und_status():
    steps = starte(neue_schritte(), "lesen", "2026-10-26T10:00:00+00:00", "3 Dateien")
    assert steps[1]["status"] == "laeuft" and steps[1]["input"] == "3 Dateien"
    steps = beende(steps, "lesen", "2026-10-26T10:00:12+00:00", "412 Abschnitte")
    assert steps[1]["status"] == "fertig" and dauer_s(steps[1]) == 12.0
    assert lauf_status(steps) == "laeuft"


def test_fehler_stoppt_lauf_und_laesst_rest_warten():
    steps = scheitere(
        starte(neue_schritte(), "lesen", "t", ""), "lesen", "t2", "Kein Text im Dokument gefunden"
    )
    assert steps[1]["status"] == "fehler" and steps[1]["error"].startswith("Kein Text")
    assert all(s["status"] == "wartet" for s in steps[2:])
    assert lauf_status(steps) == "fehler"


def test_alle_fertig_ist_fertig():
    steps = neue_schritte()
    for key, _ in SCHRITTE:
        steps = beende(starte(steps, key, "t", ""), key, "t", "")
    assert lauf_status(steps) == "fertig"


def test_funktionen_mutieren_eingabe_nicht():
    steps = neue_schritte()
    starte(steps, "lesen", "t", "x")
    assert steps[1]["status"] == "wartet"
