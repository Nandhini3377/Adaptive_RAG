"""The FastAPI application. Run with: uv run uvicorn adaptive_rag.api.app:app --reload"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adaptive_rag.api import routes_auth, routes_documents, routes_query
from adaptive_rag.config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="Adaptive RAG Engine",
        description="Picks Vector, Hybrid, or GraphRAG per document and routes each query.",
        version="0.1.0",
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

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        llm = "configured" if settings.sarvam_api_key.get_secret_value() else "missing key"
        return {"status": "ok", "llm": llm}

    return app


app = create_app()
