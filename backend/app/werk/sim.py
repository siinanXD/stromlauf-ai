"""Durchlauf-Simulation aller Auftraege: Buero, Papiermaschine, Linien, Lager, Tore. Ohne Datenbank.

Ereignisschleife (heapq) ueber Ressourcen mit Plaetzen (Personen, Maschinen, Tore) und Kalendern:
- Buero-Stationen nacheinander, je Station so viele Plaetze wie Personen, Reihenfolge nach Ankunft.
- Nach Finanzen: Kreditpruefung (offene Auftraege des Kunden + neuer Auftrag > Limit -> Klaerung).
- Arbeitsvorbereitung gibt frei: vorhandener Bestand wird reserviert, der Rest gefertigt
  (Rohpapier auf der Papiermaschine nach Ankunft, dann Linie nach Wunschtermin).
- Sind alle Positionen bereit: LKW an freie Tore (nach Ankunft), Bestand sinkt mit der Verladung.
Dauern wie in der Vorkalkulation (calc.py). Gleiche Eingabe -> gleiches Ergebnis.
"""

import heapq
import itertools
import math
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from app.werk.calc import (
    PAPER,
    Article,
    Material,
    Settings,
    iso,
    paper_kg_per_unit,
    step_groups,
    units_per_min,
)
from app.werk.calendar import ALWAYS, Window, add_work, closed_spans, next_open

CREDIT_STEP = "fin"


@dataclass
class Customer:
    id: str
    name: str
    credit_limit: float


@dataclass
class SimLine:
    article: Article
    quantity: float
    unit: str = "unit"  # unit | pallet


@dataclass
class SimOrder:
    id: str
    number: str
    customer: Customer
    received_at: datetime
    due: date | None
    lines: list[SimLine]


@dataclass
class _Job:
    order: SimOrder
    stage: str
    label: str
    minutes: float
    on_done: Any
    arrive: datetime | None = None


@dataclass
class _Resource:
    key: str
    label: str
    kind: str  # office | paper | line | dock
    capacity: int
    window: Window
    by_due: bool = False
    slots: list = field(default_factory=list)
    queue: list = field(default_factory=list)
    busy_minutes: float = 0.0  # Arbeitsminuten
    waits: list = field(default_factory=list)  # Wartezeit in offenen Stunden
    wakeup: datetime | None = None  # geplantes Aufwachen zur naechsten Oeffnung

    def __post_init__(self) -> None:
        self.slots = [None] * max(1, self.capacity)


def _units(line: SimLine) -> int:
    if line.quantity <= 0:
        raise ValueError(f"Menge für {line.article.name} muss größer als 0 sein")
    qty = line.quantity * line.article.units_per_pallet if line.unit == "pallet" else line.quantity
    return math.ceil(round(qty, 6))


def simulate(
    orders: list[SimOrder],
    stock: dict[str, int],
    materials: dict[str, Material],
    settings: Settings,
    workers: dict[str, int],
    credit_hold_min: float,
    prices: dict[str, float],
) -> dict:
    counter = itertools.count()
    events: list = []
    warnings: list[str] = []
    resources: dict[str, _Resource] = {}
    records: dict[str, dict] = {}

    def at(t: datetime, fn, *args) -> None:
        heapq.heappush(events, (t, next(counter), fn, args))

    def resource(key: str, label: str, kind: str, capacity: int, window: Window, by_due: bool = False) -> _Resource:
        if key not in resources:
            resources[key] = _Resource(key, label, kind, capacity, window, by_due)
        return resources[key]

    def priority(res: _Resource, job: _Job) -> tuple:
        if res.by_due:
            return (job.order.due or date.max, job.order.received_at, job.order.number)
        return (job.arrive,)

    def enqueue(res: _Resource, job: _Job, now: datetime) -> None:
        job.arrive = now
        heapq.heappush(res.queue, (priority(res, job), next(counter), job))
        dispatch(res, now)

    def open_minutes(a: datetime, b: datetime, window: Window) -> float:
        closed = sum(((y - x).total_seconds() for x, y in closed_spans(a, b, window)), 0.0)
        return max(0.0, (b - a).total_seconds() - closed) / 60

    def dispatch(res: _Resource, now: datetime) -> None:
        # Plaetze nur vergeben, wenn geoeffnet: sonst wuerde ein frueh angekommener Auftrag den Platz
        # ueber die Schliesszeit halten und ein dringenderer (frueherer Termin) nachrangig werden
        opening = next_open(now, res.window)
        if opening > now:
            if res.queue and res.wakeup != opening:
                res.wakeup = opening
                at(opening, wake, res)
            return
        while None in res.slots and res.queue:
            _, _, job = heapq.heappop(res.queue)
            slot = res.slots.index(None)
            res.slots[slot] = job
            start = now
            end = add_work(now, job.minutes, res.window)
            res.busy_minutes += job.minutes
            res.waits.append(open_minutes(job.arrive, start, res.window) / 60)
            records[job.order.id]["stages"].append({
                "stage": job.stage, "label": job.label, "resource": res.key, "slot": slot,
                "arrive": iso(job.arrive), "start": iso(start), "end": iso(end),
            })
            at(end, finish, res, slot, job)

    def wake(now: datetime, res: _Resource) -> None:
        res.wakeup = None
        dispatch(res, now)

    def finish(now: datetime, res: _Resource, slot: int, job: _Job) -> None:
        res.slots[slot] = None
        job.on_done(now)
        dispatch(res, now)

    # --- Bestand ------------------------------------------------------------------------------
    start_time = min((o.received_at for o in orders), default=None)
    available = dict(stock)
    level = dict(stock)
    points: dict[str, list] = {}
    articles: dict[str, Article] = {}

    def track(article: Article) -> None:
        articles.setdefault(article.code, article)
        if article.code not in points:
            level.setdefault(article.code, 0)
            available.setdefault(article.code, 0)
            points[article.code] = [[iso(start_time), level[article.code]]]

    def change(code: str, delta: int, t: datetime) -> None:
        level[code] += delta
        points[code].append([iso(t), level[code]])

    # --- Ablauf je Auftrag --------------------------------------------------------------------
    open_value: dict[str, float] = {}
    paper = materials.get(PAPER)
    maker = paper.made_on if paper else None

    def office_steps(pallets: int):
        return [s for s in settings.office_steps if pallets >= s.min_pallets]

    def run_office(now: datetime, order: SimOrder, index: int) -> None:
        rec = records[order.id]
        steps = rec["_steps"]
        if index == len(steps):
            release(now, order)
            return
        step = steps[index]
        res = resource(f"office:{step.key}", step.label, "office", workers.get(step.key, 1), settings.office)
        enqueue(res, _Job(order, f"office:{step.key}", step.label, step.minutes,
                          lambda t: after_office(t, order, index)), now)

    def after_office(now: datetime, order: SimOrder, index: int) -> None:
        rec = records[order.id]
        if rec["_steps"][index].key == CREDIT_STEP:
            customer = order.customer
            exposure = open_value.get(customer.id, 0.0) + rec["value"]
            open_value[customer.id] = exposure
            if exposure > customer.credit_limit:
                end = add_work(now, credit_hold_min, settings.office)
                rec["stages"].append({
                    "stage": "credit", "label": "Kreditklärung", "resource": "Finanzen (Klärung)", "slot": None,
                    "arrive": iso(now), "start": iso(now), "end": iso(end),
                })
                at(end, run_office, order, index + 1)
                return
        run_office(now, order, index + 1)

    def release(now: datetime, order: SimOrder) -> None:
        rec = records[order.id]
        rec["_pending"] = len(order.lines)
        for index, line in enumerate(order.lines):
            position = rec["positions"][index]
            take = min(available[line.article.code], position["units"])
            available[line.article.code] -= take
            position["from_stock"] = take
            position["produced"] = position["units"] - take
            if position["produced"] == 0:
                position_ready(now, order)
            elif maker is not None:
                minutes = position["produced"] * paper_kg_per_unit(line.article) / 1000 / maker.rate_per_h * 60
                res = resource("paper", maker.machine_name, "paper", 1, settings.production)
                enqueue(res, _Job(order, f"paper:{index}", "Rohpapier", minutes,
                                  lambda t, i=index: run_line(t, order, i, 0)), now)
            else:
                run_line(now, order, index, 0)

    def run_line(now: datetime, order: SimOrder, index: int, group_index: int) -> None:
        line = order.lines[index]
        produced = records[order.id]["positions"][index]["produced"]
        groups = step_groups(line.article.routing)
        if not groups:
            warnings.append(f"Kein Arbeitsplan für {line.article.name}: ohne Fertigungszeit simuliert")
        if group_index >= len(groups):
            change(line.article.code, produced, now)
            position_ready(now, order)
            return
        group = groups[group_index]
        if any(not step.machine_id for step in group):
            warnings.append(f"Arbeitsplan {line.article.name}: Maschine eines Schritts wurde gelöscht")
        rate = min(units_per_min(step, line.article.units_per_pallet) for step in group)
        minutes = max(step.setup_min for step in group) + produced / rate
        name = group[0].line or group[0].machine_name
        res = resource(f"line:{name}", name, "line", 1, settings.production, by_due=True)
        enqueue(res, _Job(order, f"line:{index}:{group_index}", name, minutes,
                          lambda t: run_line(t, order, index, group_index + 1)), now)

    def position_ready(now: datetime, order: SimOrder) -> None:
        rec = records[order.id]
        rec["_pending"] -= 1
        if rec["_pending"] == 0:
            rec["ready_at"] = iso(now)
            ship(now, order)

    def ship(now: datetime, order: SimOrder) -> None:
        rec = records[order.id]
        trucks = max(1, math.ceil(rec["pallets"] / settings.truck_capacity))
        rec["_trucks_left"] = trucks
        res = resource("docks", "Verladetore", "dock", settings.docks, settings.shipping)
        for k in range(trucks):
            enqueue(res, _Job(order, f"truck:{k}", f"LKW {k + 1}/{trucks}", settings.load_min,
                              lambda t: truck_done(t, order)), now)

    def truck_done(now: datetime, order: SimOrder) -> None:
        rec = records[order.id]
        rec["_trucks_left"] -= 1
        if rec["_trucks_left"] == 0:
            rec["shipped_at"] = iso(now)
            open_value[order.customer.id] = open_value.get(order.customer.id, 0.0) - rec["value"]
            for line, position in zip(order.lines, rec["positions"], strict=True):
                change(line.article.code, -position["units"], now)
                available[line.article.code] = min(available[line.article.code], level[line.article.code])

    # --- Start ----------------------------------------------------------------------------------
    for order in sorted(orders, key=lambda o: (o.received_at, o.number)):
        positions = []
        for line in order.lines:
            track(line.article)
            positions.append({"code": line.article.code, "units": _units(line), "from_stock": 0, "produced": 0})
        pallets = sum(
            math.ceil(p["units"] / line.article.units_per_pallet) for p, line in zip(positions, order.lines, strict=True)
        )
        for p in positions:
            if not prices.get(p["code"]):
                warnings.append(f"Kein Verkaufspreis für {p['code']}: Kreditprüfung ohne Auftragswert")
        records[order.id] = {
            "id": order.id, "number": order.number, "customer": order.customer.name,
            "value": sum(p["units"] * prices.get(p["code"], 0.0) for p in positions),
            "pallets": pallets, "due": order.due.isoformat() if order.due else None,
            "received_at": iso(order.received_at), "ready_at": None, "shipped_at": None,
            "stages": [], "positions": positions, "_steps": office_steps(pallets),
        }
        at(order.received_at, run_office, order, 0)
    for code in stock:
        if code not in points and start_time is not None:
            points[code] = [[iso(start_time), level[code]]]

    while events:
        t, _, fn, args = heapq.heappop(events)
        fn(t, *args)

    return _result(records, resources, points, articles, settings, start_time, warnings, open_minutes)


def _result(records, resources, points, articles, settings, start_time, warnings, open_minutes) -> dict:
    orders = []
    for rec in records.values():
        rec = {k: v for k, v in rec.items() if not k.startswith("_")}
        stages = sorted(rec["stages"], key=lambda s: (s["start"], s["stage"]))
        trucks = [
            {"truck": int(s["stage"].split(":")[1]) + 1, "dock": s["slot"] + 1, "start": s["start"], "end": s["end"]}
            for s in stages if s["stage"].startswith("truck:")
        ]
        rec["stages"] = [s for s in stages if not s["stage"].startswith("truck:")]
        if trucks:
            arrive = min(s["arrive"] for s in stages if s["stage"].startswith("truck:"))
            rec["stages"].append({
                "stage": "ship", "label": "Verladung", "resource": "docks", "slot": None,
                "arrive": arrive, "start": min(t["start"] for t in trucks), "end": max(t["end"] for t in trucks),
            })
        rec["trucks"] = sorted(trucks, key=lambda t: t["truck"])
        shipped = datetime.fromisoformat(rec["shipped_at"]) if rec["shipped_at"] else None
        due = date.fromisoformat(rec["due"]) if rec["due"] else None
        rec["days_delta"] = (due - shipped.date()).days if due and shipped else None
        rec["on_time"] = rec["days_delta"] >= 0 if rec["days_delta"] is not None else None
        orders.append(rec)
    orders.sort(key=lambda o: (o["received_at"], o["number"]))

    end_time = max((datetime.fromisoformat(o["shipped_at"]) for o in orders if o["shipped_at"]), default=start_time)

    def capacity_minutes(res: _Resource) -> float:
        return open_minutes(start_time, end_time, res.window) if start_time and end_time else 0.0
    with_due = [o for o in orders if o["on_time"] is not None]
    shipped = [o for o in orders if o["shipped_at"]]
    office_order = [f"office:{step.key}" for step in settings.office_steps]
    order_resources = sorted(
        resources.values(),
        key=lambda r: (
            {"office": 0, "paper": 1, "line": 2, "dock": 3}[r.kind],
            office_order.index(r.key) if r.key in office_order else 0,
            r.key,
        ),
    )
    return {
        "start": iso(start_time) if start_time else None,
        "end": iso(end_time) if end_time else None,
        "orders": orders,
        "resources": [{"key": r.key, "label": r.label, "kind": r.kind, "capacity": r.capacity} for r in order_resources],
        "stock": {
            code: {
                "name": articles[code].name if code in articles else code,
                "units_per_pallet": articles[code].units_per_pallet if code in articles else 1,
                "points": pts,
            }
            for code, pts in sorted(points.items())
        },
        "closed": {
            key: [[iso(a), iso(b)] for a, b in closed_spans(start_time, end_time, window)]
            for key, window in (("office", settings.office), ("shipping", settings.shipping))
            if window != ALWAYS and start_time and end_time
        },
        "kpis": {
            "on_time_rate": sum(o["on_time"] for o in with_due) / len(with_due) if with_due else None,
            "avg_lead_hours": sum(
                (datetime.fromisoformat(o["shipped_at"]) - datetime.fromisoformat(o["received_at"])).total_seconds() / 3600
                for o in shipped
            ) / len(shipped) if shipped else None,
            "utilization": {
                r.key: round(min(1.0, r.busy_minutes / capacity_minutes(r)), 3) if capacity_minutes(r) else 0.0
                for r in order_resources if r.kind in {"paper", "line"}
            },
            "avg_wait_hours": {r.key: round(sum(r.waits) / len(r.waits), 2) if r.waits else 0.0 for r in order_resources},
        },
        "warnings": list(dict.fromkeys(warnings)),
    }
