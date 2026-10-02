import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    BigInteger,
    Computed,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base
from app.tenancy import WorkspaceScoped


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class DocType(StrEnum):
    AUTO = "auto"
    SCHEMATIC = "schematic"  # Stromlaufplan
    BOM = "bom"  # Stueckliste
    TERMINAL_PLAN = "terminal_plan"  # Klemmenplan / Klemmenbelegung
    PLC_PROGRAM = "plc_program"  # Siemens AWL-Quelle
    PLC_SYMBOLS = "plc_symbols"  # Symboltabelle (.sdf)
    MANUAL = "manual"  # Handbuch
    OTHER = "other"


class DocStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class TagType(StrEnum):
    DEVICE = "device"  # Betriebsmittelkennzeichen, z.B. -K12
    TERMINAL = "terminal"  # Klemme, z.B. -X1:5
    DEVICE_PIN = "device_pin"  # Geraeteanschluss, z.B. -K1:A1 (Spule), -K1:13 (Schliesser); Art: tags.pin_kind
    PLC_ADDRESS = "plc_address"  # z.B. E0.0, A4.1, DB10.DBX2.0
    CROSS_REF = "cross_ref"  # Seitenverweis, z.B. /12.3


class Workspace(Base):
    """Mandant: ein Kunde/Werk. Alle fachlichen Zeilen tragen seine id (siehe app/tenancy.py)."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # KI-Monatslimit in Cent; None = kein Limit. Geprueft vor jedem Provider-Aufruf (app/ledger.py).
    monthly_ai_cap_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class WorkspaceMember(Base):
    """Rolle eines Nutzers in einem Workspace: admin | member."""

    __tablename__ = "workspace_members"

    workspace_id: Mapped[str] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(16), default="member")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class LoginToken(Base):
    """Magic-Link: nur der SHA-256 des Tokens liegt in der Datenbank, einmal einloesbar."""

    __tablename__ = "login_tokens"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class KnowledgeSource(WorkspaceScoped, Base):
    """Wissensquelle: Container fuer zusammengehoerige Dokumente (z.B. eine Anlage)."""

    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Document(WorkspaceScoped, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(500))
    storage_path: Mapped[str] = mapped_column(String(1000))
    doc_type: Mapped[str] = mapped_column(String(32), default=DocType.OTHER)
    status: Mapped[str] = mapped_column(String(16), default=DocStatus.PENDING)
    progress: Mapped[str] = mapped_column(String(200), default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vision_enrichment: Mapped[bool] = mapped_column(default=False)
    # Anlaeufe der Verarbeitung; begrenzt Neustart-Schleifen (ingestion/resume.py)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source: Mapped[KnowledgeSource] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tags: Mapped[list["TagOccurrence"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(WorkspaceScoped, Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # text | vision | awl_block | awl_network | symbols
    kind: Mapped[str] = mapped_column(String(24), default="text")
    section: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float]] = mapped_column(Vector(get_settings().embedding_dim))
    # Volltext fuer die Hybrid-Suche; Postgres pflegt die Spalte selbst (siehe migrations.py)
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('german', content)", persisted=True), nullable=True
    )

    document: Mapped[Document] = relationship(back_populates="chunks")

    __table_args__ = (
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_doc_page", "document_id", "page"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )


class TagOccurrence(WorkspaceScoped, Base):
    """Exakter Index aller Kennzeichen - das Rueckgrat fuer Zusammenhaenge ueber Dokumente."""

    __tablename__ = "tag_occurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    source_id: Mapped[str] = mapped_column(String(32), index=True)
    tag: Mapped[str] = mapped_column(String(120), index=True)  # normalisiert
    tag_type: Mapped[str] = mapped_column(String(16), index=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str] = mapped_column(String(500), default="")
    context: Mapped[str] = mapped_column(Text, default="")

    document: Mapped[Document] = relationship(back_populates="tags")


class Conversation(WorkspaceScoped, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), default="Neuer Chat")
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    # Stoerfall: jeder Chat einer Maschine ist einer; outcome open | resolved wie bei DiagnosisSession.
    # Spalten kamen nach der Baseline dazu: alembic/versions/0004_stoerfall_felder.py
    outcome: Mapped[str] = mapped_column(String(16), default="open", server_default="open")
    finding: Mapped[str] = mapped_column(Text, default="", server_default="")


# --- Werk: Halle -> Maschine -> Doku / Fehlerliste / Schaltschrank ---------------------------


class MachineType(StrEnum):
    CONVEYOR = "conveyor"  # Foerderband
    MAIN = "main"  # Hauptmaschine (Presse, Fraese, Spritzguss ...)
    PACKAGING = "packaging"  # Verpackungsmaschine
    ROBOT = "robot"
    STORAGE = "storage"  # Lager, Puffer, Magazin
    OTHER = "other"


class Hall(WorkspaceScoped, Base):
    """Halle: Gruppe von Maschinen mit Name und Beschreibung."""

    __tablename__ = "halls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    machines: Mapped[list["Machine"]] = relationship(
        back_populates="hall", cascade="all, delete-orphan", order_by="Machine.order_index"
    )


class Machine(WorkspaceScoped, Base):
    """Eine Maschine in der Halle. Die Doku haengt ueber source_id als Wissensquelle dran."""

    __tablename__ = "machines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    hall_id: Mapped[str] = mapped_column(ForeignKey("halls.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    machine_type: Mapped[str] = mapped_column(String(24), default=MachineType.OTHER)
    description: Mapped[str] = mapped_column(Text, default="")
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    image_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)  # Reihenfolge im Ablauf
    line: Mapped[str] = mapped_column(String(120), default="", server_default="")  # Linie/Sektor
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    hall: Mapped[Hall] = relationship(back_populates="machines")
    specs: Mapped[list["MachineSpec"]] = relationship(
        cascade="all, delete-orphan", order_by="MachineSpec.position"
    )
    source: Mapped[KnowledgeSource | None] = relationship()
    faults: Mapped[list["FaultEntry"]] = relationship(
        back_populates="machine", cascade="all, delete-orphan", order_by="FaultEntry.code"
    )
    cabinets: Mapped[list["CabinetImage"]] = relationship(
        back_populates="machine", cascade="all, delete-orphan", order_by="CabinetImage.created_at"
    )


class MachineSpec(WorkspaceScoped, Base):
    """Kennzahl einer Maschine mit Quelle, z. B. 'Leistung 10 Logs/min (Hersteller-Datenblatt)'."""

    __tablename__ = "machine_specs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(String(60), default="")
    source: Mapped[str] = mapped_column(Text, default="")  # URL oder "Richtwert ..."


class FaultEntry(WorkspaceScoped, Base):
    """Fehlerliste der Maschine: Code, Symptom, Ursache, Behebung, Verweis in die Doku."""

    __tablename__ = "fault_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(60), default="")
    symptom: Mapped[str] = mapped_column(Text, default="")
    cause: Mapped[str] = mapped_column(Text, default="")
    fix: Mapped[str] = mapped_column(Text, default="")
    doc_ref: Mapped[str] = mapped_column(String(300), default="")  # z. B. "Stromlaufplan Blatt 4"
    tags: Mapped[list] = mapped_column(JSON, default=list)  # beteiligte BMK, z. B. ["-F2", "-M1"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    machine: Mapped[Machine] = relationship(back_populates="faults")


class CabinetImage(WorkspaceScoped, Base):
    """Foto oder Aufbauplan eines Schaltschranks mit markierten Bauteilen."""

    __tablename__ = "cabinet_images"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), default="Schaltschrank")
    image_path: Mapped[str] = mapped_column(String(1000))
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    machine: Mapped[Machine] = relationship(back_populates="cabinets")
    hotspots: Mapped[list["CabinetHotspot"]] = relationship(
        back_populates="cabinet", cascade="all, delete-orphan", order_by="CabinetHotspot.tag"
    )


class CabinetHotspot(WorkspaceScoped, Base):
    """Rechteck im Schaltschrankbild, relativ (0..1) zur Bildgroesse, mit BMK."""

    __tablename__ = "cabinet_hotspots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    cabinet_id: Mapped[str] = mapped_column(
        ForeignKey("cabinet_images.id", ondelete="CASCADE"), index=True
    )
    tag: Mapped[str] = mapped_column(String(120), default="")  # normalisiertes BMK, z. B. -K1
    label: Mapped[str] = mapped_column(String(200), default="")  # z. B. "Schuetz Motor vorwaerts"
    kind: Mapped[str] = mapped_column(String(60), default="")  # Schuetz, LS-Schalter, Klemmleiste ...
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    w: Mapped[float] = mapped_column(Float, default=0.1)
    h: Mapped[float] = mapped_column(Float, default=0.1)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # nur bei Vision
    origin: Mapped[str] = mapped_column(String(16), default="manual")  # manual | vision
    confirmed: Mapped[bool] = mapped_column(default=True)  # Vision-Vorschlaege bis Bestaetigung False

    cabinet: Mapped[CabinetImage] = relationship(back_populates="hotspots")


class DiagnosisSession(WorkspaceScoped, Base):
    """Gefuehrte Fehlersuche an einer Maschine: Pruefschritte mit Ergebnis, Befund, Abschluss."""

    __tablename__ = "diagnosis_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    fault_id: Mapped[str | None] = mapped_column(
        ForeignKey("fault_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(300), default="")  # Fehlercode + Symptom bei Start
    steps: Mapped[list] = mapped_column(JSON, default=list)  # [{text, tag, ref, status, note}]
    outcome: Mapped[str] = mapped_column(String(16), default="open")  # open | resolved | unresolved
    finding: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiCall(WorkspaceScoped, Base):
    """Kostenbuch: ein KI-Aufruf, seiner Maschine und seinem Zweck zugebucht (app/ledger.py)."""

    __tablename__ = "ai_call_ledger"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    machine_id: Mapped[str | None] = mapped_column(
        ForeignKey("machines.id", ondelete="SET NULL"), nullable=True, index=True
    )
    purpose: Mapped[str] = mapped_column(String(32))  # chat | vision.page | vision.cabinet
    provider: Mapped[str] = mapped_column(String(32), default="anthropic")
    model: Mapped[str] = mapped_column(String(120))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    images: Mapped[int] = mapped_column(Integer, default=0)
    cost_microcents: Mapped[int] = mapped_column(BigInteger, default=0)  # 1 Cent = 1_000_000
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
