"""MCP-Server fuer Stromlauf AI: Werk, Doku und Signalweg als Lese-Werkzeuge.

Start (stdio):  backend/.venv/Scripts/python scripts/mcp_server.py
Umgebung:       STROMLAUF_API (Standard http://127.0.0.1:8010), STROMLAUF_APP (http://localhost:3100)
"""

import argparse
import logging
import os
from urllib.parse import quote

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp_types import ToolAnnotations

from stromlauf_mcp.client import StromlaufClient
from stromlauf_mcp.core import resolve, truncate

INSTRUCTIONS = """Stromlauf AI: Wissen über industrielle Elektrodokumentation (Stromlaufpläne, Stücklisten,
Klemmenpläne, Siemens STEP 7 AWL, Handbücher) und die Maschinen eines Werks (Halle, Linie, Kennzahlen).
Alle Werkzeuge lesen nur und rechnen deterministisch (keine Schätzung durch ein Sprachmodell).

Werkzeugwahl:
- Eine Maschine (Kennzahlen, Fehlerliste, Doku): machine_details mit Name, Kürzel oder ID.
- Betriebsmittel (-K1), Klemmen (-X1:5), SPS-Adressen (E0.0): erst search_tags (welche Maschine),
  dann find_references (Fundstellen) oder signal_path (wovon hängt es ab, was schaltet es).
- Funktionsfragen zur Doku („Was passiert bei Not-Halt?“): search_documents.
Nenne in Antworten die Fundstelle (Dokument, Seite/Blatt) und gib den Link `url` weiter, wenn vorhanden."""

TOOL_NAMES = ["machine_details", "search_tags", "find_references", "search_documents", "signal_path"]
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)


def build_server(client: StromlaufClient, app_url: str) -> MCPServer:
    server = MCPServer(
        "stromlauf", title="Stromlauf AI", version="0.1.0", instructions=INSTRUCTIONS,
        description="Werk, Elektrodoku und Signalweg (nur lesen)",
    )

    def machine_url(machine_id: str) -> str:
        return f"{app_url}/werk/maschine/{machine_id}"

    def find_machine(ref: str) -> dict:
        machines = [{**m, "hall": m.get("hall_name", "")} for m in client.get("/api/machines")]
        return resolve(machines, ref, "Maschine")

    def source_of(ref: str) -> tuple[dict, str]:
        machine = client.get(f"/api/machines/{find_machine(ref)['id']}")
        if not machine.get("source_id"):
            raise ToolError(
                f"Maschine „{machine['name']}“ hat keine Dokumentation (Wissensquelle). "
                f"Im Werk zuordnen: {machine_url(machine['id'])}"
            )
        return machine, machine["source_id"]

    @server.tool(annotations=READ_ONLY)
    def machine_details(machine: str) -> dict:
        """Eine Maschine: Kennzahlen mit Quelle, Fehlerliste (Code, Symptom, Ursache, Behebung, BMK, Verweis)
        und die verknüpfte Dokumentation.

        Args:
            machine: Maschinenname, Kürzel oder ID, z. B. "L1-UR" oder "FB-01"
        """
        found = find_machine(machine)
        detail = client.get(f"/api/machines/{found['id']}")
        specs = client.get(f"/api/machines/{found['id']}/specs")
        return {
            "name": detail["name"], "hall": detail["hall_name"], "type": detail["machine_type"], "line": detail["line"],
            "documentation": detail["source_name"], "documents": detail["document_count"],
            "specs": [{k: s[k] for k in ("label", "value", "unit", "source")} for s in specs],
            "faults": [{k: f[k] for k in ("code", "symptom", "cause", "fix", "tags", "doc_ref")} for f in detail["faults"]],
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

    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="MCP-Server für Stromlauf AI")
    parser.add_argument("--http", action="store_true", help="Streamable HTTP statt stdio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    logging.getLogger("httpx").setLevel(logging.WARNING)  # keine Zeile je Anfrage im Client-Log
    client = StromlaufClient(
        os.environ.get("STROMLAUF_API", "http://127.0.0.1:8010"),
        api_key=os.environ.get("STROMLAUF_API_KEY") or None,
    )
    server = build_server(client, os.environ.get("STROMLAUF_APP", "http://localhost:3100").rstrip("/"))
    if args.http:
        server.run("streamable-http", host="127.0.0.1", port=args.port)
    else:
        server.run("stdio")
