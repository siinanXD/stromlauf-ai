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


embeddings = LocalEmbeddings()
