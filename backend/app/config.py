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

    database_url: str = "postgresql+psycopg://stromlauf:stromlauf@localhost:5433/stromlauf"
    data_dir: Path = BACKEND_DIR / "data"

    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
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
