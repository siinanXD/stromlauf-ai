"""Schaltschrank-Aufbauplan FB-01 als PNG plus Hotspot-Liste (relativ) fuer die Beispielanlage."""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 1200
BG, PLATE, RAIL, DEV, TEXT = (232, 234, 237), (205, 208, 212), (150, 152, 156), (245, 246, 247), (25, 28, 32)

# (BMK, Beschriftung, Art, Breite in Modulen 17,5 mm)
ROWS = [
    [("-Q1", "Hauptschalter 25 A", "Hauptschalter", 4), ("-F1", "LS B6", "LS-Schalter", 2), ("-F2", "MSS 2,5-4 A", "Motorschutzschalter", 3), ("-T1", "Netzteil 24 V / 5 A", "Netzteil", 5)],
    [("-A1", "SPS CPU", "SPS", 6), ("-A1.1", "DI 16", "SPS", 3), ("-A1.2", "DO 16", "SPS", 3), ("-K3", "Sicherheitsrelais", "Sicherheitsrelais", 3)],
    [("-K1", "Schuetz vorw.", "Schuetz", 3), ("-K2", "Schuetz rueckw.", "Schuetz", 3)],
    [("-X1", "Netz", "Klemmleiste", 5), ("-X2", "24 V", "Klemmleiste", 6), ("-X3", "Feld", "Klemmleiste", 14), ("-X4", "Motor", "Klemmleiste", 4)],
]
MODULE = 26  # px je 17,5-mm-Modul


def font(size):
    for name in ["DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build(out_png: Path, out_json: Path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.rectangle([60, 60, W - 60, H - 60], fill=PLATE, outline=(120, 122, 126), width=4)
    d.text((80, 75), "Schaltschrank +ST1  Foerderband FB-01  Aufbauplan (Beispielanlage, frei erfunden)", fill=TEXT, font=font(26))
    hotspots = []
    y = 170
    for row in ROWS:
        d.rectangle([100, y + 70, W - 100, y + 86], fill=RAIL)  # Hutschiene
        x = 130
        for bmk, label, kind, modules in row:
            w = modules * MODULE + 12
            h = 150 if not bmk.startswith("-X") else 90
            top = y + 78 - h // 2
            d.rectangle([x, top, x + w, top + h], fill=DEV, outline=(90, 92, 96), width=3)
            d.text((x + 8, top + 8), bmk, fill=TEXT, font=font(22))
            d.text((x + 8, top + h - 30), label[: max(4, w // 11)], fill=(70, 72, 76), font=font(15))
            hotspots.append({"tag": bmk, "kind": kind, "label": label, "x": x / W, "y": top / H, "w": w / W, "h": h / H})
            x += w + 30
        y += 240
    d.text((80, H - 95), "Hutschienen von oben: Einspeisung/Steuerspannung, SPS, Schuetze, Klemmleisten. Kabelkanaele nicht dargestellt.", fill=(70, 72, 76), font=font(17))
    img.save(out_png, optimize=True)
    out_json.write_text(json.dumps(hotspots, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out_png, len(hotspots), "Hotspots")


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    build(out / "07_Schaltschrank_Aufbauplan_FB-01.png", out / "07_Schaltschrank_Hotspots_FB-01.json")
