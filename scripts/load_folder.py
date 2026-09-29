"""Laedt alle unterstuetzten Dateien eines Ordners als Wissensquelle in ein laufendes Backend.

Aufruf:  python scripts/load_folder.py testdata/festo --name "Festo MPS" [--api http://localhost:8010] [--vision]

Fuer eigene Testdaten (testdata/ ist in .gitignore). Dateityp wird vom Backend an der Endung erkannt.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_example import upload, wait_for  # noqa: E402

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx fehlt: cd backend && .venv/Scripts/pip install -e \".[dev]\"")

SUFFIXES = {".pdf", ".xlsx", ".csv", ".docx", ".pptx", ".md", ".html", ".txt", ".awl", ".sdf", ".png", ".jpg", ".jpeg"}


def candidate_files(folder: Path) -> list[Path]:
    """Dateien mit unterstuetzter Endung, alphabetisch. README.* beschreibt den Ordner und ist keine Kundendatei
    (bei examples/injection stuenden sonst die erwarteten Fallenmuster selbst in der Wissensquelle)."""
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in SUFFIXES and p.stem.lower() != "readme")


def _auth_headers() -> dict[str, str]:
    """API_KEY des Backends aus STROMLAUF_API_KEY (leer = Backend offen)."""
    key = os.environ.get("STROMLAUF_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--name", required=True, help="Name der Wissensquelle")
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--vision", action="store_true", help="Vision-Analyse fuer PDFs (kostet API-Tokens je Seite)")
    args = parser.parse_args()

    files = candidate_files(args.folder)
    if not files:
        sys.exit(f"Keine unterstuetzten Dateien in {args.folder}")

    with httpx.Client(base_url=args.api, timeout=300, headers=_auth_headers()) as client:
        sources = client.get("/api/sources").json()
        source = next((s for s in sources if s["name"] == args.name), None)
        if source is None:
            source = client.post("/api/sources", json={"name": args.name, "description": f"Testdaten aus {args.folder}"}).json()
            print(f"Wissensquelle angelegt: {args.name}")
        existing = {d["filename"] for d in client.get(f"/api/sources/{source['id']}/documents").json()}
        ids = []
        for path in files:
            if path.name in existing:
                print(f"schon geladen: {path.name}")
                continue
            doc = upload(client, source["id"], path, "auto", args.vision and path.suffix.lower() == ".pdf")
            print(f"hochgeladen: {path.name} ({path.stat().st_size // 1024} KB)")
            ids.append(doc["id"])
        if not ids:
            print("Nichts zu tun.")
            return 0
        print("Warte auf Ingestion ...")
        ok = wait_for(client, ids, timeout_s=3600)
        print("Fertig." if ok else "Zeitueberschreitung, Status im Frontend pruefen.")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
