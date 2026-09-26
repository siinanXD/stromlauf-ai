"""Laedt die Beispielanlage "Foerderband FB-01" in ein laufendes Stromlauf-AI-Backend.

Aufruf:  python scripts/load_example.py [--api http://localhost:8010] [--vision]

Legt die Wissensquelle an (oder verwendet eine vorhandene gleichen Namens), laedt alle Dateien aus
examples/foerderband/ hoch und wartet, bis jede Ingestion abgeschlossen ist.
"""

import argparse
import json
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
            try:
                doc = client.get(f"/api/documents/{doc_id}").json()
            except httpx.HTTPError as exc:
                print(f"  Backend nicht erreichbar ({exc.__class__.__name__}), neuer Versuch in 10 s ...")
                time.sleep(10)
                continue
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


LAYOUT_JSON = EXAMPLE_DIR / "08_Aufstellungsplan_FB-01.json"
LAYOUT_PNG = EXAMPLE_DIR / "08_Aufstellungsplan_FB-01.png"
HALL_NAME = "Halle 1 (Beispiel)"
MACHINE_NAME = "Foerderband FB-01"
FAULTS = [
    {"code": "E-F2", "symptom": "-H2 leuchtet, Band steht, Start ohne Wirkung", "cause": "Motorschutz -F2 ausgeloest (E0.2 = 0)",
     "fix": "-F2 pruefen, Motorstrom -M1 messen (Nennstrom 3,5 A). Nach Abkuehlen einschalten, mit -S1 quittieren.",
     "doc_ref": "Betriebsanleitung Kap. 6, Stromlaufplan Blatt 3", "tags": ["-F2", "-M1", "-H2"]},
    {"code": "E-BLOCK", "symptom": "-H2 leuchtet nach ca. 20 s Betrieb", "cause": "Blockade: Teil am Einlauf -B1, aber nicht am Auslauf -B2 (Timer T5)",
     "fix": "Band auf Verklemmung pruefen, -B2 reinigen und ausrichten (Klemme -X3:6, E0.5).",
     "doc_ref": "FB10 Netzwerk 5, Betriebsanleitung Kap. 6", "tags": ["-B1", "-B2", "-X3"]},
    {"code": "E-NH", "symptom": "Start ohne Wirkung, -H1 und -H2 aus", "cause": "Not-Halt nicht entriegelt, -K3 ohne Freigabe (E0.3 = 0)",
     "fix": "-S3 entriegeln, 24 V an -X3:4 pruefen, beide Kanaele -S3 11/12 und 21/22 pruefen.",
     "doc_ref": "Stromlaufplan Blatt 4", "tags": ["-S3", "-K3", "-X3"]},
    {"code": "E-PH", "symptom": "-K1 zieht an, Motor brummt, dreht nicht", "cause": "Phase fehlt am Motorabgang",
     "fix": "Spannung an -X4:U/V/W pruefen, Motorleitung -W4 und -M1:U1/V1/W1.",
     "doc_ref": "Stromlaufplan Blatt 3", "tags": ["-X4", "-M1", "-K1"]},
]


def setup_plant(client: httpx.Client, source_id: str) -> None:
    """Halle, Maschine, Schaltschrank-Aufbauplan mit Hotspots und Fehlerliste anlegen (idempotent)."""
    halls = client.get("/api/halls").json()
    hall = next((h for h in halls if h["name"] == HALL_NAME), None)
    if hall is None:
        hall = client.post("/api/halls", json={"name": HALL_NAME, "description": "Beispielhalle aus examples/foerderband"}).json()
        print(f"Halle angelegt: {HALL_NAME}")
    detail = client.get(f"/api/halls/{hall['id']}").json()
    machine = next((m for m in detail["machines"] if m["name"] == MACHINE_NAME), None)
    if machine is None:
        machine = client.post(
            f"/api/halls/{hall['id']}/machines",
            json={"name": MACHINE_NAME, "machine_type": "conveyor", "source_id": source_id, "pos_x": 72, "pos_y": 96,
                  "description": "Werkstuecktransport Einlauf -> Auslauf, Wendeschuetz -K1/-K2, SPS -A1"},
        ).json()
        print(f"Maschine angelegt: {MACHINE_NAME}")
        # zwei Nachbarn fuer den Materialfluss, ohne Doku
        before = client.post(f"/api/halls/{hall['id']}/machines", json={"name": "Magazin", "machine_type": "storage", "pos_x": 72, "pos_y": 312}).json()
        after = client.post(f"/api/halls/{hall['id']}/machines", json={"name": "Verpackung VP-02", "machine_type": "packaging", "pos_x": 504, "pos_y": 96}).json()
        client.put(f"/api/halls/{hall['id']}/flows", json=[
            {"from_machine_id": before["id"], "to_machine_id": machine["id"], "label": "Rohteile"},
            {"from_machine_id": machine["id"], "to_machine_id": after["id"], "label": "Fertigteile"},
        ])
    elif machine.get("source_id") != source_id:
        client.patch(f"/api/machines/{machine['id']}", json={"source_id": source_id})

    full = client.get(f"/api/machines/{machine['id']}").json()
    if not full["faults"]:
        for fault in FAULTS:
            client.post(f"/api/machines/{machine['id']}/faults", json=fault)
        print(f"Fehlerliste: {len(FAULTS)} Eintraege")

    plan = EXAMPLE_DIR / "07_Schaltschrank_Aufbauplan_FB-01.png"
    spots = EXAMPLE_DIR / "07_Schaltschrank_Hotspots_FB-01.json"
    if not full["cabinets"] and plan.exists() and spots.exists():
        with plan.open("rb") as f:
            cabinet = client.post(f"/api/machines/{machine['id']}/cabinets", files={"file": (plan.name, f, "image/png")},
                                  data={"title": "Schaltschrank +ST1 (Aufbauplan)"}).json()
        for spot in json.loads(spots.read_text(encoding="utf-8")):
            client.post(f"/api/cabinets/{cabinet['id']}/hotspots", json={**spot, "confirmed": True})
        print("Schaltschrank-Aufbauplan mit Hotspots angelegt")

    setup_layout(client, machine["id"])


def setup_layout(client: httpx.Client, machine_id: str) -> dict:
    """Draufsicht aus dem Soll-Layout anlegen; vorhandene Teile werden ersetzt (idempotent)."""
    data = json.loads(LAYOUT_JSON.read_text(encoding="utf-8"))
    layout = client.put(
        f"/api/machines/{machine_id}/layout",
        json={k: data[k] for k in ("width_mm", "depth_mm", "scale_note")},
    ).json()
    for part in layout["parts"]:
        client.delete(f"/api/layout-parts/{part['id']}")
    for part in data["parts"]:
        client.post(f"/api/layouts/{layout['id']}/parts", json={**part, "confirmed": True}).raise_for_status()
    if LAYOUT_PNG.exists():
        with LAYOUT_PNG.open("rb") as f:
            client.post(f"/api/machines/{machine_id}/layout/image", files={"file": (LAYOUT_PNG.name, f, "image/png")})
    print(f"Draufsicht angelegt: {len(data['parts'])} Teile")
    return layout


def compare_layout_vision(client: httpx.Client, layout_id: str) -> None:
    """Vision gegen das Soll pruefen: welche BMK wurden gefunden (kostet API-Tokens)."""
    expected = {p["tag"] for p in json.loads(LAYOUT_JSON.read_text(encoding="utf-8"))["parts"] if p["tag"]}
    result = client.post(f"/api/layouts/{layout_id}/detect", timeout=300)
    result.raise_for_status()
    found = {p["tag"] for p in result.json()["parts"] if p["origin"] == "vision" and p["tag"]}
    print(f"Vision: {len(found & expected)}/{len(expected)} Soll-BMK gefunden; fehlend: {sorted(expected - found)}; "
          f"zusaetzlich: {sorted(found - expected)}")


def maybe_compare(client: httpx.Client, enabled: bool) -> None:
    if not enabled:
        return
    for hall in client.get("/api/halls").json():
        for machine in client.get(f"/api/halls/{hall['id']}").json()["machines"]:
            if machine["name"] == MACHINE_NAME:
                compare_layout_vision(client, client.get(f"/api/machines/{machine['id']}/layout").json()["id"])
                return


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--api", default="http://localhost:8010", help="Backend-URL")
    parser.add_argument("--vision", action="store_true", help="Vision-Analyse des PDFs (kostet API-Tokens)")
    parser.add_argument("--layout-vision", action="store_true",
                        help="Draufsicht zusaetzlich per Vision erkennen und mit dem Soll vergleichen (kostet API-Tokens)")
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
            print("Alle Dokumente vorhanden.")
            setup_plant(client, source["id"])
            maybe_compare(client, args.layout_vision)
            return 0
        print("Warte auf Ingestion (erster Lauf laedt Modelle, das dauert einige Minuten) ...")
        ok = wait_for(client, ids)
        print("Fertig." if ok else "Zeitueberschreitung, Status im Frontend pruefen.")
        setup_plant(client, source["id"])
        maybe_compare(client, args.layout_vision)
        print(f"Frontend: http://localhost:3100  ->  Quelle \"{SOURCE_NAME}\", Werk -> Halle 1")
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
