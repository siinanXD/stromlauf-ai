"""Gilt fuer alle Tests unter tests/.

Jeder `TestClient(app)` durchlaeuft den lifespan. Mit RESUME_INGESTION wuerde er alle Dokumente auf PENDING
oder PROCESSING neu einreihen und in einem Daemon-Thread verarbeiten, ueber alle Workspaces. Lokal teilen
sich Testlaeufe die Entwicklungsdatenbank mit dem Backend und mit Laeufen anderer Sitzungen; ein Testlauf
griffe so nach deren Uploads, und sein Thread stirbt mitten in der Arbeit, wenn pytest endet.
"""

import os


def pytest_configure(config):
    # hart gesetzt, nicht setdefault: auch ein RESUME_INGESTION=true aus der Shell gilt in Tests nicht
    os.environ["RESUME_INGESTION"] = "false"
