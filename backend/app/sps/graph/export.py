"""Export des Signalfluss-Graphen: `graph.json` und Mermaid-Text (SIN-724).

Mermaid zeigt hoechstens `MAX_NODES` Knoten je Ansicht, damit die GitHub-Vorschau lesbar bleibt. Ist der
Graph groesser, entsteht ein Teilgraph: mit Fokus die naechsten Knoten um den Operanden (Ursachen und
Folgen nach Abstand), sonst die am staerksten vernetzten. Bausteinknoten und Aufrufkanten fehlen in der
Ansicht, sie sind Struktur und kein Signalfluss.
"""

import json
from pathlib import Path

from app.sps.graph.build import STRUCTURAL, FlowGraph

MAX_NODES = 50
_SHAPES = {"timer": ("(", ")"), "counter": ("(", ")")}
_CLASSES = {
    "input": "fill:#dbeafe,stroke:#1d4ed8",
    "output": "fill:#dcfce7,stroke:#15803d",
    "timer": "fill:#fef3c7,stroke:#b45309",
    "counter": "fill:#fef3c7,stroke:#b45309",
    "focus": "fill:#ffedd5,stroke:#c2410c,stroke-width:3px",
}


def to_json(fg: FlowGraph) -> dict:
    """Strukturierter Export (`graph.json`): Knoten und Kanten mit allen Merkmalen, sortiert und damit stabil."""
    g = fg.graph
    nodes = [{"id": n, **d} for n, d in sorted(g.nodes(data=True))]
    edges = [{"source": s, "target": t, **d} for s, t, d in sorted(g.edges(data=True), key=lambda e: e[:2])]
    return {"version": 1, "nodes": nodes, "edges": edges}


def write_json(fg: FlowGraph, path: Path | str) -> None:
    Path(path).write_text(json.dumps(to_json(fg), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _data_edges(fg: FlowGraph) -> list[tuple[str, str, dict]]:
    g = fg.graph
    return [(s, t, d) for s, t, d in g.edges(data=True) if d["kinds"] != [STRUCTURAL]]


def _pick(fg: FlowGraph, focus: str | None, depth: int | None, max_nodes: int) -> tuple[list[str], int, str | None]:
    g = fg.graph
    data_nodes = sorted(n for n, d in g.nodes(data=True) if d["kind"] != "block")
    if focus:
        start = fg.resolve(focus)
        reach = sorted(fg.upstream(start, depth) + fg.downstream(start, depth), key=lambda r: (r["depth"], r["id"]))
        chosen = [start] + [r["id"] for r in reach if r["id"] != start]
        return chosen[:max_nodes], len(chosen), start
    if len(data_nodes) <= max_nodes:
        return data_nodes, len(data_nodes), None
    degree = {n: 0 for n in data_nodes}
    for s, t, _ in _data_edges(fg):
        degree[s] += 1
        degree[t] += 1
    chosen = sorted(data_nodes, key=lambda n: (-degree[n], n))
    return sorted(chosen[:max_nodes]), len(data_nodes), None


def _text(value: str) -> str:
    return value.replace('"', "#quot;").replace("\n", " ")


def to_mermaid(fg: FlowGraph, focus: str | None = None, depth: int | None = None, max_nodes: int = MAX_NODES) -> str:
    """Mermaid-Flussdiagramm (ohne ```-Zaun). Mit `focus` Ursachen und Folgen dieses Operanden bis `depth`."""
    g = fg.graph
    chosen, total, start = _pick(fg, focus, depth, max_nodes)
    ids = {n: f"n{i}" for i, n in enumerate(sorted(chosen))}
    lines = ["flowchart LR"]
    if len(chosen) < total:
        scope = f" um {g.nodes[start]['label']}" if start else ""
        lines.append(f"%% Teilgraph{scope}: {len(chosen)} von {total} Knoten")
    for n in sorted(chosen):
        d = g.nodes[n]
        left, right = _SHAPES.get(d["kind"], ("[", "]"))
        lines.append(f'    {ids[n]}{left}"{_text(d["label"])}"{right}')
    for s, t, d in _data_edges(fg):
        if s in ids and t in ids:
            label = "/".join(k for k in d["kinds"] if k not in ("assign", "param"))
            arrow = f"-->|{_text(label)}|" if label else "-->"
            lines.append(f"    {ids[s]} {arrow} {ids[t]}")
    by_class: dict[str, list[str]] = {}
    for n in chosen:
        kind = g.nodes[n]["kind"]
        if kind in _CLASSES:
            by_class.setdefault(kind, []).append(ids[n])
    if start and start in ids:
        by_class.setdefault("focus", []).append(ids[start])
    for cls, members in by_class.items():
        lines.append(f"    classDef {cls} {_CLASSES[cls]}")
        lines.append(f"    class {','.join(members)} {cls}")
    return "\n".join(lines) + "\n"
