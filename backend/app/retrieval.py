"""Hybride Dokumentensuche: Vektoraehnlichkeit + Postgres-Volltext, verschmolzen per RRF.

Die Vektorsuche findet Umschreibungen ("Pumpe laeuft nicht an" ~ "Motorschutz ausgeloest"),
der Volltext exakte Fachbegriffe und Typbezeichnungen, die das Embedding verwaescht. Reciprocal
Rank Fusion (Cormack et al. 2009) braucht keine Gewichte und keine vergleichbaren Scores:
score(id) = sum(1 / (K + rang)) ueber alle Ranglisten, in denen id vorkommt.
"""

from collections.abc import Iterable, Sequence

from sqlalchemy import ColumnElement, Select, func, select

from app.ingestion.tags import text_search_terms
from app.models import Chunk, Document

TEXT_SEARCH_CONFIG = "german"
RRF_K = 60


def rrf_merge(rankings: Sequence[Sequence[str]], k: int = RRF_K) -> list[str]:
    """IDs nach RRF-Score absteigend; bei Gleichstand gewinnt das frueher gesehene."""
    scores: dict[str, float] = {}
    order: dict[str, int] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
            order.setdefault(item, len(order))
    return sorted(scores, key=lambda item: (-scores[item], order[item]))


def _base(source_ids: Iterable[str], doc_types: Iterable[str] | None) -> Select:
    statement = select(Chunk.id).join(Document, Chunk.document_id == Document.id)
    source_ids = list(source_ids)
    if source_ids:
        statement = statement.where(Chunk.source_id.in_(source_ids))
    if doc_types:
        statement = statement.where(Document.doc_type.in_(list(doc_types)))
    return statement


def vector_statement(
    vector: Sequence[float], source_ids: Iterable[str], doc_types: Iterable[str] | None, limit: int
) -> Select:
    return (
        _base(source_ids, doc_types).order_by(Chunk.embedding.cosine_distance(vector)).limit(limit)
    )


def query_variants(query: str) -> list[str]:
    """Die Anfrage so, wie sie kam, plus Umlaut- und ae/oe/ue-Schreibweise (soweit sie sich unterscheiden).

    Der deutsche Stemmer macht aus "Foerderband" `foerderband`, aus "Förderband" aber `forderband`: ohne beide
    Schreibweisen findet die Suche nur Dokumente, die so geschrieben sind wie die Frage."""
    own = " ".join(query.lower().split())
    return [query, *(term for term in text_search_terms(query) if term != own)]


def fulltext_query(query: str) -> ColumnElement:
    """tsquery aus allen Schreibweisen der Anfrage, ODER-verknuepft."""
    queries = [
        func.websearch_to_tsquery(TEXT_SEARCH_CONFIG, variant) for variant in query_variants(query)
    ]
    combined = queries[0]
    for other in queries[1:]:
        combined = combined.op("||")(other)
    return combined


def fulltext_statement(
    query: str, source_ids: Iterable[str], doc_types: Iterable[str] | None, limit: int
) -> Select:
    """websearch_to_tsquery vertraegt beliebige Eingaben (Anfuehrungszeichen, OR, -wort)."""
    tsquery = fulltext_query(query)
    return (
        _base(source_ids, doc_types)
        .where(Chunk.tsv.op("@@")(tsquery))
        .order_by(func.ts_rank_cd(Chunk.tsv, tsquery).desc(), Chunk.id)
        .limit(limit)
    )


def hybrid_chunk_ids(
    session,
    query: str,
    vector: Sequence[float],
    source_ids: Iterable[str],
    doc_types: Iterable[str] | None,
    limit: int,
) -> list[str]:
    """Die besten `limit` Chunk-IDs aus beiden Ranglisten (je 3*limit Kandidaten)."""
    pool = limit * 3
    source_ids = list(source_ids)
    by_vector = list(session.scalars(vector_statement(vector, source_ids, doc_types, pool)))
    by_text = list(session.scalars(fulltext_statement(query, source_ids, doc_types, pool)))
    return rrf_merge([by_vector, by_text])[:limit]
