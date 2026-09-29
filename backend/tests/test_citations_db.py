"""Zitat-Resolver gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1): Index laden, meta-Event, Endpunkt (Issue #46)."""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

SECRET = "citations-test-secret-0123456789abcd"
WS = "ws-citations-test"
OTHER_WS = "ws-citations-other"
PLAN_PDF = (
    Path(__file__).resolve().parents[2] / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
)


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    os.environ["JWT_SECRET"] = SECRET
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()


def _wipe_sources(workspace: str) -> None:
    """Alle Quellen des Test-Workspace loeschen (Cascade raeumt Dokumente, Chunks und Index mit)."""
    from sqlalchemy import select

    from app.db import session_scope
    from app.models import KnowledgeSource
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(workspace)
    try:
        with session_scope() as session:
            for source in session.scalars(select(KnowledgeSource)).all():
                session.delete(source)
    finally:
        reset_workspace(token)


@pytest.fixture(scope="module")
def world(client):
    """Eine Quelle mit Plan (echte PDF), Stueckliste (Index) und AWL (Abschnitte) in WS; Token fuer WS und OTHER_WS.

    Raeumt vorher Reste frueherer Laeufe und hinterher die eigenen Zeilen weg.
    """
    from app.auth import issue_token
    from app.config import get_settings
    from app.db import session_scope
    from app.models import (
        Chunk,
        Document,
        KnowledgeSource,
        TagOccurrence,
        User,
        Workspace,
        WorkspaceMember,
    )
    from app.tenancy import reset_workspace, set_workspace

    tokens = {}
    with session_scope() as session:
        for ws in (WS, OTHER_WS):
            session.merge(Workspace(id=ws, name=ws))
            session.merge(User(id=f"user-{ws}", email=f"{ws}@citations-test.de"))
            session.merge(WorkspaceMember(workspace_id=ws, user_id=f"user-{ws}", role="admin"))
            tokens[ws], _ = issue_token(
                user_id=f"user-{ws}",
                email=f"{ws}@citations-test.de",
                workspace_id=ws,
                role="admin",
                secret=SECRET,
                hours=1,
            )
    _wipe_sources(WS)

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            source = KnowledgeSource(name="Zitat-Test FB-01")
            session.add(source)
            session.flush()
            plan = Document(
                source_id=source.id,
                filename=PLAN_PDF.name,
                storage_path=str(PLAN_PDF),
                doc_type="schematic",
                status="ready",
                page_count=7,
            )
            bom = Document(
                source_id=source.id,
                filename="02_Stueckliste_FB-01.xlsx",
                storage_path="/nirgends/bom.xlsx",
                doc_type="bom",
                status="ready",
            )
            awl = Document(
                source_id=source.id,
                filename="04_SPS_Programm_FB-01.awl",
                storage_path="/nirgends/prog.awl",
                doc_type="plc_program",
                status="ready",
            )
            pending = Document(
                source_id=source.id,
                filename="99_Unfertig.pdf",
                storage_path="/nirgends/x.pdf",
                doc_type="manual",
                status="processing",
                page_count=3,
            )
            session.add_all([plan, bom, awl, pending])
            session.flush()
            for tag, kind in (
                ("-F2", "device"),
                ("-X3", "terminal"),
                ("-X4", "terminal"),
                ("-A1", "device"),
                ("/3.2", "cross_ref"),
            ):
                session.add(
                    TagOccurrence(
                        document_id=bom.id,
                        source_id=source.id,
                        tag=tag,
                        tag_type=kind,
                        page=None,
                        context=f"| {tag} | Teil |",
                    )
                )
            zero = [0.0] * get_settings().embedding_dim
            session.add(
                Chunk(
                    document_id=awl.id,
                    source_id=source.id,
                    page=None,
                    kind="text",
                    section="FB 10 - Foerderband FB-01 Steuerung / NW 4 Stoerung Motorschutz",
                    content="U E0.2",
                    embedding=zero,
                )
            )
            session.add(
                Chunk(
                    document_id=plan.id,
                    source_id=source.id,
                    page=3,
                    kind="text",
                    section="Hauptstromkreis",
                    content="-F2 -K1",
                    embedding=zero,
                )
            )
            source_id = source.id
    finally:
        reset_workspace(token)
    yield {"tokens": tokens, "source_id": source_id}
    _wipe_sources(WS)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _ledger_rows(workspace: str) -> int:
    from sqlalchemy import func, select

    from app.db import session_scope
    from app.models import AiCall
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(workspace)
    try:
        with session_scope() as session:
            return session.scalar(select(func.count()).select_from(AiCall)) or 0
    finally:
        reset_workspace(token)


ANSWER = (
    "-F2 ist ein Motorschutzschalter [[01_Stromlaufplan_FB-01.pdf|/3.2]], laut Stueckliste "
    "[[02_Stueckliste_FB-01.xlsx|-X3:3]]; Netzwerk [[04_SPS_Programm_FB-01.awl|FB 10 NW 4]] und Seite [[01_Stromlaufplan_FB-01.pdf|S. 3]]."
)


def test_index_der_quelle_aus_der_datenbank(world):
    from app.citations import load_docs
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            docs = {d.filename: d for d in load_docs(session, [world["source_id"]])}
            by_stem = load_docs(session, [world["source_id"]], ["01_stromlaufplan_fb-01"])
    finally:
        reset_workspace(token)
    assert set(docs) == {
        "01_Stromlaufplan_FB-01.pdf",
        "02_Stueckliste_FB-01.xlsx",
        "04_SPS_Programm_FB-01.awl",
    }  # 99_Unfertig ist nicht READY
    plan, bom, awl = (
        docs["01_Stromlaufplan_FB-01.pdf"],
        docs["02_Stueckliste_FB-01.xlsx"],
        docs["04_SPS_Programm_FB-01.awl"],
    )
    assert (plan.is_pdf, plan.path, plan.page_count, plan.pages) == (
        True,
        PLAN_PDF,
        7,
        frozenset({3}),
    )
    assert (bom.is_pdf, bom.tags) == (False, frozenset({"-F2", "-X3", "-X4", "-A1", "/3.2"}))
    assert awl.sections == ("FB 10 - Foerderband FB-01 Steuerung / NW 4 Stoerung Motorschutz",)
    assert [d.filename for d in by_stem] == ["01_Stromlaufplan_FB-01.pdf"]


def test_meta_event_traegt_die_geprueften_belege(world):
    from app.api.answer_meta import build_meta
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    refs = [
        {
            "document_id": "x",
            "filename": "01_Stromlaufplan_FB-01.pdf",
            "doc_type": "schematic",
            "page": 3,
            "section": "",
        },
        {
            "document_id": "y",
            "filename": "02_Stueckliste_FB-01.xlsx",
            "doc_type": "bom",
            "page": None,
            "section": "",
        },
    ]
    before = _ledger_rows(WS)
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            meta = build_meta(
                session,
                answer=ANSWER,
                citations=refs,
                source_ids=[world["source_id"]],
                machine_id=None,
            )
    finally:
        reset_workspace(token)
    by_loc = {(c["file"], c["locator"]): c for c in meta["citation_checks"]}
    assert by_loc[("01_Stromlaufplan_FB-01.pdf", "/3.2")]["valid"] is True
    assert by_loc[("02_Stueckliste_FB-01.xlsx", "-X3:3")] == {
        "text": "[[02_Stueckliste_FB-01.xlsx|-X3:3]]",
        "file": "02_Stueckliste_FB-01.xlsx",
        "locator": "-X3:3",
        "valid": False,
        "checked": True,
        "reason": "Kennzeichen -X3:3 nicht in 02_Stueckliste_FB-01.xlsx",
    }
    assert (
        by_loc[("04_SPS_Programm_FB-01.awl", "FB 10 NW 4")]["reason"]
        == "Datei nicht in den Fundstellen der Antwort"
    )
    assert by_loc[("01_Stromlaufplan_FB-01.pdf", "S. 3")]["valid"] is True
    assert meta["citations_valid"] == {"valid": 2, "checked": 4, "total": 4}
    assert meta["referenced_tags"] == ["-F2"] and meta["citations"] == refs
    assert _ledger_rows(WS) == before  # kein Modellaufruf, kein Kostenbuch-Eintrag


def test_leerer_scope_prueft_gegen_alle_quellen_des_workspace(world):
    """Chat auf / ohne Quellenauswahl schickt source_ids=[]; die Werkzeuge suchen dann in allen Quellen."""
    from app.citations import check_answer
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(WS)
    try:
        with session_scope() as session:
            scoped, _ = check_answer(session, ANSWER, [world["source_id"]], None)
            unscoped, _ = check_answer(session, ANSWER, [], None)
    finally:
        reset_workspace(token)
    assert unscoped == scoped
    assert [c["valid"] for c in scoped] == [True, False, True, True]


def test_endpunkt_prueft_gespeicherte_antworten_im_eigenen_workspace(client, world):
    body = {
        "answer": ANSWER,
        "source_ids": [world["source_id"]],
        "sources": [
            {"filename": "01_Stromlaufplan_FB-01.pdf"},
            {"filename": "02_Stueckliste_FB-01.xlsx"},
            {"filename": "04_SPS_Programm_FB-01.awl"},
        ],
    }
    before = _ledger_rows(WS)
    response = client.post(
        "/api/answers/validate-citations", json=body, headers=_auth(world["tokens"][WS])
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["citations_valid"] == {"valid": 3, "checked": 4, "total": 4}
    assert [c["valid"] for c in data["citation_checks"]] == [True, False, True, True]
    assert _ledger_rows(WS) == before

    # ohne Fundstellen zaehlt jede Datei der Quelle
    body.pop("sources")
    assert (
        client.post(
            "/api/answers/validate-citations", json=body, headers=_auth(world["tokens"][WS])
        ).json()["citations_valid"]["valid"]
        == 3
    )

    # fremder Workspace sieht die Quelle nicht
    foreign = client.post(
        "/api/answers/validate-citations", json=body, headers=_auth(world["tokens"][OTHER_WS])
    )
    assert foreign.status_code == 404

    # Deckel: zu lange Antwort wird mit 422 abgelehnt, bevor der Resolver rechnet
    too_long = client.post(
        "/api/answers/validate-citations",
        json={**body, "answer": "x" * 60_000},
        headers=_auth(world["tokens"][WS]),
    )
    assert too_long.status_code == 422


class _FakeGraph:
    """Ersetzt den LangGraph-Checkpointer: liefert einen festen Verlauf fuer jede Konversation."""

    def __init__(self, messages: list) -> None:
        self.messages = messages

    async def aget_state(self, config: dict):
        from types import SimpleNamespace

        return SimpleNamespace(values={"messages": self.messages})


def test_verlauf_traegt_das_meta_je_antwort_nach(client, world, monkeypatch):
    """Issue #47: GET /api/conversations/{id}/messages rechnet das meta-Event deterministisch nach."""
    from datetime import datetime, timezone

    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    from app.db import session_scope
    from app.models import Conversation
    from app.tenancy import reset_workspace, set_workspace

    refs = [
        {
            "document_id": "x",
            "filename": "01_Stromlaufplan_FB-01.pdf",
            "doc_type": "schematic",
            "page": 3,
            "section": "",
        },
        {
            "document_id": "y",
            "filename": "02_Stueckliste_FB-01.xlsx",
            "doc_type": "bom",
            "page": None,
            "section": "",
        },
    ]
    token = set_workspace(WS)
    try:
        with session_scope() as session:
            conversation = Conversation(
                title="Verlauf",
                source_ids=[world["source_id"]],
                updated_at=datetime.now(timezone.utc),
            )
            session.add(conversation)
            session.flush()
            conversation_id = conversation.id
    finally:
        reset_workspace(token)
    messages = [
        HumanMessage("Was ist -F2?"),
        AIMessage(
            content="", tool_calls=[{"name": "find_tag", "args": {"tag": "-F2"}, "id": "c1"}]
        ),
        ToolMessage(content="...", tool_call_id="c1", artifact=refs),
        AIMessage(content=ANSWER),
        HumanMessage("Ohne Beleg?"),
        AIMessage(content="Dazu steht nichts in der Doku."),
    ]
    monkeypatch.setattr(client.app.state, "graph", _FakeGraph(messages))
    before = _ledger_rows(WS)

    response = client.get(
        f"/api/conversations/{conversation_id}/messages", headers=_auth(world["tokens"][WS])
    )
    assert response.status_code == 200, response.text
    user, answer, _question2, plain = response.json()
    assert user["role"] == "user" and user.get("meta") is None
    assert answer["meta"]["referenced_tags"] == ["-F2"]
    assert answer["meta"]["citations"] == refs
    assert answer["meta"]["citations_valid"] == {"valid": 2, "checked": 4, "total": 4}
    assert [c["valid"] for c in answer["meta"]["citation_checks"]] == [True, False, False, True]
    assert [e["kind"] for e in answer["meta"]["evidence"]] == ["page"]
    assert plain["meta"] == {
        "referenced_tags": [],
        "citations": [],
        "evidence": [],
        "citation_checks": [],
        "citations_valid": {"valid": 0, "checked": 0, "total": 0},
    }
    assert _ledger_rows(WS) == before

    # fremder Workspace: 404 wie bisher; unbekannte Maschine im eigenen Workspace: 404
    assert (
        client.get(
            f"/api/conversations/{conversation_id}/messages",
            headers=_auth(world["tokens"][OTHER_WS]),
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/conversations/{conversation_id}/messages",
            params={"machine_id": "gibt-es-nicht"},
            headers=_auth(world["tokens"][WS]),
        ).status_code
        == 404
    )
