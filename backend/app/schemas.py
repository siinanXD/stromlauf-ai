from datetime import datetime
from typing import Literal

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


class DocTypeDetection(BaseModel):
    """Vorschlag fuer den Dokumenttyp vor dem Upload (POST /api/documents/detect)."""

    filename: str
    doc_type: str
    confidence: float
    reason: str
    source: str  # content | filename | suffix | none
    page_count: int | None = None  # PDF-Seiten fuer die Kostenschaetzung vor dem Upload


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_ids: list[str]
    updated_at: datetime
    # Stoerfall (jeder Chat einer Maschine): open | resolved, dazu der Befund beim Abschliessen
    outcome: str = "open"
    finding: str = ""


class ConversationPatch(BaseModel):
    """Stoerfall abschliessen oder wieder oeffnen; fehlende Felder bleiben, wie sie sind."""

    outcome: Literal["open", "resolved"] | None = None
    finding: str | None = Field(default=None, max_length=2000)


class CitedFile(BaseModel):
    filename: str


class CitationValidateRequest(BaseModel):
    """Gespeicherte Antwort nachpruefen (eval/rescore.py --api): Belege gegen Quellen und Fundstellen.

    Deckel gegen Missbrauch: der Endpunkt kostet keine Tokens, rechnet aber je Beleg gegen die Datenbank.
    """

    answer: str = Field(max_length=50_000)
    source_ids: list[str] = Field(
        default_factory=list, max_length=50
    )  # leer = alle Quellen des Workspace
    sources: list[CitedFile] | None = Field(
        default=None, max_length=500
    )  # Fundstellen der Werkzeugaufrufe; None = jede Datei der Quellen gilt


class CitationCheckOut(BaseModel):
    text: str
    file: str
    locator: str
    valid: bool
    checked: bool
    reason: str = ""


class CitationsValid(BaseModel):
    valid: int
    checked: int
    total: int


class CitationValidateOut(BaseModel):
    citation_checks: list[CitationCheckOut]
    citations_valid: CitationsValid
    referenced_tags: list[
        str
    ] = []  # Betriebsmittel der Antwort im Index der Quellen (fuer teile_praezision/-recall)


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
    # Antwort-Vertrag wie das meta-Event des Streams (referenced_tags, citations, evidence, citation_checks,
    # citations_valid), fuer Antworten im Verlauf nachgerechnet (Issue #47); None bei Nutzerfragen
    meta: dict | None = None
    # Position im ganzen Verlauf (0 = erste Nachricht), fuer das Nachladen aelterer Nachrichten
    index: int = 0


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1)
    source_ids: list[str] = []
    trace_tags: list[str] = []  # Tags am Langfuse-Trace, z. B. eval:2026-09-27, q:fb01-e03
    # Maschinen-Chat: Scope ist fest die Wissensquelle der Maschine; source_ids werden dann ignoriert
    machine_id: str | None = None
    # Modell nur fuer diese Anfrage, z. B. "openai:gpt-5-mini" (Evals vergleichen Provider); leer = CHAT_MODEL
    model: str | None = None


# --- Werk: Halle / Maschine / Fehlerliste / Schaltschrank ------------------------------------


class HallCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""


class HallUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class MachineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    machine_type: str = "other"
    description: str = ""
    source_id: str | None = None
    line: str = Field(default="", max_length=120)


class MachineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    machine_type: str | None = None
    description: str | None = None
    source_id: str | None = None
    clear_source: bool = False
    order_index: int | None = None
    line: str | None = Field(default=None, max_length=120)


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
    order_index: int
    fault_count: int = 0
    cabinet_count: int = 0
    document_count: int = 0
    line: str = ""
    key_figure: str = ""  # erste Kennzahl, z. B. "2.200 m/min"
    hall_name: str = ""


class HallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    description: str
    created_at: datetime
    machine_count: int = 0


class HallDetail(HallOut):
    machines: list[MachineOut] = []


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


class ExperienceHit(BaseModel):
    """Treffer in der Fehlerliste einer anderen Maschine: Erfahrung, kein Beleg fuer diese Maschine."""

    machine_id: str
    machine_name: str
    fault: FaultOut


class IncidentHit(BaseModel):
    """Erledigter Stoerfall derselben Quelle mit Befund."""

    conversation_id: str
    title: str
    finding: str
    updated_at: datetime


class FaultHits(BaseModel):
    """GET /api/machines/{id}/fault-hits: je Liste hoechstens 5 Treffer, der beste zuerst."""

    faults: list[FaultOut] = []
    experience: list[ExperienceHit] = []
    incidents: list[IncidentHit] = []


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


class MachineListItem(BaseModel):
    """Zeile der Maschinenuebersicht (/api/machines): Zustand der Doku und der Fehlersuche je Maschine."""

    id: str
    name: str
    machine_type: str
    line: str
    hall_id: str
    hall_name: str
    source_id: str | None
    source_name: str | None
    document_count: int
    ready_document_count: int
    fault_count: int
    open_diagnoses: int
    cabinet_count: int
    key_figure: str


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


# --- Globale Suche ------------------------------------------------------------------------------


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


class ProfileDocument(BaseModel):
    id: str
    filename: str
    doc_type: str
    status: str
    page_count: int | None
    tag_count: int


class ProfileDocType(BaseModel):
    doc_type: str
    present: bool
    filenames: list[str]


class ProfileGap(BaseModel):
    kind: str
    tag: str
    message: str
    doc_types: list[str]


class ProfileCoverage(BaseModel):
    tag: str
    tag_type: str
    docs: dict[str, int]


class ProfileSummary(BaseModel):
    devices: int
    terminals: int
    plc_addresses: int
    gaps: int


class SourceProfile(BaseModel):
    """Steckbrief einer Wissensquelle: Dokumente, Abdeckung, Luecken (deterministisch, ohne Modell)."""

    source_id: str
    source_name: str
    documents: list[ProfileDocument]
    doc_types: list[ProfileDocType]
    sheets: list[int]  # Blaetter des Stromlaufplans, leer ohne PDF-Plan
    summary: ProfileSummary
    gaps: list[ProfileGap]
    coverage: list[ProfileCoverage]


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


# --- Kennzahlen -----------------------------------------------------------------------------


class SpecIn(BaseModel):
    label: str = Field(default="", max_length=200)
    value: str = ""
    unit: str = Field(default="", max_length=60)
    source: str = ""


class SpecOut(SpecIn):
    model_config = ConfigDict(from_attributes=True)

    id: str
    position: int
