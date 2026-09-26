from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    created_at: datetime
    document_count: int = 0


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    filename: str
    doc_type: str
    status: str
    progress: str
    error: str | None
    page_count: int | None
    vision_enrichment: bool
    created_at: datetime


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_ids: list[str]
    updated_at: datetime


class SourceRef(BaseModel):
    document_id: str
    filename: str
    doc_type: str = ""
    page: int | None = None
    section: str = ""


class ToolCallOut(BaseModel):
    name: str
    args: dict


class MessageOut(BaseModel):
    role: str  # user | assistant
    content: str
    tool_calls: list[ToolCallOut] = []
    sources: list[SourceRef] = []


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1)
    source_ids: list[str] = []


# --- Werk: Halle / Maschine / Fehlerliste / Schaltschrank ------------------------------------


class HallCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class HallUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class FlowIn(BaseModel):
    from_machine_id: str
    to_machine_id: str
    label: str = ""


class FlowOut(FlowIn):
    model_config = ConfigDict(from_attributes=True)

    id: str


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    machine_type: str = "other"
    description: str = ""
    source_id: str | None = None
    pos_x: float = 0.0
    pos_y: float = 0.0


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    machine_type: str | None = None
    description: str | None = None
    source_id: str | None = None
    clear_source: bool = False
    pos_x: float | None = None
    pos_y: float | None = None
    order_index: int | None = None


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    hall_id: str
    name: str
    machine_type: str
    description: str
    source_id: str | None
    source_name: str | None = None
    has_image: bool = False
    pos_x: float
    pos_y: float
    order_index: int
    fault_count: int = 0
    cabinet_count: int = 0
    document_count: int = 0


class HallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    created_at: datetime
    machine_count: int = 0


class HallDetail(HallOut):
    machines: list[MachineOut] = []
    flows: list[FlowOut] = []


class FaultIn(BaseModel):
    code: str = ""
    symptom: str = ""
    cause: str = ""
    fix: str = ""
    doc_ref: str = ""
    tags: list[str] = []


class FaultOut(FaultIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    machine_id: str


class HotspotIn(BaseModel):
    tag: str = ""
    label: str = ""
    kind: str = ""
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(gt=0, le=1)
    h: float = Field(gt=0, le=1)
    confirmed: bool = True


class HotspotUpdate(BaseModel):
    tag: str | None = None
    label: str | None = None
    kind: str | None = None
    x: float | None = Field(default=None, ge=0, le=1)
    y: float | None = Field(default=None, ge=0, le=1)
    w: float | None = Field(default=None, gt=0, le=1)
    h: float | None = Field(default=None, gt=0, le=1)
    confirmed: bool | None = None


class HotspotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cabinet_id: str
    tag: str
    label: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    confidence: float | None
    origin: str
    confirmed: bool


class CabinetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    machine_id: str
    title: str
    width: int
    height: int
    created_at: datetime
    hotspots: list[HotspotOut] = []


class MachineDetail(MachineOut):
    faults: list[FaultOut] = []
    cabinets: list[CabinetOut] = []


class TagHit(BaseModel):
    document_id: str
    filename: str
    doc_type: str
    page: int | None
    section: str
    context: str


class TagLookup(BaseModel):
    tag: str
    hits: list[TagHit]
    bom_line: str | None = None  # Stuecklisten-Zeile, falls gefunden


# --- Draufsicht (Maschinen-Layout) ------------------------------------------------------------


class LayoutIn(BaseModel):
    width_mm: float = Field(default=0, ge=0, le=500_000)
    depth_mm: float = Field(default=0, ge=0, le=500_000)
    document_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    scale_note: str = Field(default="", max_length=60)


class LayoutPartIn(BaseModel):
    tag: str = ""
    label: str = ""
    kind: str = "Sonstiges"
    shape: str = "rect"
    x_mm: float = 0
    y_mm: float = 0
    w_mm: float = Field(default=100, gt=0)
    h_mm: float = Field(default=100, gt=0)
    rotation_deg: float = 0
    confirmed: bool = True


class LayoutPartUpdate(BaseModel):
    tag: str | None = None
    label: str | None = None
    kind: str | None = None
    shape: str | None = None
    x_mm: float | None = None
    y_mm: float | None = None
    w_mm: float | None = Field(default=None, gt=0)
    h_mm: float | None = Field(default=None, gt=0)
    rotation_deg: float | None = None
    confirmed: bool | None = None


class LayoutPartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    layout_id: str
    tag: str
    label: str
    kind: str
    shape: str
    x_mm: float
    y_mm: float
    w_mm: float
    h_mm: float
    rotation_deg: float
    confidence: float | None
    origin: str
    confirmed: bool


class LayoutOut(BaseModel):
    id: str
    machine_id: str
    width_mm: float
    depth_mm: float
    has_image: bool
    document_id: str | None
    page: int | None
    scale_note: str
    updated_at: datetime
    parts: list[LayoutPartOut] = []


class TagSearchMachine(BaseModel):
    id: str
    name: str


class TagSearchHit(BaseModel):
    tag: str
    tag_type: str
    occurrences: int
    machines: list[TagSearchMachine] = []


class LocateBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float


class LocateOut(BaseModel):
    """Ziel eines Belegs im Dokument: Seite und optional die markierte Spalte (relativ 0..1)."""

    page: int
    column: int | None = None
    box: LocateBox | None = None


class FactValue(BaseModel):
    text: str
    ref: str
    document_id: str | None = None
    filename: str | None = None
    page: int | None = None


class FactRow(BaseModel):
    label: str
    values: list[FactValue]


class FactCard(BaseModel):
    tag: str
    title: str | None = None
    bom_line: str | None = None
    rows: list[FactRow] = []


class DiagnosisStep(BaseModel):
    text: str
    tag: str = ""
    ref: str = ""
    status: str = Field(default="open", pattern="^(open|ok|nok|skip)$")
    note: str = ""


class DiagnosisStepChange(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|ok|nok|skip)$")
    note: str | None = None


class DiagnosisStart(BaseModel):
    fault_id: str | None = None
    title: str = ""


class DiagnosisUpdate(BaseModel):
    steps: list[DiagnosisStep] | None = None
    finding: str | None = None


class DiagnosisFinish(BaseModel):
    outcome: str = Field(pattern="^(resolved|unresolved)$")
    finding: str = ""
    add_to_faults: bool = False


class DiagnosisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    machine_id: str
    fault_id: str | None
    title: str
    steps: list[DiagnosisStep]
    outcome: str
    finding: str
    started_at: datetime
    finished_at: datetime | None
