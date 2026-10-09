"""Reciprocal rank fusion: merge ranked lists whose scores are not comparable.

BM25 scores (0-30+) and cosine similarities (0-1) cannot be added directly,
but ranks can: a chunk ranked high in several lists rises to the top.
score(chunk) = sum over lists of 1 / (k + rank)
"""

from adaptive_rag.config import settings
from adaptive_rag.schemas import SearchHit


def reciprocal_rank_fusion(
    ranked_lists: list[list[SearchHit]], k: int | None = None
) -> list[SearchHit]:
    """Merge lists by rank; each chunk appears once, with its fused score."""
    k = k or settings.rrf_k
    scores: dict[str, float] = {}
    hits: dict[str, SearchHit] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            scores[hit.chunk.id] = scores.get(hit.chunk.id, 0.0) + 1 / (k + rank)
            hits.setdefault(hit.chunk.id, hit)
    order = sorted(scores, key=lambda chunk_id: scores[chunk_id], reverse=True)
    return [hits[chunk_id].model_copy(update={"score": scores[chunk_id]}) for chunk_id in order]
