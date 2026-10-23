"""Abgleich Schrankfoto <-> Stromlaufplan (SIN-979): was im Schrank markiert ist, was der Plan kennt, was nur eine Seite kennt.

Reine Logik ohne Datenbank. Die Hotspot-Kennzeichen kommen aus den Schrankbildern der Maschine, die Plankennzeichen
aus dem Kennzeichen-Index der Quelle (`tag_occurrences`). Verglichen wird das Geraet ohne Anschluss: `-K1:A1` und
`-X3:5` zaehlen als `-K1` und `-X3`. Teile, die die Stueckliste ausserhalb des Schranks einbaut (Antrieb +AN1),
gelten nie als „fehlt im Schrank“; wo kein Einbauort bekannt ist, entscheidet der Kennbuchstabe (Feldgeraete:
Motor, Sensor, Taster, Leuchte, Leitung, Ventil).
"""

from dataclasses import dataclass, field

from app.ingestion.tags import normalize_tag

# Kennbuchstaben von Geraeten, die ueblicherweise ausserhalb des Schranks sitzen: M Motor, B Sensor, S Taster,
# H Leuchte, W Leitung, Y Ventil. Ob ein Teil im Feld sitzt, sagt die Stueckliste genauer; die kennt dieser Abgleich nicht.
FIELD_LETTERS = "MBSHWY"


@dataclass(frozen=True)
class CabinetCheck:
    in_both: list[str] = field(default_factory=list)
    missing_in_cabinet: list[str] = field(default_factory=list)  # im Plan, ohne Markierung im Schrankbild
    missing_in_plan: list[str] = field(default_factory=list)  # im Schrankbild markiert, dem Plan unbekannt

    def as_dict(self) -> dict:
        return {
            "in_both": self.in_both,
            "missing_in_cabinet": self.missing_in_cabinet,
            "missing_in_plan": self.missing_in_plan,
        }


def device_of(tag: str) -> str:
    """`-K1:A1` -> `-K1`; leer, wenn kein Kennzeichen daraus wird."""
    normalized = normalize_tag(tag)
    return normalized.split(":", 1)[0] if normalized.startswith("-") else ""


def is_field_device(tag: str) -> bool:
    letters = tag.lstrip("-")[:1]
    return bool(letters) and letters in FIELD_LETTERS


def _sort_key(tag: str) -> tuple:
    letters = "".join(c for c in tag if c.isalpha())
    digits = "".join(c if c.isdigit() else "." for c in tag).strip(".").split(".")
    return (letters, [int(d) for d in digits if d])


def is_cabinet_zone(code: str, name: str) -> bool:
    """Einbauort des Schranks: Klartext der Legende nennt „Schrank“, sonst der Code nach der Konvention +ST…."""
    return "schrank" in name.lower() or code.upper().startswith("+ST")


def placement(zones: list[dict]) -> dict[str, bool]:
    """Teil -> sitzt im Schrank, aus den Zonen des Maschinenmodells. Nur Einbauorte (+…) sagen es; Blatt- und
    „Ohne Einbauort“-Zonen lassen das Teil offen."""
    return {
        part["tag"]: is_cabinet_zone(zone["code"], zone["name"])
        for zone in zones
        if zone["code"].startswith("+")
        for part in zone["parts"]
    }


def compare(plan_tags, cabinet_tags, placed: dict[str, bool] | None = None) -> CabinetCheck:
    """Drei Listen aus den Plankennzeichen (Index) und den Hotspot-Kennzeichen; Eingaben duerfen Anschluesse enthalten.

    `placed` (siehe `placement`) sagt, wo die Stueckliste ein Teil einbaut; ohne Angabe entscheidet der Kennbuchstabe."""
    plan = {d for t in plan_tags if (d := device_of(t))}
    cabinet = {d for t in cabinet_tags if (d := device_of(t))}
    in_both = plan & cabinet
    placed = placed or {}
    missing_in_cabinet = {t for t in plan - cabinet if placed.get(t, not is_field_device(t))}
    missing_in_plan = cabinet - plan
    return CabinetCheck(
        in_both=sorted(in_both, key=_sort_key),
        missing_in_cabinet=sorted(missing_in_cabinet, key=_sort_key),
        missing_in_plan=sorted(missing_in_plan, key=_sort_key),
    )
