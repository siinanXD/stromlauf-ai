"""Fremd-Testdaten nach testdata/ holen und per SHA-256 pruefen (Issue #68).

Aufruf:  python scripts/fetch_testdata.py [--manifest scripts/testdata_manifest.json] [--ziel testdata]

Das Manifest nennt je Datei Zielpfad unter testdata/, Quelle (https-URL), SHA-256 und Lizenz. Eine vorhandene
Datei mit passender Pruefsumme bleibt liegen, ein zweiter Lauf laedt also nichts. Weicht eine Pruefsumme ab, bei
einer vorhandenen Datei oder einem Download, meldet das Skript die Datei, ueberschreibt nichts und endet mit Exit 1.
Eintraege ohne URL (Quelle noch unbekannt, Datei von Hand ablegen) prueft es nur, wenn die Datei da ist.
"auspacken": "awlpro" zieht die AWL-Quellen eines awlsim-Projekts in eine .awl-Datei; die Pruefsumme gilt der
ausgepackten Datei. testdata/ ist per .gitignore ausgeschlossen: Fremdlizenzen bleiben lokal, keine Downloads in
der CI.
"""

import argparse
import hashlib
import http.client
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "scripts" / "testdata_manifest.json"
TESTDATA = ROOT / "testdata"
SHA256 = re.compile(r"[0-9a-f]{64}")
UNPACKERS = ("awlpro",)
FAILED = ("Pruefsumme weicht ab", "Download mit falscher Pruefsumme", "Download fehlgeschlagen")


@dataclass(frozen=True)
class Entry:
    ziel: str  # Pfad unter testdata/, mit /
    url: str | None
    sha256: str  # der Zieldatei, bei "auspacken" also der ausgepackten
    lizenz: str
    auspacken: str | None = None
    quelle: str = ""  # Herkunft in Worten, wo die URL fehlt


def _check(item: dict, seen: set[str]) -> Entry:
    ziel = str(item.get("ziel") or "")
    path = PurePosixPath(ziel)
    if not ziel or path.is_absolute() or ".." in path.parts or "\\" in ziel or ":" in ziel:
        raise ValueError(f"ziel muss ein relativer Pfad unter testdata/ sein: {ziel!r}")
    if ziel in seen:
        raise ValueError(f"ziel doppelt: {ziel}")
    url = item.get("url")
    if url is not None and not str(url).startswith("https://"):
        raise ValueError(f"{ziel}: url nur per https: {url}")
    if not SHA256.fullmatch(str(item.get("sha256") or "")):
        raise ValueError(f"{ziel}: sha256 muss 64 Hex-Zeichen haben")
    if not str(item.get("lizenz") or "").strip():
        raise ValueError(f"{ziel}: lizenz fehlt")
    if item.get("auspacken") not in (None, *UNPACKERS):
        raise ValueError(f"{ziel}: auspacken kennt nur {', '.join(UNPACKERS)}")
    seen.add(ziel)
    return Entry(
        ziel=ziel,
        url=url,
        sha256=item["sha256"],
        lizenz=item["lizenz"],
        auspacken=item.get("auspacken"),
        quelle=item.get("quelle", ""),
    )


def load_manifest(path: Path) -> list[Entry]:
    """Manifest lesen und jeden Eintrag pruefen; ungueltige Eintraege sind ein Fehler, kein Ueberspringen."""
    seen: set[str] = set()
    return [_check(item, seen) for item in json.loads(path.read_text(encoding="utf-8"))["dateien"]]


def awlpro_sources(data: bytes) -> bytes:
    """AWL-, FUP- und Symbolquellen eines awlsim-Projekts in Dokumentreihenfolge, je mit Kopfzeile."""
    parts = []
    for source in ET.fromstring(data).iter("source"):
        body = (source.text or "").strip("\n")
        parts.append(f"// ===== Quelle: {source.get('name')} =====\n{body}")
    return "\n\n".join(parts).encode("utf-8")


def download(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "stromlauf-ai fetch_testdata"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _store(path: Path, data: bytes) -> None:
    """Erst vollstaendig schreiben, dann umbenennen: nie eine halbe Datei unter dem Zielnamen."""
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_name(path.name + ".part")
    try:
        part.write_bytes(data)
        os.replace(part, path)
    finally:
        part.unlink(missing_ok=True)


def fetch_one(entry: Entry, root: Path, get: Callable[[str], bytes]) -> tuple[str, str]:
    """(Status, Hinweis) fuer einen Eintrag; Status aus FAILED heisst Exit 1."""
    path = root / entry.ziel
    if path.exists():
        if _sha(path.read_bytes()) == entry.sha256:
            return "vorhanden", ""
        return FAILED[0], "Datei loeschen und neu laden oder die Herkunft pruefen"
    if entry.url is None:
        return "ohne Quelle", f"von Hand ablegen. {entry.quelle or 'Quelle unbekannt'}"
    try:
        data = get(entry.url)
    except (OSError, http.client.HTTPException) as exc:  # URLError und HTTPError sind OSError
        return FAILED[2], f"{entry.url}: {exc}"
    if entry.auspacken == "awlpro":
        try:
            data = awlpro_sources(data)
        except ET.ParseError:
            return FAILED[1], f"{entry.url} ist kein awlsim-Projekt"
    if _sha(data) != entry.sha256:
        return FAILED[1], entry.url
    _store(path, data)
    return "geladen", f"{len(data) / 1024:.0f} KB, {entry.lizenz}"


def main(argv: list[str] | None = None, get: Callable[[str], bytes] = download) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--manifest", type=Path, default=MANIFEST, help="Manifest mit URL, SHA-256, Lizenz"
    )
    parser.add_argument(
        "--ziel", type=Path, default=TESTDATA, help="Zielordner, Standard testdata/"
    )
    args = parser.parse_args(argv)

    counts: dict[str, int] = {}
    for entry in load_manifest(args.manifest):
        status, note = fetch_one(entry, args.ziel, get)
        counts[status] = counts.get(status, 0) + 1
        if status != "vorhanden":
            print(f"{status}: {entry.ziel}" + (f" - {note}" if note else ""))
    failed = sum(counts.get(status, 0) for status in FAILED)
    print(
        f"{counts.get('geladen', 0)} geladen, {counts.get('vorhanden', 0)} vorhanden, "
        f"{counts.get('ohne Quelle', 0)} ohne Quelle, {failed} Fehler"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
