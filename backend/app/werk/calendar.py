"""Arbeitszeit-Kalender: Wochenfenster {"days": [0..6], "from": "07:00", "to": "16:00"} oder "24/7".

Tage zaehlen ab Montag = 0. Ein Fenster je Tag; Feiertage kennt der Kalender noch nicht.
"""

from datetime import date, datetime, time, timedelta

ALWAYS = "24/7"
Window = dict | str


def _bounds(day: date, window: dict) -> tuple[datetime, datetime] | None:
    if day.weekday() not in window["days"]:
        return None
    start = datetime.combine(day, time.fromisoformat(window["from"]))
    end = datetime.combine(day, time.fromisoformat(window["to"]))
    return (start, end) if end > start else None


def next_open(t: datetime, window: Window) -> datetime:
    """Fruehester Zeitpunkt ab t, zu dem geoeffnet ist."""
    if window == ALWAYS:
        return t
    day = t.date()
    for _ in range(8):
        bounds = _bounds(day, window)
        if bounds and t < bounds[1]:
            return max(t, bounds[0])
        day += timedelta(days=1)
    raise ValueError("Kalender hat keine offene Zeit")


def add_work(t: datetime, minutes: float, window: Window) -> datetime:
    """Ende einer Arbeit von `minutes` Arbeitsminuten, die bei t (bzw. der naechsten Oeffnung) beginnt."""
    if minutes < 0:
        raise ValueError("Dauer darf nicht negativ sein")
    if window == ALWAYS:
        return t + timedelta(minutes=minutes)
    current = next_open(t, window)
    remaining = timedelta(minutes=minutes)
    while True:
        _, end = _bounds(current.date(), window)
        if remaining <= end - current:
            return current + remaining
        remaining -= end - current
        current = next_open(end, window)


def next_block(t: datetime, minutes: float, window: Window) -> datetime:
    """Fruehester Start ab t, an dem `minutes` am Stueck in ein offenes Fenster passen.

    Laenger als ein Tagesfenster: dann wie next_open (die Arbeit wird geteilt).
    """
    start = next_open(t, window)
    if window == ALWAYS:
        return start
    block = timedelta(minutes=minutes)
    for _ in range(400):
        _, end = _bounds(start.date(), window)
        if start + block <= end:
            return start
        following = next_open(end, window)
        if block > _bounds(following.date(), window)[1] - following:
            return next_open(t, window)
        start = following
    return next_open(t, window)


def closed_spans(start: datetime, end: datetime, window: Window) -> list[tuple[datetime, datetime]]:
    """Geschlossene Zeitraeume innerhalb [start, end] (fuer die Schraffur im Zeitplan)."""
    if window == ALWAYS or end <= start:
        return []
    spans = []
    current = start
    while current < end:
        opened = next_open(current, window)
        if opened > current:
            spans.append((current, min(opened, end)))
        if opened >= end:
            break
        current = _bounds(opened.date(), window)[1]
    return spans
