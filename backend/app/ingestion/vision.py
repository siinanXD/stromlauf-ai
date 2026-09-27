"""Schaltplanseiten als Bild rendern und per Claude Vision strukturiert beschreiben."""

import base64
import io
from pathlib import Path

import pypdfium2 as pdfium
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.ingestion.docling_parser import pdfium_lock

VISION_PROMPT = """Du bist Elektrokonstrukteur und analysierst eine Seite eines industriellen \
Stromlaufplans (meist EPLAN, IEC 81346). Beschreibe die Seite so, dass ein Instandhalter \
spaeter per Textsuche Zusammenhaenge findet. Erfinde nichts: was nicht lesbar ist, \
markiere mit "(unleserlich)".

Gib Markdown mit genau diesen Abschnitten aus (leere Abschnitte weglassen):

## Seite
Seitentitel, Anlage/Ort (=/+), Blattnummer, Funktion der Seite in 1-2 Saetzen.

## Betriebsmittel
Je Zeile: BMK | Art (Schuetz, Motorschutzschalter, Sicherung, Sensor, SPS-Karte, ...) | \
technische Daten/Typ | Funktion.

## Verbindungen
Je Zeile: von (BMK:Anschluss) -> nach (BMK:Anschluss) | Potential/Adernummer/Querschnitt. \
Folge den Strompfaden von oben nach unten.

## Klemmen
Klemmleiste:Klemme | intern angeschlossen an | extern angeschlossen an / Kabel.

## SPS
Adresse (z.B. E0.0) | Karte/Kanal | Signalname | angeschlossenes Betriebsmittel.

## Querverweise
Verweise auf andere Seiten (z.B. /12.3) und wozu sie gehoeren (Kontaktspiegel, Potentialweiterfuehrung).

## Funktionsbeschreibung
Kurz: was schaltet was, welche Bedingungen muessen erfuellt sein, Sicherheitsfunktionen.
"""


def render_page_png(path: Path, page: int, max_edge: int | None = None) -> bytes:
    """Rendert eine PDF-Seite (1-basiert) als PNG mit begrenzter laengster Kante."""
    max_edge = max_edge or get_settings().vision_max_edge
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            if not 1 <= page <= len(pdf):
                raise ValueError(f"Seite {page} existiert nicht (Dokument hat {len(pdf)} Seiten)")
            pdf_page = pdf[page - 1]
            width, height = pdf_page.get_size()
            scale = max_edge / max(width, height)
            image = pdf_page.render(scale=scale).to_pil().convert("RGB")
        finally:
            pdf.close()
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def image_block(png: bytes) -> dict:
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": base64.standard_b64encode(png).decode("ascii"),
        },
    }


def describe_page(path: Path, page: int, extracted_text: str = "", trace: dict | None = None) -> str:
    settings = get_settings()
    llm = ChatAnthropic(
        model=settings.vision_model,
        api_key=settings.anthropic_api_key,
        max_tokens=8000,
        max_retries=3,
    )
    hint = ""
    if extracted_text.strip():
        hint = (
            "\n\nAus dem PDF extrahierte Beschriftungen dieser Seite (zur exakten Schreibweise "
            f"von Kennzeichen):\n{extracted_text.strip()}"
        )
    message = HumanMessage(
        content=[image_block(render_page_png(path, page)), {"type": "text", "text": VISION_PROMPT + hint}]
    )
    response = llm.invoke([message], trace or None)
    content = response.content
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
