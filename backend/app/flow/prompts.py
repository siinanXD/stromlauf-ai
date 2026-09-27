"""Prompts der drei Extraktionsphasen. PROMPT_VERSION ist Teil des Cache-Schluessels:
jede Aenderung hier macht alte Ergebnisse ungueltig."""

PROMPT_VERSION = "2026-09-27.1"

RULES = """\
Regeln fuer jedes Objekt:
- source: die Marke [[Datei | Seite/Abschnitt]] der Fundstelle als file/page/chunk und ein woertliches
  Zitat von hoechstens 15 Woertern aus genau dieser Passage.
- confidence: 0 bis 1. Belegt und eindeutig = 0.9 oder hoeher; aus dem Zusammenhang erschlossen = 0.5 bis 0.8.
- assumption: true, wenn die Doku es nicht sagt und du es annimmst. Nicht raten: lieber weglassen oder
  assumption: true mit niedriger confidence.
- Adressen deutsch normalisiert schreiben: E0.0, A4.1, M10.1 (aus "E 0.0", "%I0.0", "I0.0").
- Betriebsmittelkennzeichen mit Minus: -B1, -K12, -S3."""

IO_SYSTEM = f"""\
Du liest Elektrodokumentation einer Maschine und extrahierst die SPS-Ein- und Ausgaenge.
Quellen: Symboltabelle, I/O-Belegungsliste, SPS-Belegung im Handbuch, Klemmenplan.
Liefere jeden Ein-/Ausgang genau einmal: address, symbol (falls vorhanden), direction (DI/DO/AI/AO),
description (Klartext aus der Doku), active_state (Pegel, bei dem das Signal als "aktiv/ausgeloest" gilt;
Oeffner-Taster: 0, sonst 1).
{RULES}"""

DEVICE_SYSTEM = f"""\
Du liest Elektrodokumentation einer Maschine und extrahierst Sensoren, Aktoren, Bedienelemente und
Sicherheitsgeraete mit Betriebsmittelkennzeichen (BMK).
Quellen: Stueckliste, Handbuch (Bedienelemente, Funktionsbeschreibung), Klemmenplan, Stromlaufplan.
Je Geraet: tag (BMK), kind (sensor/actuator/operator/safety/other), contact (NC=Oeffner, NO=Schliesser,
null wenn unbekannt oder nicht zutreffend), location (Einbauort, z. B. +FE1 Einlauf), description,
address (SPS-Adresse, wenn die Doku sie nennt, sonst leer).
{RULES}"""

STEPS_SYSTEM = f"""\
Du bist Steuerungstechniker und leitest aus der Funktionsbeschreibung, dem SPS-Programm (AWL) und der
I/O-Liste die Schrittkette (GRAFCET-artig) einer Maschine ab.
- Schritte: id (S0, S1, ...), name, genau ein initial=true (Grundstellung/Bereit).
- actions: welche Ausgaenge der Schritt setzt (state 1) oder ruecksetzt (state 0); io als Adresse aus der I/O-Liste.
- transitions: target (Schritt-id), conditions (UND-verknuepft; io als Adresse, state, edge fuer Flanken),
  timer_s bei Zeitgliedern, expression als Klartext.
- Nur Adressen aus der uebergebenen I/O-Liste verwenden. Fehlt ein Signal dort, nenne es in open_questions.
- Stoerungen und Not-Halt als eigene Schritte, wenn die Doku sie beschreibt.
- open_questions: was die Doku nicht hergibt (z. B. Rueckwaertsbetrieb ohne Beschreibung).
- summary: Ablauf in zwei bis drei Saetzen.
{RULES}"""


def io_user(context: str) -> str:
    return f"Dokumentation:\n\n{context}\n\nExtrahiere alle SPS-Ein- und Ausgaenge."


def device_user(context: str) -> str:
    return f"Dokumentation:\n\n{context}\n\nExtrahiere alle Sensoren, Aktoren, Bedienelemente und Sicherheitsgeraete."


def steps_user(context: str, io_table: str, machine: str) -> str:
    return (
        f"Maschine: {machine}\n\nI/O-Liste (verwende nur diese Adressen):\n{io_table}\n\n"
        f"Dokumentation:\n\n{context}\n\nLeite die Schrittkette ab."
    )
