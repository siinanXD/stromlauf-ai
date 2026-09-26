# MCP-Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lokaler MCP-Server mit 9 Lese-Werkzeugen über die Stromlauf-API.

**Architecture:** `backend/stromlauf_mcp/` (`client.py` HTTP + Fehler, `core.py` reine Auflösung/Kürzung, `server.py` `build_server(client)` + `main()`), Launcher `scripts/mcp_server.py`, Backend-Endpunkt `GET /api/search`.

**Tech Stack:** mcp 2.2 (MCPServer), httpx, FastAPI, pytest.

**Spec:** `docs/superpowers/specs/2026-09-26-mcp-server-design.md`

## Global Constraints

- Nur lesen; jedes Werkzeug `ToolAnnotations(read_only_hint=True)`. Kein LLM-Aufruf.
- `stromlauf_mcp` importiert nichts aus `app`.
- Fehler als `ToolError` mit deutscher Meldung; nie Stacktraces an den Client.

## Review Focus

1. Backend läuft nicht: klare Meldung mit Startbefehl statt Timeout/Stacktrace.
2. Mehrdeutiger Maschinenname („Palettierer“ gibt es 6×): Kandidatenliste, keine Zufallswahl.
3. Maschine ohne Wissensquelle bei `signal_path`/`find_references`: verständlicher Hinweis.
4. Kalkulation mit unbekanntem Artikel oder Menge 0: Backend-400 wird als Klartext weitergegeben.
5. Große Ausgaben (Kalkulation, Suche): gekürzt, damit das Kontextfenster des Clients nicht platzt.

---

### Task 1: Suche als API
- [ ] `backend/app/api/search.py`: `GET /api/search` (q, mode, source_id, k) → `{text, refs}` über die Agent-Werkzeuge (`.func` mit `config={"configurable": {"source_ids": [...]}}`), 400 bei leerer Anfrage/unbekanntem Modus. Registrieren in `main.py`.
- [ ] Backend neu starten, `curl` für alle drei Modi. Commit `feat(api): Dokumentensuche als Endpunkt`.

### Task 2: MCP-Paket
- [ ] Failing tests `backend/tests/test_mcp_server.py` (MockTransport): 9 Werkzeugnamen, alle read-only; `resolve` exakt/Anfang/mehrdeutig; `signal_path` fragt mit `source_id` der Maschine; `calculate_order` löst Code auf, Ergebnis ohne `closed`, Stationen gekürzt; `search_documents(machine=…)` begrenzt auf Quelle; Verbindungsfehler → ToolError mit „nicht erreichbar“.
- [ ] Implementieren (`client.py`, `core.py`, `server.py`, `__init__.py`, `__main__.py`), Launcher `scripts/mcp_server.py`, Abhängigkeit `mcp>=2.2,<3` in `pyproject.toml`.
- [ ] GREEN, ruff. Commit `feat(mcp): MCP-Server mit Lese-Werkzeugen`.

### Task 3: Live-Prüfung, Doku, PR
- [ ] Live: SDK-Client über stdio gegen lokales Backend (Werkzeuge listen, `site_overview`, `calculate_order`, `signal_path`).
- [ ] README-Abschnitt „MCP-Server“ (Claude Code: `claude mcp add`, Claude Desktop: Konfig-Schnipsel, Werkzeugliste), AGENTS.md, Recherche-Notiz ergänzen.
- [ ] Suiten, Review, PR gegen master (Hinweis: erst #12 mergen).
