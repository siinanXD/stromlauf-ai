# MCP-Server für Stromlauf AI

Stand: 2026-09-26 · Auftrag: „1, mach den MCP-Server“ (Werkzeuge von Stromlauf für Claude Desktop /
Claude Code, ohne API-Guthaben: das Sprachmodell läuft über das Abo des Nutzers).

## Ziel

Ein lokaler MCP-Server macht die deterministischen Funktionen von Stromlauf für jeden MCP-Client
nutzbar: Werk, Maschinen, Kennzeichen, Dokumentensuche, Signalweg, Vorkalkulation. Nur lesen, keine
Schreibzugriffe, kein LLM-Aufruf auf unserer Seite.

## Architektur

- Paket `backend/stromlauf_mcp/` (nur `httpx` + `mcp`, importiert nichts aus `app`: schneller Start,
  keine DB-Verbindung). Spricht die laufende Stromlauf-API an (`STROMLAUF_API`, Standard
  `http://localhost:8010`); Links in die Oberfläche über `STROMLAUF_APP` (Standard `http://localhost:3100`).
- Transport stdio (Claude Desktop, Claude Code); `--http` startet Streamable HTTP auf 127.0.0.1:8765.
- Start: `backend/.venv/Scripts/python scripts/mcp_server.py` (Launcher setzt den Pfad).
- Abhängigkeit: offizielles SDK `mcp` 2.2 (MIT, 2026-09-07, `MCPServer` aus `mcp.server.mcpserver`).
- Neuer Backend-Endpunkt `GET /api/search?q=&mode=semantic|keyword|tag&source_id=&k=` nutzt die
  vorhandenen Agent-Werkzeuge (`search_knowledge`, `keyword_search`, `find_tag`); Embeddings lokal.

## Werkzeuge (alle `read_only_hint`)

| Name | Zweck |
|---|---|
| `site_overview` | Hallen mit Art, Maschinenzahl, Linien, laufenden Fehlersuchen, Fluss zwischen Hallen |
| `hall_details(hall)` | Maschinen einer Halle mit Linie, Typ, erster Kennzahl, Doku-/Fehlerzahl |
| `machine_details(machine)` | Kennzahlen, Fehlerliste, letzte Fehlersuchen, Wissensquelle |
| `search_tags(query)` | Wo kommt ein BMK/eine Klemme/Adresse vor (je Maschine) |
| `find_references(tag, machine?)` | Alle Fundstellen eines Kennzeichens (Plan, Stückliste, Klemmenplan, AWL) |
| `search_documents(query, machine?, exact?)` | Semantische oder wörtliche Suche in der Doku |
| `signal_path(tag, machine)` | Signalweg (Quellen und Folgen) aus Klemmenplan, Stückliste, AWL |
| `list_articles` | Artikel mit Linie, Einheit, Paletten, Engpassleistung |
| `calculate_order(positions, received_at?, due_date?)` | Vorkalkulation: Termin, Stationen, Material, Kosten |

Maschinen, Hallen und Artikel werden per Name, Code oder ID gefunden (Groß-/Kleinschreibung egal,
eindeutiger Anfang reicht, z. B. „L1-UR“); mehrdeutig → Fehler mit Kandidaten. Ausgaben sind kompakt
(ohne Schraffur-Zeiträume o. ä.) und enthalten `url` in die Oberfläche. Backend nicht erreichbar →
Fehlermeldung mit Startbefehl.

## Tests

pytest ohne Netz (httpx MockTransport): Werkzeugliste und Annotationen, Namensauflösung inkl.
Mehrdeutigkeit, Signalweg nutzt die Quelle der Maschine, Kalkulation löst Artikelcodes auf und kürzt,
Suche auf Quelle der Maschine begrenzt, Backend aus → Hinweis. Live: stdio-Client gegen lokales Backend.
