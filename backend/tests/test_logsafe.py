"""SIN-130: Kein Dokumentinhalt im Log. Eine Ausnahme, deren Nachricht Kundentext traegt, darf diesen Text in keinem
Log-Record hinterlassen; Typ und Identifikatoren bleiben sichtbar."""

import logging
import re
import traceback
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

from app.ablauf.spur import Spur
from app.ingestion import pipeline
from app.logsafe import log_failure

KUNDENTEXT = "Klemme -X7:3 im Kundenplan der Firma Muster GmbH"
APP = Path(__file__).resolve().parents[1] / "app"


def _kein_kundentext(caplog) -> None:
    assert caplog.records, "es wurde nichts protokolliert"
    assert KUNDENTEXT not in caplog.text
    for record in caplog.records:
        assert KUNDENTEXT not in record.getMessage()
        if record.exc_info:  # ein Traceback haengt die Nachricht der Ausnahme an
            assert KUNDENTEXT not in "".join(traceback.format_exception(*record.exc_info))


def test_log_failure_nennt_typ_und_aufrufweg_aber_nicht_die_nachricht(caplog):
    logger = logging.getLogger("test.logsafe")

    def parser_bricht():
        raise ValueError(KUNDENTEXT)

    try:
        try:
            parser_bricht()
        except ValueError as ursache:
            raise RuntimeError(f"Folgefehler: {KUNDENTEXT}") from ursache
    except RuntimeError:
        log_failure(logger, "Datei %s fehlgeschlagen", "a.pdf")

    _kein_kundentext(caplog)
    assert "Datei a.pdf fehlgeschlagen [RuntimeError]" in caplog.text
    assert (
        "test_log_failure_nennt_typ_und_aufrufweg" in caplog.text
    )  # Aufrufweg bleibt fuer die Diagnose
    assert caplog.records[0].levelno == logging.ERROR


def test_log_failure_kennt_die_stufe_und_laeuft_auch_ohne_ausnahme(caplog):
    logger = logging.getLogger("test.logsafe")

    log_failure(logger, "ohne Ausnahme %s", 1, level=logging.WARNING)

    assert caplog.records[0].levelno == logging.WARNING
    assert caplog.records[0].getMessage() == "ohne Ausnahme 1"


def test_ingestion_loggt_unerwartete_fehler_ohne_kundentext(monkeypatch, caplog):
    document = SimpleNamespace(
        status="pending",
        error=None,
        progress="",
        attempts=0,
        storage_path="upload.pdf",
        filename="plan.pdf",
        source_id="s1",
        doc_type="schematic",
        vision_enrichment=False,
        workspace_id=None,
    )

    @contextmanager
    def fake_scope():
        yield SimpleNamespace(get=lambda _model, _id: document)

    def parser_bricht(*_args, **_kwargs):
        raise ValueError(KUNDENTEXT)

    monkeypatch.setattr(pipeline, "session_scope", fake_scope)
    monkeypatch.setattr(pipeline.ledger, "machine_for_source", lambda _session, _id: None)
    monkeypatch.setattr(pipeline, "_prepare_scan", lambda *_args: (None, ""))
    monkeypatch.setattr(pipeline, "_build_pieces", parser_bricht)

    pipeline.ingest_document("d1")

    _kein_kundentext(caplog)
    assert "Dokument d1" in caplog.text and "[ValueError]" in caplog.text
    # bleibt unveraendert: die Fehlerspalte am Dokument (Retry- und Fehlerlogik gehoeren nicht zu SIN-130)
    assert document.status == "failed"


def test_ablauf_schritt_loggt_fehler_ohne_kundentext(monkeypatch, caplog):
    from app.ablauf import lauf

    monkeypatch.setattr(lauf, "_speichere", lambda *_args, **_kwargs: None)
    ctx = SimpleNamespace(run_id="r1", model="m", machine_id=None, ergebnis={})

    def schritt_bricht(_ctx):
        raise ValueError(KUNDENTEXT)

    assert lauf._fuehre_aus(ctx, Spur(), "lesen", schritt_bricht, "in") is None

    _kein_kundentext(caplog)
    assert "Ablauf r1: Schritt lesen fehlgeschlagen [ValueError]" in caplog.text


# Diese Dateien protokollieren bewusst mit Traceback. demo.py und ablauf/spur.py begruenden es an der Stelle;
# api/auth.py meldet nur einen SMTP-Fehler (kein Dokumentinhalt) und blieb in SIN-130 unberuehrt, weil die Datei
# den PR auf risk:high hoebe.
MIT_TRACEBACK = {"demo.py", "ablauf/spur.py", "api/auth.py", "logsafe.py"}


def test_kein_traceback_ins_log_ausser_an_begruendeten_stellen():
    gefunden = []
    for datei in sorted(APP.rglob("*.py")):
        name = datei.relative_to(APP).as_posix()
        if name in MIT_TRACEBACK:
            continue
        for nummer, zeile in enumerate(datei.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\.exception\(|exc_info\s*=\s*True", zeile):
                gefunden.append(f"{name}:{nummer}")

    assert not gefunden, (
        f"logger.exception/exc_info an {gefunden}: Traceback traegt die Ausnahmenachricht und damit "
        "womoeglich Dokumentinhalt. Stattdessen app.logsafe.log_failure nutzen."
    )
