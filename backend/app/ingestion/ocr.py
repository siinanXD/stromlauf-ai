"""Texterkennung fuer Scans: RapidOCR lokal und eine unsichtbare Textebene im PDF (Issue #65).

Aus einem Scan-PDF wird ein durchsuchbares PDF wie bei OCRmyPDF: gleiches Bild, darueber unsichtbar der
erkannte Text an seiner Position, ein Textobjekt je Zeile. Danach lesen alle Leser der Textebene
(Rohtext, Blatt-Map, Spalten, Dokumenttyp, Zitat-Resolver) den Scan ohne Sonderpfad.

RapidOCR laeuft mit den mitgelieferten PP-OCRv6-Modellen ueber onnxruntime auf der CPU: kein Netz, kein
Download, keine API-Kosten. Je Seite: Detektion fuer Drehung und Schraeglage, dann die gerade gestellte
Seite erkennen, lange Zeilen an Wortluecken teilen (das Modell schneidet sie sonst nach etwa 110 Zeichen ab)
und den Text normalisieren. Messwerte: eval/run_ingest.py --ocr.
"""

import ctypes
import logging
import math
import os
import re
import shutil
import threading
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c
from PIL import Image

from app.ingestion.docling_parser import pdf_raw_text, pdfium_lock

logger = logging.getLogger(__name__)

# Weniger lesbare Zeichen in der Textebene: Seite braucht OCR. Im Bestand (FB-01, Festo, QET, AWL-Handbuch;
# 470 Seiten) hat jede Textseite weit mehr, Scans und kaputte Textebenen haben 0. 10 faengt auch eine Scanseite
# mit aufgestempelter Seitenzahl, eine fast leere Textseite kostet nur eine ueberfluessige Erkennung.
MIN_TEXT_CHARS = 10
DEFAULT_DPI = 300  # Seite ohne eingebettetes Bild (Vektorseite mit kaputter Textebene)
MIN_DPI, MAX_DPI = (
    150,
    400,
)  # native Aufloesung des Scans, begrenzt; Hochrechnen verschlechtert die Erkennung
MAX_SIDE = 5000  # RapidOCR verkleinert sonst jedes Bild auf 2000 Pixel Kantenlaenge
MAX_LINE_RATIO = (
    24  # Zeilen, die breiter als 24 Zeilenhoehen sind, werden zusaetzlich geteilt erkannt
)
SPLIT_MIN_SCORE = (
    0.8  # Mindestkonfidenz, damit das geteilte Ergebnis das am Stueck gelesene ersetzt
)
LONG_LINE_RATIO = (
    4  # fuer die Schraeglage zaehlen nur Zeilen, die mindestens 4-mal so breit wie hoch sind
)
DESKEW_MIN_DEGREES = 0.2
TALL_SHARE = (
    0.5  # liegen mehr als die Haelfte der Zeilen hochkant, ist die Seite gedreht eingescannt
)
FONT_SCALE = 0.7  # Schriftgroesse der unsichtbaren Zeile relativ zur Hoehe der erkannten Box
BOX_PADDING = 0.2  # Rand der Detektionsbox links und rechts, relativ zur Boxhoehe (unclip_ratio 1,6 von RapidOCR)

Point = tuple[float, float]
Quad = tuple[Point, Point, Point, Point]

_DASHES = str.maketrans({"–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-", "一": "-"})
# OCR verschluckt Leerzeichen vor Kennzeichen ("von-S2", "bzw.-X3:6", Klemmenkreis als "O-X2:3");
# die Kennzeichen-Grammatik verlangt davor ein Trennzeichen.
_GLUED_TAG = re.compile(r"(?<=[\w.)\]])(?=-[A-Z]{1,3}\d)")


@dataclass(frozen=True)
class OcrLine:
    """Eine erkannte Zeile. quad: oben links, oben rechts, unten rechts, unten links in Leserichtung,
    relativ zur Seite (0..1), Ursprung oben links."""

    text: str
    quad: Quad
    confidence: float


@dataclass(frozen=True)
class PageOcr:
    page: int
    lines: tuple[OcrLine, ...]
    dpi: int
    rotation: int  # Grad, um die das Bild fuer die Erkennung gedreht wurde (0, 90, 270)
    skew: float  # gemessene Schraeglage in Grad
    seconds: float

    @property
    def confidence(self) -> float | None:
        return float(np.mean([line.confidence for line in self.lines])) if self.lines else None


@dataclass(frozen=True)
class OcrReport:
    pages: tuple[PageOcr, ...]
    seconds: float

    @property
    def confidence(self) -> float | None:
        scores = [line.confidence for page in self.pages for line in page.lines]
        return float(np.mean(scores)) if scores else None

    def summary(self) -> dict:
        return {
            "seiten": [page.page for page in self.pages],
            "sekunden": round(self.seconds, 2),
            "sekunden_je_seite": round(self.seconds / len(self.pages), 2) if self.pages else None,
            "konfidenz": None if self.confidence is None else round(self.confidence, 3),
            "gedreht": {page.page: page.rotation for page in self.pages if page.rotation},
            "zeilen": sum(len(page.lines) for page in self.pages),
        }


def normalize(text: str) -> str:
    """Vollbreite Zeichen und Strich-Varianten vereinheitlichen, verschluckte Leerzeichen vor Kennzeichen ergaenzen."""
    text = unicodedata.normalize("NFKC", text).translate(_DASHES)
    return _GLUED_TAG.sub(" ", text)


def readable_chars(text: str) -> int:
    return sum(1 for char in text if char.isalnum())


def pages_without_text(path: Path) -> list[int]:
    """Seiten, deren Textebene weniger als MIN_TEXT_CHARS lesbare Zeichen hat (1-basiert)."""
    return [
        page for page, text in pdf_raw_text(path).items() if readable_chars(text) < MIN_TEXT_CHARS
    ]


def page_dpi(page: pdfium.PdfPage) -> int:
    """Native Aufloesung des groessten eingebetteten Bildes; DEFAULT_DPI ohne Bild."""
    best = None
    for image in page.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE]):
        left, _, right, _ = image.get_bounds()
        width_px, _ = image.get_px_size()
        if right > left and width_px:
            dpi = width_px / ((right - left) / 72)
            best = dpi if best is None else max(best, dpi)
    if best is None:
        return DEFAULT_DPI
    return int(round(min(max(best, MIN_DPI), MAX_DPI)))


# --- Erkennung ---------------------------------------------------------------------------------------

_engine_lock = threading.Lock()
_engine = None


def reset_engine() -> None:
    """Engine verwerfen (Tests); die naechste Erkennung laedt die Modelle neu."""
    global _engine
    with _engine_lock:
        _engine = None


def _run(image: np.ndarray, *, det: bool, cls: bool, rec: bool):
    """Ein RapidOCR-Aufruf. Alle Schalter ausdruecklich: RapidOCR merkt sich Schalter ueber Aufrufe hinweg."""
    global _engine
    with _engine_lock:
        if _engine is None:
            from rapidocr import RapidOCR

            _engine = RapidOCR(
                params={"Global.max_side_len": MAX_SIDE, "Global.log_level": "error"}
            )
        return _engine(image, use_det=det, use_cls=cls, use_rec=rec)


def _size(quad: np.ndarray) -> tuple[float, float]:
    width = max(np.linalg.norm(quad[1] - quad[0]), np.linalg.norm(quad[2] - quad[3]))
    height = max(np.linalg.norm(quad[3] - quad[0]), np.linalg.norm(quad[2] - quad[1]))
    return float(width), float(height)


def skew_angle(boxes) -> float:
    """Median-Neigung langer Zeilen in Grad (Bildkoordinaten, y nach unten; negativ = steigend)."""
    angles = []
    for box in boxes:
        quad = np.asarray(box, dtype=float)
        width, height = _size(quad)
        if height and width >= LONG_LINE_RATIO * height:
            dx, dy = quad[1] - quad[0]
            angles.append(math.degrees(math.atan2(dy, dx)))
    return float(np.median(angles)) if angles else 0.0


def _tall_share(boxes) -> float:
    sized = [_size(np.asarray(box, dtype=float)) for box in boxes]
    counted = [
        (w, h) for w, h in sized if max(w, h) >= 2 * min(w, h)
    ]  # einzelne Zeichen sagen nichts
    return sum(1 for w, h in counted if h > w) / len(counted) if counted else 0.0


def to_original(points: np.ndarray, angle: float, rotated_size, original_size) -> np.ndarray:
    """Punkte aus einem mit Image.rotate(angle, expand=True) gedrehten Bild ins Ursprungsbild zurueckrechnen."""
    radians = math.radians(angle)
    cos, sin = math.cos(radians), math.sin(radians)
    shifted = np.asarray(points, dtype=float) - np.array([rotated_size[0] / 2, rotated_size[1] / 2])
    back = np.stack(
        [shifted[:, 0] * cos - shifted[:, 1] * sin, shifted[:, 0] * sin + shifted[:, 1] * cos],
        axis=1,
    )
    return back + np.array([original_size[0] / 2, original_size[1] / 2])


def _crop(gray: np.ndarray, quad: np.ndarray) -> np.ndarray:
    import cv2

    width, height = (max(int(round(v)), 1) for v in _size(quad))
    target = np.float32([[0, 0], [width, 0], [width, height], [0, height]])
    matrix = cv2.getPerspectiveTransform(quad.astype(np.float32), target)
    return cv2.warpPerspective(gray, matrix, (width, height), borderMode=cv2.BORDER_REPLICATE)


def split_points(strip: np.ndarray, parts: int) -> list[int]:
    """Schnittstellen fuer eine Zeile in `parts` Stuecke, je in der Wortluecke nahe der gleichmaessigen Teilung."""
    height, width = strip.shape[:2]
    # Tinte relativ zum Papierton: auch duenne, unscharfe Striche (das "i") zaehlen, sonst schneidet man im Wort
    ink = (strip < np.median(strip) - 40).sum(axis=0)
    blank = ink == 0
    gaps: list[
        tuple[int, int]
    ] = []  # Laeufe leerer Spalten, mindestens ein Fuenftel der Boxhoehe breit
    start = None
    for x in range(width + 1):
        if x < width and blank[x]:
            start = x if start is None else start
        elif start is not None:
            if x - start >= max(height // 5, 2) and start > 0 and x < width:
                gaps.append((start, x))
            start = None
    cuts = [0]
    for k in range(1, parts):
        target = width * k // parts
        if gaps:
            left, right = min(gaps, key=lambda gap: abs((gap[0] + gap[1]) / 2 - target))
            cut = (left + right) // 2
        else:  # keine Wortluecke: an der duennsten Stelle nahe der Mitte schneiden
            window = range(
                max(target - width // (4 * parts), 1), min(target + width // (4 * parts), width - 1)
            )
            cut = min(window, key=lambda x: ink[x]) if window else target
        if cuts[-1] < cut < width:
            cuts.append(cut)
    return cuts + [width]


def _recognize_split(gray: np.ndarray, quad: np.ndarray) -> tuple[str, float] | None:
    """Lange Zeile in Stuecken lesen. Ohne Orientierungs-Klassifikator: die Zeile steht schon aufrecht, und auf
    Teilstuecken haelt er gerade Schrift gern fuer kopfstehend."""
    strip = _crop(gray, quad)
    height, width = strip.shape[:2]
    bounds = split_points(strip, math.ceil(width / height / MAX_LINE_RATIO))
    texts, scores = [], []
    for left, right in zip(bounds, bounds[1:], strict=False):
        piece = _run(np.ascontiguousarray(strip[:, left:right]), det=False, cls=False, rec=True)
        if piece.txts:
            texts.append(" ".join(piece.txts))
            scores.extend(piece.scores)
    return (" ".join(texts), float(np.mean(scores))) if texts else None


def recognize(image: Image.Image) -> list[OcrLine]:
    """Zeilen eines aufrechten Bildes, relativ zu diesem Bild (0..1, Ursprung oben links)."""
    gray = np.asarray(image.convert("L"))
    result = _run(gray, det=True, cls=True, rec=True)
    if result.boxes is None or not result.txts:
        return []
    width, height = image.size
    lines = []
    for box, text, score in zip(result.boxes, result.txts, result.scores, strict=True):
        quad = np.asarray(box, dtype=float)
        box_width, box_height = _size(quad)
        if box_height and box_width > MAX_LINE_RATIO * box_height:
            # Das Modell liest sehr lange Zeilen am Stueck abgeschnitten oder verstuemmelt, manchmal aber auch
            # richtig; das geteilte Ergebnis gilt nur, wenn es mehr lesbare Zeichen bei guter Konfidenz bringt.
            split = _recognize_split(gray, quad)
            if (
                split
                and split[1] >= SPLIT_MIN_SCORE
                and readable_chars(split[0]) > readable_chars(text)
            ):
                text, score = split
        text = normalize(text).strip()
        if text:
            relative = tuple((float(x) / width, float(y) / height) for x, y in quad)
            lines.append(OcrLine(text, relative, float(score)))
    return lines


def _map_lines(
    lines: list[OcrLine], angle: float, rotated: Image.Image, original_size
) -> list[OcrLine]:
    mapped = []
    for line in lines:
        points = np.array([(x * rotated.width, y * rotated.height) for x, y in line.quad])
        back = to_original(points, angle, rotated.size, original_size)
        quad = tuple((float(x) / original_size[0], float(y) / original_size[1]) for x, y in back)
        mapped.append(OcrLine(line.text, quad, line.confidence))
    return mapped


def read_page(image: Image.Image) -> tuple[list[OcrLine], int, float]:
    """Seite erkennen: Drehung und Schraeglage aus der Detektion, dann gerade gestellt erkennen.

    Liefert (Zeilen relativ zum Originalbild, Drehung in Grad, Schraeglage in Grad).
    """
    gray = image.convert("L")
    boxes = _run(np.asarray(gray), det=True, cls=False, rec=False).boxes
    boxes = [] if boxes is None else list(boxes)
    rotations = [90, 270] if _tall_share(boxes) > TALL_SHARE else [0]
    best: tuple[list[OcrLine], int, float] | None = None
    for rotation in rotations:
        turned = gray.rotate(rotation, expand=True) if rotation else gray
        if rotation:
            skew_boxes = _run(np.asarray(turned), det=True, cls=False, rec=False).boxes
            skew = skew_angle([] if skew_boxes is None else list(skew_boxes))
        else:
            skew = skew_angle(boxes)
        # PIL dreht gegen den Uhrzeigersinn; eine steigende Zeile (negativer Winkel) braucht eine Drehung im Uhrzeigersinn
        deskew = skew if abs(skew) >= DESKEW_MIN_DEGREES else 0.0
        upright = (
            turned.rotate(deskew, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)
            if deskew
            else turned
        )
        lines = recognize(upright)
        if deskew:
            lines = _map_lines(lines, deskew, upright, turned.size)
        if rotation:
            lines = _map_lines(lines, rotation, turned, gray.size)
        score = sum(line.confidence for line in lines)
        if best is None or score > sum(line.confidence for line in best[0]):
            best = (lines, rotation, skew)
    return best


# --- Textebene ---------------------------------------------------------------------------------------


def _add_line(document, page, font, line: OcrLine, width_pt: float, height_pt: float) -> None:
    def pdf_point(point: Point) -> np.ndarray:
        return np.array([point[0] * width_pt, (1 - point[1]) * height_pt])

    top_left, _, bottom_right, bottom_left = (pdf_point(point) for point in line.quad)
    baseline = bottom_right - bottom_left
    up = top_left - bottom_left
    length, box_height = float(np.linalg.norm(baseline)), float(np.linalg.norm(up))
    if length <= 0 or box_height <= 0:
        return
    # Die Detektion vergroessert jede Box um einen Rand; ohne ihn beruehren sich die Zeichenboxen benachbarter
    # Zeilen, und pdfium liest "6" und "E0.5" als "6E0.5".
    along = baseline / length
    pad = min(BOX_PADDING * box_height, 0.25 * length)
    bottom_left, length = bottom_left + along * pad, length - 2 * pad
    size = max(box_height * FONT_SCALE, 1.0)
    obj = pdfium_c.FPDFPageObj_CreateTextObj(document.raw, font, ctypes.c_float(size))
    # abschliessendes Leerzeichen: trennt die Zeile sicher von der naechsten auf derselben Hoehe
    buffer = ctypes.create_string_buffer((line.text + " \x00").encode("utf-16-le"))
    pdfium_c.FPDFText_SetText(obj, ctypes.cast(buffer, pdfium_c.FPDF_WIDESTRING))
    pdfium_c.FPDFTextObj_SetTextRenderMode(obj, pdfium_c.FPDF_TEXTRENDERMODE_INVISIBLE)
    left, bottom, right, top = (ctypes.c_float() for _ in range(4))
    pdfium_c.FPDFPageObj_GetBounds(obj, left, bottom, right, top)
    natural = right.value - left.value
    scale = length / natural if natural > 0 else 1.0
    cos, sin = along
    origin = bottom_left + up / box_height * (box_height - size) / 2  # Schrift mittig in der Box
    pdfium_c.FPDFPageObj_Transform(obj, scale * cos, scale * sin, -sin, cos, origin[0], origin[1])
    pdfium_c.FPDFPage_InsertObject(page.raw, obj)


def write_text_layer(src: Path, dst: Path, lines_by_page: dict[int, list[OcrLine]]) -> None:
    """Kopie von src mit unsichtbarem Text je Zeile auf den angegebenen Seiten (1-basiert) nach dst."""
    with pdfium_lock:
        document = pdfium.PdfDocument(str(src))
        try:
            font = pdfium_c.FPDFText_LoadStandardFont(document.raw, b"Helvetica")
            for number, lines in sorted(lines_by_page.items()):
                page = document[number - 1]
                width_pt, height_pt = page.get_size()
                for line in lines:
                    _add_line(document, page, font, line, width_pt, height_pt)
                pdfium_c.FPDFPage_GenerateContent(page.raw)
            document.save(str(dst))
        finally:
            document.close()


def render_page(path: Path, page: int) -> tuple[Image.Image, int]:
    """Seite (1-basiert) in ihrer nativen Aufloesung als Graustufenbild."""
    with pdfium_lock:
        document = pdfium.PdfDocument(str(path))
        try:
            pdf_page = document[page - 1]
            dpi = page_dpi(pdf_page)
            image = pdf_page.render(scale=dpi / 72).to_pil().convert("L")
        finally:
            document.close()
    return image, dpi


def searchable_pdf(
    src: Path,
    dst: Path,
    pages: list[int] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> OcrReport:
    """src mit erkanntem Text auf den Seiten ohne Textebene (oder `pages`) als durchsuchbares PDF nach dst.

    progress(n, gesamt) meldet vor jeder Seite den Stand (Fortschritt am Dokument: "OCR Seite n/gesamt")."""
    started = time.perf_counter()
    targets = pages_without_text(src) if pages is None else pages
    results: list[PageOcr] = []
    for index, page in enumerate(targets, start=1):
        if progress:
            progress(index, len(targets))
        page_start = time.perf_counter()
        image, dpi = render_page(src, page)
        lines, rotation, skew = read_page(image)
        results.append(
            PageOcr(
                page, tuple(lines), dpi, rotation, round(skew, 2), time.perf_counter() - page_start
            )
        )
        logger.info(
            "OCR Seite %s: %s Zeilen, %s dpi, Drehung %s, Schraeglage %.2f",
            page,
            len(lines),
            dpi,
            rotation,
            skew,
        )
    write_text_layer(src, dst, {result.page: list(result.lines) for result in results})
    return OcrReport(tuple(results), time.perf_counter() - started)


# --- Uploads (Issue #66) ------------------------------------------------------------------------------


def original_path(path: Path) -> Path:
    """Wo das unveraenderte Original eines durchsuchbar gemachten Uploads liegt: <name>.orig<endung>."""
    return path.with_name(f"{path.stem}.orig{path.suffix}")


def stored_files(path: Path) -> list[Path]:
    """Alle Dateien eines Uploads; Loeschen muss beide entfernen."""
    return [path, original_path(path)]


def prepare_pdf(
    path: Path, mode: str, progress: Callable[[int, int], None] | None = None
) -> OcrReport | None:
    """Upload unter path bei Bedarf durchsuchbar machen; das Original bleibt als original_path(path) liegen.

    mode: auto (Seiten ohne Textebene), always (jede Seite), off (keine). Neu verarbeiten beginnt immer beim
    Original, damit ein anderer Modus oder eine bessere Erkennung wirkt. So lesen alle Stellen, die storage_path
    oeffnen (Seitenbild, Spalten, Zitat-Resolver), den Scan ohne Sonderpfad und ohne Migration.
    Liefert None, wenn keine Seite OCR brauchte oder die Datei fehlt (das meldet dann das Parsen).
    """
    original = original_path(path)
    if original.exists():
        shutil.copyfile(original, path)
    if mode == "off" or not path.exists():
        return None
    if mode == "always":
        with pdfium_lock:
            document = pdfium.PdfDocument(str(path))
            try:
                pages = list(range(1, len(document) + 1))
            finally:
                document.close()
    else:
        pages = pages_without_text(path)
    if not pages:
        return None
    if not original.exists():
        shutil.copyfile(path, original)
    scratch = path.with_name(f"{path.stem}.ocr-tmp{path.suffix}")
    try:
        report = searchable_pdf(original, scratch, pages, progress)
        os.replace(scratch, path)
    finally:
        scratch.unlink(missing_ok=True)
    return report


def _decimal(value: float, digits: int) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def ocr_note(report: OcrReport) -> str:
    """Hinweis am Dokument, z. B. "7 Seiten per OCR, Ø Konfidenz 0,98, 4,4 s/Seite"."""
    pages = len(report.pages)
    if not pages:
        return ""
    parts = [f"{pages} {'Seite' if pages == 1 else 'Seiten'} per OCR"]
    if report.confidence is not None:
        parts.append(f"Ø Konfidenz {_decimal(report.confidence, 2)}")
    parts.append(f"{_decimal(report.seconds / pages, 1)} s/Seite")
    return ", ".join(parts)


def lines_to_text(lines: list[OcrLine]) -> str:
    """Zeilen in Lesereihenfolge: von oben nach unten, auf gleicher Hoehe von links nach rechts."""
    if not lines:
        return ""

    def top(line: OcrLine) -> float:
        return min(y for _, y in line.quad)

    def height(line: OcrLine) -> float:
        return max(y for _, y in line.quad) - top(line)

    tolerance = float(np.median([height(line) for line in lines])) / 2
    rows: list[list[OcrLine]] = []
    for line in sorted(lines, key=top):
        if rows and abs(top(line) - top(rows[-1][0])) <= tolerance:
            rows[-1].append(line)
        else:
            rows.append([line])
    return "\n".join(
        "  ".join(line.text for line in sorted(row, key=lambda item: min(x for x, _ in item.quad)))
        for row in rows
    )


def read_image(path: Path) -> list[tuple[str, float | None]]:
    """Text je Bild einer Datei (mehrseitige TIFF: je Seite), mit mittlerer Konfidenz."""
    from PIL import ImageOps, ImageSequence

    frames = []
    with Image.open(path) as image:
        for frame in ImageSequence.Iterator(image):
            upright = ImageOps.exif_transpose(frame.copy())
            lines, _, _ = read_page(upright)
            confidence = float(np.mean([line.confidence for line in lines])) if lines else None
            frames.append((lines_to_text(lines), confidence))
    return frames
