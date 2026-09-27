"""Neustart-Logik: unterbrochene Dokumente neu einreihen, fehlende Dateien und Schleifen stoppen."""

from types import SimpleNamespace

from app.ingestion.resume import MAX_ATTEMPTS, REQUEUED, plan_restart
from app.models import DocStatus


def doc(status, attempts=0, path="/data/uploads/a.pdf", doc_id="a"):
    return SimpleNamespace(
        id=doc_id, status=status, attempts=attempts, storage_path=path, error="alt", progress="Embeddings 3/9"
    )


def test_pending_and_processing_are_requeued():
    pending, processing = doc(DocStatus.PENDING, doc_id="p"), doc(DocStatus.PROCESSING, doc_id="q")
    assert plan_restart([pending, processing], exists=lambda _: True) == ["p", "q"]
    for document in (pending, processing):
        assert document.status == DocStatus.PENDING
        assert document.progress == REQUEUED
        assert document.error is None


def test_ready_and_failed_are_left_alone():
    ready, failed = doc(DocStatus.READY), doc(DocStatus.FAILED)
    assert plan_restart([ready, failed], exists=lambda _: True) == []
    assert ready.progress == "Embeddings 3/9"
    assert failed.error == "alt"


def test_missing_file_fails_instead_of_requeue():
    document = doc(DocStatus.PROCESSING)
    assert plan_restart([document], exists=lambda _: False) == []
    assert document.status == DocStatus.FAILED
    assert "Datei fehlt" in document.error
    assert document.progress == ""


def test_attempt_limit_stops_restart_loop():
    looping = doc(DocStatus.PROCESSING, attempts=MAX_ATTEMPTS, doc_id="l")
    fresh = doc(DocStatus.PROCESSING, attempts=MAX_ATTEMPTS - 1, doc_id="f")
    assert plan_restart([looping, fresh], exists=lambda _: True) == ["f"]
    assert looping.status == DocStatus.FAILED
    assert "Neu verarbeiten" in looping.error
