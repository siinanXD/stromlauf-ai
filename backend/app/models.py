import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db import Base


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
    PLC_ADDRESS = "plc_address"  # z.B. E0.0, A4.1, DB10.DBX2.0
    CROSS_REF = "cross_ref"  # Seitenverweis, z.B. /12.3


class KnowledgeSource(Base):
    """Wissensquelle: Container fuer zusammengehoerige Dokumente (z.B. eine Anlage)."""

    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    documents: Mapped[list["Document"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class Document(Base):
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    source: Mapped[KnowledgeSource] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    tags: Mapped[list["TagOccurrence"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class Chunk(Base):
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
    )


class TagOccurrence(Base):
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


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), default="Neuer Chat")
    source_ids: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# --- Werk: Halle -> Maschine -> Doku / Fehlerliste / Schaltschrank ---------------------------


class MachineType(StrEnum):
    CONVEYOR = "conveyor"  # Foerderband
    MAIN = "main"  # Hauptmaschine (Presse, Fraese, Spritzguss ...)
    PACKAGING = "packaging"  # Verpackungsmaschine
    ROBOT = "robot"
    STORAGE = "storage"  # Lager, Puffer, Magazin
    OTHER = "other"


class Hall(Base):
    """Produktionshalle: enthaelt Maschinen und den Materialfluss zwischen ihnen."""

    __tablename__ = "halls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    machines: Mapped[list["Machine"]] = relationship(
        back_populates="hall", cascade="all, delete-orphan", order_by="Machine.order_index"
    )
    flows: Mapped[list["HallFlow"]] = relationship(back_populates="hall", cascade="all, delete-orphan")


class Machine(Base):
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
    pos_x: Mapped[float] = mapped_column(Float, default=0.0)  # Layout-Position in der Halle (px)
    pos_y: Mapped[float] = mapped_column(Float, default=0.0)
    order_index: Mapped[int] = mapped_column(Integer, default=0)  # Reihenfolge im Ablauf
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    hall: Mapped[Hall] = relationship(back_populates="machines")
    source: Mapped[KnowledgeSource | None] = relationship()
    faults: Mapped[list["FaultEntry"]] = relationship(
        back_populates="machine", cascade="all, delete-orphan", order_by="FaultEntry.code"
    )
    cabinets: Mapped[list["CabinetImage"]] = relationship(
        back_populates="machine", cascade="all, delete-orphan", order_by="CabinetImage.created_at"
    )


class HallFlow(Base):
    """Materialfluss-Kante zwischen zwei Maschinen einer Halle."""

    __tablename__ = "hall_flows"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    hall_id: Mapped[str] = mapped_column(ForeignKey("halls.id", ondelete="CASCADE"), index=True)
    from_machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    to_machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(120), default="")

    hall: Mapped[Hall] = relationship(back_populates="flows")


class FaultEntry(Base):
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


class CabinetImage(Base):
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


class CabinetHotspot(Base):
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
