"""Steckbrief einer Wissensquelle: was die Dokumente hergeben und wo sie sich widersprechen.

Rein aus dem Kennzeichen-Index (TagOccurrence), ohne Modell und ohne API-Kosten. Antwortet auf die
Frage nach dem Upload: "Passen Plan, Stueckliste, Klemmenplan und SPS-Programm zusammen?"

Regeln (jede nur, wenn beide beteiligten Dokumenttypen vorhanden sind):
- Betriebsmittel im Plan, nicht in der Stueckliste (und umgekehrt)
- Klemme -X3:1 im Plan, nicht im Klemmenplan (und umgekehrt)
- SPS-Adresse im AWL ohne Symbol (und Symbol ohne Verwendung im AWL)
- SPS-Adresse im AWL, die im Plan nicht verdrahtet ist
- Betriebsmittel nur im Handbuch (vermutlich Tippfehler oder anderes Geraet)
- Blattverweis /12.3 auf ein Blatt, das der Plan nicht hat
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from app.models import DocType, TagType

CORE_DOC_TYPES: tuple[str, ...] = (
    DocType.SCHEMATIC,
    DocType.BOM,
    DocType.TERMINAL_PLAN,
    DocType.PLC_PROGRAM,
    DocType.PLC_SYMBOLS,
    DocType.MANUAL,
)
# Kabel/Leitungen (-W) stehen selten in Stuecklisten: kein Abgleich Plan <-> Stueckliste
_NO_BOM_LETTERS = ("W",)
_CROSS_REF = re.compile(r"^/(\d+)\.\d+$")


@dataclass
class Occurrence:
    tag: str
    tag_type: str
    doc_type: str
    document_id: str = ""
    page: int | None = None


@dataclass
class Gap:
    kind: str
    tag: str
    message: str
    doc_types: list[str] = field(default_factory=list)  # wo das Kennzeichen vorkommt


GAP_LABELS: dict[str, str] = {
    "device_not_in_bom": "Betriebsmittel im Plan, aber nicht in der Stueckliste",
    "device_not_in_schematic": "Betriebsmittel in der Stueckliste, aber nicht im Plan",
    "terminal_not_in_plan": "Klemme im Plan, aber nicht im Klemmenplan",
    "terminal_not_in_schematic": "Klemme im Klemmenplan, aber nicht im Plan",
    "address_without_symbol": "SPS-Adresse im Programm ohne Symbol",
    "symbol_unused": "Symbol ohne Verwendung im Programm",
    "address_not_in_schematic": "SPS-Adresse im Programm, aber nicht im Plan verdrahtet",
    "device_only_in_manual": "Betriebsmittel nur im Handbuch",
    "cross_ref_dangling": "Blattverweis auf ein Blatt, das der Plan nicht hat",
}


def _is_base_device(tag: str) -> bool:
    return tag.startswith("-") and ":" not in tag


def _is_pin(tag: str) -> bool:
    """-X3:1, -X4:U; nicht -X3:6. oder -X3:9/-X3 (Satzzeichen aus dem Plantext)."""
    return re.fullmatch(r"-X\d+:[A-Z0-9]+", tag) is not None


def _is_bit_address(tag: str) -> bool:
    return re.fullmatch(r"[EAM]\d+\.\d", tag) is not None


def _letters(tag: str) -> str:
    match = re.match(r"-([A-Z]{1,3})", tag)
    return match.group(1) if match else ""


def build_profile(
    occurrences: list[Occurrence], present_doc_types: set[str], known_sheets: set[int] | None = None
) -> dict:
    """Abdeckungsmatrix und Luecken. known_sheets: Blaetter des Stromlaufplans, None = nicht pruefbar."""
    where: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for o in occurrences:
        if o.tag.startswith(("=", "+")):  # Vollkennzeichen =A1+S1-K12: Basis -K12 zaehlt
            continue
        where[(o.tag, o.tag_type)][o.doc_type] += 1

    def tags_of(tag_type: str, predicate) -> dict[str, dict[str, int]]:
        return {t: dict(d) for (t, tt), d in where.items() if tt == tag_type and predicate(t)}

    devices = tags_of(TagType.DEVICE, _is_base_device)
    pins = tags_of(TagType.TERMINAL, _is_pin)
    # "A1.1" neben Betriebsmittel "-A1.1" (SPS-Karte) ist keine Ausgangsadresse
    addresses = tags_of(TagType.PLC_ADDRESS, lambda t: _is_bit_address(t) and f"-{t}" not in devices)
    refs = tags_of(TagType.CROSS_REF, lambda t: True)
    has = present_doc_types.__contains__
    gaps: list[Gap] = []

    def gap(kind: str, tag: str, docs: dict[str, int]) -> None:
        gaps.append(Gap(kind, tag, GAP_LABELS[kind], sorted(docs)))

    if has(DocType.SCHEMATIC) and has(DocType.BOM):
        for tag, docs in devices.items():
            if _letters(tag) in _NO_BOM_LETTERS:
                continue
            if DocType.SCHEMATIC in docs and DocType.BOM not in docs:
                gap("device_not_in_bom", tag, docs)
            elif DocType.BOM in docs and DocType.SCHEMATIC not in docs:
                gap("device_not_in_schematic", tag, docs)
    if has(DocType.SCHEMATIC) and has(DocType.TERMINAL_PLAN):
        for tag, docs in pins.items():
            if DocType.SCHEMATIC in docs and DocType.TERMINAL_PLAN not in docs:
                gap("terminal_not_in_plan", tag, docs)
            elif DocType.TERMINAL_PLAN in docs and DocType.SCHEMATIC not in docs:
                gap("terminal_not_in_schematic", tag, docs)
    if has(DocType.PLC_PROGRAM) and has(DocType.PLC_SYMBOLS):
        for tag, docs in addresses.items():
            if DocType.PLC_PROGRAM in docs and DocType.PLC_SYMBOLS not in docs:
                gap("address_without_symbol", tag, docs)
            elif DocType.PLC_SYMBOLS in docs and DocType.PLC_PROGRAM not in docs:
                gap("symbol_unused", tag, docs)
    if has(DocType.PLC_PROGRAM) and has(DocType.SCHEMATIC):
        for tag, docs in addresses.items():
            if tag.startswith("M"):  # Merker sind nicht verdrahtet
                continue
            if DocType.PLC_PROGRAM in docs and DocType.SCHEMATIC not in docs:
                gap("address_not_in_schematic", tag, docs)
    if has(DocType.MANUAL) and len(present_doc_types - {DocType.MANUAL, DocType.OTHER}) > 0:
        for tag, docs in devices.items():
            if set(docs) == {DocType.MANUAL}:
                gap("device_only_in_manual", tag, docs)
    if known_sheets is not None:
        for tag, docs in refs.items():
            match = _CROSS_REF.match(tag)
            if match and int(match.group(1)) not in known_sheets:
                gap("cross_ref_dangling", tag, docs)

    order = {kind: i for i, kind in enumerate(GAP_LABELS)}
    gaps.sort(key=lambda g: (order[g.kind], _sort_key(g.tag)))

    coverage = [
        {"tag": tag, "tag_type": tag_type, "docs": docs}
        for tag_type, table in ((TagType.DEVICE, devices), (TagType.TERMINAL, pins), (TagType.PLC_ADDRESS, addresses))
        for tag, docs in sorted(table.items(), key=lambda kv: _sort_key(kv[0]))
    ]
    return {
        "summary": {
            "devices": len(devices),
            "terminals": len(pins),
            "plc_addresses": len(addresses),
            "gaps": len(gaps),
        },
        "gaps": [g.__dict__ for g in gaps],
        "coverage": coverage,
    }


def _sort_key(tag: str) -> tuple:
    """-K2 vor -K12, -X3:2 vor -X3:10, E0.1 vor E1.0."""
    return tuple(int(part) if part.isdigit() else part for part in re.split(r"(\d+)", tag))
