"""Datenmodell eines Dokumentensatzes: eine Maschine mit Antrieben, Sicherheitskreisen, E/A und Handbuch.

Aus einem `Machine`-Objekt entstehen Stromlaufplan, Stueckliste, Klemmenplan, AWL, Symboltabelle und
Betriebsanleitung. Blatt/Spalten-Verweise werden beim Zeichnen des Plans erfasst (`Refs`) und danach in
die uebrigen Dokumente uebernommen; im Text stehen Platzhalter wie `{ref:-F2}`.
"""

import re
from dataclasses import dataclass

TAG = re.compile(r"-[A-Z]{1,2}\d+(?:\.\d+)?(?::[A-Za-z0-9]+)?")


@dataclass
class Device:
    bmk: str
    name: str
    typ: str
    qty: int = 1
    in_field: bool = False  # Einbauort Feld statt Schaltschrank


@dataclass
class Drive:
    """Motorabgang: Schutzorgan -> Umrichter oder Schuetz -> Klemmleiste -> Motor."""

    motor: str
    name: str
    kw: float
    amps: float
    rpm: int
    breaker: str
    breaker_name: str
    setting: str
    switch: str
    switch_name: str
    kind: str  # vfd | contactor
    strip: str  # Klemmleiste des Motorabgangs, z. B. -X4
    bus_address: int | None = None  # PROFIBUS-Adresse des Umrichters


@dataclass
class Signal:
    """Digitaler Ein- oder Ausgang der SPS."""

    address: str
    symbol: str
    comment: str
    device: str
    kind: str  # DI: cmd_no | cmd_nc | sensor | aux ; DO: coil | lamp | horn | vfd
    pins: tuple[str, str] = ("13", "14")
    terminal: str = ""  # Klemme -X3:n, wird zugewiesen


@dataclass
class SafetyCircuit:
    relay: str
    name: str
    devices: list[tuple[str, str, str]]  # (BMK, Kontakt Kanal 1, Kontakt Kanal 2)
    release_text: str  # was der Freigabekontakt 13/14 versorgt
    release_terminal: str  # z. B. -X2:3a
    feedback_input: str  # E-Adresse des Rueckmeldekontakts 23/24


@dataclass
class Fault:
    symptom: str
    cause: str
    check: str


@dataclass
class Machine:
    code: str
    title: str
    plant: str
    loc_cabinet: str
    loc_field: str
    drawing_no: str
    supply_text: str
    function: list[str]
    devices: list[Device]
    drives: list[Drive]
    safety: list[SafetyCircuit]
    inputs: list[Signal]
    outputs: list[Signal]
    merker: list[tuple[str, str, str]]
    fb_number: int
    db_number: int
    fb_title: str
    fb_static: list[tuple[str, str, str]]  # (Name, Typ, Kommentar)
    networks: str  # AWL-Netzwerke des FB (zwischen BEGIN und END_FUNCTION_BLOCK)
    ob_extra: str  # weitere OB1-Netzwerke
    extra_symbols: list[tuple[str, str, str, str]]  # (Symbol, Adresse, Typ, Kommentar)
    manual: dict
    faults: list[Fault]
    cables: list[tuple[str, str, str, str]]  # (BMK, Name, Kenndaten, Verweis-BMK fuer das Blatt)
    field_strip: str = "-X3"
    supply_strips: tuple[str, str] = ("-X1", "-X2")

    def __post_init__(self) -> None:
        # Feldklemmen -X3 vergeben: Eingaenge, Versorgung Sensoren, Ausgaenge, Rueckleiter
        n = 0
        for signal in self.inputs:
            n += 1
            signal.terminal = f"{self.field_strip}:{n}"
        self.sensor_supply = (f"{self.field_strip}:{n + 1}", f"{self.field_strip}:{n + 2}")
        n += 2
        for signal in self.outputs:
            n += 1
            signal.terminal = f"{self.field_strip}:{n}"
        self.coil_return = f"{self.field_strip}:{n + 1}"
        self.lamp_return = f"{self.field_strip}:{n + 2}"
        n += 2
        # Sicherheitskreise: je Kanal Beginn (S11/S21) und Ende (S12/S22) der Reihenschaltung
        self.safety_terminals: dict[tuple[str, int, str], str] = {}
        for circuit in self.safety:
            for channel in (1, 2):
                for end in ("start", "end"):
                    n += 1
                    self.safety_terminals[(circuit.relay, channel, end)] = f"{self.field_strip}:{n}"
        self.field_terminal_count = n
        strip = self.device(self.field_strip)
        if strip is not None:
            strip.qty = n

    def terminal_of(self, address: str) -> str:
        return next((s.terminal for s in self.inputs + self.outputs if s.address == address), "")

    def fill(self, refs: "Refs", text: str) -> str:
        """{ref:-F2} -> Blattverweis, {term:E0.1} -> Klemme des Signals, {supply24}/{supply0} -> Sensorversorgung."""
        text = re.sub(r"\{term:([^}]+)\}", lambda m: self.terminal_of(m.group(1)) or m.group(0), text)
        text = text.replace("{supply24}", self.sensor_supply[0]).replace("{supply0}", self.sensor_supply[1])
        return refs.fill(text)

    @property
    def sensors(self) -> list[Signal]:
        return [s for s in self.inputs if s.kind == "sensor"]

    @property
    def commands(self) -> list[Signal]:
        return [s for s in self.inputs if s.kind in {"cmd_no", "cmd_nc"}]

    def device(self, bmk: str) -> Device | None:
        return next((d for d in self.devices if d.bmk == bmk), None)


class Refs:
    """Blatt/Spalte je Kennzeichen. Symbolzeichnungen (primary) schlagen Texterwaehnungen."""

    def __init__(self) -> None:
        self._refs: dict[str, tuple[int, int, bool]] = {}

    def add(self, bmk: str, page: int, col: int, primary: bool = False) -> None:
        if page < 2:
            return  # Deckblatt zaehlt nicht
        self._put(bmk, page, col, primary)
        if ":" in bmk:  # Klemme -X3:5 registriert auch die Leiste -X3
            self._put(bmk.split(":")[0], page, col, primary)

    def _put(self, bmk: str, page: int, col: int, primary: bool) -> None:
        current = self._refs.get(bmk)
        if current is None or (primary and not current[2]):
            self._refs[bmk] = (page, col, primary)

    def get(self, bmk: str) -> str:
        page, col, _ = self._refs[bmk]
        return f"/{page}.{col}"

    def has(self, bmk: str) -> bool:
        return bmk in self._refs

    def fill(self, text: str) -> str:
        """Platzhalter {ref:-F2} durch den Verweis ersetzen."""
        return re.sub(r"\{ref:([^}]+)\}", lambda m: self.get(m.group(1)), text)
