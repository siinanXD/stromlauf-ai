"""`meta`-Event am Ende eines Chat-Streams: referenzierte Bauteile, Zitate, Belege - deterministisch,
ohne weiteren Modellaufruf (docs/product/ux-spec.md §3.2, Issue #27).

- referenced_tags: Betriebsmittel aus dem Antworttext, die im Kennzeichen-Index der Quelle vorkommen
- citations: die Fundstellen der Werkzeugaufrufe (dedupliziert)
- evidence: Seiten der Zitate (fuer Belegbilder) und Hotspots in Schaltschrankfotos der Maschine
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.tags import extract_tags
from app.models import Machine, TagOccurrence, TagType

MAX_TAGS = 12
MAX_PAGE_EVIDENCE = 4
MAX_HOTSPOT_EVIDENCE = 6


def tags_in_answer(text: str, known: set[str]) -> list[str]:
    """Betriebsmittel im Antworttext, Reihenfolge des ersten Vorkommens, nur bekannte Kennzeichen."""
    seen: list[str] = []
    for tag in extract_tags(text):
        if tag.tag_type == TagType.DEVICE and tag.tag in known and tag.tag not in seen:
            seen.append(tag.tag)
    return seen[:MAX_TAGS]


def page_evidence(citations: list[dict]) -> list[dict]:
    """Seitenbelege aus den Fundstellen (nur PDF-Seiten, erste je Dokument+Seite)."""
    out: list[dict] = []
    for ref in citations:
        page = ref.get("page")
        if not page or not str(ref.get("filename", "")).lower().endswith(".pdf"):
            continue
        out.append(
            {
                "kind": "page",
                "document_id": ref["document_id"],
                "filename": ref.get("filename", ""),
                "doc_type": ref.get("doc_type", ""),
                "page": page,
                "label": f"{ref.get('filename', '')} S. {page}",
            }
        )
        if len(out) >= MAX_PAGE_EVIDENCE:
            break
    return out


def hotspot_evidence(machine: Machine | None, tags: list[str]) -> list[dict]:
    if machine is None or not tags:
        return []
    wanted = {t.upper() for t in tags}
    out: list[dict] = []
    for cabinet in machine.cabinets:
        for hotspot in cabinet.hotspots:
            if hotspot.tag and hotspot.tag.upper() in wanted:
                out.append(
                    {
                        "kind": "cabinet",
                        "cabinet_id": cabinet.id,
                        "cabinet_title": cabinet.title,
                        "hotspot_id": hotspot.id,
                        "tag": hotspot.tag,
                        "label": hotspot.label,
                        "box": {"x": hotspot.x, "y": hotspot.y, "w": hotspot.w, "h": hotspot.h},
                        "confirmed": hotspot.confirmed,
                    }
                )
                if len(out) >= MAX_HOTSPOT_EVIDENCE:
                    return out
    return out


def build_meta(session: Session, *, answer: str, citations: list[dict], source_ids: list[str], machine_id: str | None) -> dict:
    known: set[str] = set()
    if source_ids:
        known = set(
            session.scalars(
                select(TagOccurrence.tag).where(TagOccurrence.source_id.in_(source_ids), TagOccurrence.tag_type == TagType.DEVICE).distinct()
            )
        )
    tags = tags_in_answer(answer, known)
    machine = session.get(Machine, machine_id) if machine_id else None
    return {
        "referenced_tags": tags,
        "citations": citations,
        "evidence": [*hotspot_evidence(machine, tags), *page_evidence(citations)],
    }
