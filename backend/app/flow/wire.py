"""Modelle fuer die Modellantwort (Structured Output) und ihre Umsetzung ins Schema.

Getrennt von schema.py, weil Structured Outputs keine Wertebereiche (ge/le) und keine Validatoren
kennen: das Modell liefert rohe Werte, hier werden sie geklemmt, Zitate auf 15 Woerter gekuerzt,
Adressen normalisiert.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.flow import schema
from app.ingestion.tags import normalize_tag


class WireSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str
    page: int | None = None
    chunk: str | None = None
    quote: str


class WireIO(BaseModel):
    """Phase A1: Ein-/Ausgang aus Symboltabelle, I/O-Liste oder Belegungstabelle."""

    model_config = ConfigDict(extra="forbid")
    address: str
    symbol: str = ""
    direction: Literal["DI", "DO", "AI", "AO"]
    description: str = ""
    active_state: Literal[0, 1] = 1
    source: WireSource
    confidence: float
    assumption: bool = False


class WireIOList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    io_points: list[WireIO]


class WireDevice(BaseModel):
    """Phase A2: Sensor, Aktor, Bedienelement oder Sicherheitsgeraet mit BMK."""

    model_config = ConfigDict(extra="forbid")
    tag: str
    kind: Literal["sensor", "actuator", "operator", "safety", "other"]
    contact: Literal["NC", "NO"] | None = None
    location: str = ""
    description: str = ""
    address: str = ""
    source: WireSource
    confidence: float
    assumption: bool = False


class WireDeviceList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    devices: list[WireDevice]


class WireAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    io: str
    state: Literal[0, 1]
    note: str = ""


class WireCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    io: str
    state: Literal[0, 1]
    edge: Literal["rising", "falling"] | None = None


class WireTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str
    conditions: list[WireCondition] = []
    timer_s: float | None = None
    expression: str = ""
    source: WireSource
    confidence: float
    assumption: bool = False


class WireStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    initial: bool = False
    actions: list[WireAction] = []
    transitions: list[WireTransition] = []
    source: WireSource
    confidence: float
    assumption: bool = False


class WireFlow(BaseModel):
    """Phase B: Schrittkette."""

    model_config = ConfigDict(extra="forbid")
    machine: str
    summary: str
    steps: list[WireStep]
    open_questions: list[str] = []


def _clamp(value: float) -> float:
    return round(min(1.0, max(0.0, float(value))), 2)


def to_source(wire: WireSource) -> schema.Source:
    words = wire.quote.split()
    quote = " ".join(words[: schema.MAX_QUOTE_WORDS])
    return schema.Source(file=wire.file, page=wire.page if wire.page and wire.page >= 1 else None, chunk=wire.chunk, quote=quote)


def merge_io(io_list: list[WireIO], devices: list[WireDevice]) -> list[schema.IOPoint]:
    """A1 und A2 deterministisch zusammenfuehren: Geraet zur Adresse ueber address oder BMK im Beschreibungstext."""
    by_address: dict[str, WireDevice] = {}
    by_tag: dict[str, WireDevice] = {}
    for device in devices:
        tag = normalize_tag(device.tag) if device.tag else ""
        if device.address:
            by_address.setdefault(normalize_tag(device.address), device)
        if tag:
            by_tag.setdefault(tag, device)

    points: list[schema.IOPoint] = []
    seen: set[str] = set()
    for io in io_list:
        address = normalize_tag(io.address)
        if address in seen:
            continue
        seen.add(address)
        device = by_address.get(address)
        if device is None:
            haystack = f"{io.description} {io.symbol}"
            device = next((d for t, d in by_tag.items() if t in haystack), None)
        kind = device.kind if device else ("actuator" if io.direction in ("DO", "AO") else "sensor")
        points.append(
            schema.IOPoint(
                address=address,
                symbol=io.symbol,
                direction=io.direction,
                kind=kind,
                contact=device.contact if device else None,
                tag=normalize_tag(device.tag) if device and device.tag else "",
                location=device.location if device else "",
                description=io.description or (device.description if device else ""),
                active_state=io.active_state,
                source=to_source(io.source),
                confidence=_clamp(io.confidence if device is None else min(io.confidence, device.confidence)),
                assumption=io.assumption or (device is None),
            )
        )
    return points


def to_steps(flow: WireFlow, known: dict[str, schema.IOPoint]) -> list[schema.Step]:
    """Schritte ins Schema; Verweise auf Adressen normalisieren, unbekannte bleiben stehen (Warnung spaeter)."""

    def ref(value: str) -> str:
        return value if value in known else (normalize_tag(value) if normalize_tag(value) in known else value)

    steps = [
        schema.Step(
            id=s.id, name=s.name, initial=s.initial,
            actions=[schema.Action(io=ref(a.io), state=a.state, note=a.note) for a in s.actions],
            transitions=[
                schema.Transition(
                    target=t.target, timer_s=t.timer_s, expression=t.expression,
                    conditions=[schema.Condition(io=ref(c.io), state=c.state, edge=c.edge) for c in t.conditions],
                    source=to_source(t.source), confidence=_clamp(t.confidence), assumption=t.assumption,
                )
                for t in s.transitions
            ],
            source=to_source(s.source), confidence=_clamp(s.confidence), assumption=s.assumption,
        )
        for s in flow.steps
    ]
    if steps and not any(s.initial for s in steps):
        steps[0].initial = True
        steps[0].assumption = True
    return steps


def default_layout(points: list[schema.IOPoint], title: str) -> schema.Layout:
    """Deterministische Draufsicht ohne Modell: Bedienung oben, Sensoren auf der Bandlinie, Aktoren darunter."""
    rows = {"operator": 0.15, "safety": 0.15, "sensor": 0.5, "actuator": 0.7, "other": 0.85}
    groups: dict[str, list[schema.IOPoint]] = {}
    for point in points:
        groups.setdefault(point.kind, []).append(point)
    elements: list[schema.LayoutElement] = []
    for kind, y in rows.items():
        members = [p for k in (kind,) for p in groups.get(k, [])]
        if kind == "safety":
            continue  # teilt sich die obere Reihe mit operator
        if kind == "operator":
            members = groups.get("operator", []) + groups.get("safety", [])
        for index, point in enumerate(members):
            x = (index + 1) / (len(members) + 1)
            shape = "arrow" if point.kind == "actuator" else "rect" if point.kind in ("operator", "safety") else "circle"
            elements.append(schema.LayoutElement(io=point.address, x=round(x, 3), y=y, shape=shape, assumption=True))
    return schema.Layout(title=f"{title}, Draufsicht (Lage geschaetzt)", elements=elements)
