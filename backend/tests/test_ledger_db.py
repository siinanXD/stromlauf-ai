"""Kostenbuch gegen Postgres (CI-Service; lokal STROMLAUF_DB_TESTS=1): Zeilen je Aufruf, Summen, Limit.

Deckt die Abnahmekriterien aus Issue #26: jeder Vision-Aufruf erzeugt genau eine Ledger-Zeile (Fake-LLM),
Summen je Maschine/Monat stimmen, am Limit wird der naechste Aufruf abgelehnt, bevor der Provider dran ist.
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)")

SECRET = "ledger-test-secret-0123456789abcdef"
WS = "ws-ledger-test"


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["JWT_SECRET"] = SECRET
    os.environ["ANTHROPIC_API_KEY"] = "sk-test-nicht-echt"  # /api/chat prueft nur, dass er gesetzt ist
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


@pytest.fixture(scope="module")
def token(client):
    from app.auth import issue_token
    from app.db import session_scope
    from app.models import User, Workspace, WorkspaceMember

    with session_scope() as session:
        session.merge(Workspace(id=WS, name="Kostenbuch"))
        session.merge(User(id="user-ledger-test", email="ledger@isolation-test.de"))
        session.merge(WorkspaceMember(workspace_id=WS, user_id="user-ledger-test", role="admin"))
    jwt, _ = issue_token(user_id="user-ledger-test", email="ledger@isolation-test.de", workspace_id=WS, role="admin", secret=SECRET, hours=1)
    return jwt


@pytest.fixture(scope="module")
def machine(client, token):
    auth = {"Authorization": f"Bearer {token}"}
    hall = client.post("/api/halls", json={"name": "Halle L", "description": ""}, headers=auth).json()
    source = client.post("/api/sources", json={"name": "Doku L", "description": ""}, headers=auth).json()
    machine = client.post(
        f"/api/halls/{hall['id']}/machines",
        json={"name": "Umroller", "machine_type": "main", "description": "", "source_id": source["id"]},
        headers=auth,
    ).json()
    if not machine.get("source_id"):
        assert client.patch(f"/api/machines/{machine['id']}", json={"source_id": source["id"]}, headers=auth).status_code == 200
    return {"id": machine["id"], "source_id": source["id"], "auth": auth}


def _in_workspace(fn):
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        return fn()
    finally:
        reset_workspace(token)


def test_jeder_vision_aufruf_erzeugt_genau_eine_zeile(client, machine, monkeypatch):
    """Seitenanalyse mit Fake-LLM: zwei Seiten -> zwei Zeilen mit den Tokens aus usage_metadata."""
    from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
    from langchain_core.messages import AIMessage
    from sqlalchemy import select

    from app import ledger
    from app.db import session_scope
    from app.ingestion import pipeline, vision
    from app.models import AiCall

    fake = FakeMessagesListChatModel(
        responses=[
            AIMessage(content="Seite 1: Schuetz -K1", usage_metadata={"input_tokens": 1500, "output_tokens": 600, "total_tokens": 2100}),
            AIMessage(content="Seite 2: Motor -M1", usage_metadata={"input_tokens": 1400, "output_tokens": 500, "total_tokens": 1900}),
        ]
    )
    monkeypatch.setattr(vision, "make_chat_model", lambda *_args, **_kwargs: fake)
    monkeypatch.setattr(vision, "render_page_png", lambda _path, _page: b"png")
    monkeypatch.setattr(pipeline, "_set_progress", lambda *_args: None)

    pieces, failed, skipped = _in_workspace(
        lambda: pipeline._vision_pieces("doc-l", Path("/nirgends/plan.pdf"), {1: "", 2: ""}, machine["id"])
    )
    assert len(pieces) == 2 and failed == [] and skipped == []

    def rows():
        with session_scope() as session:
            return [
                (c.purpose, c.machine_id, c.input_tokens, c.output_tokens, c.images, c.cost_microcents)
                for c in session.scalars(
                    select(AiCall).where(AiCall.purpose == "vision.page", AiCall.machine_id == machine["id"]).order_by(AiCall.input_tokens)
                )
            ]

    booked = _in_workspace(rows)
    assert booked == [
        ("vision.page", machine["id"], 1400, 500, 1, ledger.microcents(_vision_model(), 1400, 500)),
        ("vision.page", machine["id"], 1500, 600, 1, ledger.microcents(_vision_model(), 1500, 600)),
    ]
    assert all(cost > 0 for *_rest, cost in booked)


def _vision_model() -> str:
    from app.config import get_settings

    return get_settings().vision_model


def test_kosten_je_maschine_und_workspace(client, machine):
    from app import ledger
    from app.db import session_scope

    def book():
        with session_scope() as session:
            ledger.record(session, purpose="chat", model="claude-sonnet-5", input_tokens=8000, output_tokens=600, machine_id=machine["id"])
            ledger.record(session, purpose="flow", model="claude-sonnet-5", input_tokens=210_000, output_tokens=75_000, machine_id=machine["id"], trace_id="t-1")
            ledger.record(session, purpose="chat", model="claude-sonnet-5", input_tokens=100, output_tokens=10)  # ohne Maschine

    _in_workspace(book)
    costs = client.get(f"/api/machines/{machine['id']}/costs", headers=machine["auth"]).json()
    assert set(costs["month"]["by_purpose"]) == {"vision.page", "chat", "flow"}
    assert costs["month"]["by_purpose"]["chat"]["calls"] == 1
    assert costs["month"]["by_purpose"]["flow"]["cents"] == pytest.approx((210_000 * 2 + 75_000 * 10) / 1_000_000 * 100)
    assert costs["month"]["cents"] == pytest.approx(costs["total"]["cents"])
    assert costs["workspace"]["month_cents"] > costs["month"]["cents"]  # die Zeile ohne Maschine zaehlt im Workspace
    assert costs["workspace"]["cap_cents"] is None and costs["workspace"]["exceeded"] is False

    budget = client.get("/api/workspace/budget", headers=machine["auth"]).json()
    assert budget["month_cents"] == pytest.approx(costs["workspace"]["month_cents"])
    # fremde Maschine: 404 (Workspace-Scoping)
    assert client.get("/api/machines/gibt-es-nicht/costs", headers=machine["auth"]).status_code == 404


def test_limit_gleich_verbrauch_lehnt_naechsten_aufruf_ab(client, machine, monkeypatch):
    from app import ledger
    from app.db import session_scope

    used = client.get("/api/workspace/budget", headers=machine["auth"]).json()["month_cents"]
    cap = int(used)  # Limit = aktueller Verbrauch (abgerundet, also erreicht)
    patched = client.patch("/api/workspace/budget", json={"cap_cents": cap}, headers=machine["auth"])
    assert patched.status_code == 200 and patched.json()["exceeded"] is True

    # Chat: 402, bevor der Graph laeuft
    called = []
    monkeypatch.setattr(client.app.state, "graph", type("G", (), {"astream": lambda *a, **k: called.append(1)})())
    answer = client.post("/api/chat", json={"conversation_id": None, "message": "Hallo", "source_ids": [], "machine_id": machine["id"]}, headers=machine["auth"])
    assert answer.status_code == 402, answer.text
    assert answer.json()["code"] == "budget_exceeded" and called == []

    # Ingestion ohne KI-Schritt laeuft weiter: der Guard meldet nur, die Vision-Seiten werden uebersprungen
    from app.ingestion import pipeline

    pieces, failed, skipped = _in_workspace(lambda: pipeline._vision_pieces("doc-l", Path("/nirgends/plan.pdf"), {1: "", 2: ""}, machine["id"]))
    assert pieces == [] and failed == [] and skipped == [1, 2]

    def guard():
        with session_scope() as session:
            with pytest.raises(ledger.BudgetExceeded):
                ledger.check_budget(session)

    _in_workspace(guard)

    # Limit aufheben -> wieder frei; Schaetzung liefert Zahlen
    assert client.patch("/api/workspace/budget", json={"cap_cents": None}, headers=machine["auth"]).json()["exceeded"] is False
    estimate = client.get("/api/machines/estimate", params={"pages": 300, "photos": 3}, headers=machine["auth"]).json()
    assert estimate["total_cents"] > 0 and estimate["basis"]["vision.page"] == "list"  # < 5 Messwerte


def test_nur_admin_darf_limit_setzen(client):
    from app.auth import issue_token

    member, _ = issue_token(user_id="user-ledger-test", email="ledger@isolation-test.de", workspace_id=WS, role="member", secret=SECRET, hours=1)
    response = client.patch("/api/workspace/budget", json={"cap_cents": 100}, headers={"Authorization": f"Bearer {member}"})
    assert response.status_code == 403
