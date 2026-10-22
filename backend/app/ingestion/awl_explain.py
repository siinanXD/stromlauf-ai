"""AWL-Netzwerke im Klartext und Rueckverfolgung eines Ausgangs ("Warum kommt Ausgang X nicht?"), ohne Modell.

Die Klartext-Saetze entstehen aus der Verknuepfungslogik (U/UN/O/ON mit Klammern, FP/FN, =, S, R, Zeiten). Anweisungen
ohne Verknuepfung (Laden, Transfer, Rechnen, Spruenge) stehen unveraendert unter `other`. Die Rueckverfolgung nutzt den
Signalgraph: Eingaenge eines Netzwerks mit Klemme und Geraet, interne Merker mit dem Netzwerk, das sie schreibt.
"""

import re
from dataclasses import dataclass, field

from app.ingestion.awl_parser import AwlNetwork, parse_awl
from app.ingestion.signal_graph import Graph, _address, _bindings, _operand

LOGIC_OPS = {"U", "UN", "O", "ON"}
BLOCK_OPS = {"U(": False, "UN(": True, "O(": False, "ON(": True}
EDGE_OPS = {"FP": "steigende", "FN": "fallende"}
TIMER_OPS = {
    "SE": "Einschaltverzögerung",
    "SD": "Einschaltverzögerung",
    "SI": "Impuls",
    "SS": "speichernde Einschaltverzögerung",
    "SV": "verlängerter Impuls",
    "SA": "Ausschaltverzögerung",
}


@dataclass
class _Frame:
    groups: list[list[str]] = field(default_factory=lambda: [[]])
    opener: str = ""

    def add(self, term: str, op: str) -> None:
        if op.startswith("O") and self.groups[-1]:
            self.groups.append([term])
        else:
            self.groups[-1].append(term)

    def render(self) -> str:
        groups = [" UND ".join(g) for g in self.groups if g]
        return " ODER ".join(groups) if groups else "immer"

    def compound(self) -> bool:
        groups = [g for g in self.groups if g]
        return len(groups) > 1 or any(len(g) > 1 for g in groups)


def _code(line: str) -> str:
    return line.split("//", 1)[0].strip().rstrip(";").strip()


def _explain_call(network: AwlNetwork) -> list[str] | None:
    call = None
    params = []
    for line in network.lines:
        code = _code(line)
        if match := re.match(r"CALL\s+(FB|FC)\s*(\d+)(?:\s*,\s*(DB)\s*(\d+))?", code, re.I):
            call = f"{match.group(1).upper()} {match.group(2)}"
            if match.group(3):
                call += f" mit Instanz DB {match.group(4)}"
        elif call and (match := re.match(r"(\w+)\s*:=\s*(.+)$", code)):
            params.append(f"{match.group(1)} := {' '.join(match.group(2).split())}")
    if call is None:
        return None
    return [f"Ruft {call} auf" + (": " + ", ".join(params) + "." if params else ".")]


def explain_network(network: AwlNetwork, name: str, bindings: dict[str, str], symbols: dict[str, str]) -> dict:
    """Klartext eines Netzwerks. `name` ist der Bausteinname ("FB 10"), `symbols` Symbol -> Adresse."""
    by_address = {address: symbol for symbol, address in symbols.items()}
    operands: dict[str, dict] = {}
    comment = " ".join(line.strip()[2:].strip() for line in network.lines if line.strip().startswith("//"))

    def text_of(raw: str) -> str | None:
        raw = " ".join(raw.split())
        found = _operand(raw, name, bindings, symbols)
        if found is None:
            return None
        node_id, kind = found
        label = raw[1:] if raw.startswith("#") else raw.strip('"') if raw.startswith('"') else by_address.get(node_id, node_id)
        address = node_id if kind == "address" else ""
        operands.setdefault(node_id, {"id": node_id, "name": label, "address": address})
        return f"{label} ({address})" if address and address != label else label

    klartext = _explain_call(network)
    if klartext is not None:
        return _result(network, name, comment, klartext, [], operands)

    klartext, other = [], []
    stack = [_Frame()]
    time_value = ""

    def finish(sentence: str) -> None:
        klartext.append(sentence)
        stack[:] = [_Frame()]

    for line in network.lines:
        code = _code(line)
        if not code or code.startswith("//"):
            continue
        code = re.sub(r"^\w+:\s*", "", code) if re.match(r"^\w+:\s*\S", code) and not re.match(r"^\w+\s*:=", code) else code
        parts = code.split(None, 1)
        op = parts[0].upper() if parts else ""
        raw = parts[1] if len(parts) == 2 else ""
        frame = stack[-1]
        if op in BLOCK_OPS:
            stack.append(_Frame(opener=op))
        elif op == ")" and len(stack) > 1:
            inner = stack.pop()
            text = inner.render()
            if BLOCK_OPS[inner.opener]:
                text = f"NICHT ({text})"
            elif inner.compound():
                text = f"({text})"
            stack[-1].add(text, inner.opener)
        elif op in LOGIC_OPS and raw:
            if (text := text_of(raw)) is None:
                other.append(code)
                continue
            frame.add(f"NICHT {text}" if op.endswith("N") else text, op)
        elif op == "O" and not raw:
            frame.groups.append([])
        elif op in EDGE_OPS and raw:
            memory = text_of(raw) or raw
            what = frame.render()
            frame.groups = [[f"{EDGE_OPS[op]} Flanke von ({what}) [Flankenmerker {memory}]"]]
        elif op == "L" and raw.upper().startswith("S5T#"):
            time_value = raw.upper().removeprefix("S5T#").replace("S", " s").replace("MS", " ms").strip()
        elif op in {"=", "S", "R"} and raw and (target := text_of(raw)):
            expr = frame.render()
            if op == "=":
                finish(f"{target} ist EIN, wenn {expr}.")
            elif op == "S":
                finish(f"{target} wird gesetzt und bleibt es, wenn {expr}.")
            else:
                finish(f"{target} wird zurückgesetzt, wenn {expr}.")
        elif op in {"SPB", "SPBN"} and raw and frame.groups != [[]]:
            condition = frame.render() if op == "SPB" else f"NICHT ({frame.render()})"
            finish(f"Springt nach {raw.strip()}, wenn {condition}.")
        elif op in TIMER_OPS and raw and (target := text_of(raw)):
            wait = f" ({time_value})" if time_value else ""
            finish(f"Timer {target} läuft als {TIMER_OPS[op]}{wait}, sobald {frame.render()}.")
            time_value = ""
        else:
            other.append(code)
    return _result(network, name, comment, klartext, other, operands)


def _result(network: AwlNetwork, name: str, comment: str, klartext: list[str], other: list[str], operands: dict) -> dict:
    return {
        "id": f"{name}/NW{network.number}",
        "ref": f"{name} NW {network.number}",
        "number": network.number,
        "title": network.title,
        "comment": comment,
        "klartext": klartext,
        "other": other,
        "operands": list(operands.values()),
    }


def explain_awl(awl_text: str, symbols: dict[str, str]) -> list[dict]:
    """Alle Netzwerke einer AWL-Quelle im Klartext, mit Baustein (`block`)."""
    blocks = parse_awl(awl_text) if awl_text.strip() else []
    bindings = _bindings(blocks, symbols)
    result = []
    for block in blocks:
        name = " ".join(block.name.split())
        for network in block.networks:
            explained = explain_network(network, name, bindings, symbols)
            explained["block"] = block.label
            result.append(explained)
    return result


# --- Rueckverfolgung --------------------------------------------------------------------------


def _preds(graph: Graph, node_id: str) -> list[str]:
    return [source for (source, target) in graph.edges if target == node_id]


def _succs(graph: Graph, node_id: str) -> list[str]:
    return [target for (source, target) in graph.edges if source == node_id]


def _device_of(graph: Graph, terminal: str, upstream: bool) -> str | None:
    for node_id in _preds(graph, terminal) if upstream else _succs(graph, terminal):
        if graph.nodes[node_id].kind in {"device", "pin"}:
            return node_id.split(":", 1)[0]
    return None


def resolve_output(graph: Graph, symbols: dict[str, str], text: str) -> str | None:
    """Knoten-ID eines Ausgangs aus Adresse ("A4.0", "A 4.0"), Symbol oder Knoten-ID."""
    text = text.strip()
    for candidate in (text, _address(text) or "", symbols.get(text.strip('"'), "")):
        if candidate in graph.nodes:
            return candidate
    return None


def why_not(graph: Graph, explained: list[dict], target: str, max_depth: int = 4) -> dict:
    """Alle Netzwerke, die `target` schreiben, mit ihren Eingaengen samt Klemme und Geraet (Signalgraph).

    Ein interner Merker oder Ausgang als Eingang nennt das Netzwerk, das ihn schreibt (`written_by`); diese Netzwerke
    folgen bis `max_depth`.
    """
    by_id = {item["id"]: item for item in explained}

    def writers(node_id: str) -> list[str]:
        return [s for s in _preds(graph, node_id) if graph.nodes[s].kind == "network"]

    def entry(node_id: str) -> dict:
        node = graph.nodes[node_id]
        terminals = [s for s in _preds(graph, node_id) if graph.nodes[s].kind == "terminal"]
        terminal = terminals[0] if terminals else None
        return {
            "id": node_id,
            "kind": node.kind,
            "label": node.label,
            "terminal": terminal,
            "device": _device_of(graph, terminal, upstream=True) if terminal else None,
            "written_by": writers(node_id),
        }

    networks, seen, queue = [], set(), [(nw, 0) for nw in writers(target)]
    while queue:
        nw, depth = queue.pop(0)
        if nw in seen:
            continue
        seen.add(nw)
        inputs = [entry(s) for s in _preds(graph, nw) if graph.nodes[s].kind in {"address", "variable"}]
        item = by_id.get(nw, {})
        networks.append(
            {
                "id": nw,
                "ref": graph.nodes[nw].ref,
                "title": graph.nodes[nw].label,
                "klartext": item.get("klartext", []),
                "inputs": inputs,
                "depth": depth,
            }
        )
        if depth < max_depth:
            queue += [(w, depth + 1) for i in inputs for w in i["written_by"] if w not in seen]

    node = graph.nodes[target]
    terminals = [t for t in _succs(graph, target) if graph.nodes[t].kind == "terminal"]
    return {
        "target": {
            "id": target,
            "label": node.label,
            "terminal": terminals[0] if terminals else None,
            "device": _device_of(graph, terminals[0], upstream=False) if terminals else None,
        },
        "networks": networks,
    }
