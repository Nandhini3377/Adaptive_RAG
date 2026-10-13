# The API as one container. Build from this folder:  docker build -t adaptive-rag-api backend
#
# The folder layout inside the image mirrors the repo (/app/backend/src/...), because
# config.py finds the project root, and so data/, by walking up from its own location.
FROM python:3.12-slim

# uv, the same version the lockfile was made with
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    # Keep the embedding and reranker models (~1.2 GB) on the data volume, so a new
    # container does not download them again. The default is a temp folder.
    FASTEMBED_CACHE_PATH=/app/data/models

WORKDIR /app/backend

# Dependencies first: this layer is reused until pyproject.toml or uv.lock changes
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

# Run as an ordinary user, not root: a bug in the app then cannot change the system.
# The data folder is created first so the volume mounted on it belongs to that user.
RUN useradd --create-home --uid 1000 app && mkdir -p /app/data && chown app:app /app/data
USER app

# SQLite, Qdrant, uploads and the models live here; mount a volume on it
VOLUME /app/data
EXPOSE 8000

# One process only: the BM25 indexes are in its memory and embedded Qdrant locks its folder
CMD ["/app/backend/.venv/bin/uvicorn", "adaptive_rag.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
