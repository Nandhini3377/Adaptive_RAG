"""Hybrid mode: vector search + BM25 keyword search, merged by rank fusion."""

from adaptive_rag.retrieval.base import Retriever
from adaptive_rag.retrieval.fusion import reciprocal_rank_fusion
from adaptive_rag.schemas import RetrievalResult
from adaptive_rag.store.bm25_store import BM25Store
from adaptive_rag.store.vector_store import VectorStore


class HybridRetriever(Retriever):
    mode = "hybrid"

    def __init__(self, vector_store: VectorStore, bm25_store: BM25Store) -> None:
        self._vectors = vector_store
        self._bm25 = bm25_store

    def retrieve(
        self, question: str, owner_id: str, document_ids: list[str], k: int
    ) -> RetrievalResult:
        by_meaning = self._vectors.search(question, owner_id, document_ids=document_ids, top_k=k)
        by_keyword = self._bm25.search(question, owner_id, document_ids, k)
        return RetrievalResult(hits=reciprocal_rank_fusion([by_meaning, by_keyword])[:k])
