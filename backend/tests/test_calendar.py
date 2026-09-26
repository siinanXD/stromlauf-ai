from datetime import datetime as dt

from app.werk.calendar import add_work, closed_spans, next_open

OFFICE = {"days": [0, 1, 2, 3, 4], "from": "07:00", "to": "16:00"}


def test_work_after_friday_close_continues_monday():
    assert add_work(dt(2026, 9, 25, 15, 30), 60, OFFICE) == dt(2026, 9, 28, 7, 30)


def test_work_ending_exactly_at_close_stays_on_the_same_day():
    assert add_work(dt(2026, 9, 25, 15, 0), 60, OFFICE) == dt(2026, 9, 25, 16, 0)


def test_next_open_on_saturday_is_monday_morning():
    assert next_open(dt(2026, 9, 26, 10, 0), OFFICE) == dt(2026, 9, 28, 7, 0)


def test_work_before_opening_starts_at_opening():
    assert add_work(dt(2026, 9, 29, 6, 0), 30, OFFICE) == dt(2026, 9, 29, 7, 30)


def test_zero_minutes_means_next_open():
    assert add_work(dt(2026, 9, 26, 10, 0), 0, OFFICE) == dt(2026, 9, 28, 7, 0)


def test_work_over_several_days():
    assert add_work(dt(2026, 9, 28, 7, 0), 2 * 9 * 60 + 30, OFFICE) == dt(2026, 9, 30, 7, 30)


def test_always_open_calendar():
    assert add_work(dt(2026, 9, 26, 10, 0), 90, "24/7") == dt(2026, 9, 26, 11, 30)
    assert next_open(dt(2026, 9, 26, 3, 0), "24/7") == dt(2026, 9, 26, 3, 0)


def test_closed_spans_cover_night_and_weekend():
    spans = closed_spans(dt(2026, 9, 25, 12, 0), dt(2026, 9, 28, 12, 0), OFFICE)
    assert spans == [(dt(2026, 9, 25, 16, 0), dt(2026, 9, 28, 7, 0))]
    assert closed_spans(dt(2026, 9, 25, 12, 0), dt(2026, 9, 28, 12, 0), "24/7") == []
