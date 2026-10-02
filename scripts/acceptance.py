"""Abnahme-Nachweise fuer die Demo-Maschine (docs/product/contract.md Abschnitt 5) einsammeln, ohne Modellaufruf.

Aufruf:  python scripts/acceptance.py [--api http://localhost:8010] [--machine "Foerderband FB-01"] [--load]
                                     [--out eval/results] [--strict] [--health-timeout 600]
                                     [--min-zones 5] [--min-parts 20] [--max-ingest-min 15] [--tolerance 0.5]

Misst die Zeit, bis /api/health antwortet (Kaltstart), mit --load die Ingestion-Dauer der Beispielanlage
(scripts/load_example.py, ohne Vision), zaehlt Baugruppen und Teile des Modells (GET /api/machines/{id}/map)
und prueft je Teil eine Fundstelle (GET /api/machines/{id}/tags/{tag}), liest Kostenbuch und Schaetzung
(GET /api/machines/{id}/costs, GET /api/machines/estimate) und vergleicht beide je Zweck mit der Toleranz.
Schreibt eval/results/acceptance_<zeitstempel>.json und .md (Tabelle fuer docs/product/ACCEPTANCE.md).
Exit 1 nur mit --strict, wenn eine Pruefung fehlschlaegt; ohne --strict ist das Skript ein Nachweis-Sammler.
Zugriff: STROMLAUF_API_KEY (X-API-Key) oder STROMLAUF_TOKEN (Bearer-JWT aus dem Magic-Link-Login).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit('httpx fehlt: cd backend && pip install -e ".[dev]"')

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_OUT = ROOT / "eval" / "results"
DEFAULT_MACHINE = "Foerderband FB-01"
UNKNOWN_ZONE = "?"  # Sammelzone "Ohne Einbauort" zaehlt nicht als Baugruppe
# Zweck im Kostenbuch -> Schaetzposten (cents je Einheit) und Menge, auf die er sich bezieht
ESTIMATE_ROWS = (
    ("vision.page", "per_page_vision_cents", "pages"),
    ("vision.cabinet", "per_photo_cents", "photos"),
)


@dataclass(frozen=True)
class Thresholds:
    """Schwellen aus contract.md Abschnitt 5; Kaltstart hat dort keine Zahl und bleibt informativ."""

    min_zones: int = 5
    min_parts: int = 20
    max_ingest_min: float = 15.0
    tolerance: float = 0.5
    min_hotspots: int = 10


def auth_headers() -> dict[str, str]:
    """Bearer-JWT (STROMLAUF_TOKEN) vor API-Key (STROMLAUF_API_KEY); beides leer = Backend offen."""
    token = os.environ.get("STROMLAUF_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}
    key = os.environ.get("STROMLAUF_API_KEY", "").strip()
    return {"X-API-Key": key} if key else {}


def wait_healthy(
    client: httpx.Client,
    timeout_s: float,
    sleep_s: float = 2.0,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> float:
    """Sekunden bis zur ersten 200 auf /api/health; ein schlafender Dienst (Railway) wacht dabei auf."""
    started = clock()
    while True:
        try:
            if client.get("/api/health").status_code == 200:
                return clock() - started
        except httpx.HTTPError:
            pass
        if clock() - started >= timeout_s:
            raise RuntimeError(f"Backend {client.base_url} nach {timeout_s:.0f} s nicht erreichbar")
        sleep(sleep_s)


def find_machine(machines: list[dict], name: str) -> dict | None:
    """Erst exakter Name, dann Namensteil ohne Gross/Klein."""
    for machine in machines:
        if machine.get("name") == name:
            return machine
    needle = name.lower()
    for machine in machines:
        if needle in (machine.get("name") or "").lower():
            return machine
    return None


def map_evidence(map_json: dict, lookup: Callable[[str], dict]) -> dict:
    """Baugruppen (Zonen mit Einbauort), Teile je Herkunft und Fundstellen je Kennzeichen (einmal je Tag)."""
    all_zones = map_json.get("zones", [])
    zones = [zone for zone in all_zones if zone.get("code") != UNKNOWN_ZONE]
    parts = [part for zone in all_zones for part in zone.get("parts", [])]
    tags = list(dict.fromkeys(part["tag"] for part in parts if part.get("tag")))
    without_hit = [tag for tag in tags if not lookup(tag).get("hits")]
    cited_share = (len(tags) - len(without_hit)) / len(tags) if tags else 0.0
    return {
        "zones": len(zones),
        "zone_codes": [zone.get("code", "") for zone in zones],
        "parts": len(parts),
        "parts_by_source": dict(Counter(part.get("source", "") for part in parts)),
        "parts_without_hit": without_hit,
        "connectors": len(map_json.get("connectors", [])),  # Leitungen mit zwei Orten zaehlen nicht als Teile
        "cited_share": round(cited_share, 3),
    }


def compare_estimate(estimate: dict, costs: dict, pages: int, photos: int, tolerance: float) -> list[dict]:
    """Schaetzung (GET /api/machines/estimate) gegen das Kostenbuch je Zweck; ohne Aufruf bleibt der Vergleich offen."""
    by_purpose = (costs.get("total") or {}).get("by_purpose") or {}
    amounts = {"pages": pages, "photos": photos}
    rows = []
    for purpose, key, amount in ESTIMATE_ROWS:
        estimated = round(float(estimate.get(key, 0.0)) * amounts[amount], 3)
        booked = by_purpose.get(purpose) or {}
        actual = round(float(booked.get("cents", 0.0)), 3)
        calls = int(booked.get("calls", 0))
        deviation = within = None
        if calls > 0 and estimated > 0:
            deviation = abs(actual - estimated) / estimated
            within = deviation <= tolerance
        rows.append({"purpose": purpose, "estimated_cents": estimated, "actual_cents": actual, "calls": calls,
                     "deviation": deviation, "within": within})
    return rows


def evaluate(evidence: dict, thresholds: Thresholds) -> list[dict]:
    """Jede Pruefung: ok True/False, oder None, wenn sie auf diesem System nicht messbar war."""
    map_ = evidence["map"]
    ledger = evidence["ledger"]
    ingest_s = evidence.get("ingest_s")
    estimate_rows = [row for row in evidence["estimate"]["rows"] if row["within"] is not None]
    checks = [
        {"id": "kaltstart", "label": "Kaltstart bis /api/health", "value": evidence.get("cold_start_s"),
         "threshold": None, "ok": None, "note": "informativ, keine Schwelle im Vertrag"},
        {"id": "ingestion", "label": "Ingestion der Demo-Maschine", "value": ingest_s,
         "threshold": f"< {thresholds.max_ingest_min:g} min",
         "ok": None if ingest_s is None else ingest_s / 60 < thresholds.max_ingest_min,
         "note": "" if ingest_s is not None else "nicht gemessen (Dokumente waren schon vorhanden; --load auf leerem System)"},
        {"id": "zonen", "label": "Baugruppen im Modell", "value": map_["zones"], "threshold": f">= {thresholds.min_zones}",
         "ok": map_["zones"] >= thresholds.min_zones, "note": ", ".join(map_["zone_codes"])},
        {"id": "teile", "label": "Teile mit Kennzeichen", "value": map_["parts"], "threshold": f">= {thresholds.min_parts}",
         "ok": map_["parts"] >= thresholds.min_parts,
         "note": ", ".join(f"{source} {count}" for source, count in sorted(map_["parts_by_source"].items()))
         + (f"; dazu {map_['connectors']} Leitungen als Verbinder" if map_.get("connectors") else "")},
        {"id": "fundstellen", "label": "Teile mit mindestens einer Fundstelle", "value": map_["cited_share"],
         "threshold": "100 %", "ok": map_["parts"] > 0 and not map_["parts_without_hit"],
         "note": "ohne Fundstelle: " + ", ".join(map_["parts_without_hit"]) if map_["parts_without_hit"] else ""},
        {"id": "hotspots", "label": "Gelabelte Schaltschrankteile", "value": evidence["hotspots"],
         "threshold": f">= {thresholds.min_hotspots}", "ok": evidence["hotspots"] >= thresholds.min_hotspots, "note": ""},
        {"id": "kostenbuch", "label": "Kostenbuch der Maschine", "value": ledger["total_cents"],
         "threshold": "Eintraege vorhanden", "ok": True if ledger["total_calls"] > 0 else None,
         "note": f"{ledger['total_calls']} Aufrufe" if ledger["total_calls"] else "kein Provider-Aufruf auf diesem System"},
        {"id": "schaetzung", "label": "Schaetzung gegen Kostenbuch", "value": len(estimate_rows),
         "threshold": f"Abweichung <= {thresholds.tolerance:.0%}",
         "ok": all(row["within"] for row in estimate_rows) if estimate_rows else None,
         "note": "; ".join(f"{r['purpose']} {r['actual_cents']:.2f} ct statt {r['estimated_cents']:.2f} ct" for r in estimate_rows)
         or "kein bezahlter Aufruf zum Vergleichen"},
    ]
    return checks


def failed(checks: list[dict]) -> list[str]:
    return [check["id"] for check in checks if check["ok"] is False]


def _fmt_value(check: dict) -> str:
    value = check["value"]
    if value is None:
        return "-"
    if check["id"] in ("kaltstart", "ingestion"):
        return f"{value:.0f} s" if value < 120 else f"{value / 60:.1f} min"
    if check["id"] == "zonen":
        return f"{value} Baugruppen"
    if check["id"] == "teile":
        return f"{value} Teile"
    if check["id"] == "fundstellen":
        return f"{value:.0%}"
    if check["id"] == "kostenbuch":
        return f"{value:.2f} ct"
    if check["id"] == "schaetzung":
        return f"{value} Zwecke verglichen"
    return str(value)


def render_markdown(evidence: dict, checks: list[dict]) -> str:
    state = {True: "ok", False: "FEHLT", None: "n/a"}
    machine = evidence["machine"]
    lines = [
        f"Abnahme-Nachweise {machine['name']} (`{machine['id']}`), {evidence.get('stamp', '')} gegen `{evidence.get('api', '')}`",
        "",
        "| Pruefung | Wert | Schwelle | Stand |",
        "| --- | --- | --- | --- |",
    ]
    for check in checks:
        note = f" ({check['note']})" if check["note"] else ""
        lines.append(f"| {check['label']} | {_fmt_value(check)}{note} | {check['threshold'] or '-'} | {state[check['ok']]} |")
    documents = evidence["documents"]
    lines += ["", f"Dokumente: {documents['ready']}/{documents['count']} fertig, {documents['pages']} PDF-Seiten; "
              f"Schaetzung fuer {evidence['estimate']['pages']} Seiten und {evidence['estimate']['photos']} Fotos."]
    return "\n".join(lines) + "\n"


def write_results(evidence: dict, checks: list[dict], out_dir: Path, stamp: str | None = None) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = stamp or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    json_path = out_dir / f"acceptance_{stamp}.json"
    md_path = out_dir / f"acceptance_{stamp}.md"
    json_path.write_text(json.dumps({"stamp": stamp, "evidence": evidence, "checks": checks}, indent=1, ensure_ascii=False),
                         encoding="utf-8")
    md_path.write_text(render_markdown(evidence, checks), encoding="utf-8")
    return [json_path, md_path]


def load_measured(client: httpx.Client, log: Callable[[str], None]) -> float | None:
    """Beispielanlage wie scripts/load_example.py laden (ohne Vision) und die Ingestion-Dauer messen."""
    sys.path.insert(0, str(HERE))
    import load_example  # noqa: PLC0415 - Skript aus demselben Ordner, nur mit --load noetig

    source = load_example.find_or_create_source(client)
    existing = {doc["filename"] for doc in client.get(f"/api/sources/{source['id']}/documents").json()}
    started = time.monotonic()
    ids = []
    for name, doc_type in load_example.FILES:
        if name in existing:
            log(f"schon geladen: {name}")
            continue
        doc = load_example.upload(client, source["id"], load_example.EXAMPLE_DIR / name, doc_type, False)
        log(f"hochgeladen: {name} -> {doc['id']}")
        ids.append(doc["id"])
    ingest_s = None
    if ids:
        if not load_example.wait_for(client, ids):
            raise SystemExit("Ingestion nicht abgeschlossen (Zeitueberschreitung)")
        ingest_s = time.monotonic() - started
        log(f"Ingestion fertig nach {ingest_s:.0f} s")
    load_example.setup_plant(client, source["id"])
    return ingest_s


def collect(
    client: httpx.Client,
    machine_name: str,
    load: bool,
    health_timeout_s: float,
    thresholds: Thresholds = Thresholds(),
    log: Callable[[str], None] = print,
) -> dict:
    """Alle Nachweise gegen ein laufendes Backend; nur GET, ausser mit --load."""
    cold_start_s = wait_healthy(client, health_timeout_s)
    log(f"Backend erreichbar nach {cold_start_s:.1f} s")
    ingest_s = load_measured(client, log) if load else None

    machines = client.get("/api/machines")
    machines.raise_for_status()
    machine = find_machine(machines.json(), machine_name)
    if machine is None:
        raise SystemExit(f"Maschine {machine_name!r} nicht gefunden; vorhanden: {[m.get('name') for m in machines.json()]}")
    machine_id = machine["id"]
    detail = client.get(f"/api/machines/{machine_id}")
    detail.raise_for_status()
    detail = detail.json()
    hotspots = sum(len(cabinet.get("hotspots", [])) for cabinet in detail.get("cabinets", []))
    photos = len(detail.get("cabinets", []))

    documents = []
    if detail.get("source_id"):
        response = client.get(f"/api/sources/{detail['source_id']}/documents")
        response.raise_for_status()
        documents = response.json()
    pages = sum(int(doc.get("page_count") or 0) for doc in documents)
    ready = sum(1 for doc in documents if (doc.get("status") or "").lower() == "ready")

    estimate = client.get("/api/machines/estimate", params={"pages": pages, "photos": photos, "vision": "true"})
    estimate.raise_for_status()
    map_json = client.get(f"/api/machines/{machine_id}/map")
    map_json.raise_for_status()

    def lookup(tag: str) -> dict:
        return client.get(f"/api/machines/{machine_id}/tags/{quote(tag, safe='')}").json()

    costs = client.get(f"/api/machines/{machine_id}/costs")
    costs.raise_for_status()
    costs = costs.json()
    total = costs.get("total") or {}
    month = costs.get("month") or {}
    return {
        "api": str(client.base_url),
        "stamp": datetime.now().isoformat(timespec="seconds"),
        "machine": {"id": machine_id, "name": machine.get("name", machine_name)},
        "cold_start_s": round(cold_start_s, 2),
        "ingest_s": None if ingest_s is None else round(ingest_s, 1),
        "documents": {"count": len(documents), "ready": ready, "pages": pages},
        "map": map_evidence(map_json.json(), lookup),
        "hotspots": hotspots,
        "ledger": {"total_cents": float(total.get("cents", 0.0)), "total_calls": int(total.get("calls", 0)),
                   "month_cents": float(month.get("cents", 0.0)), "month_calls": int(month.get("calls", 0)),
                   "by_purpose": total.get("by_purpose") or {}},
        "estimate": {"rows": compare_estimate(estimate.json(), costs, pages, photos, thresholds.tolerance),
                     "pages": pages, "photos": photos, "raw": estimate.json()},
        "thresholds": asdict(thresholds),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0], formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api", default="http://localhost:8010", help="Backend-URL")
    parser.add_argument("--machine", default=DEFAULT_MACHINE, help="Name der Demo-Maschine")
    parser.add_argument("--load", action="store_true", help="Beispielanlage laden und die Ingestion-Dauer messen (ohne Vision)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Ordner fuer acceptance_<zeitstempel>.json/.md")
    parser.add_argument("--strict", action="store_true", help="Exit 1, wenn eine Pruefung fehlschlaegt")
    parser.add_argument("--health-timeout", type=float, default=600, help="Sekunden, die /api/health Zeit hat (Kaltstart)")
    parser.add_argument("--min-zones", type=int, default=Thresholds.min_zones)
    parser.add_argument("--min-parts", type=int, default=Thresholds.min_parts)
    parser.add_argument("--max-ingest-min", type=float, default=Thresholds.max_ingest_min)
    parser.add_argument("--tolerance", type=float, default=Thresholds.tolerance, help="erlaubte Abweichung der Schaetzung")
    args = parser.parse_args()
    thresholds = Thresholds(args.min_zones, args.min_parts, args.max_ingest_min, args.tolerance)

    with httpx.Client(base_url=args.api, timeout=120, headers=auth_headers()) as client:
        try:
            evidence = collect(client, args.machine, args.load, args.health_timeout, thresholds)
        except (RuntimeError, httpx.HTTPError) as exc:
            sys.exit(f"Abbruch: {exc}")
    checks = evaluate(evidence, thresholds)
    print()
    print(render_markdown(evidence, checks))
    for path in write_results(evidence, checks, args.out):
        print(f"geschrieben: {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    missing = failed(checks)
    if missing:
        print(f"Nicht erfuellt: {', '.join(missing)}" + ("" if args.strict else " (ohne --strict kein Fehler)"))
        return 1 if args.strict else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
