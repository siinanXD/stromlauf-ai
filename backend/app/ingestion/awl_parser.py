"""Parser fuer Siemens STEP 7 AWL-Quellen (.awl) und Symboltabellen (.sdf).

Zerlegt eine Quelle in Bausteine (OB/FB/FC/DB/UDT) und Netzwerke, damit jedes Netzwerk
einzeln durchsuchbar ist und seinen Baustein-Kontext behaelt.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

_BLOCK_START_RE = re.compile(
    r"^\s*(?P<kind>ORGANIZATION_BLOCK|FUNCTION_BLOCK|FUNCTION|DATA_BLOCK|TYPE)\s+(?P<name>.+?)\s*$",
    re.IGNORECASE,
)
_BLOCK_END_RE = re.compile(
    r"^\s*END_(ORGANIZATION_BLOCK|FUNCTION_BLOCK|FUNCTION|DATA_BLOCK|TYPE)\b", re.IGNORECASE
)
_NETWORK_RE = re.compile(r"^\s*NETWORK\s*$", re.IGNORECASE)
_TITLE_RE = re.compile(r"^\s*TITLE\s*=\s*(?P<title>.*)$", re.IGNORECASE)
_BEGIN_RE = re.compile(r"^\s*BEGIN\s*$", re.IGNORECASE)

_KIND_LABELS = {
    "ORGANIZATION_BLOCK": "OB",
    "FUNCTION_BLOCK": "FB",
    "FUNCTION": "FC",
    "DATA_BLOCK": "DB",
    "TYPE": "UDT",
}


@dataclass
class AwlNetwork:
    number: int
    title: str = ""
    lines: list[str] = field(default_factory=list)

    @property
    def code(self) -> str:
        return "\n".join(self.lines).strip()


@dataclass
class AwlBlock:
    kind: str  # OB | FB | FC | DB | UDT
    name: str  # z.B. 'FB 1' oder '"Motorsteuerung"'
    title: str = ""
    declaration_lines: list[str] = field(default_factory=list)
    networks: list[AwlNetwork] = field(default_factory=list)

    @property
    def label(self) -> str:
        name = self.name.split(":")[0].strip()  # FUNCTION FC 1 : VOID -> FC 1
        label = name if name.upper().startswith(self.kind) else f"{self.kind} {name}"
        return f"{label} - {self.title}" if self.title else label

    @property
    def declaration(self) -> str:
        return "\n".join(self.declaration_lines).strip()


def read_text(path: Path) -> str:
    """STEP 7 exportiert in Windows-1252; neuere Tools in UTF-8."""
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def parse_awl(text: str) -> list[AwlBlock]:
    blocks: list[AwlBlock] = []
    block: AwlBlock | None = None
    network: AwlNetwork | None = None
    in_body = False

    for raw_line in text.splitlines():
        line = raw_line.rstrip()

        if block is None:
            start = _BLOCK_START_RE.match(line)
            if start:
                kind = _KIND_LABELS[start["kind"].upper()]
                block = AwlBlock(kind=kind, name=start["name"])
                network, in_body = None, False
            continue

        if _BLOCK_END_RE.match(line):
            blocks.append(block)
            block, network = None, None
            continue

        title = _TITLE_RE.match(line)
        if _NETWORK_RE.match(line):
            network = AwlNetwork(number=len(block.networks) + 1)
            block.networks.append(network)
        elif title and network is not None and not network.title and not network.lines:
            network.title = title["title"].strip()
        elif title and network is None and not block.title:
            block.title = title["title"].strip().strip('"')
        elif _BEGIN_RE.match(line) and not in_body:
            in_body = True
        elif network is not None:
            if line.strip():
                network.lines.append(line)
        elif line.strip():
            # Deklarationsteil; bei DBs auch die Aktualwerte nach BEGIN
            block.declaration_lines.append(line)

    if block is not None:  # Datei ohne END_... abgeschnitten
        blocks.append(block)
    return blocks


def parse_symbol_table(text: str) -> list[dict[str, str]]:
    """SDF-Export: "Symbol","Adresse","Datentyp","Kommentar" je Zeile."""
    rows = []
    for record in csv.reader(io.StringIO(text)):
        cells = [c.strip() for c in record]
        if len(cells) < 2 or not cells[0]:
            continue
        cells += [""] * (4 - len(cells))
        rows.append(
            {"symbol": cells[0], "address": cells[1], "data_type": cells[2], "comment": cells[3]}
        )
    return rows
