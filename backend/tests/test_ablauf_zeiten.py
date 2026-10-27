from datetime import datetime, timedelta, timezone

from app.ablauf.schritte import SCHRITTE, beende, neue_schritte, starte
from app.ablauf.zeiten import kennzahlen

BASIS = datetime(2026, 10, 27, 10, 0, tzinfo=timezone.utc)


def _zeit(t: float) -> str:
    return (BASIS + timedelta(seconds=t)).isoformat()


def _lauf(run_id, dauern: dict[str, float], fragen: list[float] | None = None, trace_url=None):
    steps = neue_schritte()
    t = 0.0
    for key, _ in SCHRITTE:
        if key not in dauern:
            continue
        a = _zeit(t)
        t += dauern[key]
        b = _zeit(t)
        steps = beende(starte(steps, key, a, ""), key, b, "")
    if fragen is not None:
        steps = [
            {
                **s,
                "result": [
                    {"question": "q", "answer_md": "a", "sources": [], "dauer_s": d} for d in fragen
                ],
            }
            if s["key"] == "zusammenfassung"
            else s
            for s in steps
        ]
    return {
        "id": run_id,
        "steps": steps,
        "trace_url": trace_url,
        "created_at": "2026-10-27T10:00:00+00:00",
    }


def test_leer():
    k = kennzahlen([])
    assert (
        k["laeufe"] == 0
        and k["schritte"]["lesen"]["anzahl"] == 0
        and k["schritte"]["lesen"]["mittel_s"] is None
    )


def test_mittel_median_max_letzter_und_ziel():
    k = kennzahlen(
        [_lauf("neu", {"lesen": 10}), _lauf("alt", {"lesen": 70}), _lauf("uralt", {"lesen": 20})]
    )
    s = k["schritte"]["lesen"]
    assert (
        s["anzahl"] == 3 and s["mittel_s"] == 33.3 and s["median_s"] == 20.0 and s["max_s"] == 70.0
    )
    assert (
        s["letzter_s"] == 10.0
        and s["ziel_s"] == 60.0
        and s["ueber_ziel"] is False
        and s["langsamster_run_id"] == "alt"
    )


def test_ueber_ziel_bezieht_sich_auf_letzten():
    assert kennzahlen([_lauf("a", {"lesen": 61})])["schritte"]["lesen"]["ueber_ziel"] is True
    assert kennzahlen([_lauf("a", {"maschine": 500})])["schritte"]["maschine"]["ziel_s"] is None


def test_nur_abgeschlossene_schritte_zaehlen():
    lauf = _lauf("a", {"lesen": 5})
    lauf["steps"] = starte(lauf["steps"], "maschine", "2026-10-27T10:00:30+00:00", "")
    assert kennzahlen([lauf])["schritte"]["maschine"]["anzahl"] == 0


def test_gesamt_und_fragen():
    k = kennzahlen([_lauf("a", {"lesen": 100, "zusammenfassung": 50}, fragen=[10.0, 40.0])])
    assert k["gesamt"]["letzter_s"] == 150.0 and k["gesamt"]["ueber_ziel"] is False
    assert (
        k["fragen"]["anzahl"] == 2
        and k["fragen"]["max_s"] == 40.0
        and k["fragen"]["ueber_ziel"] is True
    )
