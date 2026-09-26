"""Zeichnet den Aufstellungsplan (Draufsicht) von FB-01 aus dem Soll-Layout.

Aufruf:  python scripts/make_layout_sketch.py

Quelle ist examples/foerderband/08_Aufstellungsplan_FB-01.json (Standardformat, Werte in mm).
Ergebnis ist 08_Aufstellungsplan_FB-01.png: schwarz auf weiss wie eine Zeichnung, mit Masskette,
Foerderrichtung und Schriftfeld. Damit laesst sich die Vision-Erkennung gegen das Soll pruefen.
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = ROOT / "examples" / "foerderband"
SOURCE = EXAMPLE_DIR / "08_Aufstellungsplan_FB-01.json"
TARGET = EXAMPLE_DIR / "08_Aufstellungsplan_FB-01.png"

IMAGE_WIDTH = 2400
MARGIN = 170
INK = (20, 20, 20)
LIGHT = (120, 120, 120)


def font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default(size=size)


def main() -> None:
    layout = json.loads(SOURCE.read_text(encoding="utf-8"))
    width_mm, depth_mm = layout["width_mm"], layout["depth_mm"]
    scale = (IMAGE_WIDTH - 2 * MARGIN) / width_mm
    height = int(depth_mm * scale) + 2 * MARGIN + 180
    image = Image.new("RGB", (IMAGE_WIDTH, height), "white")
    draw = ImageDraw.Draw(image)

    def px(x_mm: float, y_mm: float) -> tuple[float, float]:
        return MARGIN + x_mm * scale, MARGIN + y_mm * scale

    # Grundflaeche gestrichelt
    x0, y0 = px(0, 0)
    x1, y1 = px(width_mm, depth_mm)
    for x in range(int(x0), int(x1), 24):
        draw.line([(x, y0), (min(x + 12, x1), y0)], fill=LIGHT, width=2)
        draw.line([(x, y1), (min(x + 12, x1), y1)], fill=LIGHT, width=2)
    for y in range(int(y0), int(y1), 24):
        draw.line([(x0, y), (x0, min(y + 12, y1))], fill=LIGHT, width=2)
        draw.line([(x1, y), (x1, min(y + 12, y1))], fill=LIGHT, width=2)

    for part in layout["parts"]:
        a = px(part["x_mm"], part["y_mm"])
        b = px(part["x_mm"] + part["w_mm"], part["y_mm"] + part["h_mm"])
        if part["shape"] == "circle":
            fill = (60, 60, 60) if part["kind"] == "Not-Halt" else None
            draw.ellipse([a, b], outline=INK, width=4, fill=fill)
        else:
            draw.rectangle([a, b], outline=INK, width=5 if part["kind"] == "Band/Förderer" else 4)
        if part["kind"] == "Band/Förderer":
            for x in range(int(a[0]) + 30, int(b[0]), 34):
                draw.line([(x, a[1] + 8), (x, b[1] - 8)], fill=LIGHT, width=2)
            box = draw.textbbox((a[0] + 16, a[1] + 14), part["label"], font=font(30))
            draw.rectangle([box[0] - 6, box[1] - 4, box[2] + 6, box[3] + 4], fill="white")
            draw.text((a[0] + 16, a[1] + 14), part["label"], fill=INK, font=font(30))
            # Foerderrichtung unter dem Band
            ay = b[1] + 60
            draw.line([(a[0] + 80, ay), (b[0] - 80, ay)], fill=INK, width=4)
            draw.polygon([(b[0] - 80, ay - 14), (b[0] - 50, ay), (b[0] - 80, ay + 14)], fill=INK)
            draw.text(((a[0] + b[0]) / 2 - 120, ay + 14), "Foerderrichtung", fill=INK, font=font(28))
        elif part["kind"] == "Rahmen":
            draw.text((a[0] + 8, b[1] + 8), part["label"], fill=INK, font=font(26))
        else:
            label = part["tag"] or part["label"]
            if part["shape"] == "circle":
                draw.text((a[0] - 6, a[1] - 40), label, fill=INK, font=font(30))
            elif part["w_mm"] < 300:
                draw.text((b[0] + 10, a[1] - 6), label, fill=INK, font=font(30))
            else:
                draw.text((a[0] + 10, a[1] + 10), label, fill=INK, font=font(32))

    # Masskette oben: Gesamtbreite
    dy = MARGIN - 80
    draw.line([(x0, dy), (x1, dy)], fill=INK, width=2)
    for x in (x0, x1):
        draw.line([(x, dy - 18), (x, dy + 18)], fill=INK, width=2)
    draw.text(((x0 + x1) / 2 - 50, dy - 42), f"{width_mm:.0f}", fill=INK, font=font(32))
    # Masskette links: Tiefe
    dx = MARGIN - 80
    draw.line([(dx, y0), (dx, y1)], fill=INK, width=2)
    for y in (y0, y1):
        draw.line([(dx - 18, y), (dx + 18, y)], fill=INK, width=2)
    draw.text((dx - 84, (y0 + y1) / 2 - 16), f"{depth_mm:.0f}", fill=INK, font=font(32))

    # Schriftfeld unten rechts
    tb = [IMAGE_WIDTH - MARGIN - 700, height - 150, IMAGE_WIDTH - MARGIN, height - 30]
    draw.rectangle(tb, outline=INK, width=3)
    draw.line([(tb[0], tb[1] + 60), (tb[2], tb[1] + 60)], fill=INK, width=2)
    draw.line([(tb[0] + 420, tb[1]), (tb[0] + 420, tb[3])], fill=INK, width=2)
    draw.text((tb[0] + 16, tb[1] + 12), "FB-01 Aufstellungsplan", fill=INK, font=font(32))
    draw.text((tb[0] + 440, tb[1] + 14), "Blatt 1/1", fill=INK, font=font(28))
    draw.text((tb[0] + 16, tb[1] + 74), "Draufsicht, Masse in mm", fill=INK, font=font(26))
    draw.text((tb[0] + 440, tb[1] + 74), layout.get("scale_note", ""), fill=INK, font=font(28))

    image.save(TARGET, optimize=True)
    print(f"geschrieben: {TARGET.relative_to(ROOT)} ({image.width} x {image.height})")


if __name__ == "__main__":
    main()
