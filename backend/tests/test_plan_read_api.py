"""Planlesen per Modell je Quelle (app/api/plan_read.py, Spur D).

Einstellungen ohne Datenbank; die Endpunkte gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1), mit einem Modell-Fake an
der Stelle von make_chat_model. Kein Test ruft ein echtes Modell auf. Offener Modus im Workspace default; jeder Test
loescht genau seine Quelle.
"""

import os
import shutil
from pathlib import Path

import pytest
from plan_model_fake import FakeModel, edge

ROOT = Path(__file__).resolve().parents[2]
FB01 = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
DB = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)
# Seite 1 hat nur ein Kennzeichen und geht nicht ans Modell; Querverweise zaehlen nicht als Leitungsende
INDEX = {
    1: [("-A1", "device")],
    3: [("-K1", "device"), ("-X4:U", "terminal"), ("-X4:V", "terminal"), ("/5.3", "cross_ref")],
    4: [
        ("-S1", "device"),
        ("-S1:13", "device_pin"),
        ("-X3:1", "terminal"),
        ("E0.0", "plc_address"),
    ],
}
ANSWERS = {
    3: {"edges": [edge("-K1", "-X4:U"), edge("-K1", "-Q9")]},
    4: {"edges": [edge("-S1", "-X3:1", pins=("13", None), directed=True)]},
}


def test_planleser_ist_ohne_env_aus(monkeypatch):
    for key in ("PLAN_READER_MODEL", "PLAN_READER_BASE_URL"):
        monkeypatch.delenv(key, raising=False)
    from app.config import Settings

    settings = Settings(_env_file=None)
    assert settings.plan_reader_model == "" and settings.plan_reader_base_url == ""


def test_env_example_fuehrt_beide_einstellungen_ohne_wert():
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assert "PLAN_READER_MODEL=" in lines and "PLAN_READER_BASE_URL=" in lines


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    saved = {key: os.environ.get(key) for key in ("DATA_DIR", "JWT_SECRET", "API_KEY")}
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    os.environ.pop("JWT_SECRET", None)
    os.environ.pop("API_KEY", None)
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


@pytest.fixture
def settings(client, monkeypatch):
    """Die Einstellungen des laufenden Backends; Aenderungen gelten nur fuer einen Test."""
    from app.config import get_settings

    current = get_settings()
    monkeypatch.setattr(current, "plan_reader_model", "")
    monkeypatch.setattr(current, "plan_reader_base_url", "")
    monkeypatch.setattr(current, "openai_api_key", None)
    shutil.rmtree(current.data_dir / "plan_cache", ignore_errors=True)
    return current


@pytest.fixture
def source(client, tmp_path):
    """Quelle mit einem Stromlaufplan (Kopie von FB-01) samt Index und einer Stueckliste, die nicht zaehlt."""
    from app.db import session_scope
    from app.models import Document, KnowledgeSource, TagOccurrence
    from app.tenancy import reset_workspace, set_workspace

    plan = tmp_path / "plan.pdf"
    shutil.copyfile(FB01, plan)
    token = set_workspace("default")
    try:
        with session_scope() as session:
            knowledge = KnowledgeSource(name="Planleser-Modell-Test")
            session.add(knowledge)
            session.flush()
            document = Document(
                source_id=knowledge.id,
                filename="01_Stromlaufplan.pdf",
                storage_path=str(plan),
                doc_type="schematic",
                status="ready",
            )
            parts = Document(
                source_id=knowledge.id,
                filename="02_Stueckliste.xlsx",
                storage_path=str(tmp_path / "stueckliste.xlsx"),
                doc_type="bom",
                status="ready",
            )
            session.add_all([document, parts])
            session.flush()
            for page, rows in INDEX.items():
                for tag, tag_type in rows:
                    session.add(
                        TagOccurrence(
                            document_id=document.id,
                            source_id=knowledge.id,
                            tag=tag,
                            tag_type=tag_type,
                            page=page,
                        )
                    )
            source_id = knowledge.id
    finally:
        reset_workspace(token)
    yield {"id": source_id, "plan": plan}
    token = set_workspace("default")
    try:
        with session_scope() as session:
            session.delete(session.get(KnowledgeSource, source_id))
    finally:
        reset_workspace(token)


def _no_model(*_args, **_kwargs):
    raise AssertionError("Modell darf hier nicht gebaut werden")


@DB
def test_ohne_modell_antwortet_der_lauf_mit_409_und_der_status_mit_aus(
    client, settings, source, monkeypatch
):
    from app.ingestion import plan_model

    monkeypatch.setattr(plan_model, "make_chat_model", _no_model)
    for dry_run in ("true", "false"):
        response = client.post(f"/api/sources/{source['id']}/plan-read?dry_run={dry_run}")
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["message"] == "Kein Modell eingerichtet"
    status = client.get(f"/api/sources/{source['id']}/plan-read").json()
    assert status == {
        "configured": False,
        "model": "",
        "cached": False,
        "edges": 0,
        "dropped": 0,
        "cost_usd": None,
    }


@DB
def test_schaetzung_nennt_seiten_und_usd_ohne_modellaufruf(client, settings, source, monkeypatch):
    from app.ingestion import plan_model

    monkeypatch.setattr(plan_model, "make_chat_model", _no_model)
    settings.plan_reader_model = "openai:gpt-5-mini"
    # ohne Angabe gilt dry_run=true: ein Lauf, der Geld kostet, muss ausdruecklich angefordert werden
    for url in (
        f"/api/sources/{source['id']}/plan-read",
        f"/api/sources/{source['id']}/plan-read?dry_run=true",
    ):
        response = client.post(url)
        assert response.status_code == 200, response.text
        assert response.json() == {
            "model": "openai:gpt-5-mini",
            "pages": 2,  # Seiten 3 und 4; Seite 1 hat nur ein Kennzeichen
            "estimate_usd": pytest.approx(2 * 0.00875),  # Reasoning-Modell: 4000 raus je Seite
            "edges": None,
            "dropped": None,
            "cost_usd": None,
        }
    settings.plan_reader_base_url = "http://localhost:11434/v1"
    local = client.post(f"/api/sources/{source['id']}/plan-read?dry_run=true").json()
    assert (local["pages"], local["estimate_usd"]) == (2, 0.0)


@DB
def test_lauf_schreibt_modellkanten_und_der_status_zeigt_sie(client, settings, source, monkeypatch):
    from app.api import plan_read
    from app.ingestion import plan_model
    from app.ingestion.plan_edges import PlanEdge, read_model_edges, read_model_meta

    fake = FakeModel(ANSWERS)
    built: list[dict] = []
    budget: list[bool] = []
    monkeypatch.setattr(
        plan_model, "make_chat_model", lambda name, **kw: built.append({"name": name, **kw}) or fake
    )
    monkeypatch.setattr(plan_read.ledger, "check_budget", lambda session: budget.append(True))
    settings.plan_reader_model = "openai:gpt-5-mini"

    response = client.post(f"/api/sources/{source['id']}/plan-read?dry_run=false")
    assert response.status_code == 200, response.text
    cost = (
        2 * 3100 * 0.25 + 2 * 450 * 2.0
    ) / 1_000_000  # Tokens aus der Antwort, Preis von gpt-5-mini
    assert response.json() == {
        "model": "openai:gpt-5-mini",
        "pages": 2,
        "estimate_usd": pytest.approx(0.0175),
        "edges": 2,
        "dropped": 1,  # -Q9 steht nicht im Index dieser Seite
        "cost_usd": pytest.approx(cost),
    }
    assert sorted(fake.calls) == [3, 4] and budget == [True]
    assert built[0]["name"] == "openai:gpt-5-mini" and built[0]["base_url"] is None
    assert built[0]["reasoning_effort"] == "low"
    assert sorted(read_model_edges(source["plan"]), key=lambda e: e.page) == [
        PlanEdge("-K1", "-X4:U", 3, "modell", False),
        PlanEdge("-S1:13", "-X3:1", 4, "modell", True),
    ]
    meta = read_model_meta(source["plan"])
    assert meta["model"] == "openai:gpt-5-mini" and meta["pages"] == 2 and meta["dropped"] == 1
    assert meta["failed_pages"] == [] and meta["prompt_version"] == plan_model.PROMPT_VERSION

    status = client.get(f"/api/sources/{source['id']}/plan-read").json()
    assert status == {
        "configured": True,
        "model": "openai:gpt-5-mini",
        "cached": True,
        "edges": 2,
        "dropped": 1,
        "cost_usd": pytest.approx(cost),
    }


@DB
def test_lokaler_endpunkt_kostet_nichts_und_braucht_keinen_schluessel(
    client, settings, source, monkeypatch
):
    from app import llm
    from app.ingestion import plan_model

    fake = FakeModel(ANSWERS)
    seen = {}

    def fake_init(model, **kwargs):
        seen.update(kwargs, model=model)
        return fake

    monkeypatch.setattr(
        llm, "init_chat_model", fake_init
    )  # echtes make_chat_model, nur ohne LangChain-Modell
    monkeypatch.setattr(plan_model, "make_chat_model", llm.make_chat_model)
    settings.plan_reader_model = "openai:qwen3.5:4b"
    settings.plan_reader_base_url = "http://localhost:11434/v1"

    response = client.post(f"/api/sources/{source['id']}/plan-read?dry_run=false")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["edges"], body["estimate_usd"], body["cost_usd"]) == (2, 0.0, 0.0)
    assert seen["base_url"] == "http://localhost:11434/v1" and seen["api_key"] == llm.LOCAL_API_KEY


@DB
def test_fehlender_schluessel_ist_ein_400_mit_seinem_namen(client, settings, source):
    settings.plan_reader_model = "openai:gpt-5-mini"
    response = client.post(f"/api/sources/{source['id']}/plan-read?dry_run=false")
    assert response.status_code == 400, response.text
    assert "OPENAI_API_KEY" in response.json()["detail"]


@DB
def test_scheitert_jede_seite_gibt_es_502_und_keinen_leeren_cache(
    client, settings, source, monkeypatch
):
    from app.api import plan_read
    from app.ingestion import plan_model

    monkeypatch.setattr(
        plan_model, "make_chat_model", lambda name, **kw: FakeModel(fail_pages={3, 4})
    )
    monkeypatch.setattr(plan_read.ledger, "check_budget", lambda session: None)
    settings.plan_reader_model = "openai:gpt-5-mini"
    response = client.post(f"/api/sources/{source['id']}/plan-read?dry_run=false")
    assert response.status_code == 502, response.text
    assert "Anbieter nicht erreichbar" in response.json()["detail"]
    assert client.get(f"/api/sources/{source['id']}/plan-read").json()["cached"] is False


@DB
def test_seite_am_laengenlimit_zaehlt_als_gescheitert_und_ihre_tokens_kosten(
    client, settings, source, monkeypatch
):
    from app.api import plan_read
    from app.ingestion import plan_model
    from app.ingestion.plan_edges import read_model_meta

    fake = FakeModel(ANSWERS, length_pages={4})
    monkeypatch.setattr(plan_model, "make_chat_model", lambda name, **kw: fake)
    monkeypatch.setattr(plan_read.ledger, "check_budget", lambda session: None)
    settings.plan_reader_model = "openai:gpt-5-mini"
    response = client.post(f"/api/sources/{source['id']}/plan-read?dry_run=false")
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["edges"], body["dropped"]) == (1, 1)  # nur Seite 3
    assert body["cost_usd"] == pytest.approx(
        (3100 * 0.25 + 450 * 2.0 + 3200 * 0.25 + 8000 * 2.0) / 1e6
    )
    meta = read_model_meta(source["plan"])
    assert meta["failed_pages"] == [4] and meta["length_limit_pages"] == [4]


@DB
def test_unbekannte_quelle_ist_404(client, settings):
    settings.plan_reader_model = "openai:gpt-5-mini"
    assert client.get("/api/sources/gibtesnicht/plan-read").status_code == 404
    assert client.post("/api/sources/gibtesnicht/plan-read?dry_run=true").status_code == 404
