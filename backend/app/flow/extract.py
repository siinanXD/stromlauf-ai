"""Extraktion des Maschinenablaufs: zwei Phasen, Cache, Trace. Kein Modellaufruf, wenn der Cache trifft.

Phase A (kleines Modell, parallel): A1 I/O-Liste, A2 Sensoren/Aktoren. Deterministisch zusammengefuehrt.
Phase B (starkes Modell): Schrittkette aus Funktionsbeschreibung, AWL und der I/O-Liste.
Layout: deterministisch aus den I/O-Punkten (assumption: true), ohne Modell.
"""

import hashlib
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic

from app.config import get_settings
from app.flow import prompts, schema, wire
from app.flow.sources import DocText, load_document, render
from app.flow.tracing import Trace, log, start_trace
from app.models import DocType
from app.pricing import cost_usd

logger = logging.getLogger("flow")

IO_DOC_TYPES = {DocType.PLC_SYMBOLS, DocType.MANUAL, DocType.TERMINAL_PLAN, DocType.OTHER, DocType.SCHEMATIC}
DEVICE_DOC_TYPES = {DocType.BOM, DocType.MANUAL, DocType.TERMINAL_PLAN, DocType.SCHEMATIC, DocType.OTHER}
STEP_DOC_TYPES = {DocType.MANUAL, DocType.PLC_PROGRAM, DocType.OTHER, DocType.SCHEMATIC}
MAX_TOKENS = 16000


def cache_key(docs: list[DocText], prompt_version: str = prompts.PROMPT_VERSION) -> str:
    """SHA-256 ueber die Datei-Hashes (sortiert) und die Prompt-Version."""
    digest = hashlib.sha256()
    for doc in sorted(docs, key=lambda d: d.file):
        digest.update(f"{doc.file}:{doc.sha256}\n".encode())
    digest.update(prompt_version.encode())
    return digest.hexdigest()


def cache_path(key: str) -> Path:
    directory = get_settings().flow_cache_dir
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{key}.json"


def _usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0)


def _parse(client: Any, trace: Trace, name: str, model: str, system: str, user: str, output_format, effort: str | None = None):
    """Ein Structured-Output-Aufruf mit Generation-Span, Tokens und Kosten."""
    kwargs: dict[str, Any] = {}
    if effort:
        kwargs["output_config"] = {"effort": effort}
    with trace.generation(name, model, prompts.PROMPT_VERSION, input_preview=user[:2000]) as record:
        response = client.messages.parse(
            model=model, max_tokens=MAX_TOKENS, system=system,
            messages=[{"role": "user", "content": user}], output_format=output_format, **kwargs,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError(f"{name}: Modell hat abgelehnt ({getattr(response.stop_details, 'category', None)})")
        if response.stop_reason == "max_tokens":
            raise RuntimeError(f"{name}: Antwort abgeschnitten (max_tokens={MAX_TOKENS})")
        record.input_tokens, record.output_tokens = _usage(response)
        record.cost_usd = cost_usd(model, record.input_tokens, record.output_tokens)
        return response.parsed_output, record


def _phase(name: str, model: str, record, cached: bool = False) -> schema.Phase:
    usage = schema.Usage(
        input_tokens=record.input_tokens if record else 0, output_tokens=record.output_tokens if record else 0,
        cost_usd=record.cost_usd if record else 0.0, latency_ms=record.latency_ms if record else 0,
    )
    return schema.Phase(name=name, model=model, usage=usage, cached=cached)


def _io_table(points: list[schema.IOPoint]) -> str:
    return "\n".join(
        f"{p.address} | {p.symbol or '-'} | {p.direction} | {p.kind} | {p.tag or '-'} | {p.description}" for p in points
    )


def extract_flow(
    paths: list[Path],
    machine: str | None = None,
    force: bool = False,
    client: Any = None,
    langfuse_client: Any = None,
    names: dict[Path, str] | None = None,
) -> schema.MachineFlow:
    """Ablauf aus den Dokumenten; aus dem Cache, wenn Dateien und Prompt-Version unveraendert sind.

    names: Anzeigename je Pfad (Uploads heissen auf der Platte <uuid>.pdf).
    """
    settings = get_settings()
    docs = [load_document(path, name=(names or {}).get(path)) for path in paths]
    key = cache_key(docs)
    target = cache_path(key)
    if target.exists() and not force:
        flow = schema.MachineFlow.model_validate_json(target.read_text(encoding="utf-8"))
        flow.meta.cached = True
        log("cache_hit", cache_key=key, files=[d.file for d in docs], trace_id=flow.meta.trace_id)
        return flow

    started = time.monotonic()
    client = client or anthropic.Anthropic(api_key=settings.anthropic_api_key)
    machine_name = machine or _guess_machine(docs)
    models = {"small": settings.flow_model_small, "strong": settings.flow_model_strong}

    with start_trace(
        "extract_flow", client=langfuse_client, machine=machine_name, files=[d.file for d in docs],
        cache_key=key, prompt_version=prompts.PROMPT_VERSION, models=models,
    ) as trace:
        with trace.span("phase_a", parallel=2):
            io_context = render(docs, IO_DOC_TYPES)
            device_context = render(docs, DEVICE_DOC_TYPES)
            with ThreadPoolExecutor(max_workers=2) as pool:
                io_future = pool.submit(
                    _parse, client, trace, "io_points", models["small"], prompts.IO_SYSTEM,
                    prompts.io_user(io_context), wire.WireIOList,
                )
                device_future = pool.submit(
                    _parse, client, trace, "sensors_actuators", models["small"], prompts.DEVICE_SYSTEM,
                    prompts.device_user(device_context), wire.WireDeviceList,
                )
                io_list, io_record = io_future.result()
                device_list, device_record = device_future.result()
            points = wire.merge_io(io_list.io_points, device_list.devices)

        with trace.span("phase_b", io_points=len(points)):
            step_context = render(docs, STEP_DOC_TYPES)
            flow_wire, steps_record = _parse(
                client, trace, "steps", models["strong"], prompts.STEPS_SYSTEM,
                prompts.steps_user(step_context, _io_table(points), machine_name), wire.WireFlow,
                effort=settings.flow_effort,
            )

        with trace.span("layout"):
            known = {p.address: p for p in points} | {p.symbol: p for p in points if p.symbol}
            steps = wire.to_steps(flow_wire, known)
            layout = wire.default_layout(points, flow_wire.machine or machine_name)

        phases = [
            _phase("io_points", models["small"], io_record),
            _phase("sensors_actuators", models["small"], device_record),
            _phase("steps", models["strong"], steps_record),
            _phase("layout", "deterministic", None),
        ]
        total = schema.Usage(
            input_tokens=sum(p.usage.input_tokens for p in phases),
            output_tokens=sum(p.usage.output_tokens for p in phases),
            cost_usd=round(sum(p.usage.cost_usd for p in phases), 6),
            latency_ms=int((time.monotonic() - started) * 1000),
        )
        flow = schema.MachineFlow(
            machine=flow_wire.machine or machine_name,
            summary=flow_wire.summary,
            io_points=points,
            steps=steps,
            layout=layout,
            open_questions=flow_wire.open_questions,
            meta=schema.Meta(
                prompt_version=prompts.PROMPT_VERSION,
                cache_key=key,
                document_sha256={d.file: d.sha256 for d in docs},
                trace_id=trace.trace_id,
                models=models,
                phases=phases,
                total=total,
                extracted_at=datetime.now(timezone.utc),
            ),
        )
        unresolved = flow.unresolved_refs()
        if unresolved:
            log("unresolved_refs", trace_id=trace.trace_id, refs=unresolved)
            flow.open_questions.append("Verweise ohne I/O-Punkt: " + ", ".join(unresolved))
        target.write_text(flow.model_dump_json(indent=2), encoding="utf-8")
        log(
            "extracted", trace_id=trace.trace_id, cache_key=key, io_points=len(points), steps=len(steps),
            cost_usd=total.cost_usd, latency_ms=total.latency_ms, over_budget=total.latency_ms > 30_000,
        )
    return flow


def _guess_machine(docs: list[DocText]) -> str:
    for doc in docs:
        for passage in doc.passages[:1]:
            first = passage.text.strip().splitlines()[:1]
            if first and len(first[0]) < 80:
                return first[0].lstrip("# ").strip()
    return Path(docs[0].file).stem if docs else "Maschine"


def to_json(flow: schema.MachineFlow) -> str:
    return json.dumps(flow.model_dump(mode="json"), indent=2, ensure_ascii=False)
