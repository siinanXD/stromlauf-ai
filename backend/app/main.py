import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.agent.graph import build_graph
from app.api import (
    chat,
    diagnosis,
    facts,
    flow,
    layout,
    onboarding,
    orders,
    planning,
    plant,
    search,
    signal,
    site,
    sources,
)
from app.auth import api_key_middleware
from app.checkpointer import open_checkpointer
from app.config import get_settings
from app.db import init_db, session_scope
from app.ingestion.resume import plan_restart, resume_in_background
from app.models import DocStatus, Document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with session_scope() as session:
        # Jobs laufen im Prozess; nach einem Neustart werden angefangene neu eingereiht.
        interrupted = session.scalars(
            select(Document).where(Document.status.in_([DocStatus.PENDING, DocStatus.PROCESSING]))
        ).all()
        resume_ids = plan_restart(interrupted)
    resume_in_background(resume_ids)
    async with open_checkpointer() as checkpointer:
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(title="Stromlauf AI", lifespan=lifespan)
app.middleware("http")(api_key_middleware)
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
app.include_router(planning.router)
app.include_router(search.router)
app.include_router(orders.router)
app.include_router(flow.router)


@app.get("/api/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "chat_model": settings.chat_model,
        "api_key_configured": bool(settings.anthropic_api_key),
    }
