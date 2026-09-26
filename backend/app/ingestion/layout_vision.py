"""Draufsicht einer Maschine aus einer Skizze (Aufstellungsplan, Scan, Foto) per Claude Vision.

Liefert relative Rechtecke plus erkannte Gesamtmasse; die Umrechnung in mm macht
`layout_geometry.to_parts`. Vorschlaege werden unbestaetigt gespeichert.
"""

import base64
import json
import re

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from app.config import get_settings
from app.ingestion.layout_geometry import LAYOUT_KINDS

DETECT_PROMPT = """Du bist Konstrukteur im Anlagenbau. Das Bild zeigt eine Draufsicht \
(Vogelperspektive) einer Maschine oder Anlage: Aufstellungsplan, Skizze, Scan oder Foto.

Finde alle erkennbaren Baugruppen und Feldgeraete. Erlaubte Arten (kind): {kinds}.
Fuer jedes Teil: Rechteck als Anteil der Bildbreite/-hoehe (0.0 bis 1.0, Ursprung oben links), \
shape "circle" fuer runde Teile (z. B. Not-Halt), sonst "rect". Lies das \
Betriebsmittelkennzeichen (BMK) nur, wenn es lesbar ist (z. B. -M1, -B2, -S3); sonst tag = null. \
Erfinde keine BMK.
Wenn Masse angegeben sind (Masskette, Schriftfeld), gib die Gesamtbreite und -tiefe der \
gezeichneten Grundflaeche in mm an und beziehe die Rechtecke auf genau diese Grundflaeche; \
sonst width_mm/depth_mm = null.
{known}
Antworte NUR mit JSON, ohne Erklaertext:
{{"width_mm": 6000, "depth_mm": 1500, "items": [{{"kind": "Motor", "shape": "rect", "tag": "-M1", \
"label": "Antriebsmotor", "x": 0.02, "y": 0.30, "w": 0.06, "h": 0.2, "confidence": 0.8}}]}}
"""


def parse_vision_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("Vision-Antwort enthielt kein JSON")
    return json.loads(match.group(0))


def _positive(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def detect_layout(png: bytes, known_tags: list[str] | None = None) -> dict:
    """Ruft Claude Vision auf (kostet API-Tokens). Rueckgabe: items, width_mm, depth_mm."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY fehlt")
    known = ""
    if known_tags:
        known = (
            "\nIn der Dokumentation dieser Maschine kommen diese BMK vor, bevorzuge sie bei "
            f"unsicherer Lesung: {', '.join(sorted(known_tags)[:80])}\n"
        )
    llm = ChatAnthropic(
        model=settings.vision_model, api_key=settings.anthropic_api_key, max_tokens=4000, max_retries=2
    )
    message = HumanMessage(
        content=[
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(png).decode()},
            },
            {"type": "text", "text": DETECT_PROMPT.format(kinds=", ".join(LAYOUT_KINDS), known=known)},
        ]
    )
    content = llm.invoke([message]).content
    text = content if isinstance(content, str) else "".join(
        b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
    )
    data = parse_vision_json(text)
    items = data.get("items")
    return {
        "items": items if isinstance(items, list) else [],
        "width_mm": _positive(data.get("width_mm")),
        "depth_mm": _positive(data.get("depth_mm")),
    }
