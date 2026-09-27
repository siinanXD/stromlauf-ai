"""Vergleich gegen Gold: Adresspaarung, Feldbewertung nur bei gesetztem Gold, Schritt-Toleranz, Vorlage."""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.flow.evaluate import compare, is_template
from app.flow.schema import IOPoint, MachineFlow, Meta, Source, Step

REPO = Path(__file__).resolve().parents[2]
SRC = Source(file="f", quote="q")


def _meta() -> Meta:
    return Meta(prompt_version="t", cache_key="k", document_sha256={}, models={}, extracted_at=datetime.now(timezone.utc))


def io(address, direction="DI", kind="sensor", symbol="", contact=None, tag="", assumption=False, confidence=0.9):
    return IOPoint(address=address, direction=direction, kind=kind, symbol=symbol, contact=contact, tag=tag,
                   source=SRC, confidence=confidence, assumption=assumption)


def step(step_id, name, initial=False):
    return Step(id=step_id, name=name, initial=initial, source=SRC, confidence=0.9)


def flow(points, steps):
    return MachineFlow(machine="m", io_points=points, steps=steps, meta=_meta())


def test_io_recall_precision_and_field_scores():
    gold = flow([io("E0.0", symbol="Start", kind="operator", contact="NO", tag="-S1"), io("E0.1", symbol="Stop"), io("A4.0", "DO", "actuator")],
                [step("S0", "Grundstellung", True), step("S1", "Band vorwaerts")])
    pred = flow([io("E 0.0", symbol="start", kind="operator", contact="NC", tag="-S1"), io("A4.0", "DO", "sensor"), io("A4.1", "DO", "actuator")],
                [step("S0", "Grundstellung", True), step("S1", "Band vorwärts"), step("S2", "Stoerung")])
    result = compare(gold, pred)
    assert result["io"]["matched"] == 2 and result["io"]["missing"] == ["E0.1"] and result["io"]["extra"] == ["A4.1"]
    assert result["io"]["recall"] == 0.667 and result["io"]["precision"] == 0.667
    # symbol: Start/start und Stop fehlt -> 1/1 bewertet (E0.1 nicht gepaart); contact nur bei E0.0 im Gold: NO vs NC -> 0/1
    assert result["io"]["fields"] == {"contact": 0.0, "direction": 1.0, "kind": 0.5, "symbol": 1.0, "tag": 1.0}
    assert result["steps"]["delta"] == 1 and result["steps"]["count_ok"] is True
    assert result["steps"]["names_recall"] == 0.5


def test_step_tolerance_and_evidence_summary():
    gold = flow([], [step(f"S{i}", f"Schritt {i}", i == 0) for i in range(8)])
    pred = flow([io("E0.0", assumption=True, confidence=0.5)], [step("S0", "x", True), step("S1", "y")])
    result = compare(gold, pred)
    assert result["steps"]["count_ok"] is False  # 2 statt 8, Toleranz 2
    assert result["evidence"] == {"objects": 3, "assumptions": 1, "assumption_share": 0.333, "mean_confidence": 0.767, "unresolved_refs": []}
    assert result["io"]["recall"] is None and result["io"]["precision"] == 0.0


def test_gold_template_validates_and_is_marked():
    data = json.loads((REPO / "testdata" / "festo" / "gold.flow.json").read_text(encoding="utf-8"))
    gold = MachineFlow.model_validate(data)
    assert is_template(gold)
    assert gold.unresolved_refs() == []
    assert not is_template(flow([], []))
