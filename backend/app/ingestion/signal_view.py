"""Hauptweg eines Kennzeichens in festen Spalten (Stoerfall-Arbeitsflaeche, `GET /api/signal-path?view=main`).

Statt der ganzen Nachbarschaft zeigt die Sicht einen Weg: rueckwaerts der kuerzeste Weg ueber gerichtete Kanten bis
zu einem Knoten ohne Vorgaenger, vorwaerts bis zu einem ohne Nachfolger; bei Gleichstand gewinnt die lexikografisch
kleinste Folge der Knoten-IDs. Nachbarn abseits des Wegs stehen eine Stufe tief als Abzweige daneben.

Anschluesse (Knoten der Art "pin") gehen in ihrem Geraet auf; ihre Nummer steht an der Kante (`pins.from`,
`pins.to`). Die Spalte eines Knotens folgt aus seiner Art und seiner Lage zum ersten SPS-Knoten des Wegs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ingestion.signal_graph import HUB_DEGREE, MAX_DEPTH, Graph, _start_id

COLUMNS = (
    "feld",
    "klemme_vor",
    "sps_eingang",
    "programm",
    "sps_ausgang",
    "klemme_nach",
    "schaltgeraet",
    "verbraucher",
)
PLC_KINDS = {"address", "network", "variable"}
_BIT_INPUT = re.compile(r"E\d+\.[0-7]")
_BIT_OUTPUT = re.compile(r"A\d+\.[0-7]")


@dataclass
class _Edge:
    via: set[str] = field(default_factory=set)
    directed: bool = True
    pin_from: str | None = None
    pin_to: str | None = None


def _owner(graph: Graph, node_id: str) -> str:
    """Ein Anschluss geht in seinem Geraet auf ("-K1:A1" -> "-K1")."""
    node = graph.nodes.get(node_id)
    return node_id.split(":", 1)[0] if node is not None and node.kind == "pin" else node_id


def _pin(graph: Graph, node_id: str) -> str | None:
    node = graph.nodes.get(node_id)
    return node_id.split(":", 1)[1] if node is not None and node.kind == "pin" else None


def _collapsed(graph: Graph) -> dict[tuple[str, str], _Edge]:
    """Kanten zwischen Geraeten, Klemmen, Adressen und Programmteilen; Anschlussnummern an der Kante."""
    edges: dict[tuple[str, str], _Edge] = {}
    for (source, target), via in sorted(graph.edges.items()):
        a, b = _owner(graph, source), _owner(graph, target)
        if a == b:
            continue  # Geraet -> eigener Anschluss
        directed = (source, target) not in graph.undirected
        pair = (min(a, b), max(a, b))
        if directed:
            key = (a, b)
            if pair != key and pair in edges and not edges[pair].directed:
                old = edges.pop(
                    pair
                )  # bisher ohne Richtung, jetzt bekannt: Anschluesse tauschen die Seite
                edges[key] = _Edge(old.via, True, old.pin_to, old.pin_from)
        else:
            key = next((k for k in ((a, b), (b, a)) if k in edges), pair)
        edge = edges.setdefault(key, _Edge(directed=directed))
        edge.via |= via
        edge.directed = edge.directed or directed
        ends = {a: _pin(graph, source), b: _pin(graph, target)}
        edge.pin_from = edge.pin_from or ends[key[0]]
        edge.pin_to = edge.pin_to or ends[key[1]]
    return edges


def _shortest(start: str, step: dict[str, list[str]], degree: dict[str, int]) -> list[str]:
    """Kuerzester Weg ab start bis zu einem Knoten ohne weiteren Schritt; Gleichstand: kleinste Folge der IDs.
    Knoten mit mehr als HUB_DEGREE Kanten und Knoten in MAX_DEPTH werden nicht weiter verfolgt; sie zaehlen nur, wenn
    kein echtes Ende erreichbar ist."""
    paths = {start: (start,)}
    layer = [start]
    ends: list[tuple[str, ...]] = []
    blocked: list[tuple[str, ...]] = []
    for depth in range(MAX_DEPTH + 1):
        following: list[str] = []
        for current in sorted(layer, key=lambda n: paths[n]):
            nexts = step.get(current, [])
            if not nexts:
                if current != start:
                    ends.append(paths[current])
                continue
            if depth == MAX_DEPTH or (current != start and degree.get(current, 0) > HUB_DEGREE):
                blocked.append(paths[current])
                continue
            fresh = [n for n in sorted(nexts) if n not in paths]
            if not fresh and current != start:
                blocked.append(paths[current])  # nur Rueckwege: Ende eines Kreises (Selbsthaltung)
            for nxt in fresh:
                paths[nxt] = paths[current] + (nxt,)
                following.append(nxt)
        if ends or not following:
            break
        layer = following
    found = ends or blocked
    return list(min(found, key=lambda p: (len(p), p))) if found else [start]


def _column(
    graph: Graph, node_id: str, order: int, first_plc: int | None, start: int, last: bool
) -> str:
    node = graph.nodes[node_id]
    if node.kind == "address":
        if _BIT_INPUT.fullmatch(node_id):
            return "sps_eingang"
        if _BIT_OUTPUT.fullmatch(node_id):
            return "sps_ausgang"
        return "programm"  # Merker, Woerter
    if node.kind in ("network", "variable"):
        return "programm"
    before = order < first_plc if first_plc is not None else order < start
    if node.kind == "terminal":
        return "klemme_vor" if before else "klemme_nach"
    if before:
        return "feld"
    return "verbraucher" if last else "schaltgeraet"


def _node(graph: Graph, node_id: str, **extra) -> dict:
    node = graph.nodes[node_id]
    return {
        "id": node.id,
        "kind": node.kind,
        "label": node.label,
        "ref": node.ref,
        "detail": node.detail,
        **extra,
    }


def main_view(graph: Graph, tag: str) -> dict | None:
    """Hauptweg nach dem Vertrag der Stoerfall-Arbeitsflaeche; None, wenn das Kennzeichen nicht vorkommt."""
    found = _start_id(graph, tag)
    if found is None:
        return None
    start = _owner(graph, found)
    if start not in graph.nodes:
        return None
    edges = _collapsed(graph)
    successors: dict[str, list[str]] = {}
    predecessors: dict[str, list[str]] = {}
    neighbours: dict[str, set[str]] = {}
    for (a, b), edge in edges.items():
        neighbours.setdefault(a, set()).add(b)
        neighbours.setdefault(b, set()).add(a)
        if edge.directed:
            successors.setdefault(a, []).append(b)
            predecessors.setdefault(b, []).append(a)
    degree = {n: len(successors.get(n, [])) + len(predecessors.get(n, [])) for n in neighbours}
    backward = _shortest(start, predecessors, degree)
    forward = _shortest(start, successors, degree)
    path = list(reversed(backward)) + forward[1:]
    on_path = {node_id: index for index, node_id in enumerate(path)}
    start_at = on_path[start]
    first_plc = next((i for i, n in enumerate(path) if graph.nodes[n].kind in PLC_KINDS), None)

    nodes = []
    for index, node_id in enumerate(path):
        outside = sorted(neighbours.get(node_id, set()) - set(on_path))
        column = _column(graph, node_id, index, first_plc, start_at, index == len(path) - 1)
        nodes.append(
            _node(
                graph,
                node_id,
                main=True,
                column=column,
                order=index,
                branches=len(outside),
                parent=None,
            )
        )
    shown = set(on_path)
    for node_id in path:
        for other in sorted(neighbours.get(node_id, set()) - shown):
            shown.add(other)
            hidden = neighbours.get(other, set()) - set(on_path) - {other}
            nodes.append(
                _node(
                    graph,
                    other,
                    main=False,
                    column=None,
                    order=None,
                    branches=len(hidden),
                    parent=node_id,
                )
            )
    occupied = {node["column"] for node in nodes if node["main"]}
    return {
        "start": start,
        "view": "main",
        "columns": [column for column in COLUMNS if column in occupied],
        "nodes": nodes,
        "edges": [
            {
                "source": a,
                "target": b,
                "via": sorted(edge.via),
                "directed": edge.directed,
                "pins": {"from": edge.pin_from, "to": edge.pin_to},
            }
            for (a, b), edge in sorted(edges.items())
            if a in shown and b in shown
        ],
    }
