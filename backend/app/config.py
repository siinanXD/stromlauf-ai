from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_DIR / ".env", BACKEND_DIR / ".env"),
        extra="ignore",
    )

    anthropic_api_key: str | None = None
    chat_model: str = "claude-opus-5"
    vision_model: str = "claude-opus-5"
    # Leitplanken je Chat-Antwort (Issue #48): Werkzeugaufrufe, Zeitlimit, Nachrichten im Modellkontext (0 = alle)
    chat_max_tool_calls: int = 12
    chat_timeout_s: float = 60.0
    chat_history_messages: int = 20

    database_url: str = "postgresql+psycopg://stromlauf:stromlauf@localhost:5433/stromlauf"
    data_dir: Path = BACKEND_DIR / "data"

    # local = sentence-transformers im Prozess (bge-m3, ca. 2 GB, braucht RAM);
    # voyage = Voyage-AI-API (voyage-4, kein Modell im Container). Wechsel = neu indexieren.
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    voyage_api_key: str | None = None
    voyage_model: str = "voyage-4"
    voyage_api_url: str = "https://api.voyageai.com/v1/embeddings"
    # openai = OpenAI-Embeddings (text-embedding-3-*, dimensions = EMBEDDING_DIM). Wechsel = neu indexieren.
    # OPENAI_API_KEY gilt auch fuer Chat- und Vision-Modelle mit Praefix "openai:" (app/llm.py).
    openai_api_key: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    openai_api_url: str = "https://api.openai.com/v1"
    # e5-Modelle erwarten "query: " / "passage: " Praefixe, bge-m3 nicht.
    embedding_query_prefix: str = ""
    embedding_passage_prefix: str = ""

    ocr_enabled: bool = False
    vision_max_edge: int = 2400
    vision_concurrency: int = 4
    chunk_size: int = 1500
    chunk_overlap: int = 150

    cors_origins: str = "http://localhost:3100"

    # Ablauf-Visualisierung (app/flow): kleines Modell fuer I/O und Sensor/Aktor, starkes fuer Schrittkette
    flow_model_small: str = "claude-haiku-4-5"
    flow_model_strong: str = "claude-opus-5"
    flow_effort: str = "medium"  # low | medium | high fuer die Schrittkette

    # Langfuse (optional): ohne Schluessel laeuft die Extraktion ohne Trace
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"
    # Gemeinsamer Schluessel fuer alle /api-Routen (leer = offen, nur lokal sinnvoll)
    api_key: str | None = None
    # Anmeldung per Magic-Link + JWT (app/auth.py). Ohne JWT_SECRET: nur API_KEY bzw. offen.
    jwt_secret: str | None = None
    jwt_ttl_hours: int = 12
    auth_dev_link: bool = False  # Link in der Antwort statt per Mail (nur Entwicklung)
    smtp_url: str | None = None  # smtp://user:pass@host:587 oder smtps://user:pass@host:465
    mail_from: str = "stromlauf@localhost"
    frontend_url: str = "http://localhost:3100"

    # Gespraechsverlauf des Agenten: sqlite (Datei unter data_dir) oder postgres (DATABASE_URL)
    checkpointer: str = "sqlite"

    # Gespraechsverlauf des Agenten: sqlite (Datei unter data_dir) oder postgres (DATABASE_URL)
    checkpointer: str = "sqlite"

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def checkpoint_db(self) -> Path:
        return self.data_dir / "checkpoints.sqlite"

    @property
    def flow_cache_dir(self) -> Path:
        return self.data_dir / "flow_cache"


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    return settings
