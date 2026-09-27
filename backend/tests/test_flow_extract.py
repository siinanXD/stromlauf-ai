"""Extraktions-Pipeline ohne Netz: Fake-Client, Cache, Parallelitaet, Trace-ID, Kosten, CLI."""

import json
import logging
import threading
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.flow import extract, prompts, schema, wire
from app.flow.sources import load_document, render
from app.flow.tracing import JsonFormatter, log, logger

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "foerderband"
FILES = [EXAMPLE / "06_Betriebsanleitung_FB-01.md", EXAMPLE / "05_Symboltabelle_FB-01.sdf", EXAMPLE / "04_SPS_Programm_FB-01.awl"]
SRC = {"file": "05_Symboltabelle_FB-01.sdf", "chunk": "Zeilen 1-20", "quote": "Taster Start, Schliesser"}

IO_ANSWER = wire.WireIOList(
    io_points=[
        wire.WireIO(address="E 0.0", symbol="Start", direction="DI", description="Taster -S1 Start", source=SRC, confidence=0.95),
        wire.WireIO(address="%I0.1", symbol="Stop", direction="DI", description="Taster -S2 Stop, Oeffner", active_state=0, source=SRC, confidence=0.9),
        wire.WireIO(address="A4.0", symbol="K1_Vorwaerts", direction="DO", description="Schuetz -K1 vorwaerts", source=SRC, confidence=0.97),
        wire.WireIO(address="A4.0", symbol="Doppelt", direction="DO", description="Duplikat", source=SRC, confidence=0.5),
    ]
)
DEVICE_ANSWER = wire.WireDeviceList(
    devices=[
        wire.WireDevice(tag="-S1", kind="operator", contact="NO", location="+FE1", description="Taster gruen", source=SRC, confidence=0.9),
        wire.WireDevice(tag="-S2", kind="operator", contact="NC", location="+FE1", description="Taster rot", address="E0.1", source=SRC, confidence=0.9),
        wire.WireDevice(tag="-K1", kind="actuator", location="+ST1", description="Schuetz", source=SRC, confidence=0.8),
    ]
)
STEP_ANSWER = wire.WireFlow(
    machine="Foerderband FB-01",
    summary="Start setzt -K1, Stop loescht.",
    steps=[
        wire.WireStep(id="S0", name="Grundstellung", initial=True, actions=[wire.WireAction(io="A 4.0", state=0)],
                      transitions=[wire.WireTransition(target="S1", conditions=[wire.WireCondition(io="Start", state=1, edge="rising")],
                                                       source={**SRC, "quote": " ".join(["wort"] * 20)}, confidence=1.4)],
                      source=SRC, confidence=0.9),
        wire.WireStep(id="S1", name="Band vorwaerts", actions=[wire.WireAction(io="A4.0", state=1), wire.WireAction(io="A9.9", state=1)],
                      transitions=[wire.WireTransition(target="S0", conditions=[wire.WireCondition(io="E0.1", state=0)], source=SRC, confidence=0.9)],
                      source=SRC, confidence=0.9),
    ],
    open_questions=["Rueckwaerts?"],
)


class FakeClient:
    """Ahmt anthropic.Anthropic().messages.parse nach; A-Aufrufe warten aufeinander (Parallelitaetsnachweis)."""

    def __init__(self, parallel_timeout: float = 5.0):
        self.calls: list[dict] = []
        self.started = threading.Barrier(2, timeout=parallel_timeout)
        self.messages = SimpleNamespace(parse=self.parse)

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        fmt = kwargs["output_format"]
        if fmt is wire.WireIOList:
            self.started.wait()
            parsed, tokens = IO_ANSWER, (1000, 200)
        elif fmt is wire.WireDeviceList:
            self.started.wait()
            parsed, tokens = DEVICE_ANSWER, (800, 100)
        else:
            parsed, tokens = STEP_ANSWER, (3000, 500)
        return SimpleNamespace(
            parsed_output=parsed, stop_reason="end_turn", stop_details=None,
            usage=SimpleNamespace(input_tokens=tokens[0], output_tokens=tokens[1]),
        )


@pytest.fixture
def settings(tmp_path, monkeypatch):
    values = Settings(data_dir=tmp_path, anthropic_api_key="test", flow_model_small="claude-haiku-4-5", flow_model_strong="claude-opus-5")
    monkeypatch.setattr(extract, "get_settings", lambda: values)
    return values


def test_sources_render_marks_every_passage():
    docs = [load_document(p) for p in FILES]
    assert [d.doc_type for d in docs] == ["manual", "plc_symbols", "plc_program"]
    assert all(len(d.sha256) == 64 for d in docs)
    text = render(docs, {"plc_program"})
    assert "[[04_SPS_Programm_FB-01.awl | FB 10" in text
    assert "05_Symboltabelle" not in text


def test_cache_key_depends_on_files_and_prompt_version():
    docs = [load_document(p) for p in FILES]
    key = extract.cache_key(docs)
    assert key == extract.cache_key(list(reversed(docs)))
    assert key != extract.cache_key(docs, prompt_version="other")
    assert key != extract.cache_key(docs[:2])


def test_extract_runs_phase_a_parallel_and_writes_cache(settings):
    client = FakeClient()
    flow = extract.extract_flow(FILES, client=client, langfuse_client=False)

    models = [(c["output_format"].__name__, c["model"]) for c in client.calls]
    assert sorted(models) == [("WireDeviceList", "claude-haiku-4-5"), ("WireFlow", "claude-opus-5"), ("WireIOList", "claude-haiku-4-5")]
    assert models[-1][0] == "WireFlow", "Phase B erst nach Phase A"
    steps_call = client.calls[-1]
    assert steps_call["output_config"] == {"effort": "medium"}
    assert "E0.0 | Start | DI | operator | -S1" in steps_call["messages"][0]["content"]

    assert [p.address for p in flow.io_points] == ["E0.0", "E0.1", "A4.0"]  # normalisiert, Duplikat weg
    by = flow.io_by_ref()
    assert by["E0.0"].tag == "-S1" and by["E0.0"].contact == "NO" and by["E0.0"].assumption is False
    assert by["E0.1"].contact == "NC" and by["E0.1"].active_state == 0
    assert by["A4.0"].kind == "actuator" and by["A4.0"].confidence == 0.8

    assert [s.id for s in flow.steps] == ["S0", "S1"]
    assert flow.steps[0].actions[0].io == "A4.0"  # "A 4.0" normalisiert
    transition = flow.steps[0].transitions[0]
    assert transition.confidence == 1.0 and len(transition.source.quote.split()) == 15
    assert "A9.9" in flow.open_questions[-1]
    assert all(e.assumption for e in flow.layout.elements) and len(flow.layout.elements) == 3

    meta = flow.meta
    assert meta.cached is False and meta.trace_id and len(meta.trace_id) == 32
    assert meta.prompt_version == prompts.PROMPT_VERSION
    assert meta.models == {"small": "claude-haiku-4-5", "strong": "claude-opus-5"}
    assert [p.name for p in meta.phases] == ["io_points", "sensors_actuators", "steps", "layout"]
    assert meta.total.input_tokens == 4800 and meta.total.output_tokens == 800
    assert meta.total.cost_usd == pytest.approx(0.0010 + 0.0010 + 0.0008 + 0.0005 + 0.015 + 0.0125)
    assert set(meta.document_sha256) == {p.name for p in FILES}

    cached_file = settings.flow_cache_dir / f"{meta.cache_key}.json"
    assert cached_file.exists()
    schema.MachineFlow.model_validate_json(cached_file.read_text(encoding="utf-8"))


def test_second_run_hits_cache_without_model_calls(settings):
    client = FakeClient()
    first = extract.extract_flow(FILES, client=client, langfuse_client=False)
    calls = len(client.calls)
    second = extract.extract_flow(FILES, client=client, langfuse_client=False)
    assert len(client.calls) == calls
    assert second.meta.cached is True and second.meta.cache_key == first.meta.cache_key
    assert second.meta.trace_id == first.meta.trace_id
    forced = extract.extract_flow(FILES, client=FakeClient(), langfuse_client=False, force=True)
    assert forced.meta.cached is False


def test_refusal_and_truncation_raise(settings):
    class Refusing(FakeClient):
        def parse(self, **kwargs):
            return SimpleNamespace(parsed_output=None, stop_reason="refusal", stop_details=SimpleNamespace(category="x"),
                                   usage=SimpleNamespace(input_tokens=1, output_tokens=0))

    with pytest.raises(RuntimeError, match="abgelehnt"):
        extract.extract_flow(FILES, client=Refusing(), langfuse_client=False)


class FakeLangfuse:
    """start_as_current_observation/get_current_trace_id/flush wie der echte Client."""

    def __init__(self):
        self.observations: list[dict] = []
        self.flushed = False

    @contextmanager
    def start_as_current_observation(self, **kwargs):
        record = {"kwargs": kwargs, "updates": []}
        self.observations.append(record)
        yield SimpleNamespace(update=lambda **u: record["updates"].append(u), end=lambda: None)

    def get_current_trace_id(self):
        return "trace-abc"

    def flush(self):
        self.flushed = True


def test_langfuse_trace_id_in_json_and_generation_usage(settings):
    langfuse = FakeLangfuse()
    flow = extract.extract_flow(FILES, client=FakeClient(), langfuse_client=langfuse)
    assert flow.meta.trace_id == "trace-abc"
    assert langfuse.flushed
    names = [o["kwargs"]["name"] for o in langfuse.observations]
    assert names[0] == "extract_flow" and {"phase_a", "phase_b", "layout", "io_points", "sensors_actuators", "steps"} <= set(names)
    steps = next(o for o in langfuse.observations if o["kwargs"]["name"] == "steps")
    assert steps["kwargs"]["as_type"] == "generation" and steps["kwargs"]["model"] == "claude-opus-5"
    assert steps["kwargs"]["version"] == prompts.PROMPT_VERSION
    usage = steps["updates"][-1]
    assert usage["usage_details"] == {"input": 3000, "output": 500}
    assert usage["cost_details"]["total"] == pytest.approx(0.0275)


def test_json_log_lines_carry_trace_id(capsys):
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        log("generation", trace_id="t1", model="m", cost_usd=0.01)
    finally:
        logger.removeHandler(handler)
    line = json.loads(capsys.readouterr().err.strip().splitlines()[-1])
    assert line["event"] == "generation" and line["trace_id"] == "t1" and line["cost_usd"] == 0.01


def test_cli_writes_file_and_reports_missing(settings, tmp_path, monkeypatch, capsys):
    from app.flow import cli

    original, client = extract.extract_flow, FakeClient()
    monkeypatch.setattr(extract, "extract_flow", lambda paths, **kw: original(paths, client=client, langfuse_client=False, **kw))
    out = tmp_path / "out" / "fb01.flow.json"
    assert cli.main([str(FILES[0]), "--awl", str(FILES[2]), "--extra", str(FILES[1]), "--out", str(out), "--quiet"]) == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["machine"] == "Foerderband FB-01" and "Trace" in capsys.readouterr().err
    assert cli.main([str(tmp_path / "fehlt.pdf"), "--quiet"]) == 2


def test_display_name_overrides_upload_filename(tmp_path):
    from types import SimpleNamespace as NS

    from app.api.flow import flow_documents

    stored = tmp_path / "0123abcd.sdf"
    stored.write_bytes(FILES[1].read_bytes())
    doc = load_document(stored, "plc_symbols", name="05_Symboltabelle_FB-01.sdf")
    assert doc.file == "05_Symboltabelle_FB-01.sdf" and doc.passages[0].file == doc.file
    assert extract.cache_key([doc]) == extract.cache_key([load_document(FILES[1])])

    docs = [
        NS(status="ready", doc_type="plc_symbols", filename="b.sdf"),
        NS(status="ready", doc_type="manual", filename="z.md"),
        NS(status="failed", doc_type="manual", filename="a.md"),
        NS(status="ready", doc_type="schematic", filename="plan.pdf"),
        NS(status="ready", doc_type="manual", filename="a.md"),
    ]
    assert [d.filename for d in flow_documents(docs)] == ["a.md", "z.md", "b.sdf"]
