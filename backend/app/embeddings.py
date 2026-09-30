import hashlib
import json
import logging
import os
import tempfile
import threading
from pathlib import Path

from langchain_core.embeddings import Embeddings

from app.config import get_settings

logger = logging.getLogger(__name__)


class LocalEmbeddings(Embeddings):
    """Lokale sentence-transformers Embeddings (GPU falls vorhanden). Laedt das Modell lazy."""

    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()

    def _get_model(self):
        with self._lock:
            if self._model is None:
                import torch
                from sentence_transformers import SentenceTransformer

                settings = get_settings()
                device = "cuda" if torch.cuda.is_available() else "cpu"
                logger.info("Lade Embedding-Modell %s auf %s", settings.embedding_model, device)
                self._model = SentenceTransformer(settings.embedding_model, device=device)
                # sentence-transformers >= 5 hat die Methode umbenannt
                get_dim = getattr(self._model, "get_embedding_dimension", None)
                dim = (get_dim or self._model.get_sentence_embedding_dimension)()
                if dim != settings.embedding_dim:
                    raise RuntimeError(
                        f"EMBEDDING_DIM={settings.embedding_dim}, aber {settings.embedding_model} "
                        f"liefert {dim} Dimensionen. .env anpassen und neu indexieren."
                    )
            return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._get_model().encode(
            texts, batch_size=16, normalize_embeddings=True, show_progress_bar=False
        )
        return vectors.tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        prefix = get_settings().embedding_passage_prefix
        return self._encode([prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([get_settings().embedding_query_prefix + text])[0]


class VoyageEmbeddings(Embeddings):
    """Voyage-AI-Embeddings ueber HTTP (kein Modell im Container). Dimension aus EMBEDDING_DIM."""

    def __init__(self, transport=None) -> None:
        self._transport = transport  # Tests: httpx.MockTransport

    def _post(self, texts: list[str], input_type: str) -> list[list[float]]:
        import httpx

        settings = get_settings()
        if not settings.voyage_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=voyage, aber VOYAGE_API_KEY fehlt")
        payload = {
            "input": texts,
            "model": settings.voyage_model,
            "input_type": input_type,
            "output_dimension": settings.embedding_dim,
        }
        headers = {"Authorization": f"Bearer {settings.voyage_api_key}"}
        vectors: list[list[float]] = []
        with httpx.Client(timeout=60.0, transport=self._transport) as client:
            for start in range(0, len(texts), 128):
                chunk = dict(payload, input=texts[start : start + 128])
                for attempt in range(3):
                    response = client.post(settings.voyage_api_url, json=chunk, headers=headers)
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        continue
                    response.raise_for_status()
                    break
                data = sorted(response.json()["data"], key=lambda item: item["index"])
                vectors += [item["embedding"] for item in data]
        if vectors and len(vectors[0]) != settings.embedding_dim:
            raise RuntimeError(
                f"EMBEDDING_DIM={settings.embedding_dim}, aber Voyage liefert {len(vectors[0])}."
            )
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._post(texts, "document") if texts else []

    def embed_query(self, text: str) -> list[float]:
        return self._post([text], "query")[0]


class OpenAIEmbeddings(Embeddings):
    """OpenAI-Embeddings (text-embedding-3-*) ueber HTTP; `dimensions` = EMBEDDING_DIM, damit die Vektorspalte passt."""

    def __init__(self, transport=None) -> None:
        self._transport = transport  # Tests: httpx.MockTransport

    def _post(self, texts: list[str]) -> list[list[float]]:
        import httpx

        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=openai, aber OPENAI_API_KEY fehlt")
        url = settings.openai_api_url.rstrip("/") + "/embeddings"
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
        vectors: list[list[float]] = []
        with httpx.Client(timeout=60.0, transport=self._transport) as client:
            for start in range(0, len(texts), 128):
                payload = {
                    "input": texts[start : start + 128],
                    "model": settings.openai_embedding_model,
                    "dimensions": settings.embedding_dim,
                }
                for attempt in range(3):
                    response = client.post(url, json=payload, headers=headers)
                    if response.status_code in (429, 500, 502, 503, 504) and attempt < 2:
                        continue
                    response.raise_for_status()
                    break
                data = sorted(response.json()["data"], key=lambda item: item["index"])
                vectors += [item["embedding"] for item in data]
        if vectors and len(vectors[0]) != settings.embedding_dim:
            raise RuntimeError(f"EMBEDDING_DIM={settings.embedding_dim}, aber OpenAI liefert {len(vectors[0])}.")
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._post(texts) if texts else []

    def embed_query(self, text: str) -> list[float]:
        return self._post([text])[0]


class CachedEmbeddings(Embeddings):
    """Dokument-Vektoren je exaktem Text auf Platte wiederverwenden (EMBEDDING_CACHE_DIR, fuer CI und Eval).

    Das Einbetten der Abschnitte kostet in der Eval die meiste Zeit (bge-m3 auf der CPU), obwohl sich die
    Beispieldokumente selten aendern. Dateiname ist der SHA-256 aus model_key und Text; model_key nennt Provider,
    Modell, Dimension und Passage-Praefix, damit ein Wechsel nie alte Vektoren liefert. Anfragen laufen immer live.
    """

    def __init__(self, inner: Embeddings, cache_dir: Path, model_key: str) -> None:
        self.inner = inner
        self.cache_dir = cache_dir
        self.model_key = model_key

    def _path(self, text: str) -> Path:
        digest = hashlib.sha256(f"{self.model_key}\0{text}".encode()).hexdigest()
        return self.cache_dir / f"{digest}.json"

    @staticmethod
    def _load(path: Path) -> list[float] | None:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):  # fehlt oder unlesbar: neu rechnen
            return None

    def _store(self, path: Path, vector: list[float]) -> None:
        """Erst vollstaendig schreiben, dann umbenennen: nie eine halbe Datei unter dem Schluessel."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        handle, temp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as file:
            json.dump(vector, file)
        os.replace(temp, path)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        paths = [self._path(text) for text in texts]
        vectors = [self._load(path) for path in paths]
        missing = [i for i, vector in enumerate(vectors) if vector is None]
        if missing:
            computed = self.inner.embed_documents([texts[i] for i in missing])
            for i, vector in zip(missing, computed, strict=True):
                self._store(paths[i], vector)
                vectors[i] = vector
        reused = len(texts) - len(missing)
        logger.info("Embedding-Cache: %d aus dem Cache, %d neu gerechnet", reused, len(missing))
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.inner.embed_query(text)


def _model_key(settings) -> str:
    """Alles, was einen Dokument-Vektor ausser dem Text bestimmt."""
    provider = settings.embedding_provider.lower()
    model = {
        "local": settings.embedding_model,
        "voyage": settings.voyage_model,
        "openai": settings.openai_embedding_model,
    }[provider]
    return f"{provider}|{model}|{settings.embedding_dim}|{settings.embedding_passage_prefix}"


def make_embeddings() -> Embeddings:
    settings = get_settings()
    provider = settings.embedding_provider.lower()
    if provider == "voyage":
        inner: Embeddings = VoyageEmbeddings()
    elif provider == "openai":
        inner = OpenAIEmbeddings()
    elif provider == "local":
        inner = LocalEmbeddings()
    else:
        raise RuntimeError(
            f"EMBEDDING_PROVIDER={provider!r}: erlaubt sind local, voyage oder openai"
        )
    if settings.embedding_cache_dir is None:
        return inner
    return CachedEmbeddings(inner, settings.embedding_cache_dir, _model_key(settings))


embeddings = make_embeddings()
