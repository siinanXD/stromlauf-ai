"""Baustein-Modell fuer SPS-Quellen: STEP-7-AWL, TIA-SCL und TIA-Openness-XML (SIN-723).

Alle drei Formate werden zu demselben Modell (`schemas/plc_blocks.schema.json`): Bausteine mit
Schnittstelle und Netzwerken, je Netzwerk die Operanden mit Rolle (read/write/param/call). Ist ein
Operand in der Symboltabelle, steht der Symbolname vorn (`display`) und die Absolutadresse daneben;
fehlt er dort, bleibt die Adresse. Rein deterministisch, kein Modell.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from app.ingestion.awl_parser import (
    _BLOCK_END_RE,
    _BLOCK_START_RE,
    _KIND_LABELS,
    _TITLE_RE,
    parse_awl,
    parse_symbol_table,
)

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "plc_blocks.schema.json"

# --- Adressen und Symboltabelle ---------------------------------------------------------------

_ABS_BIT = re.compile(r"^(?P<a>[EAMIQ])\s*(?P<n>\d+)\.(?P<b>[0-7])$", re.I)
_ABS_WORD = re.compile(r"^(?P<a>P?[EAMIQ])(?P<w>[BWD])\s*(?P<n>\d+)$", re.I)
_ABS_COUNTER = re.compile(r"^(?P<a>[TZC])\s*(?P<n>\d+)$", re.I)
_ABS_DB = re.compile(r"^(?:DB\s*(?P<db>\d+)\s*\.\s*)?(?P<k>DB|DI)(?P<w>[XBWD])\s*(?P<n>\d+)(?:\.(?P<b>[0-7]))?$", re.I)
_PERCENT = re.compile(r"^%(?P<rest>[EAMIQ][BWD]?\s*\d+(?:\.[0-7])?)$", re.I)
_AREA = {"I": "E", "Q": "A"}


def absolute_address(text: str) -> str | None:
    """Kanonische Schreibweise (`E0.0`, `MW100`, `T5`, `DB10.DBX0.0`) oder None."""
    text = text.strip().strip('"')
    if m := _PERCENT.match(text):
        text = m["rest"]
    if m := _ABS_BIT.match(text):
        area = m["a"].upper()
        return f"{_AREA.get(area, area)}{int(m['n'])}.{m['b']}"
    if m := _ABS_WORD.match(text):
        area = m["a"].upper()
        area = "".join(_AREA.get(c, c) for c in area)
        return f"{area}{m['w'].upper()}{int(m['n'])}"
    if m := _ABS_COUNTER.match(text):
        area = "Z" if m["a"].upper() == "C" else m["a"].upper()
        return f"{area}{int(m['n'])}"
    if m := _ABS_DB.match(text):
        head = f"DB{int(m['db'])}." if m["db"] else ""
        tail = f".{m['b']}" if m["b"] else ""
        return f"{head}{m['k'].upper()}{m['w'].upper()}{int(m['n'])}{tail}"
    return None


class SymbolTable:
    def __init__(self, rows: list[dict[str, str]] | None = None):
        self.by_name: dict[str, str] = {}
        self.by_address: dict[str, str] = {}
        for row in rows or []:
            address = absolute_address(row["address"])
            if address is None:
                continue
            self.by_name.setdefault(row["symbol"], address)
            self.by_address.setdefault(address, row["symbol"])

    @classmethod
    def from_text(cls, text: str) -> "SymbolTable":
        return cls(parse_symbol_table(text))


# --- Operanden --------------------------------------------------------------------------------


@dataclass
class _Use:
    raw: str
    role: str


def _operand(raw: str, symbols: SymbolTable) -> dict:
    """Ein Operand mit Symbol, wo die Tabelle einen Namen hat."""
    raw = raw.strip()
    name: str | None = None
    address: str | None = None
    if raw.startswith("#"):
        scope, name = "local", raw[1:].strip('"')
    elif raw.startswith('"'):
        scope, name = "global", raw.split('"')[1]
        address = symbols.by_name.get(name)
    else:
        address = absolute_address(raw)
        scope = "absolute"
        if address:
            name = symbols.by_address.get(address)
            if name:
                scope = "global"
        else:
            name = raw
            scope = "local"
    return {"display": name or address or raw, "name": name, "address": address, "scope": scope, "roles": []}


def _collect(uses: list[_Use], symbols: SymbolTable) -> list[dict]:
    seen: dict[str, dict] = {}
    for use in uses:
        op = _operand(use.raw, symbols)
        key = op["display"]
        if key in seen:
            existing = seen[key]
            if use.role not in existing["roles"]:
                existing["roles"].append(use.role)
        else:
            op["roles"].append(use.role)
            seen[key] = op
    return list(seen.values())


# --- AWL --------------------------------------------------------------------------------------

_LABEL = re.compile(r"^\s*\w+:(?!=)\s*")
_PARAM = re.compile(r"^\s*(?P<p>\w+)\s*:=\s*(?P<v>.+?)\s*;?\s*$")
_JUMPS = {"SPA", "SPB", "SPBN", "SPBB", "SPBNB", "SPBI", "SPBIN", "SPO", "SPS", "SPZ", "SPN", "SPP",
          "SPM", "SPPZ", "SPMZ", "SPU", "JU", "JC", "JCN", "JCB", "JNB", "JBI", "JNBI", "JO", "JOS",
          "JZ", "JN", "JP", "JM", "JPZ", "JMZ", "JUO", "SPL", "LOOP"}
_CALLS = {"CALL", "UC", "CC"}
_WRITES = {"=", "S", "R", "T", "FP", "FN", "SE", "SD", "SS", "SF", "SP", "SA", "CU", "CD", "ZV", "ZR",
           "SI", "SV", "SO"}
_NO_OPERAND = {"NOP", "BE", "BEB", "BEA", "BLD", "SET", "CLR", "NOT", "SAVE", "SLW", "SRW"}
_INSTR = re.compile(r"^(?P<op>[A-Za-z=+\-*/<>(){}!?]+)\s*(?P<arg>.*)$")


def _awl_uses(lines: list[str]) -> tuple[list[_Use], int]:
    uses: list[_Use] = []
    statements = 0
    call_open = False
    for line in lines:
        code = line.split("//", 1)[0].strip().rstrip(";").strip()
        if not code:
            continue
        if call_open and (m := _PARAM.match(code)):
            uses.append(_Use(m["v"], "param"))
            continue
        call_open = False
        code = _LABEL.sub("", code, count=1).strip()
        if not code:
            continue
        m = _INSTR.match(code)
        if not m:
            continue
        statements += 1
        op, arg = m["op"].upper(), m["arg"].strip()
        if op in _CALLS:
            target = arg.split(",")[0].strip()
            if target:
                uses.append(_Use(re.sub(r"\s+", " ", target), "call"))
            for extra in arg.split(",")[1:]:
                if extra.strip():
                    uses.append(_Use(re.sub(r"\s+", " ", extra.strip()), "call"))
            call_open = True
            continue
        if op in _JUMPS or op in _NO_OPERAND or not arg:
            continue
        first = arg.split()[0]
        if first[0].isdigit() or re.match(r"^(S5T|T|L|C|W|DW|B|D|P|DT|TOD|D)#", first, re.I):
            continue
        if arg.startswith(("+", "-")) and arg[1:].isdigit():
            continue
        uses.append(_Use(re.sub(r"\s+", " ", arg), "write" if op in _WRITES else "read"))
    return uses, statements


# --- Schnittstelle ----------------------------------------------------------------------------

_SECTION = re.compile(r"^\s*(VAR_INPUT|VAR_OUTPUT|VAR_IN_OUT|VAR_TEMP|VAR_STAT|VAR|STRUCT)\b", re.I)
_DECL = re.compile(r"^\s*(?P<n>\"[^\"]+\"|\w+)\s*:\s*(?P<t>[^;/]+?)\s*(?::=[^;]*)?;\s*(?://\s*(?P<c>.*))?$")


def _interface(declaration_lines: list[str]) -> list[dict]:
    members: list[dict] = []
    section: str | None = None
    for line in declaration_lines:
        if m := _SECTION.match(line):
            section = m[1].upper()
        elif re.match(r"^\s*END_(VAR|STRUCT)\b", line, re.I):
            section = None
        elif section and (m := _DECL.match(line)):
            members.append(
                {"section": section, "name": m["n"].strip('"'), "type": m["t"].strip(), "comment": (m["c"] or "").strip()}
            )
    return members


def _block_name(raw: str) -> tuple[str, int | None]:
    name = raw.split(":")[0].strip()
    number = re.fullmatch(r"(?:OB|FB|FC|DB|UDT)\s*(\d+)", name, re.I)
    return name.strip('"'), int(number[1]) if number else None


def _block(kind: str, raw_name: str, title: str, declaration: list[str], networks: list[dict]) -> dict:
    name, number = _block_name(raw_name)
    return {"kind": kind, "name": name, "number": number, "title": title,
            "interface": _interface(declaration), "networks": networks}


def _network(number: int, title: str, comment: str, uses: list[_Use], statements: int, symbols: SymbolTable) -> dict:
    return {"number": number, "title": title, "comment": comment, "statements": statements,
            "operands": _collect(uses, symbols)}


def parse_awl_blocks(text: str, symbols: SymbolTable | None = None) -> list[dict]:
    symbols = symbols or SymbolTable()
    out = []
    for block in parse_awl(text):
        networks = []
        for net in block.networks:
            uses, statements = _awl_uses(net.lines)
            comment = "\n".join(ln.strip()[2:].strip() for ln in net.lines if ln.strip().startswith("//"))
            networks.append(_network(net.number, net.title, comment, uses, statements, symbols))
        out.append(_block(block.kind, block.name, block.title, block.declaration_lines, networks))
    return out


# --- SCL --------------------------------------------------------------------------------------

_SCL_REF = re.compile(r'(?P<o>#[A-Za-z_]\w*|"[^"]+"(?:\.\w+)*|%[EAMIQ][BWD]?\s*\d+(?:\.[0-7])?)')
_SCL_STRING = re.compile(r"'[^']*'")
_SCL_CALL_ARG = re.compile(r"(?P<p>\w+)\s*(?P<op>:=|=>)\s*(?P<v>#[A-Za-z_]\w*|\"[^\"]+\"|%[EAMIQ][BWD]?\s*\d+(?:\.[0-7])?|\w+)")


def _scl_uses(body: str) -> tuple[list[_Use], int]:
    uses: list[_Use] = []
    statements = 0
    code = re.sub(r"\(\*.*?\*\)", "", body, flags=re.S)
    code = "\n".join(ln.split("//", 1)[0] for ln in code.splitlines())
    code = _SCL_STRING.sub("''", code)
    for statement in re.split(r";|\bTHEN\b|\bELSE\b|\bDO\b", code, flags=re.I):
        statement = statement.strip()
        if not statement or re.fullmatch(r"END_\w+", statement, re.I):
            continue
        statements += 1
        statement = re.sub(r"^(?:IF|ELSIF|WHILE|UNTIL|CASE|FOR)\b", " ", statement, flags=re.I)
        if "(" in statement and (call := re.match(r"\s*(?P<c>\"[^\"]+\"|#\w+|\w+)\s*\((?P<args>.*)\)\s*$", statement, re.S)):
            uses.append(_Use(call["c"], "call"))
            for arg in _SCL_CALL_ARG.finditer(call["args"]):
                value = arg["v"]
                if value.upper() in {"TRUE", "FALSE"} or value[0].isdigit():
                    continue
                uses.append(_Use(value, "write" if arg["op"] == "=>" else "param"))
            continue
        # Zuweisung: Ziel links von := (ausserhalb von Klammern) schreibt, alles andere liest
        parts = re.split(r"(?<![<>])\:=", statement, maxsplit=1)
        if len(parts) == 2 and (target := _SCL_REF.search(parts[0])):
            uses.append(_Use(target["o"], "write"))
            rest = parts[1]
        else:
            rest = statement
        for ref in _SCL_REF.finditer(rest):
            uses.append(_Use(ref["o"], "read"))
    return uses, statements


def parse_scl_blocks(text: str, symbols: SymbolTable | None = None) -> list[dict]:
    symbols = symbols or SymbolTable()
    out: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if current is None:
            if m := _BLOCK_START_RE.match(line):
                current = {"kind": _KIND_LABELS[m["kind"].upper()], "name": m["name"], "title": "",
                           "decl": [], "body": [], "in_body": False}
            continue
        if _BLOCK_END_RE.match(line):
            out.append(_finish_scl(current, symbols))
            current = None
        elif current["in_body"]:
            current["body"].append(line)
        elif re.match(r"^\s*BEGIN\s*$", line, re.I):
            current["in_body"] = True
        elif (t := _TITLE_RE.match(line)) and not current["title"]:
            current["title"] = t["title"].strip().strip('"')
        elif line.strip():
            current["decl"].append(line)
    if current is not None:
        out.append(_finish_scl(current, symbols))
    return out


def _finish_scl(block: dict, symbols: SymbolTable) -> dict:
    body = "\n".join(block["body"])
    uses, statements = _scl_uses(body)
    comment = "\n".join(ln.strip()[2:].strip() for ln in block["body"] if ln.strip().startswith("//"))
    networks = [_network(1, block["title"], comment, uses, statements, symbols)] if statements else []
    return _block(block["kind"], block["name"], block["title"], block["decl"], networks)


# --- TIA Openness (SimaticML) -----------------------------------------------------------------

_XML_KINDS = {"SW.Blocks.OB": "OB", "SW.Blocks.FB": "FB", "SW.Blocks.FC": "FC", "SW.Blocks.GlobalDB": "DB",
              "SW.Blocks.InstanceDB": "DB"}
_XML_AREAS = {"Input": "E", "Output": "A", "Memory": "M"}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(node: ET.Element, name: str) -> str:
    for child in node.iter():
        if _local(child.tag) == name and child.text and child.text.strip():
            return child.text.strip()
    return ""


def _xml_access(access: ET.Element) -> str | None:
    scope = access.get("Scope", "")
    if scope in ("LiteralConstant", "TypedConstant", "LocalConstant"):
        return None
    if scope == "Address":
        for child in access.iter():
            if _local(child.tag) == "Address":
                area = _XML_AREAS.get(child.get("Area", ""))
                if area is None:
                    return None
                bit, typ = child.get("BitOffset", "0"), child.get("Type", "Bool")
                offset = int(bit)
                return f"{area}{offset // 8}.{offset % 8}" if typ == "Bool" else None
        return None
    names = [c.get("Name", "") for c in access.iter() if _local(c.tag) == "Component"]
    if not names:
        return None
    joined = ".".join(names)
    return f"#{joined}" if scope == "LocalVariable" else f'"{names[0]}"' + "".join(f".{n}" for n in names[1:])


def _xml_network(unit: ET.Element, number: int, symbols: SymbolTable) -> dict:
    uses: list[_Use] = []
    statements = 0
    title = ""
    comment = ""
    for child in unit:
        if _local(child.tag) == "ObjectList":
            for obj in child:
                if _local(obj.tag) == "MultilingualText":
                    kind = obj.get("CompositionName", "")
                    text = _first_text(obj, "Text")
                    if kind == "Title":
                        title = text
                    elif kind == "Comment":
                        comment = text
    for stl in (n for n in unit.iter() if _local(n.tag) == "StlStatement"):
        statements += 1
        mnemonic = ""
        for tok in stl:
            if _local(tok.tag) == "StlToken":
                mnemonic = mnemonic or tok.get("Text", "").upper()
            elif _local(tok.tag) == "Access" and (raw := _xml_access(tok)):
                uses.append(_Use(raw, "write" if mnemonic in _WRITES else "read"))
    for text_src in (n for n in unit.iter() if _local(n.tag) == "StructuredText"):
        statements += 1
        pending_write = True
        for node in text_src:
            if _local(node.tag) == "Access" and (raw := _xml_access(node)):
                uses.append(_Use(raw, "write" if pending_write else "read"))
                pending_write = False
            elif _local(node.tag) == "Token" and node.get("Text") == ";":
                pending_write = True
            elif _local(node.tag) == "Token" and node.get("Text") in (":=", "THEN", "DO"):
                pending_write = False
    return _network(number, title, comment, uses, statements, symbols)


def parse_tia_xml_blocks(text: str, symbols: SymbolTable | None = None) -> list[dict]:
    symbols = symbols or SymbolTable()
    root = ET.fromstring(text)
    out = []
    for node in root.iter():
        kind = _XML_KINDS.get(_local(node.tag))
        if kind is None:
            continue
        attrs = next((c for c in node if _local(c.tag) == "AttributeList"), None)
        name = _first_text(attrs, "Name") if attrs is not None else ""
        number = _first_text(attrs, "Number") if attrs is not None else ""
        units = [c for c in node.iter() if _local(c.tag) == "SW.Blocks.CompileUnit"]
        networks = [_xml_network(u, i, symbols) for i, u in enumerate(units, 1)]
        members = []
        for section in (n for n in node.iter() if _local(n.tag) == "Section"):
            for member in (m for m in section if _local(m.tag) == "Member"):
                members.append({"section": "VAR_" + section.get("Name", "").upper().replace("STATIC", "STAT"),
                                "name": member.get("Name", ""), "type": member.get("Datatype", ""), "comment": ""})
        out.append({"kind": kind, "name": name, "number": int(number) if number.isdigit() else None,
                    "title": "", "interface": members, "networks": networks})
    return out


# --- Einstieg ---------------------------------------------------------------------------------


@dataclass
class PlcProgram:
    source_format: str  # awl | scl | xml
    blocks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"source_format": self.source_format, "blocks": self.blocks}


def detect_format(text: str, filename: str = "") -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".xml" or text.lstrip().startswith("<"):
        return "xml"
    if suffix == ".scl":
        return "scl"
    if suffix == ".awl":
        return "awl"
    return "awl" if re.search(r"^\s*NETWORK\s*$", text, re.M | re.I) else "scl"


def parse_plc_source(text: str, symbols: SymbolTable | None = None, filename: str = "") -> PlcProgram:
    fmt = detect_format(text, filename)
    parser = {"awl": parse_awl_blocks, "scl": parse_scl_blocks, "xml": parse_tia_xml_blocks}[fmt]
    return PlcProgram(fmt, parser(text, symbols))
