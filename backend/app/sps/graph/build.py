"""Signalfluss-Graph aus dem Baustein-Modell (SIN-724).

Knoten sind Operanden (Ein-/Ausgang, Merker, Timer, Zaehler, Bausteinvariable) und Bausteine. Eine Kante
`a -> b` heisst: `a` beeinflusst `b`. Das Modell kennt je Netzwerk, welche Operanden gelesen und welche
geschrieben werden, nicht aber die Verknuepfungsstruktur. Deshalb beeinflusst im Netzwerk jeder gelesene
Operand jeden geschriebenen (konservativ: lieber eine Kante zu viel als eine Abhaengigkeit uebersehen). Die
Kante merkt sich, wie: die Befehle des Lesers (`U`, `UN`, `O` ... als UND, UND NICHT, ODER) und die des
Schreibers (`=` zuweisen, `S` setzen, `R` ruecksetzen, `FP`/`FN` Flanke, `SE`... Timer, `ZV`... Zaehler).
Vergleicher stehen als Abhaengigkeit der geladenen Operanden da, die Vergleichsart nicht.

Aufrufe (`CALL FB 10, DB 10`) loesen die uebergebenen Parameter auf: der aktuelle Operand des Aufrufers
haengt am formalen Parameter des Aufgerufenen (Eingang: Aufrufer -> Parameter, Ausgang: Parameter ->
Aufrufer, Durchgang: beides). Die Richtung steht in der Schnittstelle des Bausteins; ist er nicht im
Programm, gilt SCL `=>` als Ausgang und alles andere als Eingang.
"""

import re
from collections import deque
from dataclasses import dataclass

import networkx as nx

from app.ingestion.plc_blocks import PlcProgram, absolute_address

# Schreibender Befehl -> Art der Kante
WRITE_KINDS = {
    "=": "assign", ":=": "assign", "T": "transfer", "S": "set", "R": "reset", "FP": "edge", "FN": "edge",
    "SE": "timer", "SD": "timer", "SS": "timer", "SF": "timer", "SP": "timer", "SA": "timer",
    "ZV": "counter", "ZR": "counter", "CU": "counter", "CD": "counter", "SI": "counter", "SV": "counter",
    "SO": "counter",
}
# Lesender Befehl -> Klartext
READ_LOGIC = {
    "U": "UND", "A": "UND", "UN": "UND NICHT", "AN": "UND NICHT", "O": "ODER", "ON": "ODER NICHT",
    "X": "XOR", "XN": "XOR NICHT", "L": "laden",
}
STRUCTURAL = "call"  # Kante Aufrufer -> Aufgerufener, kein Signalfluss
_SECTION_DIRECTION = {"VAR_INPUT": "in", "VAR_OUTPUT": "out", "VAR_IN_OUT": "both"}
_AREA_KIND = {"E": "input", "A": "output", "M": "memory", "T": "timer", "Z": "counter", "D": "data"}


def _norm_block(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().strip('"')).upper()


def _block_key(name: str) -> str:
    return f"block:{name}"


def _operand_key(scope: str, display: str, address: str | None, block: str) -> str:
    if scope == "local":
        return f"{block}:{display}"
    return address or display


def _operand_kind(scope: str, address: str | None) -> str:
    if address:
        return _AREA_KIND.get(address[0], "other")
    return "local" if scope == "local" else "symbol"


def _label(scope: str, display: str, address: str | None, block: str) -> str:
    if scope == "local":
        return f"{block}: {display}"
    return f"{display} ({address})" if address and address != display else display


class FlowGraph:
    """Der Graph samt Abfragen. `graph` ist ein `networkx.DiGraph`."""

    def __init__(self, graph: nx.DiGraph):
        self.graph = graph

    # --- Aufloesen ---

    def resolve(self, operand: str) -> str:
        """Knoten-ID zu Adresse (`A 4.0`, `a4.0`, `Q4.0`), Symbolname, `Block: Name` oder Knoten-ID."""
        g = self.graph
        text = operand.strip()
        if text in g:
            return text
        address = absolute_address(text)
        if address and address in g:
            return address
        wanted = text.strip('"#').casefold()
        hits = [
            n for n, d in g.nodes(data=True)
            if d["kind"] != "block" and wanted in {d["name"].casefold(), d["label"].casefold(), n.casefold()}
        ]
        if len(hits) == 1:
            return hits[0]
        if not hits:
            raise KeyError(f"Operand nicht im Graph: {operand}")
        raise ValueError(f"Operand nicht eindeutig: {operand} ({', '.join(sorted(hits))})")

    # --- Abfragen ---

    def _walk(self, start: str, step, depth: int | None) -> list[dict]:
        seen = {start: 0}
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if depth is not None and seen[node] >= depth:
                continue
            for other, data in step(node):
                if other not in seen and data["kinds"] != [STRUCTURAL]:
                    seen[other] = seen[node] + 1
                    queue.append(other)
        out = [self._reach(n, d) for n, d in seen.items() if n != start]
        return sorted(out, key=lambda r: (r["depth"], r["id"]))

    def _reach(self, node: str, depth: int) -> dict:
        d = self.graph.nodes[node]
        return {"id": node, "label": d["label"], "kind": d["kind"], "depth": depth}

    def upstream(self, operand: str, depth: int | None = None) -> list[dict]:
        """Alles, was `operand` beeinflusst (Ursachen), mit kuerzestem Abstand; `depth=None` = unbegrenzt."""
        g = self.graph
        return self._walk(self.resolve(operand), lambda n: ((p, g.edges[p, n]) for p in g.predecessors(n)), depth)

    def downstream(self, operand: str, depth: int | None = None) -> list[dict]:
        """Alles, worauf `operand` wirkt (Folgen), mit kuerzestem Abstand."""
        g = self.graph
        return self._walk(self.resolve(operand), lambda n: ((s, g.edges[n, s]) for s in g.successors(n)), depth)

    def sources(self, operand: str) -> list[dict]:
        """Die Enden der Ursachenkette: Knoten, in die kein Signal mehr hineinlaeuft (Sensoren, Taster, Panel)."""
        g = self.graph
        return [
            r for r in self.upstream(operand)
            if not any(p != r["id"] and g.edges[p, r["id"]]["kinds"] != [STRUCTURAL] for p in g.predecessors(r["id"]))
        ]


@dataclass
class _Builder:
    blocks: list[dict]

    def __post_init__(self):
        self.g = nx.DiGraph()
        self.by_name = {_norm_block(b["name"]): b for b in self.blocks}

    def node(self, key: str, **attrs) -> str:
        if key not in self.g:
            self.g.add_node(key, **attrs)
        return key

    def operand(self, block: dict, op: dict) -> str:
        scope, display, address = op["scope"], op["display"], op["address"]
        key = _operand_key(scope, display, address, block["name"])
        return self.node(key, name=display, label=_label(scope, display, address, block["name"]),
                         kind=_operand_kind(scope, address), scope=scope, address=address,
                         block=block["name"] if scope == "local" else None)

    def block(self, name: str, kind: str = "") -> str:
        return self.node(_block_key(name), name=name, label=name, kind="block", scope="block", address=None,
                         block=None, block_kind=kind)

    def edge(self, src: str, dst: str, kinds: list[str], logic: list[str], where: str) -> None:
        if self.g.has_edge(src, dst):
            data = self.g.edges[src, dst]
            data["kinds"] = sorted({*data["kinds"], *kinds})
            data["logic"] = sorted({*data["logic"], *logic})
            if where not in data["where"]:
                data["where"].append(where)
        else:
            self.g.add_edge(src, dst, kinds=sorted(set(kinds)), logic=sorted(set(logic)), where=[where])

    def run(self) -> nx.DiGraph:
        for block in self.blocks:
            self.block(block["name"], block["kind"])
        for block in self.blocks:
            for network in block["networks"]:
                where = f"{block['name']} NW {network['number']}"
                self.logic(block, network, where)
                for call in network.get("calls", []):
                    self.call(block, call, where)
        return self.g

    def logic(self, block: dict, network: dict, where: str) -> None:
        operands = network["operands"]
        has_calls = bool(network.get("calls"))
        reads = [o for o in operands if "read" in o["roles"]]
        # Ohne Befehl ist ein Schreibzugriff in einem Aufruf nur ein Ausgangsparameter (SCL `=>`)
        writes = [o for o in operands if "write" in o["roles"] and (o.get("ops") or not has_calls)]
        if not writes:
            for op in reads:
                self.operand(block, op)
            return
        targets = [(self.operand(block, w), w) for w in writes]
        for op in reads:
            source = self.operand(block, op)
            logic = [READ_LOGIC.get(c, c) for c in op.get("ops", []) if c not in WRITE_KINDS or c in READ_LOGIC]
            for target, w in targets:
                kinds = [WRITE_KINDS[c] for c in w.get("ops", []) if c in WRITE_KINDS] or ["assign"]
                self.edge(source, target, kinds, logic, where)

    def call(self, block: dict, call: dict, where: str) -> None:
        callee = self.by_name.get(_norm_block(call["target"]))
        callee_name = callee["name"] if callee else call["target"]
        callee_node = self.block(callee_name, callee["kind"] if callee else "")
        self.edge(self.block(block["name"]), callee_node, [STRUCTURAL], [], where)
        sections = {m["name"]: m["section"] for m in callee["interface"]} if callee else {}
        for arg in call["args"]:
            actual = self.operand(block, {"scope": arg["scope"], "display": arg["value"], "address": arg["address"]})
            if callee:
                formal = self.operand(callee, {"scope": "local", "display": arg["param"], "address": None})
            else:
                formal = callee_node
            direction = _SECTION_DIRECTION.get(sections.get(arg["param"], ""), arg["direction"] or "in")
            if direction in ("in", "both"):
                self.edge(actual, formal, ["param"], [], where)
            if direction in ("out", "both"):
                self.edge(formal, actual, ["param"], [], where)


def build_graph(program: PlcProgram | dict) -> FlowGraph:
    """Graph aus `PlcProgram` oder dem Dict von `PlcProgram.to_dict()` (Schema `plc_blocks.schema.json`)."""
    data = program.to_dict() if isinstance(program, PlcProgram) else program
    return FlowGraph(_Builder(data["blocks"]).run())
