"""SPS-Erklaerer: AWL-Netzwerke im Klartext und Rueckverfolgung eines Ausgangs, deterministisch, ohne Modell."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.signal import graph_for_source
from app.db import get_session
from app.ingestion.awl_explain import explain_awl, resolve_output, why_not
from app.ingestion.awl_parser import parse_symbol_table, read_text
from app.ingestion.signal_graph import _address
from app.models import Document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/awl", tags=["awl"])


def load_program(session: Session, source_id: str) -> tuple[str, dict[str, str]]:
    """AWL-Text und Symbol -> Adresse aller Dokumente der Quelle."""
    texts, symbols = [], {}
    for doc in session.scalars(select(Document).where(Document.source_id == source_id)).all():
        path = Path(doc.storage_path)
        if not path.exists():
            continue
        try:
            if doc.doc_type == "plc_program" or path.suffix.lower() == ".awl":
                texts.append(read_text(path))
            elif doc.doc_type == "plc_symbols" or path.suffix.lower() == ".sdf":
                for row in parse_symbol_table(read_text(path)):
                    if address := _address(row["address"]):
                        symbols[row["symbol"]] = address
        except Exception:  # noqa: BLE001 - kaputte Datei: Erklaerung ohne sie
            logger.warning("AWL-Erklaerer ohne %s", path.name, exc_info=True)
    return "\n".join(texts), symbols


def _no_program() -> HTTPException:
    return HTTPException(404, detail={"reason": "no_program", "message": "Kein SPS-Programm (AWL) in dieser Quelle."})


@router.get("/networks")
def get_networks(source_id: str, session: Session = Depends(get_session)):
    """Alle Netzwerke der AWL-Quellen im Klartext."""
    text, symbols = load_program(session, source_id)
    networks = explain_awl(text, symbols)
    if not networks:
        raise _no_program()
    return {"networks": networks}


@router.get("/why")
def get_why(source_id: str, output: str, session: Session = Depends(get_session)):
    """Warum kommt Ausgang `output` (Adresse, Symbol) nicht? Alle Eingaenge seiner Netzwerke samt Klemme."""
    text, symbols = load_program(session, source_id)
    networks = explain_awl(text, symbols)
    if not networks:
        raise _no_program()
    graph, _schematic = graph_for_source(session, source_id)
    target = resolve_output(graph, symbols, output)
    if target is None:
        raise HTTPException(404, detail={"reason": "unknown_output", "message": f"{output} kommt im Programm nicht vor."})
    result = why_not(graph, networks, target)
    if not result["networks"]:
        raise HTTPException(
            404, detail={"reason": "not_written", "message": f"Kein Netzwerk schreibt {output}."}
        )
    return result
