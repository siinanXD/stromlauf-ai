"""Anlagen-Onboarding: Vorschlag fuer Maschine und Fehlerliste aus den Dokumenten, ohne Sprachmodell.

Fehlerlisten stehen in Handbuechern fast immer als Tabelle "Symptom | Ursache | Abhilfe"; solche
Markdown-Tabellen (auch aus Docling-PDFs) werden zu Fehlereintraegen.
"""

import re

from app.ingestion.tags import TagType, extract_tags

SYMPTOM = ("symptom", "stoerung", "störung", "fehlerbild", "fehler", "problem")
CAUSE = ("ursache", "moegliche ursache", "mögliche ursache", "grund")
FIX = ("pruefung", "prüfung", "abhilfe", "behebung", "massnahme", "maßnahme", "loesung", "lösung")
CODE = ("code", "fehlercode", "nr", "nr.", "meldung")

MACHINE_TYPES = (
    ("conveyor", ("foerder", "förder", "band", "transport")),
    ("robot", ("roboter", "robot", "handling")),
    ("packaging", ("verpack", "palettier", "etikett")),
    ("storage", ("lager", "magazin", "puffer", "speicher")),
    ("main", ("presse", "fraes", "fräs", "spritzguss", "dreh", "schweiss", "schweiß", "maschine")),
)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _column(header: list[str], names: tuple[str, ...]) -> int | None:
    for index, cell in enumerate(header):
        lowered = cell.lower()
        if lowered in names or any(lowered.startswith(name) for name in names):
            return index
    return None


def _cell(row: list[str], column: int | None) -> str:
    return row[column] if column is not None and column < len(row) else ""


def _reference(doc_label: str, heading: str) -> str:
    match = re.match(r"(\d+(?:\.\d+)*)\.?\s", heading)
    if match:
        return f"{doc_label} Kap. {match.group(1)}"
    return f"{doc_label}, {heading}" if heading else doc_label


def _tags(text: str) -> list[str]:
    found = [t.tag for t in extract_tags(text) if t.tag_type in (TagType.DEVICE, TagType.TERMINAL)]
    return list(dict.fromkeys(tag for tag in found if "/" not in tag))


def fault_rows_from_markdown(markdown: str, doc_label: str) -> list[dict]:
    """Fehlertabellen (Symptom + Ursache und/oder Abhilfe) aus Markdown als Fehlereintraege."""
    faults = []
    heading = ""
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if match := re.match(r"#{1,6}\s+(.*)", line):
            heading = match.group(1).strip()
        is_table = line.strip().startswith("|") and index + 1 < len(lines) and re.match(r"\s*\|?\s*:?-{3,}", lines[index + 1])
        if not is_table:
            index += 1
            continue
        header = _cells(line)
        symptom, cause, fix, code = (_column(header, names) for names in (SYMPTOM, CAUSE, FIX, CODE))
        index += 2
        rows = []
        while index < len(lines) and lines[index].strip().startswith("|"):
            rows.append(_cells(lines[index]))
            index += 1
        if symptom is None or (cause is None and fix is None):
            continue
        for row in rows:
            if not _cell(row, symptom):
                continue
            faults.append(
                {
                    "code": _cell(row, code),
                    "symptom": _cell(row, symptom),
                    "cause": _cell(row, cause),
                    "fix": _cell(row, fix),
                    "doc_ref": _reference(doc_label, heading),
                    "tags": _tags(" ".join(row)),
                }
            )
    return faults


def guess_machine(hints: list[str]) -> tuple[str, str]:
    """(Name, Maschinentyp) aus Stuecklisten-Titel oder Quellenname."""
    name = ""
    for hint in hints:
        if match := re.match(r"\s*St(?:ue|ü)ckliste\s+(.+)", hint, re.I):
            name = match.group(1).strip()
            break
    name = name or next((h.strip() for h in hints if h and h.strip()), "Neue Maschine")
    lowered = name.lower()
    machine_type = next((kind for kind, words in MACHINE_TYPES if any(w in lowered for w in words)), "other")
    return name, machine_type
