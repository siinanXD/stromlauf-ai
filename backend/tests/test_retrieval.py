"""Hybrid-Suche: RRF-Fusion und die SQL-Form beider Ranglisten (ohne Datenbank)."""

from sqlalchemy.dialects import postgresql

from app.retrieval import fulltext_statement, rrf_merge, vector_statement


def test_rrf_prefers_items_on_both_lists():
    assert rrf_merge([["a", "b", "c"], ["c", "d"]]) == ["c", "a", "b", "d"]


def test_rrf_single_list_keeps_order_and_empty_list_is_ignored():
    assert rrf_merge([["x", "y"], []]) == ["x", "y"]
    assert rrf_merge([[], []]) == []


def test_rrf_tie_goes_to_first_seen():
    # a: Rang 1 in Liste 1, b: Rang 1 in Liste 2 -> gleicher Score, a zuerst gesehen
    assert rrf_merge([["a"], ["b"]]) == ["a", "b"]


def _compile(statement):
    return statement.compile(dialect=postgresql.dialect())


def test_fulltext_statement_uses_german_websearch_and_rank():
    compiled = _compile(fulltext_statement("Motorschutz ausgelöst", ["s1"], ["manual"], 24))
    sql = str(compiled)
    assert "websearch_to_tsquery(" in sql
    assert "chunks.tsv @@" in sql
    assert "ts_rank_cd(chunks.tsv" in sql
    assert "chunks.source_id IN" in sql
    assert "documents.doc_type IN" in sql
    params = compiled.params
    assert params["websearch_to_tsquery_1"] == "german"
    assert params["websearch_to_tsquery_2"] == "Motorschutz ausgelöst"
    assert params["source_id_1"] == ["s1"]
    assert params["doc_type_1"] == ["manual"]
    assert params["param_1"] == 24


def test_vector_statement_without_filters_has_no_where():
    compiled = _compile(vector_statement([0.0] * 3, [], None, 5))
    sql = str(compiled)
    assert "WHERE" not in sql
    assert "<=>" in sql
    assert 5 in compiled.params.values()
