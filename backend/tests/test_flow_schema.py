"""Ablauf-Schema: Datei aktuell, Beispiel gueltig, Belege und Schrittregeln greifen."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.flow.schema import MachineFlow, Meta, Source, json_schema

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))


def test_schema_file_matches_models():
    from flow_schema import TARGET, render

    assert TARGET.exists(), "python scripts/flow_schema.py --write"
    assert TARGET.read_text(encoding="utf-8") == render()
    schema = json_schema()
    assert schema["$schema"].endswith("2020-12/schema")
    assert {"io_points", "steps", "meta", "machine"} <= set(schema["required"])
    assert "Source" in schema["$defs"] and "IOPoint" in schema["$defs"] and "Step" in schema["$defs"]


def test_example_validates_and_resolves_all_refs():
    data = json.loads((REPO / "schemas" / "examples" / "foerderband_fb01.flow.json").read_text(encoding="utf-8"))
    flow = MachineFlow.model_validate(data)
    assert flow.machine == "Foerderband FB-01"
    assert len(flow.io_points) == 10 and len(flow.steps) == 4
    assert flow.unresolved_refs() == []
    assert flow.io_by_ref()["LS_Einlauf"].address == "E0.4"
    assert any(s.assumption for s in flow.steps) and any(t.assumption for s in flow.steps for t in s.transitions)
    assert all(e.assumption for e in flow.layout.elements)


def test_quote_limited_to_15_words():
    Source(file="a.pdf", quote=" ".join(["w"] * 15))
    with pytest.raises(ValidationError):
        Source(file="a.pdf", quote=" ".join(["w"] * 16))


def _meta() -> Meta:
    return Meta(prompt_version="t", cache_key="x", document_sha256={}, models={}, extracted_at=datetime.now(timezone.utc))


def _step(step_id: str, initial: bool, target: str | None = None) -> dict:
    src = {"file": "f", "quote": "q"}
    return {
        "id": step_id, "name": step_id, "initial": initial, "source": src, "confidence": 1.0,
        "transitions": [{"target": target, "source": src, "confidence": 1.0}] if target else [],
    }


def test_steps_need_exactly_one_initial_and_known_targets():
    MachineFlow(machine="m", io_points=[], steps=[_step("S0", True, "S1"), _step("S1", False)], meta=_meta())
    with pytest.raises(ValidationError, match="initial"):
        MachineFlow(machine="m", io_points=[], steps=[_step("S0", False)], meta=_meta())
    with pytest.raises(ValidationError, match="unbekannten Schritt"):
        MachineFlow(machine="m", io_points=[], steps=[_step("S0", True, "S9")], meta=_meta())
    with pytest.raises(ValidationError, match="eindeutig"):
        MachineFlow(machine="m", io_points=[], steps=[_step("S0", True), _step("S0", False)], meta=_meta())


def test_unresolved_refs_are_reported_not_rejected():
    flow = MachineFlow(
        machine="m", io_points=[], meta=_meta(),
        steps=[{**_step("S0", True), "actions": [{"io": "A9.9", "state": 1}]}],
    )
    assert flow.unresolved_refs() == ["A9.9"]


def test_extra_fields_are_rejected():
    with pytest.raises(ValidationError):
        Source(file="a", quote="b", seite=3)
