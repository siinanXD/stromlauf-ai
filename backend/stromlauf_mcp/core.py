"""Reine Hilfen des MCP-Servers: Namen aufloesen, Antworten fuer ein Sprachmodell kuerzen."""

from mcp.server.mcpserver.exceptions import ToolError

KIND_LABELS = {
    "generic": "Halle", "base": "Grundstoff", "production": "Verarbeitung", "warehouse": "Lager", "office": "Büro",
}
MAX_TEXT = 8000  # Zeichen je Suchergebnis, damit das Kontextfenster des Clients nicht platzt


def _label(item: dict) -> str:
    name = str(item.get("name") or item.get("code"))
    return f"{name} ({item['hall']})" if item.get("hall") else name


def _listing(items: list[dict], limit: int) -> str:
    text = ", ".join(_label(item) for item in items[:limit])
    return f"{text} und {len(items) - limit} weitere" if len(items) > limit else text


def resolve(items: list[dict], ref: str, kind: str, keys: tuple[str, ...] = ("name", "code")) -> dict:
    """Eintrag per ID (nur exakt) oder Name/Code: exakt, sonst eindeutiger Anfang, sonst eindeutiges Teilwort."""
    needle = ref.strip().casefold()
    if not needle:
        raise ToolError(f"{kind}: Name fehlt")
    by_id = [item for item in items if str(item.get("id", "")).casefold() == needle]
    if len(by_id) == 1:
        return by_id[0]
    values = [(item, [str(item.get(key, "")).casefold() for key in keys]) for item in items]
    for match in (
        lambda v: v == needle,
        lambda v: v.startswith(needle),
        lambda v: needle in v,
    ):
        found = [item for item, vals in values if any(match(v) for v in vals)]
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise ToolError(f"{kind} „{ref}“ ist mehrdeutig: {_listing(found, 8)}. Bitte genauer angeben.")
    raise ToolError(f"{kind} „{ref}“ nicht gefunden. Vorhanden: {_listing(items, 12)}")


def machines_of(site: dict) -> list[dict]:
    """Alle Maschinen des Standorts mit Hallenname."""
    return [{**machine, "hall": hall["name"], "hall_id": hall["id"]} for hall in site["halls"] for machine in hall["machines"]]


def truncate(text: str, limit: int = MAX_TEXT) -> str:
    """Kuerzen an einer Treffergrenze ("### " am Zeilenanfang), sonst hart."""
    if len(text) <= limit:
        return text
    cut = text.rfind("\n\n### ", 0, limit)
    head = text[:cut] if cut > 0 else text[:limit]
    return f"{head}\n… (gekürzt, {len(text) - len(head)} Zeichen mehr)"
