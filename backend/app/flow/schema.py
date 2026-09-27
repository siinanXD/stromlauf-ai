"""Datenmodell der Ablauf-Visualisierung; einzige Quelle fuer `schemas/machine_flow.json`.

Jedes fachliche Feld traegt `source` (Datei, Seite oder Chunk, Zitat bis 15 Woerter) und
`confidence`. Was das Modell nicht belegen kann, steht mit `assumption: true` drin, statt geraten
zu werden. `meta` haelt Trace-ID, Modelle, Prompt-Version, Kosten und den Cache-Schluessel.

Regenerieren: `python scripts/flow_schema.py --write` (Test prueft, dass die Datei aktuell ist).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SCHEMA_VERSION = "1.0"
MAX_QUOTE_WORDS = 15


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Source(Strict):
    """Belegstelle: woher ein Feld stammt. Zitat hoechstens 15 Woerter."""

    file: str = Field(description="Dateiname des Dokuments")
    page: int | None = Field(default=None, ge=1, description="PDF-Seite (1-basiert), sonst null")
    chunk: str | None = Field(default=None, description="Abschnitt, z. B. 'FB 10 / NW 3' oder 'Kap. 3'")
    quote: str = Field(description="Woertliches Zitat, hoechstens 15 Woerter")

    @field_validator("quote")
    @classmethod
    def _short_quote(cls, value: str) -> str:
        if len(value.split()) > MAX_QUOTE_WORDS:
            raise ValueError(f"Zitat hat mehr als {MAX_QUOTE_WORDS} Woerter")
        return value.strip()


class Evidence(Strict):
    """Gemeinsame Felder aller belegten Objekte."""

    source: Source
    confidence: float = Field(ge=0.0, le=1.0, description="Sicherheit des Modells 0..1")
    assumption: bool = Field(default=False, description="true = nicht belegt, sondern angenommen")


class IOPoint(Evidence):
    """Ein Ein- oder Ausgang der SPS mit Sensor bzw. Aktor dahinter."""

    address: str = Field(description="Normalisierte SPS-Adresse, z. B. E0.0, A4.1")
    symbol: str = Field(default="", description="Symbolname aus der Symboltabelle, z. B. LS_Einlauf")
    direction: Literal["DI", "DO", "AI", "AO"]
    kind: Literal["sensor", "actuator", "operator", "safety", "other"] = Field(
        description="sensor = Sensor/Geber, actuator = Aktor, operator = Bedienelement, safety = Sicherheitskreis"
    )
    contact: Literal["NC", "NO"] | None = Field(default=None, description="Oeffner (NC) oder Schliesser (NO), sonst null")
    tag: str = Field(default="", description="Betriebsmittelkennzeichen, z. B. -B1")
    location: str = Field(default="", description="Einbauort, z. B. +FE1 Einlauf")
    description: str = Field(default="", description="Klartext, z. B. 'Lichtschranke Einlauf, 1 = Teil erkannt'")
    active_state: Literal[0, 1] = Field(default=1, description="Signalpegel, bei dem der Punkt als 'ausgeloest' gilt")


class Action(Strict):
    """Was ein Schritt tut: Ausgang setzen oder ruecksetzen."""

    io: str = Field(description="address oder symbol eines IOPoint")
    state: Literal[0, 1]
    note: str = Field(default="")


class Condition(Strict):
    """Bedingung einer Transition; alle Bedingungen einer Transition sind UND-verknuepft."""

    io: str = Field(description="address oder symbol eines IOPoint")
    state: Literal[0, 1]
    edge: Literal["rising", "falling"] | None = Field(default=None, description="Flanke statt Pegel, sonst null")


class Transition(Evidence):
    target: str = Field(description="id des Folgeschritts")
    conditions: list[Condition] = Field(default_factory=list, description="leer = sofort/Zeit")
    timer_s: float | None = Field(default=None, ge=0, description="Wartezeit in Sekunden, wenn zeitgesteuert")
    expression: str = Field(default="", description="Bedingung im Klartext, z. B. 'LS_Auslauf UND NICHT Stop'")


class Step(Evidence):
    id: str = Field(description="Eindeutig, z. B. S0, S1")
    name: str = Field(description="Kurzname, z. B. 'Grundstellung', 'Band vorwaerts'")
    initial: bool = Field(default=False, description="Anfangsschritt (genau einer)")
    actions: list[Action] = Field(default_factory=list)
    transitions: list[Transition] = Field(default_factory=list)


class LayoutElement(Strict):
    """Lage eines IOPoint in der Draufsicht, relative Koordinaten 0..1."""

    io: str = Field(description="address oder symbol eines IOPoint")
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    shape: Literal["circle", "rect", "arrow"] = "circle"
    assumption: bool = Field(default=True, description="Lage aus der Doku belegt (false) oder geschaetzt (true)")


class Layout(Strict):
    title: str = Field(default="", description="Beschriftung, z. B. 'Foerderband FB-01, Draufsicht'")
    elements: list[LayoutElement] = Field(default_factory=list)


class Usage(Strict):
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0


class Phase(Strict):
    """Ein Extraktionsschritt (Span) mit Modell und Verbrauch."""

    name: Literal["io_points", "sensors_actuators", "steps", "layout"]
    model: str
    usage: Usage
    cached: bool = False


class Meta(Strict):
    schema_version: str = SCHEMA_VERSION
    prompt_version: str = Field(description="Version der Extraktions-Prompts; Teil des Cache-Schluessels")
    cache_key: str = Field(description="SHA-256 ueber Dokument(e) + prompt_version")
    document_sha256: dict[str, str] = Field(description="Dateiname -> SHA-256")
    trace_id: str | None = Field(default=None, description="Langfuse-Trace-ID, null ohne Langfuse")
    models: dict[str, str] = Field(description="Rolle -> Modell-ID, z. B. {'small': ..., 'strong': ...}")
    phases: list[Phase] = Field(default_factory=list)
    total: Usage = Field(default_factory=Usage)
    extracted_at: datetime
    cached: bool = Field(default=False, description="true = aus dem Cache gelesen, keine Kosten")


class MachineFlow(Strict):
    """Wurzel: Ablauf einer Maschine fuer die Animation."""

    machine: str = Field(description="Name der Maschine, z. B. 'Foerderband FB-01'")
    summary: str = Field(default="", description="Ablauf in zwei bis drei Saetzen")
    io_points: list[IOPoint]
    steps: list[Step]
    layout: Layout = Field(default_factory=Layout)
    open_questions: list[str] = Field(default_factory=list, description="Was die Doku nicht hergibt")
    meta: Meta

    @field_validator("steps")
    @classmethod
    def _one_initial_and_known_targets(cls, steps: list[Step]) -> list[Step]:
        if steps and sum(s.initial for s in steps) != 1:
            raise ValueError("genau ein Schritt muss initial=true haben")
        ids = {s.id for s in steps}
        if len(ids) != len(steps):
            raise ValueError("Schritt-IDs muessen eindeutig sein")
        for step in steps:
            for transition in step.transitions:
                if transition.target not in ids:
                    raise ValueError(f"Transition von {step.id} zeigt auf unbekannten Schritt {transition.target}")
        return steps

    def io_by_ref(self) -> dict[str, IOPoint]:
        """Adresse und Symbol -> IOPoint, fuer Aktionen, Bedingungen und Layout."""
        table: dict[str, IOPoint] = {}
        for point in self.io_points:
            table[point.address] = point
            if point.symbol:
                table[point.symbol] = point
        return table

    def unresolved_refs(self) -> list[str]:
        """Verweise aus Schritten und Layout ohne passenden IOPoint (Warnung, kein Fehler)."""
        known = self.io_by_ref()
        refs = [a.io for s in self.steps for a in s.actions]
        refs += [c.io for s in self.steps for t in s.transitions for c in t.conditions]
        refs += [e.io for e in self.layout.elements]
        return sorted({r for r in refs if r not in known})


def json_schema() -> dict:
    schema = MachineFlow.model_json_schema()
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = "https://stromlauf.local/schemas/machine_flow.json"
    schema["title"] = "MachineFlow"
    return schema
