"""Voyage-Embeddings: Anfrageform, Reihenfolge, Dimension, Fehler - alles gegen einen Mock-Transport."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app import embeddings as emb


def _settings(**overrides):
    base = dict(
        embedding_provider="voyage",
        embedding_dim=4,
        voyage_api_key="vk-test",
        voyage_model="voyage-4",
        voyage_api_url="https://voyage.invalid/v1/embeddings",
        embedding_query_prefix="",
        embedding_passage_prefix="",
        embedding_cache_dir=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _transport(responder):
    return httpx.MockTransport(responder)


def test_dokumente_werden_in_reihenfolge_eingebettet(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.update(body)
        seen["auth"] = request.headers["authorization"]
        data = [{"index": i, "embedding": [float(i)] * 4} for i in reversed(range(len(body["input"])))]
        return httpx.Response(200, json={"data": data})

    vectors = emb.VoyageEmbeddings(transport=_transport(responder)).embed_documents(["a", "b", "c"])
    assert vectors == [[0.0] * 4, [1.0] * 4, [2.0] * 4]
    assert seen["model"] == "voyage-4"
    assert seen["input_type"] == "document"
    assert seen["output_dimension"] == 4
    assert seen["auth"] == "Bearer vk-test"


def test_query_nutzt_input_type_query(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())

    def responder(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content)["input_type"] == "query"
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 0.0, 0.0, 0.0]}]})

    assert emb.VoyageEmbeddings(transport=_transport(responder)).embed_query("x") == [1.0, 0.0, 0.0, 0.0]


def test_falsche_dimension_faellt_auf(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())

    def responder(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0, 2.0]}]})

    with pytest.raises(RuntimeError, match="EMBEDDING_DIM"):
        emb.VoyageEmbeddings(transport=_transport(responder)).embed_query("x")


def test_ohne_schluessel_klare_meldung(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings(voyage_api_key=None))
    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
        emb.VoyageEmbeddings(transport=_transport(lambda r: httpx.Response(500))).embed_query("x")


def test_serverfehler_wird_wiederholt(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    calls = {"n": 0}

    def responder(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.0] * 4}]})

    assert emb.VoyageEmbeddings(transport=_transport(responder)).embed_query("x") == [0.0] * 4
    assert calls["n"] == 3


def test_provider_auswahl(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings(embedding_provider="voyage"))
    assert isinstance(emb.make_embeddings(), emb.VoyageEmbeddings)
    monkeypatch.setattr(emb, "get_settings", lambda: _settings(embedding_provider="local"))
    assert isinstance(emb.make_embeddings(), emb.LocalEmbeddings)
    monkeypatch.setattr(emb, "get_settings", lambda: _settings(embedding_provider="cohere"))
    with pytest.raises(RuntimeError):
        emb.make_embeddings()
