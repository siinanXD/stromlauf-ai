"""Dokumentensuche als HTTP-Endpunkt (fuer den MCP-Server): dieselben Werkzeuge wie der Chat-Agent."""

from fastapi import APIRouter, HTTPException

from app.agent.tools import find_tag, keyword_search, search_knowledge
from app.retrieval import FUSIONS

router = APIRouter(prefix="/api", tags=["search"])

MODES = {"semantic", "keyword", "tag"}
MAX_QUERY = 200


@router.get("/search")
def search(
    q: str = "", mode: str = "semantic", source_id: str | None = None, k: int = 8, fusion: str = "hybrid"
) -> dict:
    """Hybrid (Embeddings + Volltext, lokal), woertlich oder exakt nach Kennzeichen; optional je Wissensquelle.
    fusion=vector|fulltext laesst mode=semantic nur eine der beiden Ranglisten nutzen (Messung, SIN-1232)."""
    if not q.strip():
        raise HTTPException(400, "Suchbegriff fehlt")
    if len(q) > MAX_QUERY:
        raise HTTPException(400, f"Suchbegriff zu lang (höchstens {MAX_QUERY} Zeichen)")
    if mode not in MODES:
        raise HTTPException(400, f"mode muss eins sein von {sorted(MODES)}")
    if fusion not in FUSIONS:
        raise HTTPException(400, f"fusion muss eins sein von {sorted(FUSIONS)}")
    config = {"configurable": {"source_ids": [source_id] if source_id else [], "fusion": fusion}}
    if mode == "semantic":
        text, refs = search_knowledge.func(query=q.strip(), config=config, k=max(1, min(k, 20)))
    elif mode == "keyword":
        text, refs = keyword_search.func(text=q.strip(), config=config)
    else:
        text, refs = find_tag.func(tag=q.strip(), config=config)
    return {"mode": mode, "text": text, "refs": refs}
