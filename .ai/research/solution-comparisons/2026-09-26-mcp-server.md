# Recherche: MCP-Server fuer Stromlauf

Abgerufen 2026-09-26.

- **Offizielles Python-SDK `mcp`**: Version 2.2.0, MIT, veroeffentlicht 2026-09-07, Python >= 3.10
  (pypi.org/pypi/mcp/json). In 2.x heisst die High-Level-API `MCPServer` (`mcp.server.mcpserver`);
  `mcp.server.fastmcp` wirft absichtlich einen Import-Fehler mit Hinweis auf die Migration
  (im installierten Paket gelesen). Transporte: stdio, SSE, Streamable HTTP (Pfad `/mcp`).
- **Alternativen, nicht im Detail geprueft**: Wrapper, die FastAPI-Endpunkte automatisch als
  Werkzeuge veroeffentlichen, und eigene JSON-RPC-Implementierung. Ausgeschlossen, weil ein
  Automatik-Wrapper auch schreibende Endpunkte (Loeschen, Hochladen) freigeben wuerde und ein
  Eigenbau das Protokoll nachbauen muesste.

Entscheidung: offizielles SDK, eigene schmale Werkzeugschicht mit gezielt ausgewaehlten
Lese-Werkzeugen ueber die vorhandene HTTP-API. Rueckweg: Werkzeuge sind einfache Funktionen in
`backend/stromlauf_mcp/server.py`; ein SDK-Wechsel betrifft nur `build_server`.
