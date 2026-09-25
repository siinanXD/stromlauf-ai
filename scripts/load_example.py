"""Laedt die Beispielanlage "Foerderband FB-01" in ein laufendes Stromlauf-AI-Backend.

Aufruf:  python scripts/load_example.py [--api http://localhost:8010] [--vision]

Legt die Wissensquelle an (oder verwendet eine vorhandene gleichen Namens), laedt alle Dateien aus
examples/foerderband/ hoch und wartet, bis jede Ingestion abgeschlossen ist.
"""

import argparse
import sys
import time
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx fehlt: cd backend && .venv/Scripts/pip install -e \".[dev]\"")

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_DIR = ROOT / "examples" / "foerderband"
SOURCE_NAME = "Foerderband FB-01"
SOURCE_DESCRIPTION = "Beispielanlage: Stromlaufplan, Stueckliste, Klemmenplan, AWL, Symboltabelle, Anleitung"
FILES = [
    ("01_Stromlaufplan_FB-01.pdf", "schematic"),
    ("02_Stueckliste_FB-01.xlsx", "bom"),
    ("03_Klemmenplan_FB-01.csv", "terminal_plan"),
    ("04_SPS_Programm_FB-01.awl", "plc_program"),
    ("05_Symboltabelle_FB-01.sdf", "plc_symbols"),
    ("06_Betriebsanleitung_FB-01.md", "manual"),
]
DONE_STATES = {"ready", "failed"}


def find_or_create_source(client: httpx.Client) -> dict:
    for source in client.get("/api/sources").json():
        if source["name"] == SOURCE_NAME:
            print(f"Wissensquelle vorhanden: {source['id']}")
            return source
    source = client.post("/api/sources", json={"name": SOURCE_NAME, "description": SOURCE_DESCRIPTION}).json()
    print(f"Wissensquelle angelegt: {source['id']}")
    return source


def upload(client: httpx.Client, source_id: str, path: Path, doc_type: str, vision: bool) -> dict:
    with path.open("rb") as f:
        response = client.post(
            f"/api/sources/{source_id}/documents",
            files={"file": (path.name, f)},
            data={"doc_type": doc_type, "vision": "true" if vision else "false"},
        )
    response.raise_for_status()
    return response.json()


def wait_for(client: httpx.Client, document_ids: list[str], timeout_s: int = 1800) -> bool:
    start = time.time()
    pending = set(document_ids)
    last = {}
    while pending and time.time() - start < timeout_s:
        for doc_id in list(pending):
            doc = client.get(f"/api/documents/{doc_id}").json()
            state = (doc.get("status") or "").lower()
            line = f"{doc['filename']}: {doc.get('status')} {doc.get('progress') or ''}".strip()
            if last.get(doc_id) != line:
                print("  " + line)
                last[doc_id] = line
            if state in DONE_STATES:
                pending.discard(doc_id)
        if pending:
            time.sleep(3)
    return not pending


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010", help="Backend-URL")
    parser.add_argument("--vision", action="store_true", help="Vision-Analyse des PDFs (kostet API-Tokens)")
    args = parser.parse_args()

    missing = [name for name, _ in FILES if not (EXAMPLE_DIR / name).exists()]
    if missing:
        sys.exit(f"Dateien fehlen in {EXAMPLE_DIR}: {missing}")

    with httpx.Client(base_url=args.api, timeout=120) as client:
        try:
            client.get("/api/sources").raise_for_status()
        except httpx.HTTPError as exc:
            sys.exit(f"Backend unter {args.api} nicht erreichbar: {exc}")

        source = find_or_create_source(client)
        existing = {d["filename"] for d in client.get(f"/api/sources/{source['id']}/documents").json()}
        ids = []
        for name, doc_type in FILES:
            if name in existing:
                print(f"schon geladen: {name}")
                continue
            doc = upload(client, source["id"], EXAMPLE_DIR / name, doc_type, args.vision and name.endswith(".pdf"))
            print(f"hochgeladen: {name} -> {doc['id']}")
            ids.append(doc["id"])

        if not ids:
            print("Nichts zu tun.")
            return 0
        print("Warte auf Ingestion (erster Lauf laedt Modelle, das dauert einige Minuten) ...")
        ok = wait_for(client, ids)
        print("Fertig." if ok else "Zeitueberschreitung, Status im Frontend pruefen.")
        print(f"Frontend: http://localhost:3100  ->  Quelle \"{SOURCE_NAME}\"")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
