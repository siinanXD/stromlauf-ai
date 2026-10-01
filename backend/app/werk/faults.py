"""Treffer in Fehlerlisten zu einer Meldung, ohne Modell.

Dieselbe Trefferlogik fuer das Agenten-Werkzeug search_faults und GET /api/machines/{id}/fault-hits.
"""

from app.ingestion.tags import normalize_tag


def fault_matches(fault: dict, query: str) -> bool:
    """Woertlich in Code, Symptom, Ursache, Behebung oder als Kennzeichen in tags (Schreibweise egal)."""
    needle = query.strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        str(fault.get(k, "")) for k in ("code", "symptom", "cause", "fix", "doc_ref")
    ).lower()
    if needle in haystack:
        return True
    normalized = normalize_tag(query)
    return any(normalize_tag(str(t)) == normalized for t in fault.get("tags") or [])
