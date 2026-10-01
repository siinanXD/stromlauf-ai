"""MCP-Server ohne Netz: Stromlauf-API als httpx.MockTransport."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

from stromlauf_mcp.client import StromlaufClient
from stromlauf_mcp.core import resolve, truncate
from stromlauf_mcp.server import TOOL_NAMES, build_server

SITE = {
    "halls": [
        {"id": "h1", "name": "Verarbeitung", "kind": "production", "description": "", "x": 0, "y": 0, "w": 1, "h": 1,
         "machine_count": 3, "fault_count": 0, "open_diagnoses": 1, "lines": ["L1 Toilettenpapier"], "docks": 0,
         "machines": [
             {"id": "m1", "name": "L1-UR Umroller Toilettenpapier", "machine_type": "main", "pos_x": 0, "pos_y": 0, "line": "L1 Toilettenpapier"},
             {"id": "m2", "name": "L1-PAL Palettierer", "machine_type": "robot", "pos_x": 0, "pos_y": 0, "line": "L1 Toilettenpapier"},
             {"id": "m3", "name": "L2-PAL Palettierer", "machine_type": "robot", "pos_x": 0, "pos_y": 0, "line": "L2 Küchenrolle"},
         ]},
        {"id": "h2", "name": "Halle 1 (Beispiel)", "kind": "generic", "description": "", "x": 0, "y": 0, "w": 1, "h": 1,
         "machine_count": 1, "fault_count": 3, "open_diagnoses": 0, "lines": [], "docks": 0,
         "machines": [{"id": "fb", "name": "Foerderband FB-01", "machine_type": "conveyor", "pos_x": 0, "pos_y": 0, "line": ""}]},
    ],
    "flows": [{"id": "f1", "from_hall_id": "h2", "to_hall_id": "h1", "label": "Rollen"}],
}
MACHINE = {"id": "fb", "hall_id": "h2", "name": "Foerderband FB-01", "machine_type": "conveyor", "description": "",
           "source_id": "src1", "source_name": "Foerderband FB-01", "document_count": 6, "fault_count": 1,
           "cabinet_count": 0, "line": "", "key_figure": "", "hall_name": "Halle 1 (Beispiel)",
           "faults": [{"id": "x", "machine_id": "fb", "code": "F01", "symptom": "Band steht", "cause": "-F2 ausgelöst",
                       "fix": "-F2 prüfen", "doc_ref": "Blatt 3", "tags": ["-F2"]}], "cabinets": []}
ARTICLES = [{"id": "a1", "code": "TP-3L-8x150", "name": "Toilettenpapier 3-lagig, 8 × 150 Blatt", "unit_name": "Paket",
             "units_per_pallet": 84, "line": "L1 Toilettenpapier", "paper_kg_per_unit": 0.727,
             "routing": [{"machine_name": "L1-UR", "rate": 35, "rate_unit": "unit_min"}], "bom": []}]
CALC = {"ready_at": "2026-09-28T17:06", "meets_due": True, "days_delta": 4, "received_at": "x", "due_date": "y",
        "summary": {"units": 10000, "pallets": 120, "trucks": 4, "paper_t": 7.27, "line_minutes": 305.7,
                    "bottleneck": "L1-UR", "lead_minutes": 100},
        "stations": [{"key": "ship", "label": "Verladung", "group": "Versand", "start": "a", "end": "b",
                      "work_minutes": 45.0, "calendar": "shipping", "basis": "4 LKW", "bottleneck": None,
                      "machines": [], "position": None}],
        "closed": {"office": [["a", "b"]] * 50},
        "positions": [], "materials": [{"code": "PALETTE", "name": "Europalette", "unit": "Stk", "qty": 120.0,
                                        "level": 0, "parent": None, "basis": "1 je Palette × 120", "price": 11,
                                        "price_source": "Richtwert", "cost": 1320.0, "made": False}],
        "costs": {"positions": [{"article": "TP", "units": 10000, "unit_name": "Paket", "material": 1.0,
                                 "production": 2.0, "office": 3.0, "shipping": 4.0, "total": 10.0, "per_unit": 0.001}],
                  "total": {"material": 1.0, "production": 2.0, "office": 3.0, "shipping": 4.0, "total": 10.0},
                  "office_minutes": 165, "trucks": 4},
        "warnings": []}


class Backend:
    """Antwortet wie die Stromlauf-API und merkt sich die Anfragen."""

    def __init__(self):
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/site":
            return httpx.Response(200, json=SITE)
        if path == "/api/machines/fb":
            return httpx.Response(200, json=MACHINE)
        if path == "/api/machines/m1":  # Maschine ohne Doku
            return httpx.Response(200, json={**MACHINE, "id": "m1", "name": "L1-UR Umroller Toilettenpapier", "source_id": None})
        if path in {"/api/machines/fb/specs", "/api/machines/fb/diagnoses"}:
            return httpx.Response(200, json=[])
        if path == "/api/articles":
            return httpx.Response(200, json=ARTICLES)
        if path == "/api/calc":
            return httpx.Response(200, json=CALC)
        if path == "/api/signal-path":
            return httpx.Response(200, json={"start": "-S1", "schematic": None, "edges": [{"source": "-S1", "target": "E0.0"}],
                                             "nodes": [{"id": "-S1", "kind": "device", "label": "Start", "ref": "/4.6", "detail": "", "level": 0},
                                                       {"id": "E0.0", "kind": "address", "label": "", "ref": "", "detail": "", "level": 1}]})
        if path == "/api/tags/search":
            return httpx.Response(200, json=[])
        if path == "/api/search":
            return httpx.Response(200, json={"mode": request.url.params["mode"], "text": "Treffer", "refs": []})
        return httpx.Response(404, json={"detail": "nicht gefunden"})


@pytest.fixture
def backend():
    return Backend()


@pytest.fixture
def server(backend):
    client = StromlaufClient("http://stromlauf.test", transport=httpx.MockTransport(backend))
    return build_server(client, "http://app.test")


def tool(server, name):
    return server._tool_manager.get_tool(name).fn


def test_all_tools_are_listed_and_read_only(server):
    tools = asyncio.run(server.list_tools())
    assert sorted(t.name for t in tools) == sorted(TOOL_NAMES)
    assert len(TOOL_NAMES) == 9
    assert all(t.annotations and t.annotations.read_only_hint for t in tools)
    assert all(t.description for t in tools)


def test_resolve_by_exact_name_prefix_and_ambiguity():
    items = [{"id": "1", "name": "L1-PAL Palettierer"}, {"id": "2", "name": "L2-PAL Palettierer"}]
    assert resolve(items, "l1-pal", "Maschine")["id"] == "1"
    assert resolve(items, "2", "Maschine")["id"] == "2"
    with pytest.raises(ToolError, match="mehrdeutig"):
        resolve(items, "Palettierer", "Maschine")
    with pytest.raises(ToolError, match="nicht gefunden"):
        resolve(items, "Presse", "Maschine")


def test_signal_path_uses_the_source_of_the_machine(server, backend):
    result = tool(server, "signal_path")(tag="-S1", machine="FB-01")
    request = backend.requests[-1]
    assert request.url.path == "/api/signal-path" and request.url.params["source_id"] == "src1"
    assert result["start"] == "-S1" and result["consequences"][0]["id"] == "E0.0"


def test_search_documents_is_scoped_to_the_machine(server, backend):
    tool(server, "search_documents")(query="Not-Halt", machine="Foerderband")
    params = backend.requests[-1].url.params
    assert params["mode"] == "semantic" and params["source_id"] == "src1"
    tool(server, "search_documents")(query="3RT2016", exact=True)
    params = backend.requests[-1].url.params
    assert params["mode"] == "keyword" and "source_id" not in params


def test_calculate_order_resolves_article_codes_and_compacts(server, backend):
    result = tool(server, "calculate_order")(positions=[{"article": "tp-3l", "quantity": 10000}], due_date="2026-10-02")
    body = backend.requests[-1].read().decode()
    assert '"article_id":"a1"' in body.replace(" ", "")
    assert "closed" not in result
    assert result["ready_at"] == "2026-09-28T17:06"
    assert result["stations"][0] == {"label": "Verladung", "start": "a", "end": "b", "minutes": 45, "basis": "4 LKW"}
    assert result["url"] == "http://app.test/planung"


def test_machine_details_include_faults_and_link(server):
    result = tool(server, "machine_details")(machine="FB-01")
    assert result["faults"][0]["code"] == "F01"
    assert result["url"] == "http://app.test/werk/maschine/fb"


def test_ambiguous_machine_names_are_reported(server):
    with pytest.raises(ToolError, match="L1-PAL"):
        tool(server, "machine_details")(machine="Palettierer")


def test_unreachable_backend_gives_a_start_hint():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    client = StromlaufClient("http://stromlauf.test", transport=httpx.MockTransport(refuse))
    with pytest.raises(ToolError, match="nicht erreichbar"):
        tool(build_server(client, "http://app.test"), "site_overview")()


def test_backend_errors_are_passed_as_text(server):
    with pytest.raises(ToolError, match="404: nicht gefunden"):
        tool(server, "machine_details")(machine="L2-PAL")  # Mock kennt diese Maschine nicht


# --- Befunde aus dem Abschluss-Review ---------------------------------------------------------


def test_ids_only_match_exactly_never_by_prefix():
    items = [{"id": "1a2b3c", "name": "Foerderband FB-01"}, {"id": "9f8e7d", "name": "L1-UR Umroller"}]
    assert resolve(items, "1a2b3c", "Maschine")["name"] == "Foerderband FB-01"
    with pytest.raises(ToolError, match="nicht gefunden"):
        resolve(items, "1a2", "Maschine")  # Anfang einer ID, kommt in keinem Namen vor


def test_empty_reference_and_long_candidate_lists():
    items = [{"id": str(i), "name": f"Palettierer {i}", "hall": "Verarbeitung"} for i in range(12)]
    with pytest.raises(ToolError, match="fehlt"):
        resolve(items, "  ", "Maschine")
    with pytest.raises(ToolError, match=r"Palettierer 0 \(Verarbeitung\).*und 4 weitere"):
        resolve(items, "Palettierer", "Maschine")


def test_timeout_is_not_reported_as_backend_down():
    def slow(request):
        raise httpx.ReadTimeout("timeout", request=request)

    client = StromlaufClient("http://stromlauf.test", transport=httpx.MockTransport(slow))
    with pytest.raises(ToolError, match="antwortet nicht"):
        tool(build_server(client, "http://app.test"), "site_overview")()


def test_validation_errors_name_the_field(backend):
    def invalid(request):
        return httpx.Response(422, json={"detail": [{"loc": ["body", "received_at"], "msg": "Input should be a valid datetime"}]})

    client = StromlaufClient("http://stromlauf.test", transport=httpx.MockTransport(invalid))
    with pytest.raises(ToolError, match="received_at: Input should be a valid datetime"):
        client.post("/api/calc", {})


def test_missing_signal_path_names_the_reason_sentence(backend):
    """Der Signalweg antwortet mit einem 404 samt Grund und Satz (Stoerfall-Arbeitsflaeche); das Werkzeug nennt den Satz."""

    def missing(request):
        detail = {"reason": "unknown_tag", "message": "-Q9 kommt im Signalweg nicht vor."}
        return httpx.Response(404, json={"detail": detail})

    client = StromlaufClient("http://stromlauf.test", transport=httpx.MockTransport(missing))
    with pytest.raises(ToolError, match="404: -Q9 kommt im Signalweg nicht vor"):
        client.get("/api/signal-path", tag="-Q9", source_id="src1")


def test_search_tags_without_hits_says_so(server):
    result = tool(server, "search_tags")(query="-Q99")
    assert result["hits"] == [] and "Keine" in result["note"]


def test_signal_path_link_encodes_the_tag(server):
    result = tool(server, "signal_path")(tag="=A1+S1-K12", machine="FB-01")
    assert "tag=%3DA1%2BS1-K12" in result["url"]


def test_machine_without_documentation_gets_a_hint(server):
    with pytest.raises(ToolError, match="keine Dokumentation"):
        tool(server, "signal_path")(tag="-S1", machine="L1-UR")


def test_truncation_keeps_whole_chunks():
    text = "\n\n".join(f"### Dokument {i}\n" + "x" * 900 for i in range(20))
    cut = truncate(text, 3000)
    body = cut.split("\n… ")[0]
    assert body.endswith("x") and body.count("### ") == 3
    assert "gekürzt" in cut


def test_readme_desktop_config_is_valid_json():
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
    block = readme.split("claude_desktop_config.json")[1].split("```json")[1].split("```")[0]
    assert json.loads(block)["mcpServers"]["stromlauf"]["args"][0].endswith("mcp_server.py")


def test_search_endpoint_rejects_overlong_queries():
    from fastapi import HTTPException

    from app.api.search import search

    with pytest.raises(HTTPException):
        search(q="x" * 201)
