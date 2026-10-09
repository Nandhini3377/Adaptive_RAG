"""Graph + Hybrid mode: graph traversal, BM25, and vectors, merged by rank fusion."""

from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.retrieval.fusion import reciprocal_rank_fusion
from adaptive_rag.retrieval.graph import GraphRetriever
from adaptive_rag.retrieval.hybrid import HybridRetriever
from adaptive_rag.schemas import RetrievalResult


class GraphHybridRetriever(Retriever):
    mode = "graph_hybrid"

    def __init__(self, graph: GraphRetriever, hybrid: HybridRetriever) -> None:
        self._graph = graph
        self._hybrid = hybrid

    def retrieve(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> RetrievalResult:
        from_graph = self._graph.retrieve(question, owner_id, document_ids, k)
        from_text = self._hybrid.retrieve(question, owner_id, document_ids, k)
        fused = reciprocal_rank_fusion([from_graph.hits, from_text.hits])[:k]
        return RetrievalResult(hits=fused, graph_paths=from_graph.graph_paths)
