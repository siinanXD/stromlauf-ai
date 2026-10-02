"""meta-Event: referenzierte Bauteile und Belege aus Antworttext und Fundstellen (ohne Modellaufruf)."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.answer_meta import hotspot_evidence, page_evidence, tags_in_answer


def test_nur_bekannte_betriebsmittel_in_reihenfolge_und_einmal():
    text = "Prüfe zuerst -K1 (Schütz), dann -F2. -K1 zieht nicht, wenn -S3 offen ist; -K99 gibt es nicht. Klemme -X1:5 ist keine Zone."
    assert tags_in_answer(text, {"-K1", "-F2", "-S3", "-X1"}) == ["-K1", "-F2", "-S3"]
    assert tags_in_answer("keine Kennzeichen", {"-K1"}) == []


def test_seitenbelege_nur_pdf_seiten_begrenzt():
    refs = [
        {"document_id": "d1", "filename": "plan.pdf", "doc_type": "schematic", "page": 3},
        {"document_id": "d2", "filename": "liste.xlsx", "doc_type": "bom", "page": None},
        {"document_id": "d1", "filename": "plan.pdf", "doc_type": "schematic", "page": 5},
        {"document_id": "d3", "filename": "hb.pdf", "doc_type": "manual", "page": 12},
        {"document_id": "d3", "filename": "hb.pdf", "doc_type": "manual", "page": 13},
        {"document_id": "d3", "filename": "hb.pdf", "doc_type": "manual", "page": 14},
    ]
    evidence = page_evidence(refs)
    assert [e["page"] for e in evidence] == [3, 5, 12, 13]
    assert evidence[0] == {"kind": "page", "document_id": "d1", "filename": "plan.pdf", "doc_type": "schematic", "page": 3, "label": "plan.pdf S. 3"}


def test_hotspots_der_maschine_zu_den_bauteilen():
    hotspot = SimpleNamespace(id="h1", tag="-K1", label="Hauptschütz", x=0.1, y=0.2, w=0.05, h=0.08, confirmed=True)
    other = SimpleNamespace(id="h2", tag="-M1", label="", x=0, y=0, w=0.1, h=0.1, confirmed=False)
    cabinet = SimpleNamespace(id="c1", title="Schaltschrank", hotspots=[hotspot, other])
    machine = SimpleNamespace(cabinets=[cabinet])
    evidence = hotspot_evidence(machine, ["-k1"])
    assert evidence == [
        {
            "kind": "cabinet", "cabinet_id": "c1", "cabinet_title": "Schaltschrank", "hotspot_id": "h1", "tag": "-K1",
            "label": "Hauptschütz", "box": {"x": 0.1, "y": 0.2, "w": 0.05, "h": 0.08}, "confirmed": True,
        }
    ]
    assert hotspot_evidence(None, ["-K1"]) == [] and hotspot_evidence(machine, []) == []


# --- Stoerfall-Arbeitsflaeche (Spur B3): part_kinds, signal_start, plan_spots gegen FB-01, ohne Datenbank ----------

FB01 = Path(__file__).resolve().parents[2] / "examples" / "foerderband"
PLAN = FB01 / "01_Stromlaufplan_FB-01.pdf"


def _fb01_graph():
    from app.api.signal import _graph

    files = [
        ("terminal_plan", "03_Klemmenplan_FB-01.csv"),
        ("bom", "02_Stueckliste_FB-01.xlsx"),
        ("plc_symbols", "05_Symboltabelle_FB-01.sdf"),
        ("plc_program", "04_SPS_Programm_FB-01.awl"),
    ]
    return _graph(
        tuple(
            sorted((kind, str(FB01 / name), (FB01 / name).stat().st_mtime) for kind, name in files)
        )
    )


def _fb01_devices() -> dict[str, set[str]]:
    from app.api.signal import _bom_rows

    return {"fb01": {tag for tag, _title, _ref in _bom_rows(FB01 / "02_Stueckliste_FB-01.xlsx")}}


def _rows(tag: str) -> list:
    from app.api.answer_meta import PlanRow

    def row(page: int, section: str) -> PlanRow:
        return PlanRow(tag, page, section, "doc-plan", PLAN.name, str(PLAN))

    return [
        row(1, "Deckblatt und Inhaltsverzeichnis"),
        row(3, "Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)"),
        row(6, "SPS -A1 Digitalausgaenge -A1.2"),
    ]


@pytest.fixture
def fb01_graph(monkeypatch):
    from app.api import answer_meta

    graph = _fb01_graph()
    monkeypatch.setattr(answer_meta, "graph_for_source", lambda session, source_id: (graph, None))
    return graph


def test_fb01_antwort_mit_k1_traegt_die_drei_felder(fb01_graph):
    from app.api.answer_meta import first_plan_rows, part_kinds, plan_spot, signal_start

    by_source = _fb01_devices()
    tags = tags_in_answer(
        "Prüfe zuerst -K1, das Schütz für vorwärts.", set().union(*by_source.values())
    )
    assert tags == ["-K1"]
    # FB-01 nennt -A1 (2019 nicht zulaessig): aeltere Lesart, K ist das Schuetz wie im Maschinenmodell
    assert part_kinds(tags, by_source) == {"-K1": "Schuetz/Relais"}
    assert signal_start(tags, ["fb01"]) == "-K1"
    spots = [plan_spot(row) for row in first_plan_rows(tags, _rows("-K1"))]
    assert spots == [
        {
            "tag": "-K1",
            "document_id": "doc-plan",
            "filename": PLAN.name,
            "page": 3,  # Deckblatt mit Inhaltsverzeichnis zaehlt nicht als Stelle im Plan
            "sheet": 3,
            "title": "Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)",
            "column": 4,
        }
    ]


def test_ohne_kennzeichen_bleiben_die_felder_leer(fb01_graph):
    from app.api.answer_meta import first_plan_rows, part_kinds, signal_start

    tags = tags_in_answer("Das Band steht, bitte Motorschutz pruefen.", {"-K1", "-F2"})
    assert tags == []
    assert part_kinds(tags, _fb01_devices()) == {}
    assert signal_start(tags, ["fb01"]) is None
    assert first_plan_rows(tags, _rows("-K1")) == []


def test_signal_start_nimmt_das_erste_verfolgbare_kennzeichen(fb01_graph):
    from app.api.answer_meta import signal_start

    assert signal_start(["-K99", "-F2", "-K1"], ["fb01"]) == "-F2"
    assert signal_start(["-K99"], ["fb01"]) is None
    # ohne genau eine Quelle weiss der Block nicht, wo er den Weg laden soll
    assert signal_start(["-K1"], []) is None and signal_start(["-K1"], ["fb01", "ur01"]) is None


def test_signal_start_haelt_die_antwort_nicht_auf(monkeypatch):
    import time

    from app.api import answer_meta

    def broken(session, source_id):
        raise ValueError("Klemmenplan kaputt")

    monkeypatch.setattr(answer_meta, "graph_for_source", broken)
    assert answer_meta.signal_start(["-K1"], ["fb01"]) is None

    def slow(session, source_id):
        time.sleep(0.5)
        return _fb01_graph(), None

    monkeypatch.setattr(answer_meta, "graph_for_source", slow)
    started = time.perf_counter()
    assert answer_meta.signal_start(["-K1"], ["fb01"], timeout_s=0.05) is None
    assert time.perf_counter() - started < 0.4


def test_plan_spots_hoechstens_vier_in_der_reihenfolge_der_antwort():
    from app.api.answer_meta import MAX_PLAN_SPOTS, PlanRow, first_plan_rows

    tags = ["-K1", "-K2", "-F2", "-Q1", "-M1", "-S1"]
    rows = [PlanRow(tag, 3, "Hauptstromkreis", "d", PLAN.name, str(PLAN)) for tag in reversed(tags)]
    assert [row.tag for row in first_plan_rows(tags, rows)] == tags[:MAX_PLAN_SPOTS]
    parts_list = PlanRow("-K1", 9, "Stückliste", "d", PLAN.name, str(PLAN))
    not_pdf = PlanRow("-K1", 2, "Hauptstromkreis", "d", "plan.dwg", "/plan.dwg")
    assert first_plan_rows(["-K1"], [parts_list, not_pdf]) == []


def test_plan_spot_ohne_datei_nennt_seite_ohne_blatt_und_spalte(tmp_path):
    from app.api.answer_meta import PlanRow, plan_spot

    spot = plan_spot(PlanRow("-K1", 3, "", "d", "weg.pdf", str(tmp_path / "weg.pdf")))
    assert (spot["page"], spot["sheet"], spot["column"], spot["title"]) == (3, None, None, "")


def test_part_kinds_lesart_je_quelle():
    from app.api.answer_meta import part_kinds

    # 2019-Unterklassen (QA, KF, BG) machen K zur Signalverarbeitung, Q zum Schuetz
    new = {"neu": {"-QA1", "-KF1", "-BG1", "-K1"}}
    assert part_kinds(["-K1", "-QA1"], new) == {
        "-K1": "Relais/SPS",
        "-QA1": "Schütz/Leistungsschalter",
    }
    # nur Buchstaben beider Lesarten: offen, H bekommt keine Art; ein alter Buchstabe (Y) kippt die Lesart
    assert part_kinds(["-H1"], {"s": {"-H1", "-F1"}}) == {"-H1": ""}
    assert part_kinds(["-H1"], {"s": {"-H1", "-F1", "-Y1"}}) == {"-H1": "Meldung"}
