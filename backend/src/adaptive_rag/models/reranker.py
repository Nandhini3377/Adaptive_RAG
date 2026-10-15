"""Cross-encoder reranking with FastEmbed (ms-marco-MiniLM-L-12, ONNX, no PyTorch).

The embedder compares a question and a chunk as two separate vectors (fast,
approximate). The reranker reads them together (slower, more accurate), so it
is used only on the few dozen candidates retrieval already found.
"""

import math
from functools import lru_cache

from fastembed.rerank.cross_encoder import TextCrossEncoder

from adaptive_rag.config import settings
from adaptive_rag.schemas import SearchHit


@lru_cache(maxsize=1)
def _model() -> TextCrossEncoder:
    """Load the reranker once and reuse it."""
    return TextCrossEncoder(settings.reranker_model)


def rerank(question: str, hits: list[SearchHit], top_n: int | None = None) -> list[SearchHit]:
    """Re-score hits by reading question and chunk together; best first.

    Scores are squashed to 0-1 so they are easy to read; only their order is used.
    """
    if not hits:
        return []
    raw_scores = _model().rerank(question, [hit.chunk.text for hit in hits])
    rescored = [
        hit.model_copy(update={"score": _sigmoid(raw)})
        for hit, raw in zip(hits, raw_scores, strict=True)
    ]
    rescored.sort(key=lambda hit: hit.score, reverse=True)
    return rescored[: top_n or settings.top_k]


def _sigmoid(x: float) -> float:
    """Map any number to 0-1 (the reranker outputs unbounded logits)."""
    return 1 / (1 + math.exp(-x))
