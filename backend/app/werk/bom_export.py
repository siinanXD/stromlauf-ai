"""Export der Stueckliste (SIN-732) als CSV, Excel und PDF. Reine Ausgabe, kein Modell, keine Datenbank.

Spalten: Nr., BMK, Menge, Bauteil, Hersteller, Typ, Artikelnummer, Nennwerte, Sicherheit, zu prüfen, Foto.
„Foto“ verweist auf den Kasten mit der Nr. der Zeile im Übersichtsfoto. Zellen, die mit `=`, `+`, `-`, `@`
beginnen, schreibt der Export als Text (kein Formel-Einschleusen aus gelesenen Typenschildern); BMK beginnen mit `-`.
"""

import csv
import io
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image as PdfImage
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.werk.bom import Bom, BomItem

HEADERS = ["Nr.", "BMK", "Menge", "Bauteil", "Hersteller", "Typ", "Artikelnummer", "Nennwerte", "Sicherheit", "zu prüfen", "Foto"]
MAX_PDF_PAGES = 3
MAX_ROWS_PER_PAGE = 28
PHOTO_EDGE = 1600  # längste Kante des Übersichtsfotos im PDF in Pixeln
UNSURE_FILL = "FFF2CC"
_FORMULA_START = ("=", "+", "@")


def _safe(text: str) -> str:
    """Text, den Tabellenprogramme nicht als Formel lesen."""
    return "'" + text if text.startswith(_FORMULA_START) else text


def _confidence(value: float | None) -> str:
    return "" if value is None else f"{round(value * 100)} %"


def table_rows(bom: Bom) -> list[list]:
    return [
        [
            row.number,
            ", ".join(row.bmk),
            row.quantity,
            row.part,
            row.manufacturer,
            row.type,
            row.order_number,
            row.rating,
            _confidence(row.confidence),
            "ja" if row.review else "",
            f"Kasten {row.number}",
        ]
        for row in bom.rows
    ]


def to_csv(bom: Bom) -> bytes:
    """Semikolon-getrennt mit BOM, damit deutsches Excel Umlaute und Spalten richtig öffnet."""
    out = io.StringIO()
    writer = csv.writer(out, delimiter=";", lineterminator="\r\n")
    writer.writerow(HEADERS)
    for row in table_rows(bom):
        writer.writerow([_safe(cell) if isinstance(cell, str) else cell for cell in row])
    return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8")


def to_xlsx(bom: Bom) -> bytes:
    """Tabelle mit Autofilter, fixierter Kopfzeile, Summenzeile (Formel) und gelb markierten unsicheren Zeilen."""
    book = Workbook()
    sheet = book.active
    sheet.title = "Stückliste"
    sheet.append(HEADERS)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    fill = PatternFill("solid", start_color=UNSURE_FILL, end_color=UNSURE_FILL)
    for row, values in zip(bom.rows, table_rows(bom), strict=True):
        sheet.append(values)
        for cell in sheet[sheet.max_row]:
            if isinstance(cell.value, str) and cell.value.startswith(_FORMULA_START):
                cell.data_type = "s"  # Text, keine Formel
        if row.review:
            for cell in sheet[sheet.max_row]:
                cell.fill = fill
    last = sheet.max_row
    sheet.auto_filter.ref = f"A1:{get_column_letter(len(HEADERS))}{max(last, 1)}"
    sheet.freeze_panes = "A2"
    sheet.append(["", "Summe", f"=SUM(C2:C{last})" if last > 1 else 0])
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True)
    for index, header in enumerate(HEADERS, start=1):
        width = max([len(str(header))] + [len(str(c.value or "")) for c in sheet[get_column_letter(index)]])
        sheet.column_dimensions[get_column_letter(index)].width = min(width + 2, 48)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def annotated_photo(image_path: Path, items: list[BomItem], number_by_item: dict[str, int]) -> bytes:
    """Schrankfoto mit nummerierten Kästen (Nr. der Stücklistenzeile), als JPEG verkleinert."""
    image = Image.open(image_path).convert("RGB")
    scale = min(1.0, PHOTO_EDGE / max(image.size))
    if scale < 1.0:
        image = image.resize((max(int(image.width * scale), 1), max(int(image.height * scale), 1)))
    draw = ImageDraw.Draw(image)
    width, height = image.size
    line = max(2, width // 400)
    for item in items:
        number = number_by_item.get(item.id)
        if number is None:
            continue
        x0, y0 = item.x * width, item.y * height
        x1, y1 = (item.x + item.w) * width, (item.y + item.h) * height
        color = (200, 120, 0) if item.confidence is not None and item.confidence < 0.7 else (0, 90, 200)
        draw.rectangle((x0, y0, x1, y1), outline=color, width=line)
        text = str(number)
        box = draw.textbbox((0, 0), text)
        tw, th = box[2] - box[0] + 6, box[3] - box[1] + 6
        draw.rectangle((x0, y0, x0 + tw, y0 + th), fill=color)
        draw.text((x0 + 3, y0 + 1), text, fill=(255, 255, 255))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return out.getvalue()


def to_pdf(bom: Bom, title: str, photo_jpeg: bytes | None) -> bytes:
    """A4 quer: Übersichtsfoto mit Kästen auf Seite 1, darunter bzw. danach die Tabelle; höchstens 3 Seiten.

    Passt die Tabelle nicht in drei Seiten, kürzt das PDF nicht still: Es bricht mit ValueError ab, und
    Excel/CSV bleiben der vollständige Weg."""
    if len(bom.rows) > MAX_ROWS_PER_PAGE * (MAX_PDF_PAGES - 1) + 12:
        raise ValueError("Die Stückliste ist für das PDF zu lang (höchstens 3 Seiten); bitte Excel oder CSV nehmen.")
    out = io.BytesIO()
    page = landscape(A4)
    doc = SimpleDocTemplate(
        out, pagesize=page, leftMargin=12 * mm, rightMargin=12 * mm, topMargin=10 * mm, bottomMargin=10 * mm, title=title
    )
    styles = getSampleStyleSheet()
    small = styles["BodyText"].clone("small", fontSize=7, leading=8.5)
    story = [Paragraph(f"Stückliste – {_escape(title)}", styles["Heading2"]), Spacer(1, 2 * mm)]
    if photo_jpeg:
        reader = ImageReader(io.BytesIO(photo_jpeg))
        iw, ih = reader.getSize()
        max_w, max_h = page[0] - 24 * mm, page[1] * 0.42
        ratio = min(max_w / iw, max_h / ih)
        story += [PdfImage(io.BytesIO(photo_jpeg), width=iw * ratio, height=ih * ratio), Spacer(1, 3 * mm)]
    header = [Paragraph(f"<b>{h}</b>", small) for h in HEADERS[:-1]]
    body = [
        [Paragraph(_escape(str(cell)), small) for cell in values[:-1]] for values in table_rows(bom)
    ]
    total = [Paragraph("", small), Paragraph("<b>Summe</b>", small), Paragraph(f"<b>{bom.total}</b>", small)]
    data = [header, *body, total + [Paragraph("", small)] * (len(header) - 3)]
    widths = [10, 38, 14, 36, 30, 40, 38, 36, 18, 16]
    scale = (page[0] - 24 * mm) / (sum(widths) * mm)
    table = Table(data, colWidths=[w * mm * scale for w in widths], repeatRows=1)
    style = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6E6E6")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
    ]
    for index, row in enumerate(bom.rows, start=1):
        if row.review:
            style.append(("BACKGROUND", (0, index), (-1, index), colors.HexColor(f"#{UNSURE_FILL}")))
    table.setStyle(TableStyle(style))
    story.append(table)
    doc.build(story)
    return out.getvalue()


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
