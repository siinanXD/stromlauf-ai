"""Fehlerlisten-Treffer zu einer Meldung (app/werk/faults.py, Spur B2): dieselbe Logik fuer das Agenten-Werkzeug
search_faults und GET /api/machines/{id}/fault-hits. Ohne Datenbank; die API-Tests stehen in test_stoerfall_db.py."""

from app.api.plant import MAX_FAULT_HITS, best_hits
from app.werk.faults import FaultQuery, fault_matches, fault_score, fold

# wie die Fehlerliste der Beispielanlage FB-01 (scripts/load_example.py)
MOTORSCHUTZ = {
    "code": "E-F2",
    "symptom": "-H2 leuchtet, Band steht, Start ohne Wirkung",
    "cause": "Motorschutz -F2 ausgeloest (E0.2 = 0)",
    "fix": "-F2 pruefen, Motorstrom -M1 messen (Nennstrom 3,5 A). Nach Abkuehlen einschalten, mit -S1 quittieren.",
    "doc_ref": "Betriebsanleitung Kap. 6, Stromlaufplan Blatt 3",
    "tags": ["-F2", "-M1", "-H2"],
}
BLOCKADE = {
    "code": "E-BLOCK",
    "symptom": "-H2 leuchtet nach ca. 20 s Betrieb",
    "cause": "Blockade: Teil am Einlauf -B1, aber nicht am Auslauf -B2 (Timer T5)",
    "fix": "Band auf Verklemmung pruefen, -B2 reinigen und ausrichten (Klemme -X3:6, E0.5).",
    "doc_ref": "FB10 Netzwerk 5, Betriebsanleitung Kap. 6",
    "tags": ["-B1", "-B2", "-X3"],
}
NOT_HALT = {
    "code": "E-NH",
    "symptom": "Start ohne Wirkung, -H1 und -H2 aus",
    "cause": "Not-Halt nicht entriegelt, -K3 ohne Freigabe (E0.3 = 0)",
    "fix": "-S3 entriegeln, 24 V an -X3:4 pruefen.",
    "doc_ref": "Stromlaufplan Blatt 4",
    "tags": ["-S3", "-K3", "-X3"],
}
PHASE = {
    "code": "E-PH",
    "symptom": "-K1 zieht an, Motor brummt, dreht nicht",
    "cause": "Phase fehlt am Motorabgang",
    "fix": "Spannung an -X4:U/V/W pruefen.",
    "doc_ref": "Stromlaufplan Blatt 3",
    "tags": ["-X4", "-M1", "-K1"],
}
FB01 = [MOTORSCHUTZ, BLOCKADE, NOT_HALT, PHASE]


def _hits(query: str) -> list[str]:
    return [f["code"] for f in FB01 if fault_matches(f, query)]


def test_meldung_vom_panel_trifft_ueber_einzelne_woerter():
    # Erfolgskriterium der Spec: die Meldung nennt das Symptom nicht am Stueck
    assert _hits("Störung Motorschutz Förderband") == ["E-F2"]


def test_woertliche_treffer_und_kennzeichen_wie_bisher():
    assert _hits("band steht") == ["E-F2", "E-BLOCK"]  # E-BLOCK nur ueber das Wort "Band"
    assert fault_score(MOTORSCHUTZ, "band steht") > fault_score(BLOCKADE, "band steht")
    assert _hits("f2") == ["E-F2"] and _hits("-F2") == ["E-F2"]
    assert _hits("E-PH") == ["E-PH"]
    assert _hits("Bahnriss") == []


def test_kennzeichen_ohne_minus_aus_der_meldung():
    assert _hits("K1 zieht nicht") == ["E-PH"]
    assert FaultQuery("K1 zieht nicht").tags >= {"-K1"}


def test_kurze_woerter_nur_am_wortanfang_lange_auch_im_wort():
    assert _hits("Not-Halt gedrückt") == ["E-NH"]  # "halt" steckt auch in "einschalten" (E-F2)
    assert _hits("Motor") == ["E-F2", "E-PH"]  # Wortanfang: Motorschutz, Motorstrom, Motor brummt
    assert _hits("Schutz") == ["E-F2"]  # ab sechs Buchstaben auch im Wort: Motorschutz


def test_umlaute_zaehlen_wie_ihre_umschreibung():
    assert fold("Lüfter  Störung ß") == "luefter stoerung ss"
    assert fault_matches({"cause": "Luefter verschmutzt"}, "Lüfter")
    assert fault_matches({"cause": "Lüfter verschmutzt"}, "Luefter")


def test_nur_fuellwoerter_treffen_nichts():
    query = FaultQuery("Störung: Fehler, geht nicht")
    assert not query.empty and query.terms == []
    assert [f["code"] for f in FB01 if query.score(f)] == []


def test_leere_meldung_passt_fuer_das_werkzeug_zu_allem():
    assert FaultQuery("  ").empty and fault_matches(MOTORSCHUTZ, "  ")
    assert fault_score(MOTORSCHUTZ, "") == 0  # der Endpunkt liefert dafuer leere Listen


def test_stoerfall_mit_befund_wird_ueber_titel_und_befund_gefunden():
    incident = {
        "symptom": "Band bleibt stehen",
        "cause": "Luefter am Umrichter verschmutzt, gereinigt",
    }
    assert fault_matches(incident, "Umrichter Übertemperatur")
    assert not fault_matches(incident, "Not-Halt")


def test_beste_treffer_zuerst_hoechstens_fuenf_bei_gleichstand_stabil():
    scored = [(1, "a"), (101, "b"), (1, "c"), (11, "d"), (1, "e"), (1, "f"), (1, "g")]
    assert best_hits(scored) == ["b", "d", "a", "c", "e"]
    assert len(best_hits([(1, str(i)) for i in range(9)])) == MAX_FAULT_HITS == 5
    assert best_hits([]) == []
