import logging
import threading

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


def make_embeddings() -> Embeddings:
    provider = get_settings().embedding_provider.lower()
    if provider == "voyage":
        return VoyageEmbeddings()
    if provider == "openai":
        return OpenAIEmbeddings()
    if provider == "local":
        return LocalEmbeddings()
    raise RuntimeError(f"EMBEDDING_PROVIDER={provider!r}: erlaubt sind local, voyage oder openai")


embeddings = make_embeddings()
