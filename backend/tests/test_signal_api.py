"""Signalweg-API (Stoerfall-Arbeitsflaeche, Spur A3/A4): 404 mit Grund, reine PDF-Quelle, view=main.

Ohne Datenbank: nur der Router, die Sitzung liefert Dokumente des Beispiels FB-01 aus dem Ordner examples/.
"""

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import signal
from app.db import get_session
from app.ingestion import plan_edges as plan_cache

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "foerderband"
TABLES = {
    "terminal_plan": "03_Klemmenplan_FB-01.csv",
    "bom": "02_Stueckliste_FB-01.xlsx",
    "plc_program": "04_SPS_Programm_FB-01.awl",
    "plc_symbols": "05_Symboltabelle_FB-01.sdf",
}
PLAN = "01_Stromlaufplan_FB-01.pdf"


def _document(doc_type: str, name: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=f"doc-{name}", doc_type=doc_type, filename=name, storage_path=str(EXAMPLE / name)
    )


class _Session:
    def __init__(self, documents: list[SimpleNamespace]):
        self.documents = documents

    def scalars(self, _statement):
        return SimpleNamespace(all=lambda: self.documents)


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(plan_cache, "_cache_dir", lambda: tmp_path / "plan_cache")


def _client(documents: list[SimpleNamespace]) -> TestClient:
    app = FastAPI()
    app.include_router(signal.router)
    app.dependency_overrides[get_session] = lambda: _Session(documents)
    return TestClient(app)


def test_ohne_tabellen_und_leitungen_404_mit_grund_no_sources():
    response = _client([_document("manual", "06_Betriebsanleitung_FB-01.md")]).get(
        "/api/signal-path", params={"tag": "-S1", "source_id": "src"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == {
        "reason": "no_sources",
        "message": "Keine Tabellen und keine Leitungen im Plan gefunden.",
    }


def test_unbekanntes_kennzeichen_404_mit_grund_unknown_tag():
    documents = [_document(doc_type, name) for doc_type, name in TABLES.items()]
    for view in (None, "main"):
        params = {"tag": "-Q99", "source_id": "src", **({"view": view} if view else {})}
        response = _client(documents).get("/api/signal-path", params=params)
        assert response.status_code == 404
        assert response.json()["detail"] == {
            "reason": "unknown_tag",
            "message": "-Q99 kommt im Signalweg nicht vor.",
        }


def test_reine_pdf_quelle_hat_einen_signalweg_aus_den_leitungen():
    """Nur der Stromlaufplan: Taster -> Klemme -> Eingang, Herkunft "Leitung im Plan"."""
    response = _client([_document("schematic", PLAN)]).get(
        "/api/signal-path", params={"tag": "-S1", "source_id": "src"}
    )
    assert response.status_code == 200
    body = response.json()
    level = {node["id"]: node["level"] for node in body["nodes"]}
    assert level["-S1"] < level["-X3:1"] < level["E0.0"]
    edges = {(e["source"], e["target"]): e for e in body["edges"]}
    assert edges[("-X3:1", "E0.0")]["via"] == ["leitung"] and edges[("-X3:1", "E0.0")]["directed"]
    assert body["schematic"] == {"document_id": f"doc-{PLAN}", "filename": PLAN}


def test_view_main_mit_tabellen_und_plan_nennt_beide_herkuenfte():
    documents = [_document(doc_type, name) for doc_type, name in TABLES.items()]
    documents.append(_document("schematic", PLAN))
    response = _client(documents).get(
        "/api/signal-path", params={"tag": "E0.0", "source_id": "src", "view": "main"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["view"] == "main" and body["start"] == "E0.0"
    edge = next(e for e in body["edges"] if (e["source"], e["target"]) == ("-X3:1", "E0.0"))
    assert edge["via"] == ["klemmenplan", "leitung"] and edge["pins"] == {"from": None, "to": None}


def test_werkzeug_und_api_liefern_denselben_hauptweg(monkeypatch):
    """Beide rufen main_view auf; gaebe es eine zweite Rangfolge, laufen die Wege hier auseinander."""
    from app.agent import tools

    documents = [_document(doc_type, name) for doc_type, name in TABLES.items()]
    documents.append(_document("schematic", PLAN))
    session = _Session(documents)
    session.execute = lambda _statement: SimpleNamespace(all=lambda: [("src", "FB-01")])

    class Scope:
        def __enter__(self):
            return session

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(tools, "session_scope", Scope)
    api = _client(documents).get(
        "/api/signal-path", params={"tag": "-S1", "source_id": "src", "view": "main"}
    )
    main = [
        n["id"] for n in sorted(api.json()["nodes"], key=lambda n: n["order"] or 0) if n["main"]
    ]
    text, _refs = tools.signal_path.func("-S1", {"configurable": {"source_ids": ["src"]}})
    steps = [
        line.split(" | ")[1] for line in text.splitlines() if line[:1].isdigit() and " | " in line
    ]
    assert steps == main and main[-1] == "-M1" and "-H2" not in main
