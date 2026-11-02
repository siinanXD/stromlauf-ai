"""Volltextsuche findet Umlaut und ae/oe/ue-Schreibweise gleichermassen (SIN-1463)."""

import os

import pytest
from sqlalchemy import func, select
from sqlalchemy.dialects import postgresql

from app.retrieval import TEXT_SEARCH_CONFIG, fulltext_query, query_variants


def test_variants_enthalten_die_eigene_und_beide_schreibweisen():
    assert query_variants("Foerderband Schuetz") == ["Foerderband Schuetz", "förderband schütz"]
    assert query_variants("Förderband") == ["Förderband", "foerderband"]


def test_variants_ohne_woerter_bleiben_die_anfrage():
    assert query_variants("-K1") == ["-K1"]
    assert query_variants("E0.2") == ["E0.2"]


def test_tsquery_verknuepft_die_varianten_mit_oder():
    sql = str(fulltext_query("Foerderband").compile(dialect=postgresql.dialect()))
    assert sql.count("websearch_to_tsquery(") == 2
    assert "||" in sql


@pytest.mark.skipif(
    not os.environ.get("STROMLAUF_DB_TESTS"), reason="braucht Postgres (STROMLAUF_DB_TESTS=1)"
)
@pytest.mark.parametrize(
    ("document", "query"),
    [
        ("Förderband mit Schütz und Öffner", "Foerderband Schuetz"),
        ("Foerderband mit Schuetz und Oeffner", "Förderband Schütz"),
        ("Förderband mit Schütz und Öffner", "Förderband Schütz Öffner"),
        ("Foerderband mit Schuetz", "Foerderband Schuetz"),
    ],
)
def test_postgres_findet_beide_schreibweisen(document, query):
    from app.db import session_scope

    with session_scope() as session:
        vector = func.to_tsvector(TEXT_SEARCH_CONFIG, document)
        assert session.scalar(select(vector.op("@@")(fulltext_query(query))))
