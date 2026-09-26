import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from sqlalchemy import update

from app.agent.graph import build_graph
from app.api import chat, diagnosis, facts, layout, onboarding, plant, signal, site, sources
from app.config import get_settings
from app.db import init_db, session_scope
from app.models import DocStatus, Document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db()
    with session_scope() as session:
        # Jobs laufen im Prozess; nach einem Neustart sind angefangene Jobs verloren.
        session.execute(
            update(Document)
            .where(Document.status.in_([DocStatus.PENDING, DocStatus.PROCESSING]))
            .values(status=DocStatus.FAILED, error="Verarbeitung durch Neustart unterbrochen", progress="")
        )
    async with AsyncSqliteSaver.from_conn_string(str(settings.checkpoint_db)) as checkpointer:
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(title="Stromlauf AI", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(sources.router)
app.include_router(chat.router)
app.include_router(plant.router)
app.include_router(layout.router)
app.include_router(facts.router)
app.include_router(signal.router)
app.include_router(diagnosis.router)
app.include_router(onboarding.router)
app.include_router(site.router)


@app.get("/api/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "chat_model": settings.chat_model,
        "api_key_configured": bool(settings.anthropic_api_key),
    }
