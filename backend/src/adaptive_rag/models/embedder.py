"""Text embeddings with FastEmbed (ONNX Runtime, no PyTorch)."""

from functools import lru_cache

from fastembed import TextEmbedding

from adaptive_rag.config import settings


@lru_cache(maxsize=1)
def _model() -> TextEmbedding:
    """Load the embedding model once and reuse it for every call."""
    return TextEmbedding(settings.embedding_model)


def embedding_size() -> int:
    """Return how many numbers each embedding has (384 for bge-small)."""
    return TextEmbedding.get_embedding_size(settings.embedding_model)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed document chunks for storage."""
    return [vector.tolist() for vector in _model().passage_embed(texts)]


def embed_query(question: str) -> list[float]:
    """Embed a user question for search."""
    # Questions get the instruction prefix; chunks do not (asymmetric search)
    text = settings.embedding_query_prefix + question
    return next(_model().query_embed(text)).tolist()
