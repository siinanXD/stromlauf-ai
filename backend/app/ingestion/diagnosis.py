"""Gefuehrte Fehlersuche: Pruefschritte aus einem Fehlereintrag, ohne Sprachmodell.

Die Behebung wird in Saetze zerlegt (Abkuerzungen wie "ca.", "z. B.", "Kap." trennen nicht),
jeder Satz ist ein Schritt mit dem ersten genannten Betriebsmittel und dessen Blatt-Verweis.
Beteiligte Betriebsmittel ohne eigenen Schritt bekommen "{BMK} pruefen".
"""

import re
from datetime import date

from app.ingestion.tags import TagType, extract_tags

# Satzende: Punkt + Leerraum + Grossbuchstabe/BMK, aber nicht nach gaengigen Abkuerzungen
SENTENCE_END = re.compile(
    r"(?<!\b\w)(?<!\bca)(?<!\bKap)(?<!\bNr)(?<!\bbzw)(?<!\bggf)(?<!\bvgl)"
    r"\.\s+(?=[A-ZÄÖÜ\-])|;\s*"
)


def _step(text: str, tag: str, refs: dict[str, str]) -> dict:
    return {"text": text, "tag": tag, "ref": refs.get(tag, ""), "status": "open", "note": ""}


def _tags(text: str) -> list[str]:
    """Betriebsmittel und Klemmen in Textreihenfolge."""
    found = [t for t in extract_tags(text) if t.tag_type in (TagType.DEVICE, TagType.TERMINAL)]
    ordered = sorted(found, key=lambda t: text.find(t.tag.split(":")[0]))
    tags = []
    for tag in (t.tag for t in ordered):
        strip, _, points = tag.partition(":")
        # Sammelschreibweise -X4:U/V/W -> -X4:U, -X4:V, -X4:W
        tags += [f"{strip}:{point}" for point in points.split("/")] if "/" in points else [tag]
    return list(dict.fromkeys(tags))


def _pick(tags: list[str], refs: dict[str, str]) -> str:
    """Erstes Kennzeichen mit Blatt-Verweis, sonst das erste ueberhaupt."""
    return next((tag for tag in tags if tag in refs), tags[0] if tags else "")


def build_steps(fix: str, tags: list[str], refs: dict[str, str]) -> list[dict]:
    steps = []
    for sentence in SENTENCE_END.split(fix or ""):
        text = sentence.strip().rstrip(".").strip()
        if text:
            steps.append(_step(text, _pick(_tags(text), refs), refs))
    # Klemmleiste -X4 gilt als genannt, wenn eine ihrer Klemmen (-X4:U) vorkommt
    mentioned = {part for step in steps for tag in _tags(step["text"]) for part in (tag, tag.split(":")[0])}
    steps += [_step(f"{tag} pruefen", tag, refs) for tag in tags if tag not in mentioned]
    return steps or [_step("Befund aufnehmen", "", refs)]


def append_finding(text: str, finding: str, day: date) -> str:
    line = f"[{day:%d.%m.%Y}] {finding.strip()}"
    return f"{text.rstrip()}\n{line}" if text.strip() else line
