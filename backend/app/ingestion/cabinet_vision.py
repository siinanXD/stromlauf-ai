"""Bauteile in einem Schaltschrank-Foto oder Aufbauplan per Claude Vision finden.

Liefert Rechtecke (relativ 0..1) mit Bauteilart, gelesenem BMK und Sicherheit. Die Vorschlaege
werden als unbestaetigte Hotspots gespeichert; der Nutzer bestaetigt oder korrigiert sie.
"""

import io
import json
import re
from pathlib import Path

from langchain_core.messages import HumanMessage
from PIL import Image

from app.config import get_settings
from app.ingestion.tags import normalize_tag
from app.llm import MissingKeyError, image_block, make_chat_model, missing_key

MAX_EDGE = 2000

DETECT_PROMPT = """Du bist Elektrokonstrukteur. Das Bild zeigt das Innere eines Schaltschranks \
(Foto) oder einen Schaltschrank-Aufbauplan. Finde alle erkennbaren Betriebsmittel: Schuetze, \
Motorschutzschalter, Leitungsschutzschalter, Sicherungen, Netzteile, SPS-CPU und -Baugruppen, \
Relais, Sicherheitsrelais, Frequenzumrichter, Klemmleisten, Trafos, Hauptschalter.

Fuer jedes Bauteil gib ein Rechteck als Anteil der Bildbreite/-hoehe (0.0 bis 1.0, Ursprung \
oben links) an. Lies das Betriebsmittelkennzeichen (BMK) vom Schild, wenn eins lesbar ist \
(z. B. -K1, -F2, -Q1, -X3); sonst tag = null. Erfinde keine BMK.
{known}
Antworte NUR mit JSON, ohne Erklaertext:
{{"items": [{{"kind": "Schuetz", "tag": "-K1", "label": "Schuetz 4 kW", "x": 0.12, "y": 0.30, \
"w": 0.06, "h": 0.10, "confidence": 0.8}}]}}
"""


def load_png(path: Path) -> tuple[bytes, int, int]:
    image = Image.open(path).convert("RGB")
    width, height = image.size
    scale = min(1.0, MAX_EDGE / max(width, height))
    if scale < 1.0:
        image = image.resize((int(width * scale), int(height * scale)))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue(), width, height


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def detect_components(
    path: Path, known_tags: list[str] | None = None, trace: dict | None = None
) -> list[dict]:
    settings = get_settings()
    if missing := missing_key(settings.vision_model, settings):
        raise MissingKeyError(missing)
    png, _, _ = load_png(path)
    known = ""
    if known_tags:
        known = (
            "\nIn der Stueckliste dieser Maschine kommen diese BMK vor, bevorzuge sie bei "
            f"unsicherer Lesung: {', '.join(sorted(known_tags)[:80])}\n"
        )
    llm = make_chat_model(settings.vision_model, max_tokens=4000, max_retries=2)
    message = HumanMessage(
        content=[image_block(png), {"type": "text", "text": DETECT_PROMPT.format(known=known)}]
    )
    response = llm.invoke([message], trace or None)
    content = response.content
    text = (
        content
        if isinstance(content, str)
        else "".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        )
    )
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("Vision-Antwort enthielt kein JSON")
    items = json.loads(match.group(0)).get("items", [])

    result = []
    for item in items:
        try:
            x, y, w, h = (float(item.get(k, 0)) for k in ("x", "y", "w", "h"))
        except (TypeError, ValueError):
            continue
        x, y = min(max(x, 0.0), 1.0), min(max(y, 0.0), 1.0)
        w, h = min(max(w, 0.01), 1.0 - x), min(max(h, 0.01), 1.0 - y)
        raw_tag = (item.get("tag") or "").strip()
        result.append(
            {
                "kind": str(item.get("kind") or "")[:60],
                "tag": normalize_tag(raw_tag) if raw_tag else "",
                "label": str(item.get("label") or "")[:200],
                "x": x,
                "y": y,
                "w": w,
                "h": h,
                "confidence": float(item.get("confidence") or 0.0),
            }
        )
    return result
