"""Kanten aus dem Stromlaufplan: gemeinsames Format fuer Leitungsleser und Modell (Stoerfall-Arbeitsflaeche).

Der Leitungsleser (`plan_wires`) und das optionale Modell (`plan_model`) liefern dieselben Kanten; der Signalgraph
liest beide ueber diese Funktionen. Gespeichert wird je Datei unter `data_dir/plan_cache/`, Schluessel ist der
SHA-256 der Dateibytes, damit ein neu hochgeladener Plan nie alte Kanten bekommt.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from app.config import get_settings

# Erhoehen, sobald sich die Regeln des Leitungslesers aendern: alte Cache-Dateien gelten dann nicht mehr.
PLAN_READER_VERSION = 1
VIA = ("leitung", "lage", "modell")


@dataclass(frozen=True)
class PlanEdge:
    source: str  # Knoten-ID wie im Signalgraphen: "-S1", "-K1:A1", "-X1:3", "E0.3"
    target: str
    page: int  # PDF-Seite, 1-basiert
    via: str  # "leitung" | "lage" | "modell"
    directed: bool = True  # False: Richtung unklar -> nur Abzweig, nie Hauptweg


def _cache_dir() -> Path:
    return get_settings().data_dir / "plan_cache"


def file_key(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _to_json(edges: list[PlanEdge]) -> list[dict]:
    return [asdict(edge) for edge in edges]


def _from_json(rows: list[dict]) -> list[PlanEdge]:
    return [PlanEdge(**row) for row in rows]


def read_edges(path: Path) -> list[PlanEdge] | None:
    """Kanten des Leitungslesers aus dem Cache; None, wenn fuer diese Datei und Version noch nichts gerechnet ist."""
    target = _cache_dir() / f"{file_key(path)}-v{PLAN_READER_VERSION}.json"
    if not target.exists():
        return None
    return _from_json(json.loads(target.read_text(encoding="utf-8")))


def write_edges(path: Path, edges: list[PlanEdge]) -> None:
    directory = _cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{file_key(path)}-v{PLAN_READER_VERSION}.json"
    target.write_text(json.dumps(_to_json(edges), ensure_ascii=False), encoding="utf-8")


def read_model_edges(path: Path) -> list[PlanEdge]:
    """Kanten eines Modelllaufs fuer diese Datei, neueste Prompt-Version zuerst; [] ohne Lauf."""
    directory = _cache_dir() / "model"
    if not directory.exists():
        return []
    files = sorted(
        directory.glob(f"{file_key(path)}-*.json"), key=lambda f: f.stat().st_mtime, reverse=True
    )
    if not files:
        return []
    return _from_json(json.loads(files[0].read_text(encoding="utf-8"))["edges"])


def write_model_edges(path: Path, prompt_version: str, edges: list[PlanEdge], meta: dict) -> None:
    """meta: model, pages, dropped, cost_usd. Bleibt neben den Kanten stehen, damit der Status ohne Lauf lesbar ist."""
    directory = _cache_dir() / "model"
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{file_key(path)}-{prompt_version}.json"
    payload = {"meta": meta, "edges": _to_json(edges)}
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def read_model_meta(path: Path) -> dict | None:
    """meta des neuesten Modelllaufs fuer diese Datei; None ohne Lauf."""
    directory = _cache_dir() / "model"
    if not directory.exists():
        return None
    files = sorted(
        directory.glob(f"{file_key(path)}-*.json"), key=lambda f: f.stat().st_mtime, reverse=True
    )
    if not files:
        return None
    return json.loads(files[0].read_text(encoding="utf-8"))["meta"]
