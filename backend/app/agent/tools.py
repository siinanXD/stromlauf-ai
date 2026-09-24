"""Werkzeuge des Agenten. Der Filter auf Wissensquellen kommt ueber config["configurable"]."""

from pathlib import Path

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from sqlalchemy import or_, select

from app.db import session_scope
from app.embeddings import embeddings
from app.ingestion.tags import normalize_tag
from app.ingestion.vision import image_block, render_page_png
from app.models import Chunk, DocStatus, Document, KnowledgeSource, TagOccurrence


def _source_ids(config: RunnableConfig) -> list[str]:
    return list((config.get("configurable") or {}).get("source_ids") or [])


def _scoped(statement, column, config: RunnableConfig):
    source_ids = _source_ids(config)
    return statement.where(column.in_(source_ids)) if source_ids else statement


def _ref(document: Document, page: int | None, section: str = "") -> dict:
    return {
        "document_id": document.id,
        "filename": document.filename,
        "doc_type": document.doc_type,
        "page": page,
        "section": section,
    }


def _format_chunk(document: Document, chunk: Chunk) -> str:
    location = f"S. {chunk.page}" if chunk.page else chunk.section or "-"
    return (
        f"### {document.filename} ({document.doc_type}) | {location} | "
        f"document_id={document.id} | {chunk.kind}\n{chunk.content}"
    )


@tool(response_format="content_and_artifact")
def search_knowledge(
    query: str, config: RunnableConfig, doc_types: list[str] | None = None, k: int = 8
) -> tuple[str, list[dict]]:
    """Semantische Suche ueber alle Dokumente der gewaehlten Wissensquellen
    (Stromlaufplaene inkl. Vision-Beschreibungen, Stuecklisten, Klemmenplaene, AWL-Netzwerke,
    Handbuecher). Gut fuer Funktionsfragen ("Was schaltet die Pumpe ein?").
    Fuer exakte Kennzeichen (-K12, E0.0, -X1:5) stattdessen find_tag verwenden.

    Args:
        query: Suchanfrage in natuerlicher Sprache, am besten mit Fachbegriffen.
        doc_types: Optionaler Filter, Werte aus: schematic, bom, terminal_plan, plc_program,
            plc_symbols, manual, other.
        k: Anzahl Treffer (1-20).
    """
    vector = embeddings.embed_query(query)
    statement = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .order_by(Chunk.embedding.cosine_distance(vector))
        .limit(max(1, min(k, 20)))
    )
    statement = _scoped(statement, Chunk.source_id, config)
    if doc_types:
        statement = statement.where(Document.doc_type.in_(doc_types))

    with session_scope() as session:
        rows = session.execute(statement).all()
        if not rows:
            return "Keine Treffer. Sind Dokumente hochgeladen und fertig verarbeitet?", []
        text = "\n\n".join(_format_chunk(document, chunk) for chunk, document in rows)
        refs = [_ref(document, chunk.page, chunk.section) for chunk, document in rows]
    return text, refs


@tool(response_format="content_and_artifact")
def find_tag(tag: str, config: RunnableConfig) -> tuple[str, list[dict]]:
    """Exakte Suche nach einem Kennzeichen ueber ALLE Dokumente: Betriebsmittel (-K12, -Q3),
    Klemmen (-X1 oder -X1:5), SPS-Adressen (E0.0, A4.1, MW100, DB10.DBX2.0).
    Liefert jede Fundstelle mit Dokument, Seite/Netzwerk und Textumgebung - das zentrale
    Werkzeug, um Zusammenhaenge zwischen Plan, Stueckliste, Klemmenplan und AWL zu finden.
    Schreibweise ist egal ("k12", "e 0.0", "%I0.0" werden normalisiert).
    """
    normalized = normalize_tag(tag)
    statement = (
        select(TagOccurrence, Document)
        .join(Document, TagOccurrence.document_id == Document.id)
        .where(
            or_(
                TagOccurrence.tag == normalized,
                TagOccurrence.tag.like(f"{normalized}:%"),  # -X1 -> alle Klemmen der Leiste
                TagOccurrence.tag.like(f"%{normalized}"),  # -K12 -> =A1+S1-K12
            )
        )
        .order_by(Document.doc_type, Document.filename, TagOccurrence.page, TagOccurrence.id)
        .limit(80)
    )
    statement = _scoped(statement, TagOccurrence.source_id, config)

    with session_scope() as session:
        rows = session.execute(statement).all()
        if not rows:
            return (
                f"Kennzeichen {normalized} nicht im Index gefunden. "
                "Alternative: search_knowledge oder keyword_search.",
                [],
            )
        lines = [f"Fundstellen fuer {normalized} ({len(rows)}):"]
        refs = []
        for occurrence, document in rows:
            location = f"S. {occurrence.page}" if occurrence.page else occurrence.section or "-"
            lines.append(
                f"- {occurrence.tag} | {document.filename} ({document.doc_type}) | {location} | "
                f"document_id={document.id} | ...{occurrence.context}..."
            )
            refs.append(_ref(document, occurrence.page, occurrence.section))
    return "\n".join(lines), refs


@tool(response_format="content_and_artifact")
def keyword_search(text: str, config: RunnableConfig) -> tuple[str, list[dict]]:
    """Woertliche Textsuche (ohne Beruecksichtigung von Gross-/Kleinschreibung), z.B. fuer
    Artikelnummern, Typbezeichnungen (3RT2016-1BB41), Kabelnamen (-W12) oder Symbolnamen
    aus dem SPS-Programm."""
    statement = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.content.ilike(f"%{text}%"))
        .order_by(Document.filename, Chunk.page)
        .limit(15)
    )
    statement = _scoped(statement, Chunk.source_id, config)
    with session_scope() as session:
        rows = session.execute(statement).all()
        if not rows:
            return f'Kein Abschnitt enthaelt "{text}".', []
        body = "\n\n".join(_format_chunk(document, chunk) for chunk, document in rows)
        refs = [_ref(document, chunk.page, chunk.section) for chunk, document in rows]
    return body, refs


@tool(response_format="content_and_artifact")
def get_page(document_id: str, page: int, config: RunnableConfig) -> tuple[str, list[dict]]:
    """Liefert den kompletten Text einer Seite (extrahierter Text + Vision-Beschreibung).
    Verwenden, um einem Querverweis (z.B. /12.3 -> Seite 12) zu folgen oder einen
    Suchtreffer im ganzen Seitenkontext zu lesen."""
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            return f"Dokument {document_id} nicht gefunden. list_documents zeigt gueltige IDs.", []
        chunks = session.scalars(
            select(Chunk)
            .where(Chunk.document_id == document_id, Chunk.page == page)
            .order_by(Chunk.kind, Chunk.id)
        ).all()
        if not chunks:
            return f"Seite {page} von {document.filename} hat keinen indexierten Text.", []
        text = "\n\n".join(_format_chunk(document, chunk) for chunk in chunks)
        return text, [_ref(document, page)]


@tool(response_format="content_and_artifact")
def view_page(document_id: str, page: int, config: RunnableConfig) -> tuple[list[dict], list[dict]]:
    """Zeigt dir eine PDF-Seite als Bild, damit du den Stromlaufplan selbst ansehen kannst:
    Strompfade verfolgen, Kontakte/Spulen zuordnen, Verdrahtung pruefen. Verwenden, wenn der
    Text nicht reicht oder eine Verbindung sicher bestaetigt werden muss."""
    with session_scope() as session:
        document = session.get(Document, document_id)
        if document is None:
            return [{"type": "text", "text": f"Dokument {document_id} nicht gefunden."}], []
        path, ref = Path(document.storage_path), _ref(document, page)
    if path.suffix.lower() != ".pdf":
        return [{"type": "text", "text": f"{ref['filename']} ist kein PDF - get_page nutzen."}], []
    try:
        png = render_page_png(path, page)
    except ValueError as exc:
        return [{"type": "text", "text": str(exc)}], []
    caption = {"type": "text", "text": f"{ref['filename']}, Seite {page}"}
    return [caption, image_block(png)], [ref]


@tool
def get_plc_block(block: str, config: RunnableConfig) -> str:
    """Liefert einen kompletten SPS-Baustein (Deklaration + alle Netzwerke) aus den
    AWL-Quellen, z.B. block="FB 10" oder "OB 1" oder ein Symbolname."""
    needle = " ".join(block.upper().replace('"', "").split())
    statement = (
        select(Chunk, Document)
        .join(Document, Chunk.document_id == Document.id)
        .where(Chunk.kind.in_(["awl_block", "awl_network"]))
        .order_by(Document.filename, Chunk.id)
    )
    statement = _scoped(statement, Chunk.source_id, config)
    with session_scope() as session:
        parts = []
        for chunk, document in session.execute(statement).all():
            label = " ".join(str(chunk.meta.get("block", "")).upper().replace('"', "").split())
            name, _, title = label.partition(" - ")
            symbolic_name = name.split(" ", 1)[-1]  # 'FB MOTOR' -> 'MOTOR'
            if needle in (name, symbolic_name) or (title and needle in title):
                parts.append(f"[{document.filename}] {chunk.content}")
    if not parts:
        return f"Baustein {block} nicht gefunden. keyword_search nach dem Namen versuchen."
    return "\n\n".join(parts)


@tool
def list_documents(config: RunnableConfig) -> str:
    """Listet die Dokumente der gewaehlten Wissensquellen mit document_id, Typ und Seitenzahl."""
    statement = (
        select(Document, KnowledgeSource)
        .join(KnowledgeSource, Document.source_id == KnowledgeSource.id)
        .order_by(KnowledgeSource.name, Document.filename)
    )
    statement = _scoped(statement, Document.source_id, config)
    with session_scope() as session:
        rows = session.execute(statement).all()
        if not rows:
            return "Keine Dokumente vorhanden."
        return "\n".join(
            f"- {source.name} / {document.filename} | typ={document.doc_type} | "
            f"seiten={document.page_count or '-'} | status={document.status}"
            f"{'' if document.status == DocStatus.READY else ' (nicht durchsuchbar)'} | "
            f"document_id={document.id}"
            for document, source in rows
        )


TOOLS = [search_knowledge, find_tag, keyword_search, get_page, view_page, get_plc_block, list_documents]
