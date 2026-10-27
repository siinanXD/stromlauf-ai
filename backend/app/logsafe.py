"""Fehler protokollieren, ohne Dokumentinhalt ins Log zu schreiben (SIN-130).

`logger.exception` und `exc_info=True` haengen den Traceback samt Ausnahmenachricht an. Parser, Datenbanktreiber
und Modellanbieter nehmen die Eingabe gern in ihre Nachricht auf (SQLAlchemy die Parameter des Statements, ein
Parser die kaputte Zeile, ein Anbieter die Anfrage). Dokumenttext, Prompts und Antworten gehoeren aber nicht ins
Log. Deshalb steht hier nur der Ausnahmetyp und der Aufrufweg (Datei, Zeile, Funktion); die Nachricht der
Ausnahme und die ihrer Ursachen bleiben draussen.
"""

import logging
import sys
import traceback


def log_failure(
    logger: logging.Logger, message: str, *args: object, level: int = logging.ERROR
) -> None:
    """Wie `logger.exception(message, *args)`, aber nur mit Typ und Aufrufweg der gerade behandelten Ausnahme.

    Gehoert in einen `except`-Block. `message` nennt die Identifikatoren (Dokument-, Lauf-, Maschinen-ID),
    nie Inhalt. Ausserhalb eines `except`-Blocks steht nur die Meldung im Log.
    """
    exc = sys.exc_info()[1]
    if exc is None:
        logger.log(level, message, *args)
        return
    frames = "".join(traceback.format_tb(exc.__traceback__)).rstrip()
    logger.log(level, message + " [%s]\n%s", *args, type(exc).__name__, frames)
