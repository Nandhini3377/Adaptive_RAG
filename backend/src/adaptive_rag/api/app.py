"""The FastAPI application. Run with: uv run uvicorn adaptive_rag.api.app:app --reload"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adaptive_rag import services
from adaptive_rag.api import routes_auth, routes_documents, routes_eval, routes_query
from adaptive_rag.config import settings
from adaptive_rag.store import db

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """On start: rebuild keyword indexes (they live in memory) and clear stale eval runs."""
    with db.session_scope() as session:
        rebuilt = services.bm25_store().rebuild_from_db(session)
        # Background work dies with the process; don't leave runs stuck as "running"
        for run in session.query(db.EvalRun).filter(db.EvalRun.status == "running"):
            run.status = "failed"
            run.metrics = {"error": "Server restarted during the run"}
    log.info("Rebuilt %d BM25 indexes", rebuilt)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Adaptive RAG Engine",
        description="Picks Vector, Hybrid, or GraphRAG per document and routes each query.",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # the Next.js dashboard
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_auth.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_query.router)
    app.include_router(routes_eval.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        llm = "configured" if settings.sarvam_api_key.get_secret_value() else "missing key"
        graph = services.graph_store()
        neo4j = "up" if graph is not None and graph.ping() else "down"
        return {"status": "ok", "llm": llm, "neo4j": neo4j}

    return app


app = create_app()
