"""Scan-Fixtures aus dem Beispielplan FB-01: dieselben Blaetter als Bild, ohne Textebene (Issue #64).

Aufruf:  python scripts/example_docs/make_scan.py [ZIELORDNER]      (Standard: examples/scan)

Erzeugt aus examples/foerderband/01_Stromlaufplan_FB-01.pdf:
- 01_Stromlaufplan_FB-01_scan.pdf      alle 7 Blaetter als Bild, keine Textebene
- 01_Stromlaufplan_FB-01_teilscan.pdf  Text-PDF, nur Blatt 3 als Bild
- 01_Stromlaufplan_FB-01_quer.pdf      Text-PDF, Blatt 4 als Bild und um 90 Grad gedreht (hochkant gescannt)

"Scan" heisst hier: 200 dpi, Graustufen, 0,5 Grad schief, grauer Papierton, Rauschen mit festem Seed, leicht
unscharf, JPEG. Gleiche Umgebung ergibt gleiche Bytes; die Ground Truth bleibt eval/ingest_gold/fb01.json.
"""

import hashlib
import io
import re
import sys
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "examples" / "foerderband" / "01_Stromlaufplan_FB-01.pdf"
TARGET = ROOT / "examples" / "scan"

DPI = 200
SKEW_DEGREES = 0.5
PAPER = 242  # grauer Papierton statt reinem Weiss
NOISE = 4.0  # Standardabweichung des Rauschens in Graustufen
BLUR = 0.6  # Radius der Unschaerfe in Pixeln
QUALITY = 60  # JPEG-Qualitaet
SEED = 64  # Issue-Nummer; je Blatt SEED + Blattnummer
# pdfium schreibt beim Speichern Erstellzeit und Zufalls-ID; beide werden durch feste Werte gleicher Laenge
# ersetzt, damit die Offsets der Querverweistabelle stimmen und gleiche Eingaben gleiche Bytes ergeben.
_CREATION_DATE = re.compile(rb"/CreationDate\(D:\d{14}")
_FILE_ID = re.compile(rb"/ID\[<[0-9A-Fa-f]{32}><[0-9A-Fa-f]{32}>\]")


def scan_image(source: Path, page: int, rotate: int = 0) -> Image.Image:
    """Blatt `page` (1-basiert) als Scan; rotate=90 dreht das Bild wie ein hochkant eingelegtes Blatt."""
    pdf = pdfium.PdfDocument(str(source))
    try:
        image = pdf[page - 1].render(scale=DPI / 72).to_pil().convert("L")
    finally:
        pdf.close()
    image = image.rotate(SKEW_DEGREES, resample=Image.Resampling.BICUBIC, fillcolor=255)
    pixels = np.asarray(image, dtype=np.float32) * (PAPER / 255.0)
    pixels += np.random.default_rng(SEED + page).normal(0.0, NOISE, pixels.shape)
    image = Image.fromarray(np.clip(pixels, 0, 255).astype(np.uint8))
    image = image.filter(ImageFilter.GaussianBlur(BLUR))
    return image.rotate(rotate, expand=True) if rotate else image


def image_pdf(images: list[Image.Image]) -> bytes:
    """Reines Bild-PDF ohne Textebene; ohne Zeitstempel, damit gleiche Bilder gleiche Bytes ergeben."""
    buffer = io.BytesIO()
    images[0].save(
        buffer,
        "PDF",
        save_all=True,
        append_images=images[1:],
        resolution=DPI,
        quality=QUALITY,
        title="Stromlaufplan Foerderband FB-01 (Scan)",
        creationDate=None,
        modDate=None,
    )
    return buffer.getvalue()


def _without_timestamp(data: bytes) -> bytes:
    """Erstellzeit fest, Datei-ID aus dem Inhalt statt zufaellig (gleiche Laenge, Offsets bleiben gueltig)."""
    data = _CREATION_DATE.sub(b"/CreationDate(D:20260929000000", data)
    zeroed = _FILE_ID.sub(b"/ID[<" + b"0" * 32 + b"><" + b"0" * 32 + b">]", data)
    digest = hashlib.md5(zeroed, usedforsecurity=False).hexdigest().upper().encode()
    return _FILE_ID.sub(b"/ID[<" + digest + b"><" + digest + b">]", zeroed)


def with_scanned_pages(source: Path, scans: dict[int, Image.Image], out: Path) -> None:
    """Text-PDF, in dem die Blaetter aus `scans` durch Bildseiten ersetzt sind."""
    text = pdfium.PdfDocument(str(source))
    result = pdfium.PdfDocument.new()
    images = []
    buffer = io.BytesIO()
    try:
        for page in range(1, len(text) + 1):
            if page in scans:
                images.append(pdfium.PdfDocument(image_pdf([scans[page]])))
                result.import_pages(images[-1], [0])
            else:
                result.import_pages(text, [page - 1])
        result.save(buffer)
    finally:
        for pdf in (*images, result, text):
            pdf.close()
    out.write_bytes(_without_timestamp(buffer.getvalue()))


def build(target: Path = TARGET, source: Path = SOURCE) -> list[Path]:
    target.mkdir(parents=True, exist_ok=True)
    full = target / "01_Stromlaufplan_FB-01_scan.pdf"
    partial = target / "01_Stromlaufplan_FB-01_teilscan.pdf"
    sideways = target / "01_Stromlaufplan_FB-01_quer.pdf"
    pdf = pdfium.PdfDocument(str(source))
    pages = len(pdf)
    pdf.close()
    full.write_bytes(image_pdf([scan_image(source, page) for page in range(1, pages + 1)]))
    with_scanned_pages(source, {3: scan_image(source, 3)}, partial)
    with_scanned_pages(source, {4: scan_image(source, 4, rotate=90)}, sideways)
    return [full, partial, sideways]


if __name__ == "__main__":
    for path in build(Path(sys.argv[1]) if len(sys.argv) > 1 else TARGET):
        print(
            f"{path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path}: {path.stat().st_size // 1024} KB"
        )
