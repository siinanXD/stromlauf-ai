"""Laedt das Testwerk Tissue in ein laufendes Stromlauf-AI-Backend.

Aufruf:  python scripts/load_testwerk.py [--api http://localhost:8010] [--refresh]

Legt 4 Hallen (Papiermaschine PM1, Verarbeitung, Lager & Versand, Buero) mit 30 Maschinen,
Linien, Kennzahlen und Materialfluss an, dazu die Stammdaten der Vorkalkulation (Artikel,
Materialien, Arbeitsplaene, Parameter; gleiche Codes werden ersetzt). Kein KI-Aufruf, keine Kosten. Die Beschreibung jeder
Halle beginnt mit "Testwerk Tissue:"; nur solche Hallen ersetzt --refresh (samt Maschinen).
Gibt es eine gleichnamige eigene Halle, bricht der Lader ab und fasst sie nicht an.
Standort-Fluesse zwischen anderen Hallen bleiben erhalten.
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import httpx
except ImportError:  # pragma: no cover
    sys.exit("httpx fehlt: cd backend && .venv/Scripts/pip install -e \".[dev]\"")

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "examples" / "testwerk" / "testwerk.json"


def call(client: httpx.Client, method: str, url: str, body=None):
    response = client.request(method, url, json=body)
    if response.is_error:
        sys.exit(f"{method} {url} -> {response.status_code}: {response.text}")
    return response.json() if response.content else None


def marked_description(werk: dict, hall: dict) -> str:
    """Beschreibung mit Kennung, damit --refresh nur eigene Hallen ersetzt."""
    return f"{werk['name']}: {hall['description']}"


def split_existing(existing: list[dict], werk: dict) -> tuple[list[dict], list[dict]]:
    """Vorhandene Hallen mit Testwerk-Namen: (vom Lader angelegt, fremd)."""
    names = {hall["name"] for hall in werk["halls"]}
    marker = f"{werk['name']}:"
    same_name = [h for h in existing if h["name"] in names]
    own = [h for h in same_name if h["description"].startswith(marker)]
    return own, [h for h in same_name if not h["description"].startswith(marker)]


def master_data_payload(werk: dict, machine_ids: dict[str, str]) -> dict:
    """Stammdaten der Vorkalkulation fuer PUT /api/master-data: Maschinen-Schluessel -> IDs."""
    materials = []
    for item in werk.get("materials", []):
        made = item.get("made_on") or {}
        materials.append({
            "code": item["code"], "name": item["name"], "unit": item["unit"], "price": item.get("price"),
            "price_source": item.get("price_source", ""),
            "made_on_machine_id": machine_ids[made["machine"]] if made else None,
            "made_rate_per_h": made.get("rate_per_h"), "made_basis": made.get("basis", ""),
            "bom": item["bom"],
        })
    articles = []
    for item in werk.get("articles", []):
        routing = [
            {**{k: v for k, v in step.items() if k != "machine"}, "machine_id": machine_ids[step["machine"]]}
            for step in item["routing"]
        ]
        base = {k: v for k, v in item.items() if k not in {"tech", "routing"}}
        articles.append({**base, **item["tech"], "routing": routing})
    return {"materials": materials, "articles": articles, "settings": werk.get("settings", {})}


def load(client: httpx.Client, werk: dict, refresh: bool) -> None:
    own, foreign = split_existing(call(client, "GET", "/api/site")["halls"], werk)
    if foreign:
        found = ", ".join(h["name"] for h in foreign)
        sys.exit(f"Eigene Halle(n) mit gleichem Namen: {found}. Umbenennen, dann erneut laden.")
    if own and not refresh:
        found = ", ".join(h["name"] for h in own)
        sys.exit(f"Testwerk ist schon da ({found}). --refresh loescht diese Hallen samt Maschinen und legt sie neu an.")
    for hall in own:
        call(client, "DELETE", f"/api/halls/{hall['id']}")
        print(f"ersetzt: {hall['name']}")

    # Nach dem Loeschen sind nur noch Fluesse zwischen fremden Hallen uebrig
    kept = [
        {key: flow[key] for key in ("from_hall_id", "to_hall_id", "label")}
        for flow in call(client, "GET", "/api/site")["flows"]
    ]
    hall_ids: dict[str, str] = {}
    all_machines: dict[str, str] = {}
    for hall in werk["halls"]:
        created = call(client, "POST", "/api/halls", {
            "name": hall["name"], "description": marked_description(werk, hall), "kind": hall["kind"],
        })
        site = hall["site"]
        call(client, "PATCH", f"/api/halls/{created['id']}", {
            "site_x": site["x"], "site_y": site["y"], "site_w": site["w"], "site_h": site["h"],
        })
        hall_ids[hall["name"]] = created["id"]
        machine_ids: dict[str, str] = {}
        for machine in hall["machines"]:
            made = call(client, "POST", f"/api/halls/{created['id']}/machines", {
                "name": machine["name"],
                "machine_type": machine["machine_type"],
                "description": machine["description"],
                "line": machine["line"],
                "pos_x": machine["x"],
                "pos_y": machine["y"],
            })
            call(client, "PUT", f"/api/machines/{made['id']}/specs", machine["specs"])
            machine_ids[machine["key"]] = made["id"]
            all_machines[machine["key"]] = made["id"]
        call(client, "PUT", f"/api/halls/{created['id']}/flows", [
            {"from_machine_id": machine_ids[a], "to_machine_id": machine_ids[b], "label": label}
            for a, b, label in hall["flows"]
        ])
        print(f"angelegt: {hall['name']} ({len(hall['machines'])} Maschinen)")

    new = [
        {"from_hall_id": hall_ids[a], "to_hall_id": hall_ids[b], "label": label}
        for a, b, label in werk["site_flows"]
    ]
    call(client, "PUT", "/api/site/flows", kept + new)
    master = call(client, "PUT", "/api/master-data", master_data_payload(werk, all_machines))
    total = sum(len(h["machines"]) for h in werk["halls"])
    print(f"Fertig: {len(werk['halls'])} Hallen, {total} Maschinen, {len(new)} Standort-Fluesse, "
          f"{master['articles']} Artikel, {master['materials']} Materialien.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", default="http://localhost:8010")
    parser.add_argument("--refresh", action="store_true", help="vorhandenes Testwerk ersetzen")
    args = parser.parse_args()
    werk = json.loads(DATA.read_text(encoding="utf-8"))
    with httpx.Client(base_url=args.api, timeout=60) as client:
        load(client, werk, args.refresh)


if __name__ == "__main__":
    main()
