import uuid
from datetime import date, datetime, timezone
from enum import StrEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Computed,
    Date,
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
    # Art (generic|base|production|warehouse|office) und Rechteck im Standortplan (px, 0 = nicht platziert).
    # Spalten kamen nach der ersten Version dazu: siehe app/migrations.py
    kind: Mapped[str] = mapped_column(String(24), default="generic", server_default="generic")
    site_x: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    site_y: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    site_w: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    site_h: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")

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
    layout: Mapped["MachineLayout | None"] = relationship(
        back_populates="machine", cascade="all, delete-orphan", uselist=False
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


class SiteFlow(Base):
    """Materialfluss zwischen zwei Hallen im Standortplan."""

    __tablename__ = "site_flows"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    from_hall_id: Mapped[str] = mapped_column(ForeignKey("halls.id", ondelete="CASCADE"), index=True)
    to_hall_id: Mapped[str] = mapped_column(ForeignKey("halls.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(120), default="")


class MachineSpec(Base):
    """Kennzahl einer Maschine mit Quelle, z. B. 'Leistung 10 Logs/min (Hersteller-Datenblatt)'."""

    __tablename__ = "machine_specs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    machine_id: Mapped[str] = mapped_column(ForeignKey("machines.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(Text, default="")
    unit: Mapped[str] = mapped_column(String(60), default="")
    source: Mapped[str] = mapped_column(Text, default="")  # URL oder "Richtwert ..."


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


class MachineLayout(Base):
    """Draufsicht einer Maschine in mm; Skizze als Upload oder als Seite eines Dokuments."""

    __tablename__ = "machine_layouts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    machine_id: Mapped[str] = mapped_column(
        ForeignKey("machines.id", ondelete="CASCADE"), unique=True, index=True
    )
    width_mm: Mapped[float] = mapped_column(Float, default=0.0)
    depth_mm: Mapped[float] = mapped_column(Float, default=0.0)
    image_path: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scale_note: Mapped[str] = mapped_column(String(60), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    machine: Mapped[Machine] = relationship(back_populates="layout")
    parts: Mapped[list["LayoutPart"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan", order_by="LayoutPart.tag"
    )


class LayoutPart(Base):
    """Baugruppe oder Feldgeraet in der Draufsicht (Rechteck oder Kreis, Werte in mm)."""

    __tablename__ = "layout_parts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    layout_id: Mapped[str] = mapped_column(ForeignKey("machine_layouts.id", ondelete="CASCADE"), index=True)
    tag: Mapped[str] = mapped_column(String(120), default="")
    label: Mapped[str] = mapped_column(String(200), default="")
    kind: Mapped[str] = mapped_column(String(40), default="Sonstiges")
    shape: Mapped[str] = mapped_column(String(10), default="rect")  # rect | circle
    x_mm: Mapped[float] = mapped_column(Float, default=0.0)
    y_mm: Mapped[float] = mapped_column(Float, default=0.0)
    w_mm: Mapped[float] = mapped_column(Float, default=100.0)
    h_mm: Mapped[float] = mapped_column(Float, default=100.0)
    rotation_deg: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # nur bei Vision
    origin: Mapped[str] = mapped_column(String(16), default="manual")  # manual | vision
    confirmed: Mapped[bool] = mapped_column(default=True)

    layout: Mapped[MachineLayout] = relationship(back_populates="parts")


class DiagnosisSession(Base):
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


# --- Vorkalkulation: Stammdaten ---------------------------------------------------------------


class Article(Base):
    """Verkaufsartikel mit technischen Daten (daraus Rohpapier je Einheit), Stueckliste, Arbeitsplan."""

    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    unit_name: Mapped[str] = mapped_column(String(40), default="Paket")
    units_per_pallet: Mapped[int] = mapped_column(Integer)
    sheets_per_unit: Mapped[int] = mapped_column(Integer)
    sheet_w_mm: Mapped[float] = mapped_column(Float)
    sheet_l_mm: Mapped[float] = mapped_column(Float)
    plies: Mapped[int] = mapped_column(Integer)
    gsm: Mapped[float] = mapped_column(Float)
    waste_pct: Mapped[float] = mapped_column(Float, default=3.0)
    line: Mapped[str] = mapped_column(String(120), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")  # Verkaufspreis EUR/Einheit

    routing: Mapped[list["RoutingStep"]] = relationship(
        cascade="all, delete-orphan", order_by="RoutingStep.seq"
    )
    bom: Mapped[list["BomLine"]] = relationship(
        cascade="all, delete-orphan", foreign_keys="BomLine.article_id", order_by="BomLine.position"
    )


class Material(Base):
    """Material (Zukauf mit Preis oder Eigenfertigung auf einer Maschine mit eigener Rezeptur)."""

    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    unit: Mapped[str] = mapped_column(String(20))
    price: Mapped[float | None] = mapped_column(Float, nullable=True)  # EUR je Einheit
    price_source: Mapped[str] = mapped_column(Text, default="")
    made_on_machine_id: Mapped[str | None] = mapped_column(
        ForeignKey("machines.id", ondelete="SET NULL"), nullable=True
    )
    made_rate_per_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    made_basis: Mapped[str] = mapped_column(Text, default="")

    made_on: Mapped["Machine | None"] = relationship()
    bom: Mapped[list["BomLine"]] = relationship(
        cascade="all, delete-orphan", foreign_keys="BomLine.parent_material_id", order_by="BomLine.position"
    )


class BomLine(Base):
    """Stuecklistenzeile: Eltern (Artikel oder Material) braucht qty Einheiten eines Materials."""

    __tablename__ = "bom_lines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    article_id: Mapped[str | None] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    parent_material_id: Mapped[str | None] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"), nullable=True, index=True
    )
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"))
    qty: Mapped[float] = mapped_column(Float)
    per: Mapped[str] = mapped_column(String(10), default="unit")  # unit | pallet
    position: Mapped[int] = mapped_column(Integer, default=0)

    material: Mapped[Material] = relationship(foreign_keys=[material_id])


class RoutingStep(Base):
    """Arbeitsplanschritt: Artikel auf Maschine mit Leistung, Ruestzeit und Herleitung."""

    __tablename__ = "routing_steps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), index=True)
    seq: Mapped[int] = mapped_column(Integer, default=0)
    # SET NULL: wird die Maschine geloescht, bleibt der Schritt (mit Leistung) und die Kalkulation warnt
    machine_id: Mapped[str | None] = mapped_column(ForeignKey("machines.id", ondelete="SET NULL"), nullable=True)
    rate: Mapped[float] = mapped_column(Float)
    rate_unit: Mapped[str] = mapped_column(String(12), default="unit_min")  # unit_min | pallet_h
    setup_min: Mapped[float] = mapped_column(Float, default=0.0)
    coupled: Mapped[bool] = mapped_column(Boolean, default=True)
    basis: Mapped[str] = mapped_column(Text, default="")

    machine: Mapped[Machine | None] = relationship()


class PlantSetting(Base):
    """Werksparameter als JSON, z. B. 'calc': Kalender, Buero-Stationen, LKW, Tore, Saetze."""

    __tablename__ = "plant_settings"

    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)


# --- Leitstand: Kunden, Auftraege, Bestand ------------------------------------------------------


class Customer(Base):
    """Kunde mit Kreditlimit (Finanzen pruefen offene Auftragswerte dagegen)."""

    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    credit_limit: Mapped[float] = mapped_column(Float, default=0.0)


class Order(Base):
    """Kundenauftrag im Auftragsbuch."""

    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    number: Mapped[str] = mapped_column(String(40), unique=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id", ondelete="SET NULL"), nullable=True)
    received_at: Mapped[datetime] = mapped_column(DateTime)  # Ortszeit, ohne Zeitzone
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    customer: Mapped[Customer | None] = relationship()
    lines: Mapped[list["OrderLine"]] = relationship(cascade="all, delete-orphan", order_by="OrderLine.position")


class OrderLine(Base):
    __tablename__ = "order_lines"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(10), default="unit")  # unit | pallet
    position: Mapped[int] = mapped_column(Integer, default=0)

    article: Mapped[Article] = relationship()


class StockItem(Base):
    """Lagerbestand je Artikel in Verkaufseinheiten (Anfangsbestand der Simulation)."""

    __tablename__ = "stock"

    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True)
    units: Mapped[int] = mapped_column(Integer, default=0)

    article: Mapped[Article] = relationship()
