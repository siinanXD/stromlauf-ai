"""Stoerfall-Backend gegen Postgres (CI; lokal STROMLAUF_DB_TESTS=1), Spur B: Migration und PATCH, Verlauf in
Stuecken, fault-hits mit drei Listen, meta-Felder fuer eine FB-01-Antwort.

Laeuft in eigenen Workspaces, damit die Demo-Daten im Standard-Workspace keine Treffer beisteuern; raeumt vorher
Reste frueherer Laeufe und hinterher die eigenen Zeilen weg. Die Dokumente zeigen auf die Beispieldateien unter
examples/foerderband/ und werden nur gelesen.
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)

SECRET = "stoerfall-test-secret-0123456789abcd"
WS = "ws-stoerfall-test"
OTHER_WS = "ws-stoerfall-other"
FB01 = Path(__file__).resolve().parents[2] / "examples" / "foerderband"
PLAN = FB01 / "01_Stromlaufplan_FB-01.pdf"
SHEET3 = "Hauptstromkreis Foerdermotor -M1 (Wendeschuetz)"
FB01_FAULTS = [
    ("E-F2", "-H2 leuchtet, Band steht", "Motorschutz -F2 ausgeloest (E0.2 = 0)", ["-F2", "-M1"]),
    ("E-BLOCK", "-H2 leuchtet nach ca. 20 s Betrieb", "Blockade am Einlauf -B1", ["-B1", "-B2"]),
    ("E-NH", "Start ohne Wirkung", "Not-Halt nicht entriegelt", ["-S3", "-K3"]),
    ("E-PH", "-K1 zieht an, Motor brummt", "Phase fehlt am Motorabgang", ["-K1", "-M1"]),
]


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    saved = {key: os.environ.get(key) for key in ("JWT_SECRET", "DATA_DIR")}
    os.environ["JWT_SECRET"] = SECRET
    os.environ["DATA_DIR"] = str(tmp_path_factory.mktemp("data"))
    from app.config import get_settings

    get_settings.cache_clear()
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(
        app
    ) as client:  # lifespan: init_db bringt die Datenbank auf 0004_stoerfall_felder
        yield client
    for key, value in saved.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    get_settings.cache_clear()


def _in(workspace: str, action):
    from app.db import session_scope
    from app.tenancy import reset_workspace, set_workspace

    token = set_workspace(workspace)
    try:
        with session_scope() as session:
            return action(session)
    finally:
        reset_workspace(token)


def _wipe(session) -> None:
    from sqlalchemy import select

    from app.models import Conversation, Hall, KnowledgeSource

    for model in (Hall, KnowledgeSource, Conversation):
        for row in session.scalars(select(model)).all():
            session.delete(row)


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _create_world(session) -> dict:
    from app.models import (
        Conversation,
        Document,
        FaultEntry,
        Hall,
        KnowledgeSource,
        Machine,
        TagOccurrence,
        TagType,
    )

    source = KnowledgeSource(name="Stoerfall-Test FB-01")
    hall = Hall(name="Halle Stoerfall-Test")
    session.add_all([source, hall])
    session.flush()
    documents = {
        kind: Document(
            source_id=source.id,
            filename=name,
            storage_path=str(FB01 / name),
            doc_type=kind,
            status="ready",
        )
        for kind, name in (
            ("schematic", PLAN.name),
            ("bom", "02_Stueckliste_FB-01.xlsx"),
            ("terminal_plan", "03_Klemmenplan_FB-01.csv"),
            ("plc_program", "04_SPS_Programm_FB-01.awl"),
            ("plc_symbols", "05_Symboltabelle_FB-01.sdf"),
        )
    }
    machine = Machine(hall_id=hall.id, name="Foerderband Test", source_id=source.id)
    other = Machine(hall_id=hall.id, name="Presse Test")
    empty = Machine(hall_id=hall.id, name="Ohne Liste")
    session.add_all([*documents.values(), machine, other, empty])
    session.flush()
    plan_id = documents["schematic"].id
    for tag, page, section in (
        ("-K1", 1, "Deckblatt und Inhaltsverzeichnis"),
        ("-K1", 3, SHEET3),
        ("-F2", 3, SHEET3),
        ("-A1", 5, "SPS -A1 Digitaleingaenge -A1.1"),
    ):
        session.add(
            TagOccurrence(
                document_id=plan_id,
                source_id=source.id,
                tag=tag,
                tag_type=TagType.DEVICE,
                page=page,
                section=section,
                context=tag,
            )
        )
    for code, symptom, cause, tags in FB01_FAULTS:
        session.add(
            FaultEntry(machine_id=machine.id, code=code, symptom=symptom, cause=cause, tags=tags)
        )
    for n in range(1, 8):  # sieben Treffer an der anderen Maschine: hoechstens 5 kommen zurueck
        session.add(
            FaultEntry(machine_id=other.id, code=f"P{n}", cause=f"Motorschutz -F{n} ausgeloest")
        )
    conversations = {
        "found": Conversation(
            title="Band steht",
            source_ids=[source.id],
            outcome="resolved",
            finding="Motorschutz -F2 auf 3,5 A nachgestellt",
        ),
        "no_finding": Conversation(
            title="Motorschutz", source_ids=[source.id], outcome="resolved", finding=""
        ),
        "open": Conversation(title="Störung Motorschutz", source_ids=[source.id]),
        "other_source": Conversation(
            title="Motorschutz",
            source_ids=["andere-quelle"],
            outcome="resolved",
            finding="Motorschutz",
        ),
        "unrelated": Conversation(
            title="Übertemperatur",
            source_ids=[source.id],
            outcome="resolved",
            finding="Luefter gereinigt",
        ),
        "patch": Conversation(title="Zum Abschliessen", source_ids=[source.id]),
        "history": Conversation(title="Verlauf", source_ids=[source.id]),
    }
    session.add_all(conversations.values())
    session.flush()
    return {
        "source_id": source.id,
        "machine_id": machine.id,
        "other_id": other.id,
        "empty_id": empty.id,
        "conversations": {key: c.id for key, c in conversations.items()},
    }


@pytest.fixture(scope="module")
def world(client):
    from app.auth import issue_token
    from app.db import session_scope
    from app.models import User, Workspace, WorkspaceMember

    tokens = {}
    with session_scope() as session:
        for ws in (WS, OTHER_WS):
            session.merge(Workspace(id=ws, name=ws))
            session.merge(User(id=f"user-{ws}", email=f"{ws}@stoerfall-test.de"))
            session.merge(WorkspaceMember(workspace_id=ws, user_id=f"user-{ws}", role="admin"))
            tokens[ws], _ = issue_token(
                user_id=f"user-{ws}",
                email=f"{ws}@stoerfall-test.de",
                workspace_id=ws,
                role="admin",
                secret=SECRET,
                hours=1,
            )
    _in(WS, _wipe)
    data = _in(WS, _create_world)
    yield {**data, "tokens": tokens}
    _in(WS, _wipe)


# --- B1: Migration, PATCH, Verlauf in Stuecken -----------------------------------------------------------------


def test_bestehende_zeilen_bekommen_den_standard_der_migration(client, world):
    from sqlalchemy import text

    def insert_old_row(session) -> None:
        # wie ein Chat aus der Zeit vor 0004: ohne outcome und finding geschrieben
        session.execute(
            text(
                "INSERT INTO conversations (id, title, source_ids, created_at, updated_at, workspace_id) "
                "VALUES ('stoerfall-alt', 'Alter Chat', CAST(:ids AS json), now(), now(), :ws)"
            ),
            {"ids": f'["{world["source_id"]}"]', "ws": WS},
        )

    _in(WS, insert_old_row)
    listed = client.get(
        "/api/conversations",
        params={"source_id": world["source_id"]},
        headers=_auth(world["tokens"][WS]),
    ).json()
    old = next(c for c in listed if c["id"] == "stoerfall-alt")
    assert (old["outcome"], old["finding"]) == ("open", "")


def test_patch_schliesst_und_oeffnet_den_stoerfall(client, world):
    conversation_id = world["conversations"]["patch"]
    headers = _auth(world["tokens"][WS])
    url = f"/api/conversations/{conversation_id}"

    done = client.patch(
        url, json={"outcome": "resolved", "finding": "Luefter gereinigt"}, headers=headers
    )
    assert done.status_code == 200, done.text
    assert (done.json()["outcome"], done.json()["finding"]) == ("resolved", "Luefter gereinigt")
    listed = client.get(
        "/api/conversations", params={"source_id": world["source_id"]}, headers=headers
    ).json()
    assert next(c for c in listed if c["id"] == conversation_id)["outcome"] == "resolved"

    reopened = client.patch(url, json={"outcome": "open"}, headers=headers).json()
    assert (reopened["outcome"], reopened["finding"]) == ("open", "Luefter gereinigt")
    assert client.patch(url, json={}, headers=headers).json()["outcome"] == "open"

    assert client.patch(url, json={"outcome": "erledigt"}, headers=headers).status_code == 422
    assert client.patch(url, json={"finding": "x" * 2001}, headers=headers).status_code == 422
    assert (
        client.patch(
            "/api/conversations/gibt-es-nicht", json={"outcome": "resolved"}, headers=headers
        ).status_code
        == 404
    )
    foreign = client.patch(
        url, json={"outcome": "resolved"}, headers=_auth(world["tokens"][OTHER_WS])
    )
    assert foreign.status_code == 404


class _FakeGraph:
    """Ersetzt den LangGraph-Checkpointer: liefert einen festen Verlauf fuer jede Konversation."""

    def __init__(self, messages: list) -> None:
        self.messages = messages

    async def aget_state(self, config: dict):
        from types import SimpleNamespace

        return SimpleNamespace(values={"messages": self.messages})


def test_verlauf_in_stuecken_mit_index_und_meta(client, world, monkeypatch):
    from langchain_core.messages import AIMessage, HumanMessage

    messages = []
    for n in range(3):
        messages += [HumanMessage(f"Frage {n}"), AIMessage(f"Antwort {n}: -K1 pruefen.")]
    monkeypatch.setattr(client.app.state, "graph", _FakeGraph(messages))
    headers = _auth(world["tokens"][WS])
    url = f"/api/conversations/{world['conversations']['history']}/messages"

    def page(**params) -> list[tuple[int, str]]:
        response = client.get(url, params=params, headers=headers)
        assert response.status_code == 200, response.text
        return [(m["index"], m["content"]) for m in response.json()]

    assert [index for index, _ in page()] == [0, 1, 2, 3, 4, 5]  # ohne Parameter alles, wie bisher
    assert page(limit=2) == [(4, "Frage 2"), (5, "Antwort 2: -K1 pruefen.")]
    assert page(limit=2, before=4) == [(2, "Frage 1"), (3, "Antwort 1: -K1 pruefen.")]
    assert page(before=1) == [(0, "Frage 0")]

    answer = client.get(url, params={"limit": 1}, headers=headers).json()[0]
    assert answer["meta"]["referenced_tags"] == ["-K1"]
    assert answer["meta"]["part_kinds"] == {"-K1": "Schuetz/Relais"}
    assert [spot["page"] for spot in answer["meta"]["plan_spots"]] == [3]

    for bad in ({"limit": 0}, {"limit": 201}, {"before": -1}):
        assert client.get(url, params=bad, headers=headers).status_code == 422


# --- B2: fault-hits --------------------------------------------------------------------------------------------


def test_fault_hits_liefert_fehlerliste_erfahrung_und_stoerfaelle(client, world):
    response = client.get(
        f"/api/machines/{world['machine_id']}/fault-hits",
        params={"q": "Störung Motorschutz Förderband"},
        headers=_auth(world["tokens"][WS]),
    )
    assert response.status_code == 200, response.text
    hits = response.json()
    assert [f["code"] for f in hits["faults"]] == ["E-F2"]
    assert hits["faults"][0]["machine_id"] == world["machine_id"]
    assert [e["fault"]["code"] for e in hits["experience"]] == ["P1", "P2", "P3", "P4", "P5"]
    assert {e["machine_id"] for e in hits["experience"]} == {world["other_id"]}
    assert {e["machine_name"] for e in hits["experience"]} == {"Presse Test"}
    # nur erledigt, mit Befund, gleiche Quelle; offene und andere Quellen nicht
    assert [i["conversation_id"] for i in hits["incidents"]] == [world["conversations"]["found"]]
    incident = hits["incidents"][0]
    assert (incident["title"], incident["finding"]) == (
        "Band steht",
        "Motorschutz -F2 auf 3,5 A nachgestellt",
    )
    assert incident["updated_at"]


def test_fault_hits_ohne_treffer_und_ohne_fehlerliste_drei_leere_listen(client, world):
    headers = _auth(world["tokens"][WS])
    empty = {"faults": [], "experience": [], "incidents": []}

    def hits(machine_id: str, q: str):
        return client.get(
            f"/api/machines/{machine_id}/fault-hits", params={"q": q}, headers=headers
        )

    assert hits(world["machine_id"], "Quarkbrot").json() == empty
    assert hits(world["machine_id"], "").json() == empty
    # Maschine ohne Fehlerliste und ohne Quelle: Erfahrung anderer Maschinen gibt es trotzdem
    alone = hits(world["empty_id"], "Motorschutz").json()
    assert alone["faults"] == [] and alone["incidents"] == [] and len(alone["experience"]) == 5
    assert hits(world["empty_id"], "Quarkbrot").json() == empty
    assert hits("gibt-es-nicht", "Motorschutz").status_code == 404
    foreign = client.get(
        f"/api/machines/{world['machine_id']}/fault-hits",
        params={"q": "Motorschutz"},
        headers=_auth(world["tokens"][OTHER_WS]),
    )
    assert foreign.status_code == 404


# --- B3: meta fuer eine FB-01-Antwort --------------------------------------------------------------------------


def test_meta_einer_fb01_antwort_mit_k1(world):
    from app.api.answer_meta import build_meta
    from app.api.signal import graph_for_source

    # Graph einmal vorab bauen: build_meta wartet hoechstens SIGNAL_START_TIMEOUT_S darauf
    _in(WS, lambda session: graph_for_source(session, world["source_id"]))

    def meta(answer: str) -> dict:
        return _in(
            WS,
            lambda session: build_meta(
                session,
                answer=answer,
                citations=[],
                source_ids=[world["source_id"]],
                machine_id=world["machine_id"],
            ),
        )

    with_tag = meta("Prüfe -K1 im Hauptstromkreis.")
    assert with_tag["referenced_tags"] == ["-K1"]
    assert with_tag["part_kinds"] == {"-K1": "Schuetz/Relais"}
    assert with_tag["signal_start"] == "-K1"
    assert with_tag["plan_spots"] == [
        {
            "tag": "-K1",
            "document_id": with_tag["plan_spots"][0]["document_id"],
            "filename": PLAN.name,
            "page": 3,
            "sheet": 3,
            "title": SHEET3,
            "column": 4,
        }
    ]

    without = meta("Das Band steht, bitte den Motorschutz pruefen.")
    assert (without["part_kinds"], without["signal_start"], without["plan_spots"]) == ({}, None, [])
