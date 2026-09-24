"""Dokumente mit Docling nach Markdown wandeln - seitenweise, damit Quellenangaben stimmen."""

import logging
import threading
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

from app.config import get_settings

logger = logging.getLogger(__name__)

DOCLING_SUFFIXES = {".pdf", ".docx", ".xlsx", ".pptx", ".html", ".htm", ".md", ".csv",
                    ".png", ".jpg", ".jpeg", ".tif", ".tiff"}  # fmt: skip
PLAIN_TEXT_SUFFIXES = {".txt", ".log", ".ini", ".xml", ".json"}

_converter = None
_converter_lock = threading.Lock()
# pdfium ist nicht threadsicher
pdfium_lock = threading.Lock()


@dataclass
class ParsedPage:
    page: int | None  # 1-basiert; None bei Formaten ohne Seiten
    markdown: str
    raw_text: str = ""

    @property
    def text(self) -> str:
        """Docling-Markdown, ergaenzt um PDF-Rohtext wenn das Layoutmodell wenig erkannt hat.

        Stromlaufplan-Seiten sind fuer Docling oft ein einziges "Bild"; die Beschriftungen
        (BMK, Klemmen, Adressen) stecken dann nur im Rohtext.
        """
        markdown = self.markdown.replace("<!-- image -->", "").strip()
        raw = self.raw_text.strip()
        if raw and len(markdown) < 0.6 * len(raw):
            return f"{markdown}\n\n### Beschriftungen (Rohtext)\n{raw}".strip()
        return markdown


def _get_converter():
    global _converter
    with _converter_lock:
        if _converter is None:
            from docling.datamodel.base_models import InputFormat
            from docling.datamodel.pipeline_options import PdfPipelineOptions
            from docling.document_converter import DocumentConverter, PdfFormatOption

            options = PdfPipelineOptions()
            options.do_ocr = get_settings().ocr_enabled
            options.do_table_structure = True
            _converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
            )
        return _converter


def pdf_raw_text(path: Path) -> dict[int, str]:
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            texts = {}
            for index in range(len(pdf)):
                textpage = pdf[index].get_textpage()
                texts[index + 1] = textpage.get_text_bounded()
            return texts
        finally:
            pdf.close()


def pdf_page_count(path: Path) -> int:
    with pdfium_lock:
        pdf = pdfium.PdfDocument(str(path))
        try:
            return len(pdf)
        finally:
            pdf.close()


def parse_document(path: Path) -> list[ParsedPage]:
    suffix = path.suffix.lower()
    if suffix in PLAIN_TEXT_SUFFIXES:
        from app.ingestion.awl_parser import read_text

        return [ParsedPage(page=None, markdown=read_text(path))]
    if suffix not in DOCLING_SUFFIXES:
        raise ValueError(f"Dateityp {suffix} wird nicht unterstuetzt")

    result = _get_converter().convert(str(path))
    document = result.document

    if suffix != ".pdf":
        return [ParsedPage(page=None, markdown=document.export_to_markdown())]

    raw_texts = pdf_raw_text(path)
    pages = []
    for page_no in sorted(raw_texts):
        try:
            markdown = document.export_to_markdown(page_no=page_no)
        except Exception:  # Docling kennt die Seite nicht (z.B. leere Seite)
            logger.warning("Docling lieferte kein Markdown fuer Seite %s von %s", page_no, path.name)
            markdown = ""
        pages.append(ParsedPage(page=page_no, markdown=markdown, raw_text=raw_texts[page_no]))
    return pages
