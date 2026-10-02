import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from app.agent.graph import build_graph
from app.api import (
    auth,
    chat,
    costs,
    diagnosis,
    facts,
    machine_map,
    onboarding,
    plan_read,
    plant,
    search,
    signal,
    sources,
)
from app.auth import auth_middleware
from app.checkpointer import open_checkpointer
from app.config import get_settings
from app.db import init_db, session_scope
from app.ingestion.resume import plan_restart, resume_in_background
from app.ledger import BudgetExceeded
from app.llm import missing_key
from app.models import DocStatus, Document

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if get_settings().resume_ingestion:
        with session_scope() as session:
            # Jobs laufen im Prozess; nach einem Neustart werden angefangene neu eingereiht.
            interrupted = session.scalars(
                select(Document).where(Document.status.in_([DocStatus.PENDING, DocStatus.PROCESSING]))
            ).all()
            resume_ids = plan_restart(interrupted)
        resume_in_background(resume_ids)
    else:
        logger.info("RESUME_INGESTION=false: unterbrochene Dokumente bleiben unangetastet")
    async with open_checkpointer() as checkpointer:
        app.state.checkpointer = checkpointer
        app.state.graph = build_graph(checkpointer)
        yield


app = FastAPI(title="Stromlauf AI", lifespan=lifespan)
app.middleware("http")(auth_middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BudgetExceeded)
async def _budget_exceeded(request: Request, exc: BudgetExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=402,
        content={
            "detail": str(exc),
            "code": "budget_exceeded",
            "used_cents": exc.used_cents,
            "cap_cents": exc.cap_cents,
        },
    )


app.include_router(auth.router)
app.include_router(sources.router)
app.include_router(costs.router)
app.include_router(machine_map.router)
app.include_router(chat.router)
app.include_router(plant.router)
app.include_router(facts.router)
app.include_router(signal.router)
app.include_router(diagnosis.router)
app.include_router(onboarding.router)
app.include_router(search.router)
app.include_router(plan_read.router)


@app.get("/api/health")
def health():
    settings = get_settings()
    try:
        configured = missing_key(settings.chat_model, settings) is None
    except ValueError:  # Modellname ohne erkennbaren Provider: kein 500 im Health-Check
        configured = False
    return {
        "status": "ok",
        "chat_model": settings.chat_model,
        "api_key_configured": configured,
    }
