"""Startet den MCP-Server von Stromlauf AI (stdio; mit --http als Streamable HTTP auf Port 8765).

Aufruf:  backend/.venv/Scripts/python scripts/mcp_server.py [--http] [--port 8765]

Braucht das laufende Stromlauf-Backend (STROMLAUF_API, Standard http://localhost:8010).
Kein KI-Aufruf auf dieser Seite: das Sprachmodell ist der MCP-Client (Claude Desktop, Claude Code).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from stromlauf_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()
