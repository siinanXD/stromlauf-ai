"""Pruefvorlage nach DGUV Vorschrift 3 / DIN VDE 0105-100 (SIN-733): aus der Stueckliste eine vorausgefuellte Liste.

Reine Ausgabe ohne Datenbank und Modell. Das ist eine Arbeitsvorlage, keine Pruefbescheinigung: Die Software traegt nur
Betriebsmittel (BMK, Typ) und die Pruefpunkte je Bauteilart ein. Messwerte und Ergebnis bleiben leer, es gibt keine
Bewertung und kein vorbelegtes Ergebnis. Normen stehen nur als Verweis, ihr Text ist nicht abgedruckt.
"""

import io
import re
from dataclasses import dataclass, field

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.werk.bom import Bom, letter_for

NOTICE = (
    "Vorausgefüllt durch Software, Prüfung und Bewertung durch Elektrofachkraft. "
    "Diese Vorlage ist keine Prüfbescheinigung und enthält keine Bewertung."
)
REFERENCE = "Verweis: DGUV Vorschrift 3, DIN VDE 0105-100 (Normtexte nicht abgedruckt)."
HEADER_FIELDS = ("Anlage", "Prüfer", "Datum", "Messgerät")
MEASURE_HEADERS = {
    "rpe": "Schutzleiterwiderstand",
    "riso": "Isolationswiderstand",
    "rcd": "Auslösestrom / -zeit (RCD)",
}
MEASURES = tuple(MEASURE_HEADERS)
NOT_APPLICABLE = "–"
RESULT_HEADER = "Ergebnis"

# Pruefpunkte und Messungen je Bauteilart; Auswahl ueber den Kennbuchstaben, RCD vorab ueber das Wort.
_RCD_RE = re.compile(r"\b(fi|rcd|rcbo|fehlerstrom\w*)\b", re.IGNORECASE)
_VISUAL = "Sichtprüfung (Zustand, Beschädigung)"
_MARKING = "Kennzeichnung lesbar und vollständig"
CHECKS_RCD = ([_VISUAL, _MARKING, "Auslöseprüfung (Prüftaste und Messung)"], ("rpe", "riso", "rcd"))
CHECKS_PROTECT = ([_VISUAL, _MARKING], ())
CHECKS_TERMINAL = (["Sitz der Klemme und Leiter", "Beschriftung vorhanden"], ())
CHECKS_DEVICE = ([_VISUAL, _MARKING], ("rpe", "riso"))
CHECKS_BY_LETTER = {"F": CHECKS_PROTECT, "X": CHECKS_TERMINAL}


@dataclass
class CheckRow:
    bmk: str
    part: str
    type: str
    points: list[str]
    measures: tuple[str, ...]  # Messungen, die bei diesem Betriebsmittel vorgesehen sind; das Feld bleibt leer
    result: str = ""  # immer leer: die Elektrofachkraft traegt es ein


@dataclass
class CheckTemplate:
    title: str
    rows: list[CheckRow] = field(default_factory=list)


def checks_for(part: str, type_: str = "") -> tuple[list[str], tuple[str, ...]]:
    if _RCD_RE.search(f"{part} {type_}"):
        return CHECKS_RCD
    return CHECKS_BY_LETTER.get(letter_for(part, type_), CHECKS_DEVICE)


def build_template(bom: Bom, title: str) -> CheckTemplate:
    """Eine Zeile je Betriebsmittel (BMK), nicht je Stuecklistenposition; Reihenfolge der Stueckliste."""
    rows: list[CheckRow] = []
    seen: set[str] = set()
    for item in bom.rows:
        points, measures = checks_for(item.part, item.type)
        for bmk in item.bmk:
            if bmk in seen:
                continue
            seen.add(bmk)
            rows.append(CheckRow(bmk, item.part, item.type, list(points), measures))
    return CheckTemplate(title=title, rows=rows)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_pdf(template: CheckTemplate) -> bytes:
    """A4 quer: Hinweis, Kopf mit leeren Feldern, Tabelle mit leeren Mess- und Ergebnisfeldern; Kopfzeile wiederholt."""
    out = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        out,
        pagesize=page,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
        title=f"Prüfvorlage – {template.title}",
    )
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=7.5, leading=9)
    notice = styles["BodyText"].clone("notice", fontSize=9, leading=11, textColor=colors.HexColor("#8A1C1C"))
    story = [
        Paragraph(f"Prüfvorlage DGUV V3 – {_escape(template.title)}", styles["Heading2"]),
        Paragraph(f"<b>{_escape(NOTICE)}</b>", notice),
        Paragraph(_escape(REFERENCE), small),
        Spacer(1, 3 * mm),
    ]
    head = Table(
        [[Paragraph(f"<b>{name}:</b>", small) for name in HEADER_FIELDS], [""] * len(HEADER_FIELDS)],
        colWidths=[(page[0] - 24 * mm) / len(HEADER_FIELDS)] * len(HEADER_FIELDS),
        rowHeights=[None, 8 * mm],
    )
    head.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
    story += [head, Spacer(1, 4 * mm)]
    headers = ["BMK", "Typ", "Prüfpunkte", *MEASURE_HEADERS.values(), RESULT_HEADER]
    data = [[Paragraph(f"<b>{h}</b>", small) for h in headers]]
    for row in template.rows:
        label = f"{row.part} {row.type}".strip() if row.type != row.part else row.part
        points = "<br/>".join(f"☐ {_escape(p)}" for p in row.points)
        cells = [Paragraph(_escape(row.bmk), small), Paragraph(_escape(label), small), Paragraph(points, small)]
        cells += ["" if key in row.measures else Paragraph(NOT_APPLICABLE, small) for key in MEASURES]
        cells.append(row.result)
        data.append(cells)
    widths = [22, 50, 80, 28, 28, 32, 28]
    scale = (page[0] - 24 * mm) / (sum(widths) * mm)
    table = Table(data, colWidths=[w * mm * scale for w in widths], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6E6E6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return out.getvalue()
