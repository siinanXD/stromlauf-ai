"""Abnahme-Nachweise (scripts/acceptance.py): Rechnung und Sammlung gegen eine gemockte API."""

import importlib.util
import json
import sys
from pathlib import Path

import httpx
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "acceptance.py"
_spec = importlib.util.spec_from_file_location("acceptance", SCRIPT)
acceptance = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = acceptance  # dataclasses schlagen das Modul ueber sys.modules nach
_spec.loader.exec_module(acceptance)

MACHINE_ID = "m-fb01"
SOURCE_ID = "s-fb01"

MAP = {
    "machine_id": MACHINE_ID,
    "source_id": SOURCE_ID,
    "part_count": 4,
    "connectors": [],
    "zones": [
        {"id": "+ST1", "code": "+ST1", "name": "Schaltschrank",
         "parts": [{"tag": "-K1", "label": "Hauptschuetz", "kind": "Schuetz", "source": "bom"},
                   {"tag": "-F2", "label": "Motorschutz", "kind": "Schutz", "source": "bom"}]},
        {"id": "+FE1", "code": "+FE1", "name": "Feld",
         "parts": [{"tag": "-M1", "label": "Motor", "kind": "Motor", "source": "bom"}]},
        {"id": "?", "code": "?", "name": "Ohne Einbauort",
         "parts": [{"tag": "-B7", "label": "", "kind": "Sensor", "source": "index"}]},
    ],
}
ESTIMATE = {
    "pages": 12, "photos": 1, "vision": True,
    "per_page_vision_cents": 2.0, "per_photo_cents": 1.0,
    "chat_per_answer_cents": 1.5, "total_cents": 25.0, "basis": {"vision.page": "list", "vision.cabinet": "list"},
    "models": {"vision": "v", "chat": "c"},
}
COSTS = {
    "machine_id": MACHINE_ID,
    "month": {"cents": 33.0, "calls": 13, "by_purpose": {}},
    "total": {"cents": 33.0, "calls": 13, "by_purpose": {
        "vision.page": {"cents": 30.0, "calls": 12},
        "vision.cabinet": {"cents": 3.0, "calls": 1},
    }},
    "workspace": {"month_cents": 33.0, "month_calls": 13, "cap_cents": None, "exceeded": False},
}


def lookup_all_but_b7(tag: str) -> dict:
    hits = [] if tag == "-B7" else [{"document_id": "d1", "filename": "01_Stromlaufplan_FB-01.pdf", "doc_type": "schematic",
                                     "page": 3, "section": "", "context": tag}]
    return {"tag": tag, "hits": hits, "bom_line": None}


def test_wait_healthy_misst_bis_zur_ersten_antwort():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json={"status": "ok"}) if calls["n"] >= 3 else httpx.Response(503)

    ticks = iter([0.0, 0.0, 2.0, 4.0])
    slept = []
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api") as client:
        seconds = acceptance.wait_healthy(client, timeout_s=60, sleep_s=2.0, clock=lambda: next(ticks), sleep=slept.append)
    assert calls["n"] == 3
    assert seconds == pytest.approx(4.0)
    assert slept == [2.0, 2.0]


def test_wait_healthy_bricht_nach_timeout_ab():
    ticks = iter([0.0, 0.0, 30.0, 61.0])
    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)), base_url="http://api") as client:
        with pytest.raises(RuntimeError, match="nicht erreichbar"):
            acceptance.wait_healthy(client, timeout_s=60, sleep_s=1.0, clock=lambda: next(ticks), sleep=lambda s: None)


def test_wait_healthy_zaehlt_verbindungsfehler_als_noch_nicht_da():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("Verbindung abgelehnt", request=request)
        return httpx.Response(200, json={"status": "ok"})

    ticks = iter([0.0, 0.0, 1.0, 1.0])
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://api") as client:
        assert acceptance.wait_healthy(client, timeout_s=10, sleep_s=1.0, clock=lambda: next(ticks), sleep=lambda s: None) == 1.0


def test_find_machine_exakt_dann_enthalten():
    machines = [{"id": "a", "name": "Foerderband FB-01"}, {"id": "b", "name": "Presse P-02"}]
    assert acceptance.find_machine(machines, "Foerderband FB-01")["id"] == "a"
    assert acceptance.find_machine(machines, "fb-01")["id"] == "a"
    assert acceptance.find_machine(machines, "Umroller") is None


def test_map_evidence_zaehlt_zonen_ohne_unbekannt_und_prueft_fundstellen():
    evidence = acceptance.map_evidence(MAP, lookup_all_but_b7)
    assert evidence["zones"] == 2
    assert evidence["zone_codes"] == ["+ST1", "+FE1"]
    assert evidence["parts"] == 4
    assert evidence["parts_by_source"] == {"bom": 3, "index": 1}
    assert evidence["parts_without_hit"] == ["-B7"]
    assert evidence["connectors"] == 0
    assert evidence["cited_share"] == pytest.approx(0.75)


def test_map_evidence_zaehlt_leitungen_als_verbinder_nicht_als_teile():
    with_cable = {**MAP, "connectors": [{"source": "+ST1", "target": "+FE1", "label": "-W3"}]}
    evidence = acceptance.map_evidence(with_cable, lookup_all_but_b7)
    assert evidence["connectors"] == 1 and evidence["parts"] == 4
    checks = {c["id"]: c for c in acceptance.evaluate(_evidence(map={**evidence, "zones": 2, "zone_codes": ["+ST1", "+FE1"]}), acceptance.Thresholds())}
    assert "1 Leitungen als Verbinder" in checks["teile"]["note"]


def test_map_evidence_fragt_jedes_dokumentierte_kennzeichen_nur_einmal():
    asked = []
    duplicated = {**MAP, "zones": MAP["zones"] + [{"id": "+X", "code": "+X", "name": "Doppelt", "parts": MAP["zones"][0]["parts"]}]}

    def lookup(tag: str) -> dict:
        asked.append(tag)
        return lookup_all_but_b7(tag)

    acceptance.map_evidence(duplicated, lookup)
    assert sorted(asked) == ["-B7", "-F2", "-K1", "-M1"]


def test_compare_estimate_je_zweck_mit_toleranz():
    rows = acceptance.compare_estimate(ESTIMATE, COSTS, pages=12, photos=1, tolerance=0.5)
    by = {r["purpose"]: r for r in rows}
    assert by["vision.page"] == {"purpose": "vision.page", "estimated_cents": 24.0, "actual_cents": 30.0, "calls": 12,
                                 "deviation": pytest.approx(0.25), "within": True}
    assert by["vision.cabinet"]["deviation"] == pytest.approx(2.0)
    assert by["vision.cabinet"]["within"] is False
    assert set(by) == {"vision.page", "vision.cabinet"}


def test_compare_estimate_ohne_kostenbuch_eintraege():
    rows = acceptance.compare_estimate(ESTIMATE, {"total": {"by_purpose": {}}}, pages=12, photos=1, tolerance=0.5)
    assert all(r["within"] is None and r["actual_cents"] == 0.0 for r in rows)


def _evidence(**overrides) -> dict:
    base = {
        "machine": {"id": MACHINE_ID, "name": "Foerderband FB-01"},
        "cold_start_s": 3.2,
        "ingest_s": None,
        "documents": {"count": 6, "ready": 6, "pages": 12},
        "map": {"zones": 3, "zone_codes": ["+ST1", "+FE1", "+BP1"], "parts": 25, "parts_by_source": {"bom": 25},
                "parts_without_hit": [], "cited_share": 1.0},
        "hotspots": 14,
        "ledger": {"total_cents": 0.0, "total_calls": 0, "month_cents": 0.0, "month_calls": 0, "by_purpose": {}},
        "estimate": {"rows": [{"purpose": "vision.page", "estimated_cents": 24.0, "actual_cents": 0.0, "calls": 0,
                               "deviation": None, "within": None}], "pages": 12, "photos": 1},
    }
    base.update(overrides)
    return base


def test_evaluate_prueft_schwellen_und_markiert_ungemessenes():
    checks = {c["id"]: c for c in acceptance.evaluate(_evidence(), acceptance.Thresholds())}
    assert checks["zonen"]["ok"] is False and checks["zonen"]["value"] == 3
    assert checks["teile"]["ok"] is True
    assert checks["fundstellen"]["ok"] is True
    assert checks["ingestion"]["ok"] is None
    assert checks["schaetzung"]["ok"] is None
    assert checks["kostenbuch"]["ok"] is None
    assert checks["hotspots"]["ok"] is True
    assert checks["kaltstart"]["ok"] is None and checks["kaltstart"]["value"] == 3.2


def test_evaluate_ingestion_und_schaetzung_gemessen():
    measured = _evidence(
        ingest_s=17 * 60,
        ledger={"total_cents": 33.0, "total_calls": 13, "month_cents": 33.0, "month_calls": 13, "by_purpose": {}},
        estimate={"rows": [{"purpose": "vision.page", "estimated_cents": 24.0, "actual_cents": 30.0, "calls": 12,
                            "deviation": 0.25, "within": True},
                           {"purpose": "vision.cabinet", "estimated_cents": 1.0, "actual_cents": 3.0, "calls": 1,
                            "deviation": 2.0, "within": False}], "pages": 12, "photos": 1},
    )
    checks = {c["id"]: c for c in acceptance.evaluate(measured, acceptance.Thresholds())}
    assert checks["ingestion"]["ok"] is False
    assert checks["schaetzung"]["ok"] is False
    assert checks["kostenbuch"]["ok"] is True
    assert acceptance.failed(acceptance.evaluate(measured, acceptance.Thresholds())) == ["ingestion", "zonen", "schaetzung"]


def test_render_markdown_zeigt_stand_je_pruefung():
    evidence = _evidence()
    text = acceptance.render_markdown(evidence, acceptance.evaluate(evidence, acceptance.Thresholds()))
    assert "| Pruefung | Wert | Schwelle | Stand |" in text
    assert "3 Baugruppen" in text and "FEHLT" in text
    assert "25 Teile" in text and "ok" in text
    assert "n/a" in text
    assert "Foerderband FB-01" in text


def _mock_api(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if request.method != "GET":
        return httpx.Response(405, json={"detail": f"kein Schreibzugriff erwartet: {request.method} {path}"})
    if path == "/api/health":
        return httpx.Response(200, json={"status": "ok"})
    if path == "/api/machines":
        return httpx.Response(200, json=[{"id": MACHINE_ID, "name": "Foerderband FB-01", "source_id": SOURCE_ID},
                                         {"id": "m-2", "name": "Presse", "source_id": None}])
    if path == f"/api/machines/{MACHINE_ID}":
        return httpx.Response(200, json={"id": MACHINE_ID, "name": "Foerderband FB-01", "source_id": SOURCE_ID,
                                         "cabinets": [{"id": "c1", "hotspots": [{"id": f"h{i}"} for i in range(14)]}]})
    if path == f"/api/sources/{SOURCE_ID}/documents":
        return httpx.Response(200, json=[{"id": "d1", "filename": "01_Stromlaufplan_FB-01.pdf", "status": "ready", "page_count": 12},
                                         {"id": "d2", "filename": "02_Stueckliste_FB-01.xlsx", "status": "ready", "page_count": None}])
    if path == "/api/machines/estimate":
        assert request.url.params["pages"] == "12" and request.url.params["photos"] == "1"
        return httpx.Response(200, json=ESTIMATE)
    if path == f"/api/machines/{MACHINE_ID}/map":
        return httpx.Response(200, json=MAP)
    if path.startswith(f"/api/machines/{MACHINE_ID}/tags/"):
        return httpx.Response(200, json=lookup_all_but_b7(path.rsplit("/", 1)[-1]))
    if path == f"/api/machines/{MACHINE_ID}/costs":
        return httpx.Response(200, json=COSTS)
    return httpx.Response(404, json={"detail": f"nicht gemockt: {path}"})


def test_collect_sammelt_alle_nachweise_ohne_schreibzugriff(tmp_path: Path):
    with httpx.Client(transport=httpx.MockTransport(_mock_api), base_url="http://api") as client:
        evidence = acceptance.collect(client, machine_name="Foerderband FB-01", load=False, health_timeout_s=5)
    assert evidence["machine"]["id"] == MACHINE_ID
    assert evidence["documents"] == {"count": 2, "ready": 2, "pages": 12}
    assert evidence["hotspots"] == 14
    assert evidence["map"]["zones"] == 2 and evidence["map"]["parts"] == 4
    assert evidence["ledger"]["total_calls"] == 13
    assert {r["purpose"] for r in evidence["estimate"]["rows"]} == {"vision.page", "vision.cabinet"}
    assert evidence["ingest_s"] is None
    assert evidence["cold_start_s"] >= 0

    written = acceptance.write_results(evidence, acceptance.evaluate(evidence, acceptance.Thresholds()), tmp_path, stamp="t")
    assert json.loads((tmp_path / "acceptance_t.json").read_text(encoding="utf-8"))["evidence"]["hotspots"] == 14
    assert "| Pruefung |" in (tmp_path / "acceptance_t.md").read_text(encoding="utf-8")
    assert written == [tmp_path / "acceptance_t.json", tmp_path / "acceptance_t.md"]


def test_collect_meldet_fehlende_maschine():
    with httpx.Client(transport=httpx.MockTransport(_mock_api), base_url="http://api") as client:
        with pytest.raises(SystemExit, match="Umroller"):
            acceptance.collect(client, machine_name="Umroller", load=False, health_timeout_s=5)
