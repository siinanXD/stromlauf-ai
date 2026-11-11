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


# --- Fusion waehlbar (SIN-1232): vector | fulltext | hybrid, ohne Datenbank ---


class _Session:
    """Liefert je Rangliste feste IDs; welche gefragt ist, zeigt der SQL-Operator."""

    def scalars(self, statement):
        return ["v1", "beide"] if "<=>" in str(_compile(statement)) else ["beide", "t1"]


def _ids(**kwargs) -> list[str]:
    from app.retrieval import hybrid_chunk_ids

    return hybrid_chunk_ids(_Session(), "Motorschutz", [0.0] * 3, [], None, 8, **kwargs)


def test_fusion_hybrid_ist_standard_und_verschmilzt_beide_ranglisten():
    assert _ids() == _ids(fusion="hybrid") == ["beide", "v1", "t1"]


def test_fusion_vector_nutzt_nur_den_vektorzweig():
    assert _ids(fusion="vector") == ["v1", "beide"]


def test_fusion_fulltext_nutzt_nur_den_volltextzweig():
    assert _ids(fusion="fulltext") == ["beide", "t1"]


def test_unbekannte_fusion_ist_ein_fehler():
    import pytest

    with pytest.raises(ValueError):
        _ids(fusion="quatsch")


def test_api_search_reicht_fusion_durch_und_lehnt_unbekannte_ab(monkeypatch):
    import pytest
    from fastapi import HTTPException

    from app.api import search as api

    seen = {}

    def fake(query, config, k):
        seen.update(config["configurable"])
        return "Treffer", []

    monkeypatch.setattr(api, "search_knowledge", type("Tool", (), {"func": staticmethod(fake)}))
    api.search(q="Motorschutz")
    assert seen["fusion"] == "hybrid"
    api.search(q="Motorschutz", fusion="fulltext", source_id="s1")
    assert seen == {"source_ids": ["s1"], "fusion": "fulltext"}
    with pytest.raises(HTTPException) as error:
        api.search(q="Motorschutz", fusion="quatsch")
    assert error.value.status_code == 400


def test_search_knowledge_liest_fusion_aus_der_konfiguration(monkeypatch):
    from contextlib import contextmanager

    from app.agent import tools

    seen = []

    @contextmanager
    def no_session():
        yield None

    monkeypatch.setattr(tools.embeddings, "embed_query", lambda query: [0.0] * 3)
    monkeypatch.setattr(tools, "session_scope", no_session)
    monkeypatch.setattr(tools, "hybrid_chunk_ids", lambda *args, **kwargs: seen.append(kwargs) or [])
    tools.search_knowledge.func(query="x", config={"configurable": {"source_ids": []}})
    tools.search_knowledge.func(query="x", config={"configurable": {"source_ids": [], "fusion": "vector"}})
    assert seen == [{"fusion": "hybrid"}, {"fusion": "vector"}]
    # das Modell darf die Fusion nicht waehlen: kein Argument im Werkzeugschema
    assert "fusion" not in tools.search_knowledge.args
