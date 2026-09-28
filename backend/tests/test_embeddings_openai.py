"""OpenAI-Embeddings: Anfrageform (model, dimensions), Reihenfolge, Batches, Fehler - gegen einen Mock-Transport."""

import json
from types import SimpleNamespace

import httpx
import pytest

from app import embeddings as emb


def _settings(**overrides):
    base = dict(
        embedding_provider="openai",
        embedding_dim=4,
        openai_api_key="sk-test",
        openai_embedding_model="text-embedding-3-small",
        openai_api_url="https://openai.invalid/v1",
        embedding_query_prefix="",
        embedding_passage_prefix="",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_dokumente_in_reihenfolge_mit_modell_und_dimension(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    seen = {}

    def responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen.update(body)
        seen["auth"] = request.headers["authorization"]
        seen["url"] = str(request.url)
        data = [{"index": i, "embedding": [float(i)] * 4} for i in reversed(range(len(body["input"])))]
        return httpx.Response(200, json={"data": data})

    vectors = emb.OpenAIEmbeddings(transport=httpx.MockTransport(responder)).embed_documents(["a", "b", "c"])
    assert vectors == [[0.0] * 4, [1.0] * 4, [2.0] * 4]
    assert seen["model"] == "text-embedding-3-small"
    assert seen["dimensions"] == 4
    assert seen["auth"] == "Bearer sk-test"
    assert seen["url"] == "https://openai.invalid/v1/embeddings"


def test_abfrage_liefert_einen_vektor_und_grosse_listen_gehen_in_batches(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    calls = []

    def responder(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        calls.append(len(body["input"]))
        return httpx.Response(200, json={"data": [{"index": i, "embedding": [1.0] * 4} for i in range(len(body["input"]))]})

    client = emb.OpenAIEmbeddings(transport=httpx.MockTransport(responder))
    assert client.embed_query("frage") == [1.0] * 4
    assert len(client.embed_documents(["t"] * 300)) == 300
    assert calls == [1, 128, 128, 44]
    assert client.embed_documents([]) == []


def test_fehlender_schluessel_und_falsche_dimension_brechen_laut_ab(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings(openai_api_key=None))
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        emb.OpenAIEmbeddings(transport=httpx.MockTransport(lambda r: httpx.Response(200))).embed_query("x")

    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    wrong = httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [{"index": 0, "embedding": [1.0] * 3}]}))
    with pytest.raises(RuntimeError, match="EMBEDDING_DIM=4"):
        emb.OpenAIEmbeddings(transport=wrong).embed_query("x")


def test_make_embeddings_kennt_openai(monkeypatch):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    assert isinstance(emb.make_embeddings(), emb.OpenAIEmbeddings)
    monkeypatch.setattr(emb, "get_settings", lambda: _settings(embedding_provider="cohere"))
    with pytest.raises(RuntimeError, match="local, voyage oder openai"):
        emb.make_embeddings()
