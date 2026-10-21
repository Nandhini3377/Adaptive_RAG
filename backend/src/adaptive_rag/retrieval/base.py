"""One interface for every retrieval mode (FR22), so the router can swap them."""

from abc import ABC, abstractmethod
from collections import Counter
from collections.abc import Callable

from adaptive_rag.config import settings
from adaptive_rag.schemas import GraphPath, Mode, RetrievalResult, SearchHit

Reranker = Callable[[str, list[SearchHit], int], list[SearchHit]]


class Retriever(ABC):
    """Finds candidate chunks for a question within the owner's documents."""

    mode: Mode

    @abstractmethod
    def retrieve(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> RetrievalResult:
        """Return up to k candidates, best first."""


def rerank_hits(
    rerank: Reranker,
    question: str,
    hits: list[SearchHit],
    top_n: int,
    paths: list[GraphPath] | None = None,
) -> list[SearchHit]:
    """Rerank candidates, but keep the chunks graph paths cite.

    A graph path proves its chunk states an edge the question asked about, even when the
    chunk reads nothing like the question (a table row, "X depends on Y" for a question
    about Z). The reranker scores those low, so the `graph_pinned_chunks` chunks cited by
    the most path edges are guaranteed a place in the top n. The reranker's order is
    kept: a pinned chunk it missed takes the last slot instead of pushing its best down
    (measured: pinning to the front moved the answer from 1st to 3rd on simple questions).
    """
    if not paths:
        return rerank(question, hits, top_n)
    ranked = rerank(question, hits, len(hits))
    in_hits = {hit.chunk.id for hit in ranked}
    cited = Counter(
        chunk_id for path in paths for chunk_id in path.chunk_ids if chunk_id in in_hits
    )
    first_seen = list(dict.fromkeys(cited.elements()))
    pinned = sorted(cited, key=lambda chunk_id: (-cited[chunk_id], first_seen.index(chunk_id)))
    pinned = pinned[: min(settings.graph_pinned_chunks, top_n)]
    top = ranked[:top_n]
    missing = [c for c in pinned if c not in {hit.chunk.id for hit in top}]
    if not missing:
        return top
    keep = [hit for hit in top if hit.chunk.id not in pinned][: top_n - len(pinned)]
    kept_ids = {hit.chunk.id for hit in keep} | set(pinned)
    # Reranker order throughout; only chunks pushed out by the pinned ones are dropped
    return [hit for hit in ranked if hit.chunk.id in kept_ids]
