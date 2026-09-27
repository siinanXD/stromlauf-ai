"""Langfuse-Trace je Extraktion plus strukturierte JSON-Logs mit derselben Trace-ID.

Ohne LANGFUSE_PUBLIC_KEY/SECRET_KEY (oder ohne Paket) laeuft alles als No-op; die Pipeline
merkt den Unterschied nur an meta.trace_id = null.

Eigenes Modul, weil die Extraktion Spans, Tokens und Kosten selbst setzt (kein LangChain im
Spiel). Chat und Vision laufen ueber LangChain und nutzen den Callback aus `app/tracing.py`;
die Schluesselpruefung steht nur dort.
"""

import json
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("flow")


class JsonFormatter(logging.Formatter):
    """Eine JSON-Zeile je Eintrag; Felder aus record.extra landen flach im Objekt."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update(getattr(record, "fields", {}))
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging(level: int = logging.INFO) -> None:
    """Logger 'flow' schreibt JSON-Zeilen auf stderr (Handler nur einmal)."""
    if any(isinstance(h.formatter, JsonFormatter) for h in logger.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False


def log(event: str, **fields: Any) -> None:
    logger.info(event, extra={"fields": {"event": event, **fields}})


@dataclass
class GenerationRecord:
    name: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass
class Trace:
    """Ein Extraktionslauf. trace_id ist die Langfuse-ID oder eine lokale UUID."""

    trace_id: str
    name: str
    _client: Any = None
    _root: Any = None
    generations: list[GenerationRecord] = field(default_factory=list)

    @contextmanager
    def span(self, name: str, **metadata: Any) -> Iterator[None]:
        started = time.monotonic()
        log("span_start", trace_id=self.trace_id, span=name, **metadata)
        if self._client is None:
            yield
        else:
            with self._client.start_as_current_observation(name=name, as_type="span", metadata=metadata):
                yield
        log("span_end", trace_id=self.trace_id, span=name, latency_ms=int((time.monotonic() - started) * 1000))

    @contextmanager
    def generation(self, name: str, model: str, prompt_version: str, input_preview: str = "") -> Iterator[GenerationRecord]:
        """Ein Modellaufruf. Der Aufrufer fuellt record.input_tokens/output_tokens/cost_usd."""
        record = GenerationRecord(name=name, model=model)
        started = time.monotonic()
        if self._client is None:
            try:
                yield record
            finally:
                self._finish(record, started, prompt_version)
            return
        with self._client.start_as_current_observation(
            name=name, as_type="generation", model=model, input=input_preview, version=prompt_version
        ) as observation:
            try:
                yield record
            finally:
                self._finish(record, started, prompt_version)
                observation.update(
                    usage_details={"input": record.input_tokens, "output": record.output_tokens},
                    cost_details={"total": record.cost_usd},
                    metadata={"latency_ms": record.latency_ms, "prompt_version": prompt_version},
                )

    def _finish(self, record: GenerationRecord, started: float, prompt_version: str) -> None:
        record.latency_ms = int((time.monotonic() - started) * 1000)
        self.generations.append(record)
        log(
            "generation", trace_id=self.trace_id, generation=record.name, model=record.model,
            prompt_version=prompt_version, input_tokens=record.input_tokens, output_tokens=record.output_tokens,
            cost_usd=record.cost_usd, latency_ms=record.latency_ms,
        )

    def finish(self, output: dict | None = None) -> None:
        if self._root is not None:
            self._root.update(output=output)
            self._root.end()
        if self._client is not None:
            self._client.flush()


def _langfuse_client():
    """Client samt Schluessel- und Paketpruefung kommt aus app.tracing."""
    from app.tracing import langfuse_client

    return langfuse_client()


@contextmanager
def start_trace(name: str, client=None, **metadata: Any) -> Iterator[Trace]:
    """Trace oeffnen; client=None nimmt Langfuse aus den Settings, client=False erzwingt No-op."""
    if client is None:
        client = _langfuse_client()
    if not client:
        trace = Trace(trace_id=uuid.uuid4().hex, name=name)
        log("trace_start", trace_id=trace.trace_id, name=name, langfuse=False, **metadata)
        try:
            yield trace
        finally:
            trace.finish()
            log("trace_end", trace_id=trace.trace_id, name=name)
        return
    root = client.start_as_current_observation(name=name, as_type="span", metadata=metadata)
    observation = root.__enter__()
    trace = Trace(trace_id=client.get_current_trace_id() or uuid.uuid4().hex, name=name, _client=client, _root=None)
    log("trace_start", trace_id=trace.trace_id, name=name, langfuse=True, **metadata)
    try:
        yield trace
    finally:
        root.__exit__(None, None, None)
        observation.update(output={"generations": len(trace.generations)})
        client.flush()
        log("trace_end", trace_id=trace.trace_id, name=name)
