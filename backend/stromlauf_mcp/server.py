"""MCP-Server fuer Stromlauf AI: Werk, Doku, Signalweg und Vorkalkulation als Lese-Werkzeuge.

Start (stdio):  backend/.venv/Scripts/python scripts/mcp_server.py
Umgebung:       STROMLAUF_API (Standard http://127.0.0.1:8010), STROMLAUF_APP (http://localhost:3100)
"""

import argparse
import logging
import os
from typing import Literal
from urllib.parse import quote

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations
from pydantic import BaseModel, Field

from stromlauf_mcp.client import StromlaufClient
from stromlauf_mcp.core import KIND_LABELS, compact_calc, machines_of, resolve, truncate

INSTRUCTIONS = """Stromlauf AI: Wissen über industrielle Elektrodokumentation (Stromlaufpläne, Stücklisten,
Klemmenpläne, Siemens STEP 7 AWL, Handbücher) und ein Werk mit Hallen, Linien und Maschinen.
Alle Werkzeuge lesen nur und rechnen deterministisch (keine Schätzung durch ein Sprachmodell).

Werkzeugwahl:
- Überblick über das Werk: site_overview, dann hall_details / machine_details.
- Betriebsmittel (-K1), Klemmen (-X1:5), SPS-Adressen (E0.0): erst search_tags (welche Maschine),
  dann find_references (Fundstellen) oder signal_path (wovon hängt es ab, was schaltet es).
- Funktionsfragen zur Doku („Was passiert bei Not-Halt?“): search_documents.
- Lieferzeit, Material, Kosten eines Auftrags: list_articles, dann calculate_order.
Nenne in Antworten die Fundstelle (Dokument, Seite/Blatt) und gib den Link `url` weiter, wenn vorhanden.
Kosten sind Richtwerte; sag das dazu."""

TOOL_NAMES = [
    "site_overview", "hall_details", "machine_details", "search_tags", "find_references",
    "search_documents", "signal_path", "list_articles", "calculate_order",
]
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


class OrderPosition(BaseModel):
    article: str = Field(description="Artikelcode oder Name, z. B. 'TP-3L-8x150'")
    quantity: float = Field(description="Menge, größer 0")
    unit: Literal["unit", "pallet"] = Field(default="unit", description="'unit' = Verkaufseinheiten (Pakete, Boxen), 'pallet' = Paletten")


def build_server(client: StromlaufClient, app_url: str) -> MCPServer:
    server = MCPServer(
        "stromlauf", title="Stromlauf AI", version="0.1.0", instructions=INSTRUCTIONS,
        description="Werk, Elektrodoku, Signalweg und Vorkalkulation (nur lesen)",
    )

    def machine_url(machine_id: str) -> str:
        return f"{app_url}/werk/maschine/{machine_id}"

    def find_machine(ref: str) -> dict:
        return resolve(machines_of(client.get("/api/site")), ref, "Maschine")

    def source_of(ref: str) -> tuple[dict, str]:
        machine = client.get(f"/api/machines/{find_machine(ref)['id']}")
        if not machine.get("source_id"):
            raise ToolError(
                f"Maschine „{machine['name']}“ hat keine Dokumentation (Wissensquelle). "
                f"Im Werk zuordnen: {machine_url(machine['id'])}"
            )
        return machine, machine["source_id"]

    @server.tool(annotations=READ_ONLY)
    def site_overview() -> dict:
        """Überblick über das Werk: Hallen mit Art, Maschinenzahl, Linien, laufenden Fehlersuchen und Toren,
        dazu der Materialfluss zwischen den Hallen."""
        site = client.get("/api/site")
        names = {hall["id"]: hall["name"] for hall in site["halls"]}
        return {
            "halls": [
                {
                    "name": hall["name"], "kind": KIND_LABELS.get(hall["kind"], hall["kind"]),
                    "machines": hall["machine_count"], "lines": hall["lines"],
                    "open_diagnoses": hall["open_diagnoses"], "docks": hall["docks"],
                    "url": f"{app_url}/werk/halle/{hall['id']}",
                }
                for hall in site["halls"]
            ],
            "flows": [
                {"from": names.get(f["from_hall_id"]), "to": names.get(f["to_hall_id"]), "label": f["label"]}
                for f in site["flows"]
            ],
            "url": f"{app_url}/werk",
        }

    @server.tool(annotations=READ_ONLY)
    def hall_details(hall: str) -> dict:
        """Maschinen einer Halle mit Linie, Typ, wichtigster Kennzahl, Zahl der Dokumente und Fehlereinträge.

        Args:
            hall: Hallenname oder ID, z. B. "Verarbeitung"
        """
        found = resolve(client.get("/api/site")["halls"], hall, "Halle")
        detail = client.get(f"/api/halls/{found['id']}")
        return {
            "name": detail["name"], "kind": KIND_LABELS.get(detail["kind"], detail["kind"]),
            "description": detail["description"],
            "machines": [
                {
                    "name": m["name"], "type": m["machine_type"], "line": m["line"], "key_figure": m["key_figure"],
                    "documents": m["document_count"], "faults": m["fault_count"], "url": machine_url(m["id"]),
                }
                for m in detail["machines"]
            ],
            "url": f"{app_url}/werk/halle/{detail['id']}",
        }

    @server.tool(annotations=READ_ONLY)
    def machine_details(machine: str) -> dict:
        """Eine Maschine: Kennzahlen mit Quelle, Fehlerliste (Code, Symptom, Ursache, Behebung, BMK, Verweis),
        die letzten Fehlersuchen und die verknüpfte Dokumentation.

        Args:
            machine: Maschinenname, Kürzel oder ID, z. B. "L1-UR" oder "FB-01"
        """
        found = find_machine(machine)
        detail = client.get(f"/api/machines/{found['id']}")
        specs = client.get(f"/api/machines/{found['id']}/specs")
        diagnoses = client.get(f"/api/machines/{found['id']}/diagnoses")
        return {
            "name": detail["name"], "hall": detail["hall_name"], "type": detail["machine_type"], "line": detail["line"],
            "documentation": detail["source_name"], "documents": detail["document_count"],
            "specs": [{k: s[k] for k in ("label", "value", "unit", "source")} for s in specs],
            "faults": [{k: f[k] for k in ("code", "symptom", "cause", "fix", "tags", "doc_ref")} for f in detail["faults"]],
            "recent_diagnoses": [
                {k: d.get(k) for k in ("title", "outcome", "finding", "started_at")} for d in diagnoses[:5]
            ],
            "url": machine_url(detail["id"]),
        }

    @server.tool(annotations=READ_ONLY)
    def search_tags(query: str) -> dict:
        """In welchen Maschinen kommt ein Kennzeichen vor? Betriebsmittel (-K1), Klemmen (-X3:1),
        SPS-Adressen (E0.0); Anfang genügt, Schreibweise egal.

        Args:
            query: Kennzeichen oder Anfang davon, z. B. "-K1" oder "E0."
        """
        hits = client.get("/api/tags/search", q=query)
        if not hits:
            return {"hits": [], "note": f"Keine Treffer für „{query}“. Schreibweise prüfen oder search_documents nutzen."}
        return {
            "hits": [
                {
                    "tag": h["tag"], "type": h["tag_type"], "occurrences": h["occurrences"],
                    "machines": [{"name": m["name"], "url": machine_url(m["id"])} for m in h["machines"]],
                }
                for h in hits[:30]
            ]
        }

    @server.tool(annotations=READ_ONLY)
    def find_references(tag: str, machine: str | None = None) -> dict:
        """Alle Fundstellen eines Kennzeichens in Stromlaufplan, Stückliste, Klemmenplan und AWL mit Dokument,
        Seite und Textumgebung.

        Args:
            tag: Kennzeichen, z. B. "-K1", "-X3:1", "E0.0"
            machine: Optional die Maschine, auf deren Doku gesucht wird
        """
        source_id = source_of(machine)[1] if machine else None
        found = client.get("/api/search", q=tag, mode="tag", source_id=source_id)
        return {"text": truncate(found["text"]), "references": found["refs"][:40]}

    @server.tool(annotations=READ_ONLY)
    def search_documents(query: str, machine: str | None = None, exact: bool = False, k: int = 6) -> dict:
        """Suche in der Dokumentation: semantisch (Bedeutung, z. B. „Was passiert bei Not-Halt?“) oder mit
        exact=true wörtlich (Artikelnummern, Symbolnamen).

        Args:
            query: Frage oder Suchtext
            machine: Optional die Maschine, auf deren Doku gesucht wird
            exact: true = wörtliche Suche statt semantischer
            k: Anzahl Treffer bei semantischer Suche (1-20)
        """
        source_id = source_of(machine)[1] if machine else None
        found = client.get(
            "/api/search", q=query, mode="keyword" if exact else "semantic", source_id=source_id, k=max(1, min(k, 20))
        )
        return {"text": truncate(found["text"]), "references": found["refs"][:20]}

    @server.tool(annotations=READ_ONLY)
    def signal_path(tag: str, machine: str) -> dict:
        """Signalweg eines Kennzeichens aus Klemmenplan, Stückliste, Symboltabelle und AWL: wovon es abhängt
        (sources) und was es schaltet (consequences), mit Blattverweis und AWL-Netzwerk.

        Args:
            tag: Kennzeichen, z. B. "-S1", "E0.0", "-K1"
            machine: Maschine, deren Doku ausgewertet wird, z. B. "FB-01"
        """
        detail, source_id = source_of(machine)
        path = client.get("/api/signal-path", tag=tag, source_id=source_id)

        def node(n: dict) -> dict:
            item = {"id": n["id"], "kind": n["kind"], "label": n["label"], "ref": n["ref"], "level": n["level"]}
            if n.get("detail"):
                item["awl"] = truncate(n["detail"], 600)
            return item

        nodes = sorted(path["nodes"], key=lambda n: n["level"])
        return {
            "start": path["start"],
            "sources": [node(n) for n in nodes if n["level"] < 0],
            "consequences": [node(n) for n in nodes if n["level"] > 0],
            "edges": [f"{e['source']} -> {e['target']}" for e in path["edges"]],
            "schematic": path.get("schematic"),
            "url": f"{machine_url(detail['id'])}?tag={quote(tag, safe='')}&tab=signalweg",
        }

    @server.tool(annotations=READ_ONLY)
    def list_articles() -> list[dict]:
        """Verkaufsartikel für die Vorkalkulation: Code, Name, Linie, Einheit, Einheiten je Palette,
        Rohpapier je Einheit und Engpassleistung der Linie."""
        result = []
        for a in client.get("/api/articles"):
            rates = [
                s["rate"] * a["units_per_pallet"] / 60 if s["rate_unit"] == "pallet_h" else s["rate"] for s in a["routing"]
            ]
            result.append({
                "code": a["code"], "name": a["name"], "line": a["line"], "unit": a["unit_name"],
                "units_per_pallet": a["units_per_pallet"], "paper_kg_per_unit": round(a["paper_kg_per_unit"], 3),
                "bottleneck_units_per_min": round(min(rates), 2) if rates else None,
            })
        return result

    @server.tool(annotations=READ_ONLY)
    def calculate_order(positions: list[OrderPosition], received_at: str | None = None, due_date: str | None = None) -> dict:
        """Vorkalkulation eines Auftrags: frühester Verladetermin, ob der Wunschtermin hält, Zeitplan je Station
        (Büro, Papiermaschine, Linien, Verladung) mit Herleitung, Materialbedarf und Kosten (Richtwerte).
        Annahme: freie Kapazität, keine anderen Aufträge, Rohstoffe vorrätig.

        Args:
            positions: Positionen mit Artikel (Code oder Name), Menge und Einheit
            received_at: Auftragseingang "YYYY-MM-DDTHH:MM" (Ortszeit), Standard jetzt
            due_date: Wunschtermin "YYYY-MM-DD"
        """
        articles = client.get("/api/articles")
        body_positions = []
        for raw in positions:
            position = raw if isinstance(raw, OrderPosition) else OrderPosition.model_validate(raw)
            article = resolve(articles, position.article, "Artikel", keys=("code", "name"))
            body_positions.append({"article_id": article["id"], "quantity": position.quantity, "unit": position.unit})
        result = client.post(
            "/api/calc", {"received_at": received_at, "due_date": due_date, "positions": body_positions}
        )
        return compact_calc(result, app_url)

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MCP-Server für Stromlauf AI")
    parser.add_argument("--http", action="store_true", help="Streamable HTTP statt stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # keine Zeile je Anfrage im Client-Log
    client = StromlaufClient(os.environ.get("STROMLAUF_API", "http://127.0.0.1:8010"))
    server = build_server(client, os.environ.get("STROMLAUF_APP", "http://localhost:3100").rstrip("/"))
    if args.http:
        server.run("streamable-http", host="127.0.0.1", port=args.port)
    else:
        server.run("stdio")
