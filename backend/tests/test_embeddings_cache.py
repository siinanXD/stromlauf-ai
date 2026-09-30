"""Embedding-Cache (EMBEDDING_CACHE_DIR, nur CI/Eval): gleiche Abschnitte werden nicht neu eingebettet."""

import json
from types import SimpleNamespace

from app import embeddings as emb
from app.config import Settings


class CountingEmbeddings:
    """Rechnet Vektoren aus dem Text und merkt sich, was es rechnen musste."""

    def __init__(self) -> None:
        self.documents: list[str] = []
        self.queries: list[str] = []

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.documents += texts
        return [[len(text) + 0.1, 0.2 + 0.1, -1 / 3] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.5, 0.5, 0.5]


def _cached(tmp_path, inner, model_key="local|BAAI/bge-m3|1024|"):
    return emb.CachedEmbeddings(inner, tmp_path / "cache", model_key)


def test_gleicher_abschnitt_wird_nur_einmal_eingebettet(tmp_path):
    inner = CountingEmbeddings()
    first = _cached(tmp_path, inner).embed_documents(["Blatt 3 -K1", "Blatt 4 -X1:5"])
    again = _cached(tmp_path, inner).embed_documents(["Blatt 3 -K1", "Blatt 4 -X1:5"])
    assert again == first  # Zahlen exakt wie gerechnet, auch 0.2 + 0.1 und -1/3
    assert inner.documents == ["Blatt 3 -K1", "Blatt 4 -X1:5"]


def test_nur_neue_abschnitte_werden_gerechnet_und_die_reihenfolge_bleibt(tmp_path):
    inner = CountingEmbeddings()
    cached = _cached(tmp_path, inner)
    cached.embed_documents(["a", "bb"])
    vectors = cached.embed_documents(["bb", "ccc", "a"])
    assert inner.documents == ["a", "bb", "ccc"]
    assert [vector[0] for vector in vectors] == [2.1, 3.1, 1.1]


def test_anderes_modell_oder_praefix_rechnet_neu(tmp_path):
    inner = CountingEmbeddings()
    _cached(tmp_path, inner).embed_documents(["a"])
    _cached(tmp_path, inner, model_key="local|BAAI/bge-m3|1024|passage: ").embed_documents(["a"])
    _cached(tmp_path, inner, model_key="openai|text-embedding-3-small|1024|").embed_documents(["a"])
    assert inner.documents == ["a", "a", "a"]


def test_unlesbare_cache_datei_wird_neu_gerechnet(tmp_path):
    inner = CountingEmbeddings()
    cached = _cached(tmp_path, inner)
    cached.embed_documents(["a"])
    (entry,) = (tmp_path / "cache").iterdir()
    entry.write_text("{kaputt", encoding="utf-8")
    assert cached.embed_documents(["a"]) == [[1.1, 0.30000000000000004, -1 / 3]]
    assert inner.documents == ["a", "a"]
    assert json.loads(entry.read_text(encoding="utf-8"))[0] == 1.1  # repariert


def test_anfragen_laufen_immer_live(tmp_path):
    inner = CountingEmbeddings()
    cached = _cached(tmp_path, inner)
    assert cached.embed_query("Was macht -K1?") == [0.5, 0.5, 0.5]
    cached.embed_query("Was macht -K1?")
    assert inner.queries == ["Was macht -K1?", "Was macht -K1?"]
    assert not (tmp_path / "cache").exists()


def _settings(**overrides):
    base = dict(
        embedding_provider="local",
        embedding_model="BAAI/bge-m3",
        embedding_dim=1024,
        embedding_passage_prefix="",
        voyage_model="voyage-4",
        openai_embedding_model="text-embedding-3-small",
        embedding_cache_dir=None,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_ohne_cache_verzeichnis_bleibt_der_provider_unveraendert(monkeypatch, tmp_path):
    monkeypatch.setattr(emb, "get_settings", lambda: _settings())
    assert isinstance(emb.make_embeddings(), emb.LocalEmbeddings)

    settings = _settings(embedding_cache_dir=tmp_path, embedding_passage_prefix="p: ")
    monkeypatch.setattr(emb, "get_settings", lambda: settings)
    cached = emb.make_embeddings()
    assert isinstance(cached, emb.CachedEmbeddings)
    assert isinstance(cached.inner, emb.LocalEmbeddings)
    assert cached.model_key == "local|BAAI/bge-m3|1024|p: "


def test_leere_einstellung_schaltet_den_cache_aus(monkeypatch):
    """.env.example fuehrt EMBEDDING_CACHE_DIR= leer; das darf nicht das aktuelle Verzeichnis als Cache nehmen."""
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", "")
    assert Settings(_env_file=None).embedding_cache_dir is None
    monkeypatch.setenv("EMBEDDING_CACHE_DIR", "/tmp/emb")
    assert str(Settings(_env_file=None).embedding_cache_dir).replace("\\", "/") == "/tmp/emb"
