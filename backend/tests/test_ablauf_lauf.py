"""Ablauf-Orchestrator ohne Datenbank: feste Fragen, Spur ohne Tracing, lesbare Modellfehler."""

from contextlib import contextmanager
from types import SimpleNamespace

import httpx

from app.ablauf.fragen import FRAGEN
from app.ablauf.schritte import beende, neue_schritte, starte
from app.ablauf.spur import Spur


def test_drei_feste_fragen():
    assert len(FRAGEN) == 3 and FRAGEN[0].startswith("Was ist das für eine Anlage")


def test_spur_ohne_tracing_ist_noop(monkeypatch):
    monkeypatch.setattr("app.ablauf.spur.tracing_enabled", lambda: False)
    spur = Spur.fuer("r1", "ollama:qwen3.5:9b")
    with spur.schritt("lesen", "3 Dateien") as s:
        s.output("ok")
    assert spur.url() is None
    spur.schliessen("fertig")


def test_modellfehler_wird_lesbar():
    from app.ablauf.lauf import fehlertext

    assert (
        fehlertext(ConnectionError("refused"), "ollama:qwen3.5:9b")
        == "Modell nicht erreichbar: ollama:qwen3.5:9b"
    )
    assert fehlertext(ValueError("x"), "m") == "ValueError: x"
    assert fehlertext(TimeoutError(), "m") == "Zeitlimit überschritten"


def test_verbindungsfehler_der_clients_werden_lesbar():
    from app.ablauf.lauf import fehlertext

    class APIConnectionError(Exception):  # wie openai.APIConnectionError, ohne Import
        pass

    assert fehlertext(httpx.ConnectError("refused"), "m") == "Modell nicht erreichbar: m"
    assert fehlertext(APIConnectionError("down"), "m") == "Modell nicht erreichbar: m"


def test_fehler_in_einem_schritt_beendet_den_lauf_ohne_zu_werfen(monkeypatch):
    from app.ablauf import lauf

    steps = beende(neue_schritte(), "hochladen", "2026-10-26T10:00:00+00:00", "2 Dateien")
    run = SimpleNamespace(
        id="r1",
        source_id="s1",
        workspace_id=None,
        model="m",
        steps=steps,
        status="laeuft",
        machine_id=None,
        trace_url=None,
        error=None,
        finished_at=None,
    )

    @contextmanager
    def fake_scope():
        yield SimpleNamespace(get=lambda _model, _id: run)

    def kaputt(_ctx):
        raise ValueError("Datei unlesbar")

    monkeypatch.setattr(lauf, "session_scope", fake_scope)
    monkeypatch.setattr("app.ablauf.spur.tracing_enabled", lambda: False)
    monkeypatch.setattr(lauf, "schritt_lesen", kaputt)

    lauf.starte_lauf("r1", graph=None, loop=None)

    lesen = next(s for s in run.steps if s["key"] == "lesen")
    assert lesen["status"] == "fehler" and lesen["input"] == "2 Dateien"
    assert run.status == "fehler" and run.error == "ValueError: Datei unlesbar"
    assert run.finished_at is not None
    assert all(s["status"] == "wartet" for s in run.steps[2:])


def test_kaputtes_langfuse_laesst_den_schritt_fertig_werden(monkeypatch):
    from app.ablauf import lauf

    class KaputteWurzel:
        def start_as_current_observation(self, **_kwargs):
            raise RuntimeError("langfuse down")

    gespeichert = []
    monkeypatch.setattr(
        lauf, "_speichere", lambda run_id, aendere, **f: gespeichert.append(aendere)
    )
    ctx = SimpleNamespace(run_id="r1", model="m", machine_id=None, ergebnis={})
    spur = Spur(client=None, root=KaputteWurzel(), attrs={})

    ausgabe = lauf._fuehre_aus(ctx, spur, "lesen", lambda _ctx: "3 Dokumente", "in")

    assert ausgabe == "3 Dokumente"
    steps = gespeichert[-1](starte(neue_schritte(), "lesen", "t", "in"))
    assert next(s for s in steps if s["key"] == "lesen")["status"] == "fertig"


def test_zusammenfassung_schreibt_dauer_je_frage(monkeypatch):
    from app.ablauf import lauf

    @contextmanager
    def fake_scope():
        yield SimpleNamespace()

    monkeypatch.setattr(lauf, "session_scope", fake_scope)
    monkeypatch.setattr(lauf, "machine_scope", lambda _session, _id: (None, {"name": "M"}))
    monkeypatch.setattr(lauf, "beantworte", lambda *a, **k: ("Antwort", []))
    ctx = lauf.LaufKontext("r1", "s1", None, "m", graph=None, loop=None, machine_id="m1")

    lauf.schritt_zusammenfassung(ctx)

    antworten = ctx.ergebnis["zusammenfassung"]
    assert len(antworten) == len(FRAGEN)
    assert all(a["dauer_s"] >= 0 for a in antworten)
