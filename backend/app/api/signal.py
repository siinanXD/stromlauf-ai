"""Signalweg eines Kennzeichens, deterministisch aus den Dokumenten einer Wissensquelle.

Quellen: Klemmenplan, Stueckliste, Symboltabelle und AWL; dazu die Kanten aus Stromlaufplan-PDFs (Leitungen bzw. Lage
im Plan, `plan_wires.plan_edges`, und ein optionaler Modelllauf, `plan_edges.read_model_edges`). So hat auch eine
Maschine, deren Dokumentation nur aus dem Plan besteht, einen Signalweg.
"""

import csv
import io
import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

import openpyxl
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.ingestion.awl_parser import parse_symbol_table, read_text
from app.ingestion.plan_edges import read_model_edges
from app.ingestion.plan_wires import plan_edges
from app.ingestion.signal_graph import Graph, add_plan_edges, build_graph, signal_path
from app.ingestion.signal_view import main_view
from app.models import Document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["signal"])

TERMINAL_COLUMNS = ("klemmleiste", "klemme", "ziel intern", "ziel extern", "funktion", "blatt")


def _terminal_rows(path: Path) -> list[list[str]]:
    """Klemmenplan-CSV in die Spaltenfolge Leiste; Klemme; intern; extern; Funktion; Blatt bringen."""
    text = read_text(path)
    delimiter = ";" if text.count(";") >= text.count(",") else ","
    rows = [[cell.strip() for cell in row] for row in csv.reader(io.StringIO(text), delimiter=delimiter)]
    header = next((row for row in rows if any(c.lower() == "klemme" for c in row)), None)
    if header is None:
        return rows
    index = [next((i for i, c in enumerate(header) if c.lower().startswith(name)), None) for name in TERMINAL_COLUMNS]
    return [[row[i] if i is not None and i < len(row) else "" for i in index] for row in rows if row is not header]


def _bom_rows(path: Path) -> list[tuple[str, str, str]]:
    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        rows = [[str(c).strip() if c is not None else "" for c in row] for row in workbook.active.iter_rows(values_only=True)]
    finally:
        workbook.close()
    header_at = next((i for i, row in enumerate(rows) if any(c.upper() == "BMK" for c in row)), None)
    if header_at is None:
        return []
    header = [c.lower() for c in rows[header_at]]
    tag_col = header.index("bmk")
    title_col = next((i for i, c in enumerate(header) if c.startswith("bezeichnung")), tag_col + 1)
    ref_col = next((i for i, c in enumerate(header) if c.startswith("blatt")), None)
    return [
        (row[tag_col], row[title_col] if title_col < len(row) else "", row[ref_col] if ref_col is not None and ref_col < len(row) else "")
        for row in rows[header_at + 1 :]
        if len(row) > tag_col and row[tag_col].startswith("-")
    ]


TABLE_TYPES = {"terminal_plan", "bom", "plc_symbols", "plc_program"}


def _is_plan(doc_type: str, path: str) -> bool:
    return doc_type == "schematic" and path.lower().endswith(".pdf")


def _graph_input(doc_type: str, path: str) -> bool:
    return doc_type in TABLE_TYPES or _is_plan(doc_type, path)


def _model_stamp() -> int:
    """Stand der Modelllaeufe (data/plan_cache/model): neuer Lauf, neuer Graph, auch wenn das PDF gleich bleibt."""
    directory = get_settings().data_dir / "plan_cache" / "model"
    if not directory.exists():
        return 0
    return max((f.stat().st_mtime_ns for f in directory.glob("*.json")), default=0)


@lru_cache(maxsize=16)
def _graph(files: tuple[tuple[str, str, float], ...], model_stamp: int = 0) -> Graph:
    """files: (doc_type, Pfad, mtime); mtime und model_stamp nur als Cache-Schluessel."""
    terminal_rows: list[list[str]] = []
    bom_rows: list[tuple[str, str, str]] = []
    symbols: list[dict[str, str]] = []
    awl = []
    plans = []
    for doc_type, raw_path, _mtime in files:
        path = Path(raw_path)
        suffix = path.suffix.lower()
        try:
            if _is_plan(doc_type, raw_path):
                plans += plan_edges(path) + read_model_edges(path)
            elif doc_type == "terminal_plan" and suffix in {".csv", ".txt"}:
                terminal_rows += _terminal_rows(path)
            elif doc_type == "bom" and suffix in {".xlsx", ".xlsm"}:
                bom_rows += _bom_rows(path)
            elif doc_type == "plc_symbols" or suffix == ".sdf":
                symbols += parse_symbol_table(read_text(path))
            elif doc_type == "plc_program" or suffix == ".awl":
                awl.append(read_text(path))
        except Exception:  # noqa: BLE001 - kaputte/fremde Datei (BadZipFile, csv.Error ...): Graph ohne sie
            logger.warning("Signalweg ohne %s", path.name, exc_info=True)
            continue
    graph = build_graph(terminal_rows, bom_rows, symbols, "\n".join(awl))
    return add_plan_edges(graph, plans)


def graph_for_source(session: Session, source_id: str) -> tuple[Graph, Document | None]:
    documents = session.scalars(select(Document).where(Document.source_id == source_id)).all()
    files = tuple(
        sorted(
            (d.doc_type, d.storage_path, Path(d.storage_path).stat().st_mtime)
            for d in documents
            if _graph_input(d.doc_type, d.storage_path) and Path(d.storage_path).exists()
        )
    )
    schematic = next((d for d in documents if d.doc_type == "schematic" and d.filename.lower().endswith(".pdf")), None)
    stamp = _model_stamp() if any(_is_plan(doc_type, path) for doc_type, path, _ in files) else 0
    return _graph(files, stamp), schematic


def _missing(reason: str, message: str) -> HTTPException:
    """404 mit Grund fuer den leeren Zustand der Signalweg-Ansicht (Vertrag der Stoerfall-Arbeitsflaeche)."""
    return HTTPException(404, detail={"reason": reason, "message": message})


@router.get("/signal-path")
def get_signal_path(
    tag: str,
    source_id: str,
    view: Literal["main"] | None = None,
    session: Session = Depends(get_session),
):
    graph, schematic = graph_for_source(session, source_id)
    if not graph.nodes:
        raise _missing("no_sources", "Keine Tabellen und keine Leitungen im Plan gefunden.")
    path = main_view(graph, tag) if view == "main" else signal_path(graph, tag)
    if path is None:
        raise _missing("unknown_tag", f"{tag} kommt im Signalweg nicht vor.")
    path["schematic"] = {"document_id": schematic.id, "filename": schematic.filename} if schematic else None
    return path
