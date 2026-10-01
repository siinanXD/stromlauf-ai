"""Signalweg einer Anlage als gerichteter Graph, deterministisch aus den Dokumenten.

Quellen: Klemmenplan (Feldgeraet -> Klemme -> SPS-Eingang bzw. Ausgang/Schaltgeraet -> Klemme ->
Verbraucher), Symboltabelle (Symbol = Adresse) und AWL (gelesene Groessen -> Netzwerk -> geschriebene
Groessen; FB-Parameter werden ueber den CALL im OB bzw. den Deklarationskommentar an Adressen
gebunden). Kein Sprachmodell.

Jede Kante traegt ihre Herkunft (`via`): "klemmenplan", "awl" aus den Tabellen, "leitung", "lage" oder "modell" aus
dem Stromlaufplan (`plan_edges`). Kanten ohne bekannte Richtung stehen zusaetzlich in `Graph.undirected`; sie
erscheinen als Nachbarn, bestimmen aber keine Ebene und keinen Hauptweg.
"""

import re
from collections import deque
from dataclasses import dataclass, field

from app.ingestion.awl_parser import parse_awl
from app.ingestion.plan_edges import PlanEdge
from app.ingestion.tags import TagType, extract_tags, normalize_tag, pin_kind

ADDRESS = re.compile(r"(?<![\w.\-])([EAM])\s*(\d{1,4})\s*\.\s*([0-7])(?![\d])", re.I)
WORD = re.compile(r"(?<![\w.\-])(MW|MB|MD|EW|AW|EB|AB)\s*(\d{1,4})(?![\d.])", re.I)
TIMER = re.compile(r"^(T|Z)\s*(\d{1,4})$", re.I)
SUPPLY_WORDS = ("0 v", "+24", "24 v", "schutzleiter", "netz", "versorgung")
# Eingangsklemmen S12/S22 eines Sicherheitsrelais: das Feldgeraet (Not-Halt, Schutztuer) speist das Relais
SAFETY_INPUT = re.compile(r"-K\d+:S[12]2\b")
READ_OPS = {"U", "UN", "O", "ON", "X", "XN", "L", "FP", "FN"}
WRITE_OPS = {"=", "S", "R", "T", "SE", "SI", "SV", "SA", "SS", "ZV", "ZR"}
# Seit #98 kostet ein Schaltgeraet im Weg bis zu zwei Stufen mehr (Spule -> Geraet -> Kontakt)
MAX_DEPTH = 16
HUB_DEGREE = 8


@dataclass
class Node:
    id: str
    kind: str  # device | pin | terminal | address | network | variable
    label: str = ""
    ref: str = ""
    detail: str = ""  # AWL-Code eines Netzwerks


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: dict[tuple[str, str], set[str]] = field(default_factory=dict)  # (Quelle, Ziel) -> Herkunft
    undirected: set[tuple[str, str]] = field(default_factory=set)  # sortierte Paare ohne bekannte Richtung

    def node(self, node_id: str, kind: str, label: str = "", ref: str = "") -> str:
        existing = self.nodes.get(node_id)
        if existing is None:
            self.nodes[node_id] = Node(node_id, kind, label, ref)
        else:
            existing.label = existing.label or label
            existing.ref = existing.ref or ref
        return node_id

    def edge(self, source: str, target: str, via: str = "klemmenplan", directed: bool = True) -> None:
        """Kante mit Herkunft. Eine gerichtete Kante macht ein bisher ungerichtetes Paar gerichtet; eine ungerichtete
        zu einem gerichteten Paar ergaenzt nur dessen Herkunft."""
        if source == target:
            return
        pair = (min(source, target), max(source, target))
        if directed:
            if pair in self.undirected:
                self.undirected.discard(pair)
                self.edges.setdefault((source, target), set()).update(self.edges.pop(pair))
            self.edges.setdefault((source, target), set()).add(via)
            return
        for key in ((source, target), (target, source)):
            if key in self.edges and pair not in self.undirected:
                self.edges[key].add(via)
                return
        self.edges.setdefault(pair, set()).add(via)
        self.undirected.add(pair)

    def directed_edges(self) -> list[tuple[str, str]]:
        return [key for key in self.edges if key not in self.undirected]


def _address(text: str) -> str | None:
    text = text.strip().strip('"')
    if match := ADDRESS.fullmatch(text):
        return f"{match.group(1).upper()}{int(match.group(2))}.{match.group(3)}"
    if match := WORD.fullmatch(text):
        return f"{match.group(1).upper()}{int(match.group(2))}"
    return None


def _addresses_in(text: str) -> list[str]:
    return [f"{m.group(1).upper()}{int(m.group(2))}.{m.group(3)}" for m in ADDRESS.finditer(text)]


def _devices_in(text: str) -> list[str]:
    devices = []
    for tag in extract_tags(text):
        if tag.tag_type == TagType.DEVICE and not re.fullmatch(r"-A\d+(\.\d+)?", tag.tag):
            devices.append(tag.tag)
    return list(dict.fromkeys(devices))


# --- Klemmenplan ------------------------------------------------------------------------------


def _ends(
    graph: Graph, text: str, labels: dict[str, tuple[str, str]], ref: str
) -> list[tuple[str, str]]:
    """(Geraet, Knoten an der Klemme) je Geraet einer Zelle. Hat der Anschluss eine Art (Spule, Kontakt; Issue #98),
    ist er der Knoten an der Klemme, und das Geraet steht nicht noch einmal ohne ihn da."""
    tags = extract_tags(text)
    pins = [t.tag for t in tags if t.tag_type == TagType.DEVICE_PIN and pin_kind(t.tag)]
    ends = []
    for pin in pins:
        ends.append((pin.split(":", 1)[0], graph.node(pin, "pin", pin_kind(pin) or "", ref)))
    with_pin = {device for device, _ in ends}
    ends += [(device, device) for device in _devices_in(text) if device not in with_pin]
    for device, _ in ends:
        graph.node(device, "device", *labels.get(device, ("", "")))
    return list(dict.fromkeys(ends))


def _add_terminal_rows(graph: Graph, rows: list[list[str]], labels: dict[str, tuple[str, str]]) -> None:
    for row in rows:
        if len(row) < 6 or not row[1].startswith("-X") or ":" not in row[1]:
            continue
        _strip, terminal, intern, extern, function, ref = (cell.strip() for cell in row[:6])
        if any(word in function.lower() for word in SUPPLY_WORDS) or re.match(r"-X[12]:", terminal):
            continue  # Versorgung/Sammelschienen verbinden alles mit allem
        term = graph.node(normalize_tag(terminal), "terminal", function, ref)
        addresses = [graph.node(a, "address") for a in _addresses_in(intern)]
        intern_ends = [(a, a) for a in addresses] or _ends(graph, intern, labels, ref)
        extern_ends = _ends(graph, extern, labels, ref)
        inputs = any(a.startswith("E") for a in addresses) or bool(SAFETY_INPUT.search(intern))
        sources, targets = (extern_ends, intern_ends) if inputs else (intern_ends, extern_ends)
        # Der Weg laeuft durch das Geraet: Klemme -> Spule -> Geraet, Geraet -> Kontakt -> Klemme
        for device, at in sources:
            graph.edge(device, at)
            graph.edge(at, term)
        for device, at in targets:
            graph.edge(term, at)
            graph.edge(at, device)


# --- AWL --------------------------------------------------------------------------------------


def _operand(raw: str, block: str, bindings: dict[str, str], symbols: dict[str, str]) -> tuple[str, str] | None:
    """(Knoten-ID, Art) eines AWL-Operanden; Konstanten und Spruenge -> None."""
    raw = raw.strip()
    if not raw or raw[0].isdigit() or "#" in raw[1:] or raw.upper().startswith(("S5T#", "T#", "L#")):
        return None
    if raw.startswith("#"):
        name = raw[1:]
        return (bindings[f"{block}#{name}"], "address") if f"{block}#{name}" in bindings else (f"{block}#{name}", "variable")
    if raw.startswith('"'):
        symbol = raw.strip('"')
        return (symbols[symbol], "address") if symbol in symbols else (f'"{symbol}"', "variable")
    if address := _address(raw):
        return address, "address"
    if match := TIMER.fullmatch(raw):
        return f"{match.group(1).upper()}{match.group(2)}", "variable"
    return None


def _bindings(blocks, symbols: dict[str, str]) -> dict[str, str]:
    """FB-Parameter -> Adresse: aus CALL-Zeilen (Param := E 0.0) und Deklarationskommentaren '(E0.0)'."""
    bindings: dict[str, str] = {}
    for block in blocks:
        for network in block.networks:
            called = None
            for line in network.lines:
                if match := re.match(r"\s*CALL\s+(FB|FC)\s*(\d+)", line, re.I):
                    called = f"{match.group(1).upper()} {match.group(2)}"
                elif called and (match := re.match(r"\s*(\w+)\s*:=\s*(.+?)\s*;?\s*$", line)):
                    target = _address(match.group(2)) or symbols.get(match.group(2).strip().strip('"'))
                    if target:
                        bindings[f"{called}#{match.group(1)}"] = target
        for line in block.declaration_lines:
            if (match := re.match(r"\s*(\w+)\s*:\s*\w+", line)) and (addresses := _addresses_in(line.split("//", 1)[-1])):
                bindings.setdefault(f"{block.name}#{match.group(1)}", addresses[0])
    return bindings


def _add_awl(graph: Graph, awl_text: str, symbols: dict[str, str]) -> None:
    blocks = parse_awl(awl_text) if awl_text.strip() else []
    bindings = _bindings(blocks, symbols)
    comments = {
        f"{' '.join(block.name.split())}#{match.group(1)}": match.group(2).strip()
        for block in blocks
        for line in block.declaration_lines
        if (match := re.match(r"\s*(\w+)\s*:[^/]*//\s*(.+)$", line))
    }
    for block in blocks:
        name = " ".join(block.name.split())
        for network in block.networks:
            if any(re.match(r"\s*CALL\b", line, re.I) for line in network.lines):
                continue  # Aufrufe binden nur Parameter
            reads, writes = [], []
            for line in network.lines:
                code = line.split("//", 1)[0].strip().rstrip(";").strip()
                code = re.sub(r"^\w+:\s*", "", code)  # Sprungmarke
                parts = code.split(None, 1)
                if len(parts) != 2:
                    continue
                op, raw = parts[0].upper(), parts[1]
                operand = _operand(raw, name, bindings, symbols)
                if operand is None:
                    continue
                (reads if op in READ_OPS else writes if op in WRITE_OPS else []).append(operand)
            if not writes:
                continue
            nw = graph.node(f"{name}/NW{network.number}", "network", network.title, f"{name} NW {network.number}")
            graph.nodes[nw].detail = "\n".join(line.rstrip() for line in network.lines)
            for node_id, kind in reads:
                graph.edge(graph.node(node_id, kind, comments.get(node_id, "")), nw, "awl")
            for node_id, kind in writes:
                graph.edge(nw, graph.node(node_id, kind, comments.get(node_id, "")), "awl")


def build_graph(
    terminal_rows: list[list[str]],
    bom_rows: list[tuple[str, str, str]],
    symbols: list[dict[str, str]],
    awl_text: str,
) -> Graph:
    graph = Graph()
    labels = {normalize_tag(tag): (str(title or ""), str(ref or "")) for tag, title, ref in bom_rows if tag}
    for tag, (title, ref) in labels.items():
        if tag.startswith("-") and not tag.startswith("-W") and not re.fullmatch(r"-X\d+", tag):
            graph.node(tag, "device", title, ref)
    symbol_map = {row["symbol"]: address for row in symbols if (address := _address(row["address"]))}
    for row in symbols:
        if address := _address(row["address"]):
            graph.node(address, "address", f'{row["symbol"]} · {row["comment"]}'.strip(" ·"))
    _add_terminal_rows(graph, terminal_rows, labels)
    _add_awl(graph, awl_text, symbol_map)
    # Geraete, die nur ueber das Programm vorkommen, bekommen Bezeichnung und Verweis aus der Stueckliste
    for node in graph.nodes.values():
        if node.kind == "device" and node.id in labels:
            node.label, node.ref = node.label or labels[node.id][0], node.ref or labels[node.id][1]
    return graph


# --- Stromlaufplan ----------------------------------------------------------------------------


def _plan_node(graph: Graph, node_id: str, page: int) -> str:
    """Knoten fuer ein Ende einer Plan-Kante; Blatt-Verweis "S. n", wenn die Tabellen keinen nennen."""
    ref = f"S. {page}"
    if _address(node_id):
        return graph.node(node_id, "address", "", ref)
    if kind := pin_kind(node_id):
        return graph.node(node_id, "pin", kind, ref)
    if node_id.startswith("-X") and ":" in node_id:
        return graph.node(node_id, "terminal", "", ref)
    return graph.node(node_id, "device", "", ref)


def add_plan_edges(graph: Graph, edges: list[PlanEdge]) -> Graph:
    """Kanten aus dem Stromlaufplan (Leitung, Lage, Modell) in den Graphen. Ein Anschluss haengt wie im Klemmenplan
    an seinem Geraet: Spule -> Geraet, Geraet -> Kontakt (Issue #98)."""
    for plan in edges:
        for node_id in (plan.source, plan.target):
            _plan_node(graph, node_id, plan.page)
            if kind := pin_kind(node_id):
                device = _plan_node(graph, node_id.split(":", 1)[0], plan.page)
                if kind == "Spule":
                    graph.edge(node_id, device, plan.via)
                else:
                    graph.edge(device, node_id, plan.via)
        graph.edge(plan.source, plan.target, plan.via, plan.directed)
    return graph


# --- Pfad -------------------------------------------------------------------------------------


def _start_id(graph: Graph, tag: str) -> str | None:
    key = normalize_tag(tag)
    # ein Anschluss ohne eigenen Knoten ("-K2:13", der Plan nennt den Kontakt nicht) startet beim Geraet
    for candidate in (tag.strip(), key, _address(tag) or "", key.split(":", 1)[0]):
        if candidate in graph.nodes:
            return candidate
    return None


def signal_path(graph: Graph, tag: str, depth: int = MAX_DEPTH, hub: int = HUB_DEGREE) -> dict | None:
    """Quellen (Level < 0) und Folgen (Level > 0) eines Kennzeichens; None, wenn unbekannt."""
    start = _start_id(graph, tag)
    if start is None:
        return None
    successors: dict[str, list[str]] = {}
    predecessors: dict[str, list[str]] = {}
    for source, target in graph.directed_edges():
        successors.setdefault(source, []).append(target)
        predecessors.setdefault(target, []).append(source)
    degree = {n: len(successors.get(n, [])) + len(predecessors.get(n, [])) for n in graph.nodes}

    level = {start: 0}
    for neighbours, sign in ((successors, 1), (predecessors, -1)):
        queue = deque([(start, 0)])
        seen = {start}
        while queue:
            current, distance = queue.popleft()
            if distance >= depth or (current != start and degree.get(current, 0) > hub):
                continue
            for nxt in sorted(neighbours.get(current, [])):
                if nxt in seen:
                    continue
                seen.add(nxt)
                level.setdefault(nxt, sign * (distance + 1))
                queue.append((nxt, distance + 1))

    edges = [
        {"source": s, "target": t, "via": sorted(via), "directed": (s, t) not in graph.undirected}
        for (s, t), via in sorted(graph.edges.items())
        if s in level and t in level and ((s, t) in graph.undirected or level[s] < level[t])
    ]
    nodes = [
        {**vars(graph.nodes[node_id]), "level": lvl}
        for node_id, lvl in sorted(level.items(), key=lambda item: (item[1], item[0]))
    ]
    return {"start": start, "nodes": nodes, "edges": edges}
