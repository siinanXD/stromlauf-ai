"""Blatttitel und Stuecklistenseiten einer mehrseitigen Schaltplan-PDF, ohne Modell (Issue #39).

Reale Exporte (EPLAN, QElectroTech) buendeln Deckblatt, Inhaltsverzeichnis, Stromlaufplan, Klemmenplaene und
Stueckliste in einer PDF. Der Titel eines Blatts steht im Schriftfeld der Seite und im Inhaltsverzeichnis
("Blatt 4  Not-Halt-Kreis", "4 Mains Power Supply IM ..."); wo beides zusammenpasst, ist der Titel sicher.
Seiten mit einer Stuecklisten-Ueberschrift (Stueckliste, Nomenclature, Parts list) liefern Bezeichnungen fuer
das Maschinenmodell, bilden aber keine Blatt-Zone.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

PARTS_LIST_TITLE = re.compile(
    r"^\W*(nomenclature|artikelst(ü|ue)ckliste|st(ü|ue)ckliste|bauteilliste|parts?\s*list|bill of materials?)\b", re.I
)
_CONTENTS_PAGES = 3
_ENTRY_INLINE = re.compile(r"^(?:blatt|seite|folio|page|sheet)?\s*[:.]?\s*(\d{1,3})\s+(\S.*)$", re.I)
_ENTRY_LABEL = re.compile(r"^(?:blatt|seite|folio|page|sheet)\s*[:.]?\s*(\d{1,3})\s*$", re.I)
_FRAME_LINE = re.compile(r"^[\d\s]+$|^[A-Z]$")  # Spaltenraster "1 2 3 ..." und Zeilenbuchstaben des Rahmens


def is_parts_list(title: str | None) -> bool:
    return bool(title) and PARTS_LIST_TITLE.match(title) is not None


def _lines(page) -> list[str]:
    text = getattr(page, "raw_text", "") or getattr(page, "markdown", "")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _contents(pages: list) -> dict[int, list[str]]:
    """Titelkandidaten je Blattnummer aus den ersten Seiten: "4 Mains Power Supply ..." oder "Blatt 4" + Folgezeile."""
    entries: dict[int, list[str]] = {}
    for page in pages[:_CONTENTS_PAGES]:
        lines = _lines(page)
        for index, line in enumerate(lines):
            if (label := _ENTRY_LABEL.match(line)) and index + 1 < len(lines):
                entries.setdefault(int(label.group(1)), []).append(lines[index + 1])
            elif inline := _ENTRY_INLINE.match(line):
                entries.setdefault(int(inline.group(1)), []).append(inline.group(2).strip())
    return entries


def _title_lines(page) -> list[str]:
    return [
        line for line in _lines(page)
        if 2 <= len(line) <= 80 and re.search(r"[A-Za-z]", line) and not _FRAME_LINE.match(line)
    ]


def page_titles(pages: Iterable, sheet_of: dict[int, int] | None = None) -> tuple[dict[int, str], set[int]]:
    """(Titel je Seite, Seiten mit Stueckliste). Seiten ohne sicheren Titel fehlen im Dict.

    Das Inhaltsverzeichnis nennt Blaetter, nicht Seiten: sheet_of ist das Blatt je Seite aus der Blatt-Map
    (pdf_layout.sheet_map, Issue #67), damit Deckblatt und Inhaltsverzeichnis vor Blatt 1 nichts verschieben.
    Ohne sheet_of gilt Seite = Blatt.
    """
    pages = list(pages)
    contents = _contents(pages)
    titles: dict[int, str] = {}
    parts: set[int] = set()
    for page in pages:
        number = getattr(page, "page", None)
        if number is None:
            continue
        sheet = number if sheet_of is None else sheet_of.get(number)
        lines = _title_lines(page)
        title = ""
        for candidate in contents.get(sheet, []) if sheet is not None else []:
            for line in lines:
                if candidate == line or candidate.startswith(line + " ") or line.startswith(candidate):
                    if len(line) > len(title):
                        title = line
        if not title:
            title = next((line for line in lines if is_parts_list(line)), "")
        if title:
            titles[number] = title
        if is_parts_list(title):
            parts.add(number)
    return titles, parts
