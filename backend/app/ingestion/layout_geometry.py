"""Draufsicht einer Maschine: Umrechnung von Vision-Rechtecken (relativ 0..1) in mm.

Koordinaten in mm, Ursprung oben links, x nach rechts, y nach unten.
"""

from app.ingestion.tags import normalize_tag

LAYOUT_KINDS: tuple[str, ...] = (
    "Motor",
    "Sensor",
    "Taster",
    "Not-Halt",
    "Leuchte",
    "Schaltschrank",
    "Band/Förderer",
    "Rahmen",
    "Schutztür",
    "Sonstiges",
)
SHAPES = ("rect", "circle")
FALLBACK_MM = 1000.0  # Layout ohne Masse (leer begonnen, Vision ohne Masskette)
MIN_PART_MM = 1.0


def _clamp(value: float, low: float, high: float) -> float:
    return min(max(value, low), high)


def clamp_part(
    x: float, y: float, w: float, h: float, width_mm: float, depth_mm: float
) -> tuple[float, float, float, float]:
    """Haelt ein Teil vollstaendig innerhalb der Grundflaeche."""
    w = _clamp(w, MIN_PART_MM, width_mm)
    h = _clamp(h, MIN_PART_MM, depth_mm)
    return _clamp(x, 0.0, width_mm - w), _clamp(y, 0.0, depth_mm - h), w, h


def to_parts(items: list[dict], width_mm: float, depth_mm: float) -> list[dict]:
    """Vision-Eintraege in LayoutPart-Felder (mm) umrechnen; unbrauchbare Eintraege verwerfen."""
    width = width_mm if width_mm and width_mm > 0 else FALLBACK_MM
    depth = depth_mm if depth_mm and depth_mm > 0 else FALLBACK_MM
    parts = []
    for item in items:
        try:
            rx, ry, rw, rh = (float(item[k]) for k in ("x", "y", "w", "h"))
        except (KeyError, TypeError, ValueError):
            continue
        x, y, w, h = clamp_part(rx * width, ry * depth, rw * width, rh * depth, width, depth)
        kind = item.get("kind")
        raw_tag = str(item.get("tag") or "").strip()
        try:
            confidence = float(item.get("confidence")) if item.get("confidence") is not None else None
        except (TypeError, ValueError):
            confidence = None
        parts.append(
            {
                "tag": normalize_tag(raw_tag) if raw_tag else "",
                "label": str(item.get("label") or "")[:200],
                "kind": kind if kind in LAYOUT_KINDS else "Sonstiges",
                "shape": item.get("shape") if item.get("shape") in SHAPES else "rect",
                "x_mm": round(x, 1),
                "y_mm": round(y, 1),
                "w_mm": round(w, 1),
                "h_mm": round(h, 1),
                "rotation_deg": 0.0,
                "confidence": confidence,
            }
        )
    return parts


def drop_known_tags(parts: list[dict], known: set[str]) -> list[dict]:
    """Vorschlaege fuer BMK weglassen, die in der Draufsicht schon bestaetigt sind."""
    return [p for p in parts if not p["tag"] or p["tag"] not in known]
