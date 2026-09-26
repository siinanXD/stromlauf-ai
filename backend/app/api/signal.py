"""Signalweg eines Kennzeichens, deterministisch aus den Dokumenten einer Wissensquelle."""

import csv
import io
from functools import lru_cache
from pathlib import Path

import openpyxl
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.ingestion.awl_parser import parse_symbol_table, read_text
from app.ingestion.signal_graph import Graph, build_graph, signal_path
from app.models import Document

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
    sheet = openpyxl.load_workbook(path, read_only=True, data_only=True).active
    rows = [[str(c).strip() if c is not None else "" for c in row] for row in sheet.iter_rows(values_only=True)]
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


@lru_cache(maxsize=16)
def _graph(files: tuple[tuple[str, str, float], ...]) -> Graph:
    """files: (doc_type, Pfad, mtime); mtime nur als Cache-Schluessel."""
    terminal_rows: list[list[str]] = []
    bom_rows: list[tuple[str, str, str]] = []
    symbols: list[dict[str, str]] = []
    awl = []
    for doc_type, raw_path, _mtime in files:
        path = Path(raw_path)
        suffix = path.suffix.lower()
        try:
            if doc_type == "terminal_plan" and suffix in {".csv", ".txt"}:
                terminal_rows += _terminal_rows(path)
            elif doc_type == "bom" and suffix in {".xlsx", ".xlsm"}:
                bom_rows += _bom_rows(path)
            elif doc_type == "plc_symbols" or suffix == ".sdf":
                symbols += parse_symbol_table(read_text(path))
            elif doc_type == "plc_program" or suffix == ".awl":
                awl.append(read_text(path))
        except (OSError, ValueError, KeyError):
            continue  # unlesbare Datei: Graph ohne sie
    return build_graph(terminal_rows, bom_rows, symbols, "\n".join(awl))


def graph_for_source(session: Session, source_id: str) -> tuple[Graph, Document | None]:
    documents = session.scalars(select(Document).where(Document.source_id == source_id)).all()
    files = tuple(
        sorted(
            (d.doc_type, d.storage_path, Path(d.storage_path).stat().st_mtime)
            for d in documents
            if d.doc_type in {"terminal_plan", "bom", "plc_symbols", "plc_program"} and Path(d.storage_path).exists()
        )
    )
    schematic = next((d for d in documents if d.doc_type == "schematic" and d.filename.lower().endswith(".pdf")), None)
    return _graph(files), schematic


@router.get("/signal-path")
def get_signal_path(tag: str, source_id: str, session: Session = Depends(get_session)):
    graph, schematic = graph_for_source(session, source_id)
    if not graph.nodes:
        raise HTTPException(404, "Kein Klemmenplan, keine Symboltabelle und kein AWL-Programm in dieser Quelle")
    path = signal_path(graph, tag)
    if path is None:
        raise HTTPException(404, f"{tag} kommt im Klemmenplan bzw. SPS-Programm nicht vor")
    path["schematic"] = {"document_id": schematic.id, "filename": schematic.filename} if schematic else None
    return path
