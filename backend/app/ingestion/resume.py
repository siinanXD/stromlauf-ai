"""Ingestion nach einem Neustart fortsetzen.

Die Verarbeitung laeuft im Backend-Prozess (BackgroundTasks). Stirbt der Prozess, bleiben
Dokumente auf PENDING oder PROCESSING stehen. Beim Start werden sie neu eingereiht statt als
fehlgeschlagen markiert. Damit ein Dokument, das den Prozess jedes Mal zum Absturz bringt
(z. B. Speicher), keine Endlosschleife erzeugt, zaehlt `Document.attempts` die Anlaeufe; nach
MAX_ATTEMPTS bleibt es FAILED, bis jemand "Neu verarbeiten" klickt (setzt den Zaehler zurueck).
"""

import logging
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

from app.models import DocStatus

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
REQUEUED = "nach Neustart neu eingereiht"


def plan_restart(documents: Iterable, exists: Callable[[Path], bool] = Path.exists) -> list[str]:
    """Setzt Status/Fehler der unterbrochenen Dokumente und liefert die IDs, die neu laufen sollen."""
    requeue: list[str] = []
    for document in documents:
        if document.status not in (DocStatus.PENDING, DocStatus.PROCESSING):
            continue
        document.progress = ""
        if not exists(Path(document.storage_path)):
            document.status = DocStatus.FAILED
            document.error = f"Datei fehlt nach Neustart: {document.storage_path}"
        elif document.attempts >= MAX_ATTEMPTS:
            document.status = DocStatus.FAILED
            document.error = (
                f"Verarbeitung {document.attempts}-mal durch Neustart unterbrochen; "
                "mit 'Neu verarbeiten' erneut anstossen"
            )
        else:
            document.status = DocStatus.PENDING
            document.error = None
            document.progress = REQUEUED
            requeue.append(document.id)
    return requeue


def resume_in_background(document_ids: list[str]) -> threading.Thread | None:
    """Verarbeitet die Dokumente nacheinander in einem Daemon-Thread (die Pipeline serialisiert ohnehin)."""
    if not document_ids:
        return None
    from app.ingestion.pipeline import ingest_document

    def run() -> None:
        logger.info("Setze Ingestion von %d Dokument(en) nach Neustart fort", len(document_ids))
        for document_id in document_ids:
            ingest_document(document_id)

    thread = threading.Thread(target=run, name="ingest-resume", daemon=True)
    thread.start()
    return thread
