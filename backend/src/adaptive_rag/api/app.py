"""The FastAPI application. Run with: uv run uvicorn adaptive_rag.api.app:app --reload"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware

from adaptive_rag import services
from adaptive_rag.api import routes_auth, routes_documents, routes_lab, routes_query
from adaptive_rag.config import settings
from adaptive_rag.store import db

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """On start: rebuild keyword indexes (they live in memory)."""
    with db.session_scope() as session:
        rebuilt = services.bm25_store().rebuild_from_db(session)
    log.info("Rebuilt %d BM25 indexes", rebuilt)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Adaptive RAG Engine",
        description="Picks Vector, Hybrid, or GraphRAG per document and routes each query.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.api_docs_enabled else None,
        redoc_url="/redoc" if settings.api_docs_enabled else None,
        openapi_url="/openapi.json" if settings.api_docs_enabled else None,
    )

    @app.middleware("http")
    async def reject_oversized_requests(request: Request, call_next):  # type: ignore[no-untyped-def]
        """Turn away a too-large upload from its declared size, before reading any of it."""
        declared = request.headers.get("content-length", "")
        # 1 MB of slack: a multipart upload is a little bigger than the file inside it
        if declared.isdigit() and int(declared) > (settings.max_upload_mb + 1) * 1024 * 1024:
            return Response(
                f"Request is larger than {settings.max_upload_mb} MB",
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            )
        return await call_next(request)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # the Next.js dashboard
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(routes_auth.router)
    app.include_router(routes_documents.router)
    app.include_router(routes_query.router)
    app.include_router(routes_lab.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        llm = "configured" if settings.sarvam_api_key.get_secret_value() else "missing key"
        graph = services.graph_store()
        neo4j = "up" if graph is not None and graph.ping() else "down"
        return {"status": "ok", "llm": llm, "neo4j": neo4j}

    return app


app = create_app()
